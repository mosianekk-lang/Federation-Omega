from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum, StrEnum
import re
from typing import Any, Iterable


class CapabilityState(StrEnum):
    EXECUTABLE_NOW = "EXECUTABLE_NOW"
    VERIFY_ONLY = "VERIFY_ONLY"
    AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"
    RUNTIME_DEPENDENT = "RUNTIME_DEPENDENT"
    DESIGN_ONLY = "DESIGN_ONLY"
    UNSUPPORTED = "UNSUPPORTED"


class PreservationState(StrEnum):
    FULL_PRESERVED = "FULL_PRESERVED"
    ARCHIVED_QUERYABLE = "ARCHIVED_QUERYABLE"
    RESTRICTED_TEST_ONLY = "RESTRICTED_TEST_ONLY"
    METADATA_ONLY_SECRET = "METADATA_ONLY_SECRET"


class ActivationState(StrEnum):
    ACTIVE_VALIDATED = "ACTIVE_VALIDATED"
    ACTIVE_BOUNDED = "ACTIVE_BOUNDED"
    PRESERVED_DORMANT = "PRESERVED_DORMANT"
    STAGED_NOT_RUNNING = "STAGED_NOT_RUNNING"
    EXECUTION_HELD = "EXECUTION_HELD"
    MATTER_TRANSFER_HELD = "MATTER_TRANSFER_HELD"


class AssessmentState(StrEnum):
    EXECUTABLE = "EXECUTABLE"
    PARTIAL = "PARTIAL"
    AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"
    RUNTIME_DEPENDENT = "RUNTIME_DEPENDENT"
    DESIGN_ONLY = "DESIGN_ONLY"
    UNSUPPORTED = "UNSUPPORTED"


class ProofLevel(IntEnum):
    NONE = 0
    DESIGNED = 10
    STAGED = 20
    LOCAL_OUTPUT = 30
    SERVICE_READBACK = 50
    LEDGER_READBACK = 55
    CONNECTOR_READBACK = 60
    INDEPENDENT_READBACK = 80
    MULTI_SOURCE_VERIFIED = 90


