from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from math import isfinite
from pathlib import Path
from typing import Iterable


class CreativeCanaryState(str, Enum):
    SOURCE_CONTRACT_READY = "SOURCE_CONTRACT_READY"
    HOLD_EFFECT_AUTHORITY = "HOLD_EFFECT_AUTHORITY"
    HOLD_PROVIDER_RECEIPT = "HOLD_PROVIDER_RECEIPT"
    HOLD_ASSET_READBACK = "HOLD_ASSET_READBACK"
    HOLD_SEMANTIC_READBACK = "HOLD_SEMANTIC_READBACK"
    HOLD_ROLLBACK_PROOF = "HOLD_ROLLBACK_PROOF"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True, slots=True)
class CreativeCanarySpec:
    canary_id: str
    objective: str
    synthetic_only: bool
    case_data_allowed: bool
    real_person_allowed: bool
    provider_mutation_allowed: bool
    publishing_allowed: bool
    external_communication_allowed: bool
    production_traffic_allowed: bool
    provider_effect_authorized: bool
    max_provider_calls: int
    max_assets: int
    max_source_spend: float
    required_semantic_assertions: tuple[str, ...]
    rollback_requirement: str

    def __post_init__(self) -> None:
        if not self.canary_id.strip():
            raise ValueError("canary_id is required")
        if not self.objective.strip():
            raise ValueError("objective is required")
        if not self.synthetic_only:
            raise ValueError("v1 creative canary must be synthetic_only")
        forbidden = {
            "case_data_allowed": self.case_data_allowed,
            "real_person_allowed": self.real_person_allowed,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "publishing_allowed": self.publishing_allowed,
            "external_communication_allowed": self.external_communication_allowed,
            "production_traffic_allowed": self.production_traffic_allowed,
            "provider_effect_authorized": self.provider_effect_authorized,
        }
        enabled = sorted(name for name, value in forbidden.items() if value)
        if enabled:
            raise ValueError(f"v1 source canary cannot authorize consequential effects: {enabled}")
        if not 1 <= int(self.max_provider_calls) <= 3:
            raise ValueError("max_provider_calls must be in [1, 3]")
        if not 1 <= int(self.max_assets) <= 3:
            raise ValueError("max_assets must be in [1, 3]")
        if not isfinite(float(self.max_source_spend)) or float(self.max_source_spend) != 0.0:
            raise ValueError("v1 source canary max_source_spend must be exactly zero")
        assertions = tuple(item.strip() for item in self.required_semantic_assertions if item.strip())
        if not assertions:
            raise ValueError("at least one semantic assertion is required")
        if len(set(assertions)) != len(assertions):
            raise ValueError("semantic assertions must be unique")
        if not self.rollback_requirement.strip():
            raise ValueError("rollback_requirement is required")


