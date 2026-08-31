from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json

from .improvement_catalog import ImprovementSpec, IMPROVEMENT_CATALOG
from .mission_compiler import CreativeMissionProgram


class AutopilotState(str, Enum):
    ADVANCE = "ADVANCE"
    SELF_REPAIR = "SELF_REPAIR"
    RETRY = "RETRY"
    REROUTE = "REROUTE"
    EVALUATOR_OPTIMIZER = "EVALUATOR_OPTIMIZER"
    RIPPLE_RECOMPILE = "RIPPLE_RECOMPILE"
    ROLLBACK_CHAMPION = "ROLLBACK_CHAMPION"
    HOLD_PROOF = "HOLD_PROOF"
    HOLD_AUTHORITY = "HOLD_AUTHORITY"
    OWNER_RELEASE_REQUIRED = "OWNER_RELEASE_REQUIRED"
    INTERNAL_COMPLETE = "INTERNAL_COMPLETE"


@dataclass(frozen=True, slots=True)
class AutopilotTelemetry:
    stage_id: str
    attempt: int = 0
    proof_ok: bool = True
    source_drift: bool = False
    state_corruption: bool = False
    artifact_drift: bool = False
    recoverable_failure: bool = False
    failure_class: str = ""
    repeated_failure_count: int = 0
    alternative_route_available: bool = False
    provider_available: bool = True
    quality_score: float | None = None
    target_quality_score: float | None = None
    owner_correction_present: bool = False
    value_regression: bool = False
    authority_bound: bool = False
    semantic_readback_ok: bool = True
    latency_budget_breached: bool = False
    cost_budget_breached: bool = False
    signals: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AutopilotDecision:
    state: AutopilotState
    current_stage: str
    next_stage: str
    actions: tuple[str, ...]
    repair_actions: tuple[str, ...]
    learning_actions: tuple[str, ...]
    improvement_candidates: tuple[str, ...]
    owner_interrupt: bool
    continuation_allowed: bool
    authority_ceiling: str
    reasons: tuple[str, ...]
    provider_effect_authorized: bool
    financial_effect_authorized: bool
    publication_authorized: bool
    decision_sha256: str


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _next_stage(program: CreativeMissionProgram, stage_id: str) -> str:
    ids = [item.stage_id for item in program.stages]
    try:
        index = ids.index(stage_id)
    except ValueError as exc:
        raise ValueError("SOVARA_AUTOPILOT_UNKNOWN_STAGE") from exc
    return ids[index + 1] if index + 1 < len(ids) else ""


def _candidate_score(item: ImprovementSpec, signals: set[str]) -> tuple[int, int, str]:
    priority = {"P0": 0, "P1": 1, "P2": 2}[item.priority]
    haystack = f"{item.category} {item.title} {item.frontier_gene} {item.target_module}".upper()
    matches = sum(1 for signal in signals if signal in haystack)
    return (-matches, priority, item.improvement_id)


def select_improvement_candidates(signals: tuple[str, ...], *, limit: int = 8) -> tuple[str, ...]:
    normalized = {item.strip().upper().replace("-", "_") for item in signals if item.strip()}
    ranked = sorted(IMPROVEMENT_CATALOG, key=lambda item: _candidate_score(item, normalized))
    if not normalized:
        ranked = [item for item in ranked if item.priority == "P0"]
    return tuple(item.improvement_id for item in ranked[: max(1, int(limit))])


