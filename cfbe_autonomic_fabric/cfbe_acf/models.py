from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from .util import (
    digest_json,
    ensure_absolute_uri,
    new_traceparent,
    parse_utc,
    reject_sensitive,
    require_bool,
    require_finite_number,
    require_int,
    require_nonempty,
    utc_now,
    validate_traceparent,
)


class ProofStage(str, Enum):
    UNKNOWN = "UNKNOWN"
    DISCOVERED = "DISCOVERED"
    SOURCE_PRESENT = "SOURCE_PRESENT"
    CONFIGURED = "CONFIGURED"
    AUTHENTICATED = "AUTHENTICATED"
    TRANSPORT_PROVEN = "TRANSPORT_PROVEN"
    SEMANTICALLY_VERIFIED = "SEMANTICALLY_VERIFIED"
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    SOAK_VERIFIED = "SOAK_VERIFIED"


PROOF_ORDER = tuple(ProofStage)
_CLOUDEVENT_RESERVED = {
    "id", "source", "type", "data", "subject", "time", "specversion",
    "datacontenttype", "traceparent",
}


def proof_rank(stage: str | ProofStage) -> int:
    return PROOF_ORDER.index(ProofStage(stage))


@dataclass(frozen=True, slots=True)
class CloudEvent:
    id: str
    source: str
    type: str
    data: Mapping[str, Any]
    subject: str = ""
    time: str = field(default_factory=utc_now)
    specversion: str = "1.0"
    datacontenttype: str = "application/json"
    traceparent: str = field(default_factory=new_traceparent)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_nonempty(self.id, "id")
        ensure_absolute_uri(self.source, "source")
        require_nonempty(self.type, "type")
        parse_utc(self.time)
        validate_traceparent(self.traceparent)
        if self.specversion != "1.0":
            raise ValueError("unsupported CloudEvents specversion")
        reject_sensitive(dict(self.data), "data")
        reject_sensitive(dict(self.extensions), "extensions")
        collisions = _CLOUDEVENT_RESERVED & set(self.extensions)
        if collisions:
            raise ValueError("CloudEvent extension collides with reserved attribute")

    def to_dict(self) -> dict[str, Any]:
        reject_sensitive(dict(self.data), "data")
        reject_sensitive(dict(self.extensions), "extensions")
        if _CLOUDEVENT_RESERVED & set(self.extensions):
            raise ValueError("CloudEvent extension collides with reserved attribute")
        value = asdict(self)
        value.update(value.pop("extensions"))
        return value


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    id: str
    state: str
    capabilities: tuple[str, ...]
    authority_ceiling: str
    proof_stage: ProofStage
    observed_at: str
    cost_class: str
    reversible: bool
    semantic_readback: bool
    failure_domain: str
    strategy: str = "REUSE"
    risk: float = 0.0
    owner_burden: float = 0.0
    effectful: bool = False
    proof_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProviderDescriptor":
        raw_capabilities = value.get("capabilities", [])
        raw_proof_refs = value.get("proof_refs", [])
        if not isinstance(raw_capabilities, list) or not all(
            isinstance(item, str) and item.strip() for item in raw_capabilities
        ):
            raise ValueError("provider.capabilities must be a list of nonempty strings")
        if not isinstance(raw_proof_refs, list) or not all(
            isinstance(item, str) and item.strip() for item in raw_proof_refs
        ):
            raise ValueError("provider.proof_refs must be a list of nonempty strings")
        capabilities = tuple(sorted(set(raw_capabilities)))
        result = cls(
            id=str(require_nonempty(value.get("id"), "provider.id")),
            state=str(require_nonempty(value.get("state"), "provider.state")),
            capabilities=capabilities,
            authority_ceiling=str(value.get("authority_ceiling", "A0")),
            proof_stage=ProofStage(value.get("proof_stage", "UNKNOWN")),
            observed_at=str(require_nonempty(value.get("observed_at"), "provider.observed_at")),
            cost_class=str(value.get("cost_class", "UNKNOWN")),
            reversible=require_bool(value.get("reversible", False), "provider.reversible"),
            semantic_readback=require_bool(
                value.get("semantic_readback", False), "provider.semantic_readback"
            ),
            failure_domain=str(require_nonempty(value.get("failure_domain"), "provider.failure_domain")),
            strategy=str(value.get("strategy", "REUSE")).upper(),
            risk=require_finite_number(value.get("risk", 0), "provider.risk"),
            owner_burden=require_finite_number(
                value.get("owner_burden", 0), "provider.owner_burden"
            ),
            effectful=require_bool(value.get("effectful", False), "provider.effectful"),
            proof_refs=tuple(raw_proof_refs),
        )
        observed = parse_utc(result.observed_at)
        if (observed - parse_utc(utc_now())).total_seconds() > 300:
            raise ValueError("provider observation exceeds allowed future skew")
        if not result.capabilities:
            raise ValueError("provider.capabilities required")
        if result.authority_ceiling not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
            raise ValueError("invalid authority ceiling")
        if result.strategy not in {"REUSE", "REPAIR", "ADAPT", "FORGE"}:
            raise ValueError("invalid strategy")
        return result

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["proof_stage"] = self.proof_stage.value
        return value