@dataclass(frozen=True, slots=True)
class CreativeCanaryObservation:
    source_revision: str
    runtime_identity: str
    provider_name: str
    provider_request_id: str
    provider_native_readback: bool
    asset_ids: tuple[str, ...]
    asset_sha256: tuple[str, ...]
    semantic_assertions_passed: tuple[str, ...]
    rollback_or_disable_proven: bool
    rollback_or_disable_ref: str
    proof_ref: str
    provider_cost: float | None = None
    case_data_processed: bool = False
    real_person_processed: bool = False
    provider_mutation_performed: bool = False
    publishing_performed: bool = False
    external_communication_performed: bool = False
    production_traffic_modified: bool = False

    def __post_init__(self) -> None:
        if self.provider_cost is not None:
            if not isfinite(float(self.provider_cost)) or float(self.provider_cost) < 0:
                raise ValueError("provider_cost must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class CreativeCanaryDecision:
    state: CreativeCanaryState
    verified: bool
    next_gate: str
    reasons: tuple[str, ...]
    truth_boundary: str


_TRUTH_BOUNDARY = (
    "A SOVARA Creative canary is proven only by same-run provider-native execution, exact asset readback, "
    "required semantic assertions, and rollback/disable evidence. Source tests or simulated observations do not "
    "prove provider execution. Any source-only or simulated result does not prove provider execution, media generation, "
    "publishing, production traffic, value, repeated success, or spend authority."
)


def load_creative_canary_spec(path: str | Path) -> CreativeCanarySpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "SOVARA_CREATIVE_CANARY_CONTRACT_V1":
        raise ValueError("unsupported creative canary schema")
    return CreativeCanarySpec(
        canary_id=str(payload.get("canary_id", "")),
        objective=str(payload.get("objective", "")),
        synthetic_only=bool(payload.get("synthetic_only", False)),
        case_data_allowed=bool(payload.get("case_data_allowed", False)),
        real_person_allowed=bool(payload.get("real_person_allowed", False)),
        provider_mutation_allowed=bool(payload.get("provider_mutation_allowed", False)),
        publishing_allowed=bool(payload.get("publishing_allowed", False)),
        external_communication_allowed=bool(payload.get("external_communication_allowed", False)),
        production_traffic_allowed=bool(payload.get("production_traffic_allowed", False)),
        provider_effect_authorized=bool(payload.get("provider_effect_authorized", False)),
        max_provider_calls=int(payload.get("max_provider_calls", 0)),
        max_assets=int(payload.get("max_assets", 0)),
        max_source_spend=float(payload.get("max_source_spend", -1)),
        required_semantic_assertions=tuple(payload.get("required_semantic_assertions") or ()),
        rollback_requirement=str(payload.get("rollback_requirement", "")),
    )


def source_only_canary_decision(spec: CreativeCanarySpec) -> CreativeCanaryDecision:
    return CreativeCanaryDecision(
        state=CreativeCanaryState.HOLD_EFFECT_AUTHORITY,
        verified=False,
        next_gate="BOUND_PROVIDER_EFFECT_AND_FINITE_SPEND_OR_ZERO_COST_AUTHORITY",
        reasons=(
            "SOURCE_CONTRACT_VALID",
            "PROVIDER_EFFECT_NOT_AUTHORIZED_BY_SOURCE",
            "PROVIDER_AND_ASSET_READBACK_NOT_YET_OBSERVED",
        ),
        truth_boundary=_TRUTH_BOUNDARY,
    )


def _valid_sha256(value: str) -> bool:
    raw = value.strip().lower()
    return len(raw) == 64 and all(ch in "0123456789abcdef" for ch in raw)


def evaluate_creative_canary(
    spec: CreativeCanarySpec,
    observation: CreativeCanaryObservation | None,
    *,
    provider_effect_authority_bound: bool,
    finite_spend_authorized: bool,
) -> CreativeCanaryDecision:
    if not provider_effect_authority_bound:
        return source_only_canary_decision(spec)
    if observation is None:
        return CreativeCanaryDecision(
            CreativeCanaryState.HOLD_PROVIDER_RECEIPT,
            False,
            "EXECUTE_ONE_BOUND_PROVIDER_CANARY_AND_CAPTURE_PROVIDER_NATIVE_RECEIPT",
            ("EFFECT_AUTHORITY_BOUND", "PROVIDER_OBSERVATION_REQUIRED"),
            _TRUTH_BOUNDARY,
        )

    forbidden_effects = {
        "CASE_DATA_PROCESSED": observation.case_data_processed,
        "REAL_PERSON_PROCESSED": observation.real_person_processed,
        "PROVIDER_MUTATION_PERFORMED": observation.provider_mutation_performed,
        "PUBLISHING_PERFORMED": observation.publishing_performed,
        "EXTERNAL_COMMUNICATION_PERFORMED": observation.external_communication_performed,
        "PRODUCTION_TRAFFIC_MODIFIED": observation.production_traffic_modified,
    }
    violations = tuple(sorted(name for name, value in forbidden_effects.items() if value))
    if violations:
        return CreativeCanaryDecision(
            CreativeCanaryState.HOLD_EFFECT_AUTHORITY,
            False,
            "QUARANTINE_CANARY_AND_RESTORE_NO_EFFECT_BOUNDARY",
            violations,
            _TRUTH_BOUNDARY,
        )

    if observation.provider_cost is not None and observation.provider_cost > 0 and not finite_spend_authorized:
        return CreativeCanaryDecision(
            CreativeCanaryState.HOLD_EFFECT_AUTHORITY,
            False,
            "BIND_EXPLICIT_FINITE_SPEND_AUTHORITY_BEFORE_PAID_CANARY",
            ("PAID_PROVIDER_EFFECT_WITHOUT_FINITE_SPEND_AUTHORITY",),
            _TRUTH_BOUNDARY,
        )

    provider_fields = (
        observation.source_revision.strip(),
        observation.runtime_identity.strip(),
        observation.provider_name.strip(),
        observation.provider_request_id.strip(),
        observation.proof_ref.strip(),
    )
    if not observation.provider_native_readback or not all(provider_fields):
        return CreativeCanaryDecision(
            CreativeCanaryState.HOLD_PROVIDER_RECEIPT,
            False,
            "CAPTURE_EXACT_PROVIDER_NATIVE_REQUEST_AND_RUNTIME_READBACK",
            ("PROVIDER_NATIVE_RECEIPT_INCOMPLETE",),
            _TRUTH_BOUNDARY,
        )

    asset_ids = tuple(item.strip() for item in observation.asset_ids if item.strip())
    hashes = tuple(item.strip().lower() for item in observation.asset_sha256 if item.strip())
    if (
        not asset_ids
        or len(asset_ids) != len(hashes)
        or len(asset_ids) > spec.max_assets
        or any(not _valid_sha256(item) for item in hashes)
    ):
        return CreativeCanaryDecision(
            CreativeCanaryState.HOLD_ASSET_READBACK,
            False,
            "CAPTURE_BOUNDED_ASSET_IDS_AND_EXACT_SHA256_READBACK",
            ("ASSET_READBACK_INCOMPLETE_OR_INVALID",),
            _TRUTH_BOUNDARY,
        )

    required = set(spec.required_semantic_assertions)
    passed = {item.strip() for item in observation.semantic_assertions_passed if item.strip()}
    missing = tuple(sorted(required - passed))
    if missing:
        return CreativeCanaryDecision(
            CreativeCanaryState.HOLD_SEMANTIC_READBACK,
            False,
            "SATISFY_CANONICAL_CREATIVE_SEMANTIC_ASSERTIONS",
            tuple(f"MISSING:{item}" for item in missing),
            _TRUTH_BOUNDARY,
        )

    if not observation.rollback_or_disable_proven or not observation.rollback_or_disable_ref.strip():
        return CreativeCanaryDecision(
            CreativeCanaryState.HOLD_ROLLBACK_PROOF,
            False,
            "PROVE_ASSET_DISABLE_DELETE_OR_ROUTE_ROLLBACK",
            ("ROLLBACK_OR_DISABLE_PROOF_REQUIRED",),
            _TRUTH_BOUNDARY,
        )

    return CreativeCanaryDecision(
        CreativeCanaryState.VERIFIED,
        True,
        "FORCED_FAILURE_AND_RECOVERY_CANARY",
        (
            "PROVIDER_NATIVE_EXECUTION_VERIFIED",
            "ASSET_READBACK_VERIFIED",
            "SEMANTIC_ASSERTIONS_VERIFIED",
            "ROLLBACK_OR_DISABLE_VERIFIED",
        ),
        _TRUTH_BOUNDARY,
    )


def missing_semantic_assertions(
    spec: CreativeCanarySpec,
    passed: Iterable[str],
) -> tuple[str, ...]:
    observed = {item.strip() for item in passed if item.strip()}
    return tuple(sorted(set(spec.required_semantic_assertions) - observed))