class SovaraCreativeAutopilot:
    """Bounded self-driving control loop for a compiled SOVARA mission.

    The controller may automatically plan, observe, retry, reroute, repair, learn,
    evaluate and recompile internal/read-only work. It never manufactures provider,
    financial, publication or consequential-effect authority. External transitions
    remain blocked until the required authority is independently bound.
    """

    max_stage_retries = 2

    def decide(
        self,
        *,
        program: CreativeMissionProgram,
        telemetry: AutopilotTelemetry,
    ) -> AutopilotDecision:
        stage = program.stage(telemetry.stage_id)
        following = _next_stage(program, stage.stage_id)
        signals = set(telemetry.signals)
        if telemetry.failure_class:
            signals.add(telemetry.failure_class)
        if telemetry.source_drift:
            signals.add("SOURCE_DRIFT")
        if telemetry.state_corruption:
            signals.add("STATE_CORRUPTION")
        if telemetry.artifact_drift:
            signals.add("ASSET_VERSION_FABRIC")
        if telemetry.value_regression:
            signals.add("VALUE_INTELLIGENCE")
        if telemetry.latency_budget_breached or telemetry.cost_budget_breached:
            signals.add("SCHEDULING")
        candidates = select_improvement_candidates(tuple(sorted(signals)))

        state = AutopilotState.ADVANCE
        actions: tuple[str, ...] = ("ADVANCE_TO_NEXT_STAGE",)
        repairs: tuple[str, ...] = ()
        learning: tuple[str, ...] = ()
        reasons: tuple[str, ...] = ("CURRENT_STAGE_ACCEPTED",)
        owner_interrupt = False
        continuation = True
        next_stage = following

        if telemetry.source_drift or telemetry.state_corruption or telemetry.artifact_drift:
            state = AutopilotState.SELF_REPAIR
            actions = ("FREEZE_STALE_DERIVATIONS", "RECOMPILE_FROM_VERIFIED_STATE")
            repairs = (
                "REFRESH_SOURCE_AND_STATE_LEASES",
                "VERIFY_DURABLE_STATE",
                "INVALIDATE_ONLY_AFFECTED_RESULTS",
                "REPLAY_DETERMINISTIC_STAGES",
            )
            learning = ("FAILURE_WIN_CAPTURE", "CFBE_GAP_REMEASUREMENT")
            reasons = tuple(
                item
                for item, active in (
                    ("SOURCE_DRIFT", telemetry.source_drift),
                    ("STATE_CORRUPTION", telemetry.state_corruption),
                    ("ARTIFACT_DRIFT", telemetry.artifact_drift),
                )
                if active
            )
            next_stage = "10-state"
        elif not telemetry.proof_ok or not telemetry.semantic_readback_ok:
            state = AutopilotState.HOLD_PROOF
            actions = ("HOLD_CURRENT_STAGE", "RECONCILE_PROOF_AND_READBACK")
            repairs = ("REPROBE_SAME_SEMANTIC_SURFACE", "REBUILD_PROOF_BINDING")
            learning = ("PROOF_FAILURE_MEMORY",)
            reasons = tuple(
                item
                for item, active in (
                    ("PROOF_INVALID", not telemetry.proof_ok),
                    ("SEMANTIC_READBACK_INVALID", not telemetry.semantic_readback_ok),
                )
                if active
            )
            next_stage = stage.stage_id
        elif stage.authority_required and not telemetry.authority_bound:
            state = AutopilotState.HOLD_AUTHORITY
            actions = ("HOLD_BEFORE_EFFECT",)
            repairs = ("CHECK_EXISTING_AUTHORITY", "PREPARE_MINIMUM_AUTHORITY_REQUEST")
            learning = ()
            reasons = ("EFFECT_AUTHORITY_NOT_BOUND",)
            owner_interrupt = True
            continuation = False
            next_stage = stage.stage_id
        elif telemetry.recoverable_failure:
            if telemetry.attempt < self.max_stage_retries:
                state = AutopilotState.RETRY
                actions = ("RETRY_CURRENT_STAGE",)
                repairs = ("APPLY_BOUNDED_BACKOFF", "PRESERVE_IDEMPOTENCY_KEY")
                learning = ("FAILURE_PATTERN_LEARNING",)
                reasons = ("RECOVERABLE_FAILURE_WITHIN_RETRY_BUDGET",)
                next_stage = stage.stage_id
            elif telemetry.alternative_route_available:
                state = AutopilotState.REROUTE
                actions = ("OPEN_PROVIDER_CIRCUIT", "SELECT_NEXT_STRONG_ROUTE")
                repairs = ("ISOLATE_FAILED_ROUTE", "PRESERVE_MISSION_STATE")
                learning = ("ROUTE_FAILURE_MEMORY", "CFBE_ROUTE_CHALLENGE")
                reasons = ("RETRY_BUDGET_EXHAUSTED_ALTERNATIVE_AVAILABLE",)
                next_stage = "40-route"
            else:
                state = AutopilotState.SELF_REPAIR
                actions = ("OPEN_FAILURE_WIN", "OPEN_CFBE_CHALLENGE", "ROLLBACK_TO_LAST_VERIFIED_STATE")
                repairs = ("ROOT_CAUSE_MODEL", "CAPABILITY_FOUNDRY_PROPOSAL", "REGRESSION_TEST_BEFORE_RETRY")
                learning = ("FAILURE_WIN_CAPTURE", "REPAIR_OUTCOME_LEARNING")
                reasons = ("RETRY_BUDGET_EXHAUSTED_NO_SAFE_ROUTE",)
                next_stage = "87-repair"
        elif not telemetry.provider_available and stage.stage_id in {"40-route", "50-preflight", "60-execute"}:
            if telemetry.alternative_route_available:
                state = AutopilotState.REROUTE
                actions = ("SELECT_HEALTHY_PROVIDER_OR_TOOL_ROUTE",)
                repairs = ("LEASE_PROVIDER_HEALTH", "CIRCUIT_BREAK_UNAVAILABLE_ROUTE")
                learning = ("PROVIDER_HEALTH_MEMORY",)
                reasons = ("CURRENT_PROVIDER_UNAVAILABLE",)
                next_stage = "40-route"
            else:
                state = AutopilotState.SELF_REPAIR
                actions = ("FALL_BACK_TO_SOVEREIGN_OR_NON_GENERATIVE_ROUTE", "OPEN_CAPABILITY_GAP")
                repairs = ("CAPABILITY_FOUNDRY_PROPOSAL",)
                learning = ("PROVIDER_GAP_MEMORY",)
                reasons = ("NO_HEALTHY_PROVIDER_ROUTE",)
                next_stage = "87-repair"
        elif telemetry.owner_correction_present:
            state = AutopilotState.RIPPLE_RECOMPILE
            actions = ("CAPTURE_OWNER_CORRECTION", "APPLY_MINIMUM_RIPPLE", "RECOMPILE_AFFECTED_STAGES")
            repairs = ("PRESERVE_LOCKED_APPROVED_STATE", "INVALIDATE_ONLY_DEPENDANTS")
            learning = ("TASTE_CAPTURE", "CORRECTION_PATTERN_LEARNING", "CFBE_QUALITY_REMEASUREMENT")
            reasons = ("OWNER_CORRECTION_PRESENT",)
            next_stage = "30-producer"
        elif telemetry.quality_score is not None and telemetry.target_quality_score is not None and telemetry.quality_score < telemetry.target_quality_score:
            state = AutopilotState.EVALUATOR_OPTIMIZER
            actions = ("RUN_EVALUATOR_OPTIMIZER", "GENERATE_BOUNDED_CHALLENGER")
            repairs = ("RIPPLE_REGENERATION", "PRESERVE_UNAFFECTED_STAGES")
            learning = ("QUALITY_LEARNING", "CFBE_CHAMPION_CHALLENGER")
            reasons = ("QUALITY_BELOW_TARGET",)
            next_stage = "80-qa"
        elif telemetry.value_regression or telemetry.cost_budget_breached or telemetry.latency_budget_breached:
            state = AutopilotState.ROLLBACK_CHAMPION
            actions = ("ROLLBACK_TO_LAST_VALUE_PROVEN_CHAMPION", "OPEN_CFBE_VALUE_CHALLENGE")
            repairs = ("REMEASURE_ROUTE_COST_QUALITY_LATENCY",)
            learning = ("VALUE_REGRESSION_MEMORY", "ROUTE_RETIREMENT_EVALUATION")
            reasons = tuple(
                item
                for item, active in (
                    ("VALUE_REGRESSION", telemetry.value_regression),
                    ("COST_BUDGET_BREACHED", telemetry.cost_budget_breached),
                    ("LATENCY_BUDGET_BREACHED", telemetry.latency_budget_breached),
                )
                if active
            )
            next_stage = "40-route"
        elif stage.stage_id == "90-release":
            state = AutopilotState.OWNER_RELEASE_REQUIRED
            actions = ("PRESENT_RELEASE_PACKET",)
            repairs = ()
            learning = ()
            reasons = ("CONSEQUENTIAL_RELEASE_REMAINS_HUMAN_OR_AUTHORITY_GATED",)
            owner_interrupt = True
            continuation = False
            next_stage = ""
        elif not following:
            state = AutopilotState.INTERNAL_COMPLETE
            actions = ("SEAL_INTERNAL_COMPLETION_RECEIPT",)
            reasons = ("ALL_INTERNAL_STAGES_COMPLETE",)
            next_stage = ""

        base = {
            "state": state.value,
            "current_stage": stage.stage_id,
            "next_stage": next_stage,
            "actions": list(actions),
            "repair_actions": list(repairs),
            "learning_actions": list(learning),
            "improvement_candidates": list(candidates),
            "owner_interrupt": owner_interrupt,
            "continuation_allowed": continuation,
            "authority_ceiling": program.authority_ceiling,
            "reasons": list(reasons),
            "provider_effect_authorized": False,
            "financial_effect_authorized": False,
            "publication_authorized": False,
            "program_sha256": program.program_sha256,
        }
        return AutopilotDecision(
            state=state,
            current_stage=stage.stage_id,
            next_stage=next_stage,
            actions=actions,
            repair_actions=repairs,
            learning_actions=learning,
            improvement_candidates=candidates,
            owner_interrupt=owner_interrupt,
            continuation_allowed=continuation,
            authority_ceiling=program.authority_ceiling,
            reasons=reasons,
            provider_effect_authorized=False,
            financial_effect_authorized=False,
            publication_authorized=False,
            decision_sha256=_digest(base),
        )