@dataclass(frozen=True, slots=True)
class ExecutionContract:
    id: str
    mission_id: str
    mission_version: int
    objective: str
    provider_id: str
    action: str
    capabilities: tuple[str, ...]
    authority_class: str
    effectful: bool
    dry_run: bool
    idempotency_key: str
    payload_digest: str
    route_fingerprint: str
    executor_identity: str
    maximum_incremental_cost: float
    required_proof_stage: ProofStage
    stop_conditions: tuple[str, ...]
    issued_at: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExecutionContract":
        raw_capabilities = value.get("capabilities", [])
        raw_stop_conditions = value.get("stop_conditions", [])
        if not isinstance(raw_capabilities, (list, tuple)) or not all(
            isinstance(item, str) and item.strip() for item in raw_capabilities
        ):
            raise ValueError("contract.capabilities must be nonempty strings")
        if not isinstance(raw_stop_conditions, (list, tuple)) or not all(
            isinstance(item, str) and item.strip() for item in raw_stop_conditions
        ):
            raise ValueError("contract.stop_conditions must be nonempty strings")
        contract = cls(
            id=str(require_nonempty(value.get("id"), "contract.id")),
            mission_id=str(require_nonempty(value.get("mission_id"), "contract.mission_id")),
            mission_version=require_int(value.get("mission_version"), "contract.mission_version", minimum=1),
            objective=str(require_nonempty(value.get("objective"), "contract.objective")),
            provider_id=str(require_nonempty(value.get("provider_id"), "contract.provider_id")),
            action=str(require_nonempty(value.get("action"), "contract.action")),
            capabilities=tuple(sorted(set(raw_capabilities))),
            authority_class=str(value.get("authority_class", "")),
            effectful=require_bool(value.get("effectful"), "contract.effectful"),
            dry_run=require_bool(value.get("dry_run"), "contract.dry_run"),
            idempotency_key=str(require_nonempty(value.get("idempotency_key"), "contract.idempotency_key")),
            payload_digest=str(require_nonempty(value.get("payload_digest"), "contract.payload_digest")),
            route_fingerprint=str(require_nonempty(value.get("route_fingerprint"), "contract.route_fingerprint")),
            executor_identity=str(require_nonempty(value.get("executor_identity"), "contract.executor_identity")),
            maximum_incremental_cost=require_finite_number(
                value.get("maximum_incremental_cost"), "contract.maximum_incremental_cost"
            ),
            required_proof_stage=ProofStage(value.get("required_proof_stage")),
            stop_conditions=tuple(raw_stop_conditions),
            issued_at=str(require_nonempty(value.get("issued_at"), "contract.issued_at")),
        )
        if not contract.capabilities or not contract.stop_conditions:
            raise ValueError("contract capabilities and stop_conditions required")
        if contract.authority_class not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
            raise ValueError("invalid contract authority_class")
        for field_name in ("idempotency_key", "payload_digest", "route_fingerprint"):
            field_value = getattr(contract, field_name)
            if len(field_value) != 64 or any(ch not in "0123456789abcdef" for ch in field_value):
                raise ValueError(f"contract.{field_name} must be sha256 hex")
        if contract.id != "XCT-" + contract.idempotency_key[:24]:
            raise ValueError("contract.id must be derived from idempotency_key")
        parse_utc(contract.issued_at)
        return contract

    @property
    def fingerprint(self) -> str:
        return digest_json(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["required_proof_stage"] = self.required_proof_stage.value
        return value