class RouteState(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    BANNED_UNLESS_CLEARED = "BANNED_UNLESS_CLEARED"


class FaultSeverity(StrEnum):
    WATCH = "WATCH"
    WARN = "WARN"
    BLOCK = "BLOCK"
    HARD_BLOCK = "HARD_BLOCK"


class EngineEnvironment(StrEnum):
    IDEA = "IDEA"
    SANDBOX = "SANDBOX"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
    ARCHIVED = "ARCHIVED"
    QUARANTINED = "QUARANTINED"


class PromotionDecision(StrEnum):
    BLOCKED = "BLOCKED"
    SANDBOX_READY = "SANDBOX_READY"
    STAGING_READY = "STAGING_READY"
    PRODUCTION_READY = "PRODUCTION_READY"


@dataclass(frozen=True)
class CapabilityContract:
    capability_id: str
    name: str
    state: CapabilityState
    can_read: bool = False
    can_write: bool = False
    can_execute: bool = False
    can_verify: bool = False
    authority_required: bool = False
    external_effect: bool = False
    proof_required: str = ""
    fallback_route: str = ""
    preservation_state: PreservationState = PreservationState.FULL_PRESERVED
    activation_state: ActivationState = ActivationState.PRESERVED_DORMANT
    carrier_ids: tuple[str, ...] = ()
    superseded_by: str = ""
    permanent_exclusion_requested: bool = False
    owner_decision_reference: str = ""
    preservation_copy_reference: str = ""

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id is required")
        if not self.name.strip():
            raise ValueError("name is required")
        if self.permanent_exclusion_requested and not (
            self.owner_decision_reference.strip() and self.preservation_copy_reference.strip()
        ):
            raise ValueError(
                "Permanent exclusion requires an item-specific owner decision reference "
                "and a preservation-copy reference."
            )
        if self.preservation_state == PreservationState.METADATA_ONLY_SECRET and self.activation_state not in {
            ActivationState.EXECUTION_HELD,
            ActivationState.PRESERVED_DORMANT,
        }:
            raise ValueError(
                "Secret-bearing records may preserve metadata only and cannot be activated."
            )

    @property
    def preserved(self) -> bool:
        return self.preservation_state in set(PreservationState)

    @property
    def activation_allows_execution(self) -> bool:
        return self.activation_state in {
            ActivationState.ACTIVE_VALIDATED,
            ActivationState.ACTIVE_BOUNDED,
        }

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        value["preservation_state"] = self.preservation_state.value
        value["activation_state"] = self.activation_state.value
        value["carrier_ids"] = list(self.carrier_ids)
        value["preserved"] = self.preserved
        value["activation_allows_execution"] = self.activation_allows_execution
        return value


@dataclass(frozen=True)
class CapabilityAssessment:
    state: AssessmentState
    required_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    gated_capabilities: tuple[str, ...]
    selected_routes: tuple[str, ...]
    claim_limit: str
    preserved_capabilities: tuple[str, ...] = ()
    preservation_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value


@dataclass(frozen=True)
class ClaimDecision:
    allowed: bool
    required_level: ProofLevel
    provided_level: ProofLevel
    blocked_terms: tuple[str, ...]
    safe_wording: str
    missing_conditions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["required_level"] = self.required_level.name
        value["provided_level"] = self.provided_level.name
        return value


@dataclass(frozen=True)
class FaultRecord:
    fault_id: str
    layer_type: str
    detected_problem: str
    banned_pattern: str
    bypass_rule: str
    severity: FaultSeverity
    proof_required: str
    route_id: str | None = None


@dataclass(frozen=True)
class EnginePromotionRequest:
    engine_id: str
    target_environment: EngineEnvironment
    objective: str
    risk_class: str
    profile_complete: bool
    governor_attached: bool
    fault_rules_attached: bool
    proof_rules_attached: bool
    tests_passed: bool
    proof_ledger_written: bool
    risk_accepted: bool
    rollback_ready: bool
    status_path_ready: bool
    last_known_good_registered: bool
    approval_granted: bool = False
    live_readback_plan_ready: bool = False


@dataclass(frozen=True)
class EnginePromotionResult:
    decision: PromotionDecision
    missing_gates: tuple[str, ...]
    claim_language: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["decision"] = self.decision.value
        return value


CLAIM_RULES: tuple[tuple[str, ProofLevel], ...] = (
    ("fully automated", ProofLevel.INDEPENDENT_READBACK),
    ("complete", ProofLevel.INDEPENDENT_READBACK),
    ("final", ProofLevel.INDEPENDENT_READBACK),
    ("deployed", ProofLevel.SERVICE_READBACK),
    ("operational", ProofLevel.SERVICE_READBACK),
    ("live", ProofLevel.SERVICE_READBACK),
    ("verified", ProofLevel.CONNECTOR_READBACK),
    ("staged", ProofLevel.STAGED),
    ("designed", ProofLevel.DESIGNED),
)


def assess_capabilities(required: Iterable[str], contracts: Iterable[CapabilityContract]) -> CapabilityAssessment:
    required_ids = tuple(dict.fromkeys(required))
    if not required_ids:
        return CapabilityAssessment(
            AssessmentState.UNSUPPORTED,
            (),
            (),
            (),
            (),
            "No required capabilities were supplied; execution cannot be assessed.",
        )
    by_id = {item.capability_id: item for item in contracts}
    missing = tuple(item for item in required_ids if item not in by_id)
    if missing:
        return CapabilityAssessment(
            AssessmentState.UNSUPPORTED,
            required_ids,
            missing,
            (),
            (),
            "Required capability contracts are missing; execution cannot be claimed.",
        )

    selected = tuple(by_id[item].fallback_route or by_id[item].name for item in required_ids)
    states = {by_id[item].state for item in required_ids}
    preserved = tuple(item for item in required_ids if by_id[item].preserved)
    preservation_warnings = tuple(
        f"{item}:{by_id[item].preservation_state.value}:{by_id[item].activation_state.value}"
        for item in required_ids
        if not by_id[item].activation_allows_execution
    )
    gated = tuple(
        item
        for item in required_ids
        if by_id[item].state not in {CapabilityState.EXECUTABLE_NOW, CapabilityState.VERIFY_ONLY}
        or not by_id[item].activation_allows_execution
    )

    if CapabilityState.UNSUPPORTED in states:
        state = AssessmentState.UNSUPPORTED
        limit = "No supported route exists for at least one required capability."
    elif CapabilityState.AUTHORITY_REQUIRED in states or any(
        by_id[item].authority_required for item in required_ids
    ):
        state = AssessmentState.AUTHORITY_REQUIRED
        limit = "An exact authority action is required before execution."
    elif CapabilityState.RUNTIME_DEPENDENT in states:
        state = AssessmentState.RUNTIME_DEPENDENT
        limit = "Runtime integration is required; design or queue state is not execution proof."
    elif CapabilityState.DESIGN_ONLY in states:
        state = AssessmentState.DESIGN_ONLY
        limit = "Only the design layer is supported; the implementation remains preserved."
    elif any(not by_id[item].activation_allows_execution for item in required_ids):
        state = AssessmentState.PARTIAL
        limit = (
            "The required capability is preserved, but execution or matter transfer is held "
            "until its proof, authority, safety or scope gate passes."
        )
    elif all(
        by_id[item].state == CapabilityState.EXECUTABLE_NOW and by_id[item].can_execute
        for item in required_ids
    ):
        state = AssessmentState.EXECUTABLE
        limit = "The required capabilities are executable now, subject to result readback."
    else:
        state = AssessmentState.PARTIAL
        limit = "The route can verify or partially act, but cannot claim end-to-end execution."

    return CapabilityAssessment(
        state,
        required_ids,
        (),
        gated,
        selected,
        limit,
        preserved,
        preservation_warnings,
    )


def govern_claim(
    claim: str,
    proof_level: ProofLevel,
    *,
    execution_verified: bool = False,
    gap_scan_complete: bool = False,
    lifecycle_complete: bool = False,
) -> ClaimDecision:
    lowered = claim.lower()

    def present(term: str) -> bool:
        pattern = r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)"
        return re.search(pattern, lowered) is not None

    matched = [(term, level) for term, level in CLAIM_RULES if present(term)]
    required = max((level for _, level in matched), default=ProofLevel.NONE)
    blocked_terms = tuple(term for term, level in matched if proof_level < level)
    missing: list[str] = []

    if any(
        present(term) for term in ("deployed", "live", "operational", "fully automated")
    ) and not execution_verified:
        missing.append("execution_verified")
    if any(
        present(term) for term in ("complete", "final", "fully automated")
    ) and not gap_scan_complete:
        missing.append("gap_scan_complete")
    if present("fully automated") and not lifecycle_complete:
        missing.append("lifecycle_complete")

    allowed = proof_level >= required and not missing
    if allowed:
        safe = claim
    elif proof_level >= ProofLevel.CONNECTOR_READBACK:
        safe = (
            "The available state was read back for the stated scope; broader completion "
            "or live execution is not proven."
        )
    elif proof_level >= ProofLevel.LEDGER_READBACK:
        safe = "The control or ledger state exists and was read back; runtime execution is not proven."
    elif proof_level >= ProofLevel.STAGED:
        safe = "The change is staged or designed; deployment and live operation remain unverified."
    elif proof_level >= ProofLevel.DESIGNED:
        safe = "The design layer exists; implementation and execution remain unverified."
    else:
        safe = "The claim is not currently supported by proof."

    return ClaimDecision(allowed, required, proof_level, blocked_terms, safe, tuple(missing))


