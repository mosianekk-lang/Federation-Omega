"""Typed, canonical and value-suppressed contracts for owner-intent audits."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class ValidationError(ValueError):
    """Raised when an audit contract is incomplete or unsafe."""


class Verdict(str, Enum):
    ALIGN = "ALIGN"
    ALIGN_WITH_CONDITIONS = "ALIGN_WITH_CONDITIONS"
    BLOCK = "BLOCK"
    SOVEREIGN_DECISION_REQUIRED = "SOVEREIGN_DECISION_REQUIRED"


class TaskState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"
    DEAD_LETTER = "DEAD_LETTER"
    CANCELLED = "CANCELLED"
    QUARANTINED = "QUARANTINED"
    ARCHIVED = "ARCHIVED"


class ActionKind(str, Enum):
    """The complete set of kinds the guardian may assess as effect-free."""

    READ_ONLY_AUDIT = "READ_ONLY_AUDIT"
    READ_ONLY_VERIFY = "READ_ONLY_VERIFY"
    READ_ONLY_SEARCH = "READ_ONLY_SEARCH"
    READ_ONLY_COMPARE = "READ_ONLY_COMPARE"
    READ_ONLY_STATUS = "READ_ONLY_STATUS"
    LOCAL_STOP_CONTROL = "LOCAL_STOP_CONTROL"


class RequestedEffect(str, Enum):
    """Closed vocabulary: every effect is prohibited by deterministic policy."""

    IMPERSONATE_OWNER = "IMPERSONATE_OWNER"
    SEND_COMMUNICATION = "SEND_COMMUNICATION"
    CONSENT_OR_WAIVER = "CONSENT_OR_WAIVER"
    LEGAL_SETTLEMENT = "LEGAL_SETTLEMENT"
    SPEND_OR_BILL = "SPEND_OR_BILL"
    ACCESS_SECRET = "ACCESS_SECRET"
    PUBLISH = "PUBLISH"
    DEPLOY = "DEPLOY"
    MERGE = "MERGE"
    WORKFLOW_DISPATCH = "WORKFLOW_DISPATCH"
    CLOUD_MUTATION = "CLOUD_MUTATION"
    WRITE_LOCAL_OR_REMOTE = "WRITE_LOCAL_OR_REMOTE"
    DELETE_RESOURCE = "DELETE_RESOURCE"
    EXECUTE_COMMAND = "EXECUTE_COMMAND"


def canonical_json(value: Any) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_json_strict(text: str) -> Any:
    """Parse JSON while rejecting duplicate keys and non-finite constants."""

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationError(f"duplicate_json_key:{key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ValidationError(f"invalid_json_number:{value}")

    return json.loads(text, object_pairs_hook=no_duplicates, parse_constant=invalid_constant)


def _required_text(value: Any, name: str, maximum: int = 50_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name}_required")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValidationError(f"{name}_too_long")
    return normalized


def _identifier(value: Any, name: str) -> str:
    normalized = _required_text(value, name, 200)
    if not IDENTIFIER_RE.fullmatch(normalized):
        raise ValidationError(f"{name}_invalid")
    return normalized


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{name}_invalid")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name}_invalid") from exc
    if not math.isfinite(number) or number < 0:
        raise ValidationError(f"{name}_invalid")
    return number


def _nonnegative_int(value: Any, name: str, maximum: int = 100) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{name}_invalid")
    return value


def _string_tuple(value: Any, name: str, *, maximum: int = 100) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{name}_invalid")
    return tuple(_required_text(item, f"{name}_item", 2_000) for item in value)


def _hash_tuple(value: Any, name: str, *, maximum: int = 100) -> tuple[str, ...]:
    result = _string_tuple(value, name, maximum=maximum)
    for item in result:
        if not SHA256_RE.fullmatch(item):
            raise ValidationError(f"{name}_hash_invalid")
    return result


def _bool_map(value: Any, name: str) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{name}_required")
    result: dict[str, bool] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, bool):
            raise ValidationError(f"{name}_invalid")
        result[key] = item
    return result


def _hash_map(value: Any, name: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ValidationError(f"{name}_required")
    result: dict[str, str] = {}
    for key, item in value.items():
        source_id = _identifier(key, f"{name}_source")
        if not isinstance(item, str) or not SHA256_RE.fullmatch(item):
            raise ValidationError(f"{name}_hash_invalid:{source_id}")
        result[source_id] = item
    return result


def _required_hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValidationError(f"{name}_invalid")
    return value


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValidationError(f"{name}_unknown_fields:{','.join(unknown)}")


def _enum(value: Any, enum_type: type[Enum], name: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name}_unsupported") from exc


@dataclass(frozen=True)
class ProposedAction:
    """Hash/reference-only proposed action carrying no execution capability."""

    action_id: str
    authority_class: str
    kind: ActionKind
    description_hash: str
    requested_effects: tuple[RequestedEffect, ...] = ()
    claim_hashes: tuple[str, ...] = ()
    estimated_cost: float = 0.0
    recurring_cost: float = 0.0
    user_burden: float = 0.0
    reversible: bool = True
    owner_decision_required: bool = False
    formation_gate_decision: str = ""
    formation_permit_current: bool = False
    state_claims: Mapping[str, bool] = field(default_factory=dict)
    proof: Mapping[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProposedAction":
        if not isinstance(value, Mapping):
            raise ValidationError("proposed_action_required")
        _reject_unknown(value, {
            "action_id", "authority_class", "kind", "description_hash",
            "requested_effects", "claim_hashes", "estimated_cost", "recurring_cost",
            "user_burden", "reversible", "owner_decision_required",
            "formation_gate_decision", "formation_permit_current", "state_claims", "proof",
        }, "proposed_action")
        authority_class = _required_text(value.get("authority_class"), "authority_class", 8)
        if authority_class not in {f"A{i}" for i in range(6)}:
            raise ValidationError("authority_class_invalid")
        reversible = value.get("reversible", True)
        owner_decision = value.get("owner_decision_required", False)
        permit_current = value.get("formation_permit_current", False)
        if not all(isinstance(item, bool) for item in (reversible, owner_decision, permit_current)):
            raise ValidationError("proposed_action_boolean_invalid")
        gate_decision = str(value.get("formation_gate_decision") or "")
        if gate_decision not in {"", "EXECUTE"}:
            raise ValidationError("formation_gate_decision_invalid")
        effects = _string_tuple(value.get("requested_effects"), "requested_effects")
        state_claims = _bool_map(value.get("state_claims", {}), "state_claims")
        proof = _bool_map(value.get("proof", {}), "proof")
        unknown_states = sorted(set(state_claims) - {"deployed", "proven", "autonomous"})
        if unknown_states:
            raise ValidationError(f"state_claims_unsupported:{','.join(unknown_states)}")
        unknown_proof = sorted(set(proof) - {
            "deployment_readback", "semantic_verification", "independent_attestation",
            "live_scheduler", "live_canary", "trusted_runtime_attestation",
        })
        if unknown_proof:
            raise ValidationError(f"proof_unsupported:{','.join(unknown_proof)}")
        return cls(
            action_id=_identifier(value.get("action_id"), "action_id"),
            authority_class=authority_class,
            kind=_enum(value.get("kind"), ActionKind, "action_kind"),
            description_hash=_required_hash(value.get("description_hash"), "description_hash"),
            requested_effects=tuple(_enum(item, RequestedEffect, "requested_effect") for item in effects),
            claim_hashes=_hash_tuple(value.get("claim_hashes"), "claim_hashes"),
            estimated_cost=_number(value.get("estimated_cost", 0), "estimated_cost"),
            recurring_cost=_number(value.get("recurring_cost", 0), "recurring_cost"),
            user_burden=_number(value.get("user_burden", 0), "user_burden"),
            reversible=reversible,
            owner_decision_required=owner_decision,
            formation_gate_decision=gate_decision,
            formation_permit_current=permit_current,
            state_claims=state_claims,
            proof=proof,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "authority_class": self.authority_class,
            "kind": self.kind.value,
            "description_hash": self.description_hash,
            "requested_effects": [effect.value for effect in self.requested_effects],
            "claim_hashes": list(self.claim_hashes),
            "estimated_cost": self.estimated_cost,
            "recurring_cost": self.recurring_cost,
            "user_burden": self.user_burden,
            "reversible": self.reversible,
            "owner_decision_required": self.owner_decision_required,
            "formation_gate_decision": self.formation_gate_decision,
            "formation_permit_current": self.formation_permit_current,
            "state_claims": dict(sorted(self.state_claims.items())),
            "proof": dict(sorted(self.proof.items())),
        }


@dataclass(frozen=True)
class AuditRequest:
    """Evidence-bound request whose continuity capsule must be externally attested."""

    mission_id: str
    mission_version: int
    latest_instruction_hash: str
    requirement_ids: tuple[str, ...]
    source_hashes: Mapping[str, str]
    source_readback_hash: str
    formation_mission_hash: str
    policy_hash: str
    local_bible_transaction_id: str
    local_bible_transaction_hash: str
    local_bible_audit_hash: str
    local_bible_read_model_hash: str
    local_bible_hash_chain_valid: bool
    mission_current: bool
    source_fingerprints_current: bool
    requirements_current: bool
    trusted_attestation_id: str
    trusted_attestation_hash: str
    proposed_action: ProposedAction
    manual_user_task_count: int = 0
    cadence_every: int = 5

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuditRequest":
        if not isinstance(value, Mapping):
            raise ValidationError("audit_request_required")
        _reject_unknown(value, {
            "mission_id", "mission_version", "latest_instruction_hash", "requirement_ids",
            "source_hashes", "source_readback_hash", "formation_mission_hash", "policy_hash",
            "local_bible_transaction_id", "local_bible_transaction_hash", "local_bible_audit_hash",
            "local_bible_read_model_hash", "local_bible_hash_chain_valid", "mission_current",
            "source_fingerprints_current", "requirements_current", "trusted_attestation_id",
            "trusted_attestation_hash", "proposed_action", "manual_user_task_count", "cadence_every",
        }, "audit_request")
        version = value.get("mission_version")
        cadence = value.get("cadence_every", 5)
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValidationError("mission_version_invalid")
        if isinstance(cadence, bool) or not isinstance(cadence, int) or not 1 <= cadence <= 100:
            raise ValidationError("cadence_every_invalid")
        boolean_names = (
            "local_bible_hash_chain_valid", "mission_current",
            "source_fingerprints_current", "requirements_current",
        )
        booleans = {name: value.get(name) for name in boolean_names}
        if any(not isinstance(item, bool) for item in booleans.values()):
            raise ValidationError("continuity_boolean_required")
        requirement_ids = _string_tuple(value.get("requirement_ids"), "requirement_ids")
        if not requirement_ids:
            raise ValidationError("requirement_ids_required")
        request = cls(
            mission_id=_identifier(value.get("mission_id"), "mission_id"),
            mission_version=version,
            latest_instruction_hash=_required_hash(value.get("latest_instruction_hash"), "latest_instruction_hash"),
            requirement_ids=tuple(_identifier(item, "requirement_id") for item in requirement_ids),
            source_hashes=_hash_map(value.get("source_hashes"), "source_hashes"),
            source_readback_hash=_required_hash(value.get("source_readback_hash"), "source_readback_hash"),
            formation_mission_hash=_required_hash(value.get("formation_mission_hash"), "formation_mission_hash"),
            policy_hash=_required_hash(value.get("policy_hash"), "policy_hash"),
            local_bible_transaction_id=_identifier(value.get("local_bible_transaction_id"), "local_bible_transaction_id"),
            local_bible_transaction_hash=_required_hash(value.get("local_bible_transaction_hash"), "local_bible_transaction_hash"),
            local_bible_audit_hash=_required_hash(value.get("local_bible_audit_hash"), "local_bible_audit_hash"),
            local_bible_read_model_hash=_required_hash(value.get("local_bible_read_model_hash"), "local_bible_read_model_hash"),
            local_bible_hash_chain_valid=booleans["local_bible_hash_chain_valid"],
            mission_current=booleans["mission_current"],
            source_fingerprints_current=booleans["source_fingerprints_current"],
            requirements_current=booleans["requirements_current"],
            trusted_attestation_id=_identifier(value.get("trusted_attestation_id"), "trusted_attestation_id"),
            trusted_attestation_hash=_required_hash(value.get("trusted_attestation_hash"), "trusted_attestation_hash"),
            proposed_action=ProposedAction.from_dict(value.get("proposed_action", {})),
            manual_user_task_count=_nonnegative_int(value.get("manual_user_task_count", 0), "manual_user_task_count"),
            cadence_every=cadence,
        )
        if request.trusted_attestation_hash != request.attestation_binding_hash:
            raise ValidationError("continuity_attestation_binding_mismatch")
        return request

    @property
    def continuity_binding(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "mission_version": self.mission_version,
            "latest_instruction_hash": self.latest_instruction_hash,
            "requirement_ids": list(self.requirement_ids),
            "source_hashes": dict(sorted(self.source_hashes.items())),
            "source_readback_hash": self.source_readback_hash,
            "formation_mission_hash": self.formation_mission_hash,
            "policy_hash": self.policy_hash,
            "local_bible_transaction_id": self.local_bible_transaction_id,
            "local_bible_transaction_hash": self.local_bible_transaction_hash,
            "local_bible_audit_hash": self.local_bible_audit_hash,
            "local_bible_read_model_hash": self.local_bible_read_model_hash,
            "local_bible_hash_chain_valid": self.local_bible_hash_chain_valid,
            "mission_current": self.mission_current,
            "source_fingerprints_current": self.source_fingerprints_current,
            "requirements_current": self.requirements_current,
        }

    @property
    def continuity_binding_hash(self) -> str:
        """Compatibility name for the complete trusted request/action binding."""

        return self.attestation_binding_hash

    @property
    def attestation_binding(self) -> dict[str, Any]:
        return {
            **self.continuity_binding,
            "proposed_action": self.proposed_action.to_dict(),
            "manual_user_task_count": self.manual_user_task_count,
            "cadence_every": self.cadence_every,
        }

    @property
    def attestation_binding_hash(self) -> str:
        return sha256_json(self.attestation_binding)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.attestation_binding,
            "trusted_attestation_id": self.trusted_attestation_id,
            "trusted_attestation_hash": self.trusted_attestation_hash,
        }

    @property
    def input_hash(self) -> str:
        return sha256_json(self.to_dict())

    def advisory_payload(self) -> dict[str, Any]:
        """Return only hashes, references, enums and booleans; no raw source values."""

        return {
            "attestation_binding_hash": self.attestation_binding_hash,
            "trusted_attestation_id": self.trusted_attestation_id,
            "trusted_attestation_hash": self.trusted_attestation_hash,
            "action": self.proposed_action.to_dict(),
            "input_hash": self.input_hash,
        }


@dataclass(frozen=True)
class AuditResult:
    verdict: Verdict
    reason_codes: tuple[str, ...]
    conditions: tuple[str, ...]
    requirement_matrix: tuple[Mapping[str, str], ...]
    source_trace: tuple[Mapping[str, str], ...]
    cadence_due: bool
    delivered_output_count: int
    output_ledger_hash: str
    output_ledger_verified: bool
    advisory_available: bool
    policy_version: str
    input_hash: str
    advisory: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reason_codes": list(self.reason_codes),
            "conditions": list(self.conditions),
            "requirement_matrix": [dict(row) for row in self.requirement_matrix],
            "source_trace": [dict(row) for row in self.source_trace],
            "cadence_due": self.cadence_due,
            "delivered_output_count": self.delivered_output_count,
            "output_ledger_hash": self.output_ledger_hash,
            "output_ledger_verified": self.output_ledger_verified,
            "advisory_available": self.advisory_available,
            "policy_version": self.policy_version,
            "input_hash": self.input_hash,
            "advisory": dict(self.advisory),
            "authorizes_action": False,
            "effect_performed": False,
            "release_authority": "NONE",
            "manual_user_tasks": [],
            "owner_action_required": self.verdict == Verdict.SOVEREIGN_DECISION_REQUIRED,
        }

    @property
    def result_hash(self) -> str:
        return sha256_json(self.to_dict())

    def with_advisory(self, advisory: Mapping[str, Any]) -> "AuditResult":
        return AuditResult(
            verdict=self.verdict,
            reason_codes=self.reason_codes,
            conditions=self.conditions,
            requirement_matrix=self.requirement_matrix,
            source_trace=self.source_trace,
            cadence_due=self.cadence_due,
            delivered_output_count=self.delivered_output_count,
            output_ledger_hash=self.output_ledger_hash,
            output_ledger_verified=self.output_ledger_verified,
            advisory_available=self.advisory_available,
            policy_version=self.policy_version,
            input_hash=self.input_hash,
            advisory=dict(advisory),
        )