def evaluate_engine_promotion(request: EnginePromotionRequest) -> EnginePromotionResult:
    missing: list[str] = []
    base = {
        "profile_complete": request.profile_complete,
        "governor_attached": request.governor_attached,
        "fault_rules_attached": request.fault_rules_attached,
        "proof_rules_attached": request.proof_rules_attached,
    }
    missing.extend(name for name, passed in base.items() if not passed)

    if request.target_environment in {EngineEnvironment.STAGING, EngineEnvironment.PRODUCTION}:
        stage = {
            "tests_passed": request.tests_passed,
            "proof_ledger_written": request.proof_ledger_written,
            "risk_accepted": request.risk_accepted,
        }
        missing.extend(name for name, passed in stage.items() if not passed)

    if request.target_environment == EngineEnvironment.PRODUCTION:
        production = {
            "rollback_ready": request.rollback_ready,
            "status_path_ready": request.status_path_ready,
            "last_known_good_registered": request.last_known_good_registered,
            "live_readback_plan_ready": request.live_readback_plan_ready,
        }
        missing.extend(name for name, passed in production.items() if not passed)
        if request.risk_class.upper() in {"MEDIUM", "HIGH", "CRITICAL"} and not request.approval_granted:
            missing.append("approval_granted")

    if missing:
        return EnginePromotionResult(
            PromotionDecision.BLOCKED,
            tuple(dict.fromkeys(missing)),
            "Engine promotion is blocked until every required gate is proved.",
        )
    if request.target_environment == EngineEnvironment.SANDBOX:
        return EnginePromotionResult(
            PromotionDecision.SANDBOX_READY,
            (),
            "Engine profile is ready for sandbox testing.",
        )
    if request.target_environment == EngineEnvironment.STAGING:
        return EnginePromotionResult(
            PromotionDecision.STAGING_READY,
            (),
            "Engine passed the staging promotion gates.",
        )
    if request.target_environment == EngineEnvironment.PRODUCTION:
        return EnginePromotionResult(
            PromotionDecision.PRODUCTION_READY,
            (),
            "Engine passed production-readiness gates; live status still requires deployment readback.",
        )
    return EnginePromotionResult(
        PromotionDecision.BLOCKED,
        ("unsupported_target_environment",),
        "This environment is not a promotion target.",
    )
