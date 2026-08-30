from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import median
from typing import Iterable, Sequence


CONSTITUTIONAL_CORE = frozenset(
    {
        "SLOS.MISSION.FIDELITY",
        "SLOS.SOURCE.PROOF_HIERARCHY",
        "SLOS.AUTHORITY.SEPARATION",
        "SLOS.PROOF.TERMINAL_TRUTH",
        "SLOS.PROOF.NO_INHERITANCE",
        "SLOS.EXECUTION.REVERSIBILITY",
        "SLOS.OWNER.BURDEN_MINIMIZATION",
        "SLOS.HISTORY.INTEGRITY",
        "SLOS.EFFECT.EXACT_ISOLATION",
    }
)


class ObservationMode(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    HOSTED_SHADOW = "HOSTED_SHADOW"
    OBSERVED = "OBSERVED"


@dataclass(frozen=True, slots=True)
class MissionOracle:
    mission_id: str
    required_controls: frozenset[str]
    critical_controls: frozenset[str] = frozenset()
    require_stale_state_rejection: bool = False
    require_duplicate_suppression: bool = False
    require_trace_complete: bool = True

    def __post_init__(self) -> None:
        if not self.mission_id:
            raise ValueError("MISSION_ORACLE_ID_REQUIRED")
        if not self.required_controls:
            raise ValueError("MISSION_ORACLE_CONTROLS_REQUIRED")
        if not self.critical_controls.issubset(self.required_controls):
            raise ValueError("MISSION_ORACLE_CRITICAL_CONTROL_NOT_REQUIRED")


@dataclass(frozen=True, slots=True)
class ProfileObservation:
    profile: str
    mission_id: str
    mode: ObservationMode
    active_controls: frozenset[str]
    context_chars: int
    tool_round_trips: int
    owner_interventions: int
    stale_state_rejected: bool
    duplicate_suppressed: bool
    trace_complete: bool
    proof_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.profile or not self.mission_id:
            raise ValueError("PROFILE_OBSERVATION_IDENTITY_REQUIRED")
        if self.context_chars <= 0:
            raise ValueError("PROFILE_CONTEXT_CHARS_POSITIVE_REQUIRED")
        if self.tool_round_trips < 0 or self.owner_interventions < 0:
            raise ValueError("PROFILE_COUNTS_NONNEGATIVE_REQUIRED")
        if self.mode in {ObservationMode.HOSTED_SHADOW, ObservationMode.OBSERVED} and not self.proof_refs:
            raise ValueError("PROOF_REFERENCED_PROFILE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ProfileEvaluation:
    mission_id: str
    profile: str
    missing_controls: tuple[str, ...]
    critical_missing: tuple[str, ...]
    behavior_failures: tuple[str, ...]
    control_coverage: float
    hard_veto: bool


@dataclass(frozen=True, slots=True)
class PairMeasurement:
    mission_id: str
    baseline_profile: str
    candidate_profile: str
    mode: ObservationMode
    context_reduction: float
    tool_round_trip_delta: int
    owner_intervention_delta: int
    candidate_control_coverage: float
    candidate_missing_controls: tuple[str, ...]
    candidate_behavior_failures: tuple[str, ...]
    structural_pass: bool
    truth_state: str


@dataclass(frozen=True, slots=True)
class CampaignMeasurement:
    pair_count: int
    observed_pair_count: int
    hosted_shadow_pair_count: int
    structural_pass_count: int
    zero_critical_omissions: bool
    median_context_reduction: float
    median_tool_round_trip_delta: float
    median_owner_intervention_delta: float
    structural_candidate: bool
    empirical_value_candidate: bool
    stable_promotion_allowed: bool
    truth_state: str


def evaluate_profile(oracle: MissionOracle, observation: ProfileObservation) -> ProfileEvaluation:
    if observation.mission_id != oracle.mission_id:
        raise ValueError("MISSION_PROFILE_MISMATCH")
    missing = tuple(sorted(oracle.required_controls - observation.active_controls))
    critical_missing = tuple(sorted(oracle.critical_controls - observation.active_controls))
    behavior_failures: list[str] = []
    if oracle.require_stale_state_rejection and not observation.stale_state_rejected:
        behavior_failures.append("STALE_STATE_REJECTION")
    if oracle.require_duplicate_suppression and not observation.duplicate_suppressed:
        behavior_failures.append("DUPLICATE_SUPPRESSION")
    if oracle.require_trace_complete and not observation.trace_complete:
        behavior_failures.append("TRACE_COMPLETENESS")
    required_count = len(oracle.required_controls)
    coverage = (required_count - len(missing)) / required_count
    return ProfileEvaluation(
        mission_id=oracle.mission_id,
        profile=observation.profile,
        missing_controls=missing,
        critical_missing=critical_missing,
        behavior_failures=tuple(behavior_failures),
        control_coverage=coverage,
        hard_veto=bool(critical_missing or behavior_failures),
    )


def compare_pair(
    oracle: MissionOracle,
    baseline: ProfileObservation,
    candidate: ProfileObservation,
    *,
    minimum_context_reduction: float = 0.80,
) -> PairMeasurement:
    if not 0 <= minimum_context_reduction < 1:
        raise ValueError("MINIMUM_CONTEXT_REDUCTION_RANGE")
    if baseline.mode != candidate.mode:
        raise ValueError("PAIR_OBSERVATION_MODE_MISMATCH")
    baseline_eval = evaluate_profile(oracle, baseline)
    candidate_eval = evaluate_profile(oracle, candidate)
    if baseline_eval.hard_veto or baseline_eval.missing_controls:
        raise ValueError("BASELINE_ORACLE_NOT_SATISFIED")
    context_reduction = 1 - (candidate.context_chars / baseline.context_chars)
    non_regression = (
        not candidate_eval.hard_veto
        and not candidate_eval.missing_controls
        and candidate_eval.control_coverage >= baseline_eval.control_coverage
        and candidate.tool_round_trips <= baseline.tool_round_trips
        and candidate.owner_interventions <= baseline.owner_interventions
    )
    structural_pass = non_regression and context_reduction >= minimum_context_reduction
    truth_state = (
        "OBSERVED_PAIR_PASS"
        if structural_pass and candidate.mode == ObservationMode.OBSERVED
        else "HOSTED_SHADOW_PAIR_PASS"
        if structural_pass and candidate.mode == ObservationMode.HOSTED_SHADOW
        else "SYNTHETIC_PAIR_PASS"
        if structural_pass
        else "PAIR_HOLD"
    )
    return PairMeasurement(
        mission_id=oracle.mission_id,
        baseline_profile=baseline.profile,
        candidate_profile=candidate.profile,
        mode=candidate.mode,
        context_reduction=context_reduction,
        tool_round_trip_delta=candidate.tool_round_trips - baseline.tool_round_trips,
        owner_intervention_delta=candidate.owner_interventions - baseline.owner_interventions,
        candidate_control_coverage=candidate_eval.control_coverage,
        candidate_missing_controls=candidate_eval.missing_controls,
        candidate_behavior_failures=candidate_eval.behavior_failures,
        structural_pass=structural_pass,
        truth_state=truth_state,
    )


def aggregate_campaign(
    pairs: Sequence[PairMeasurement],
    *,
    minimum_observed_pairs: int = 30,
    minimum_context_reduction: float = 0.80,
) -> CampaignMeasurement:
    if not pairs:
        raise ValueError("CAMPAIGN_PAIRS_REQUIRED")
    if minimum_observed_pairs <= 0:
        raise ValueError("CAMPAIGN_MINIMUM_OBSERVED_POSITIVE")
    reductions = [pair.context_reduction for pair in pairs]
    tool_deltas = [pair.tool_round_trip_delta for pair in pairs]
    owner_deltas = [pair.owner_intervention_delta for pair in pairs]
    observed_count = sum(pair.mode == ObservationMode.OBSERVED for pair in pairs)
    hosted_shadow_count = sum(pair.mode == ObservationMode.HOSTED_SHADOW for pair in pairs)
    pass_count = sum(pair.structural_pass for pair in pairs)
    zero_critical_omissions = all(
        not pair.candidate_missing_controls and not pair.candidate_behavior_failures
        for pair in pairs
    )
    median_reduction = median(reductions)
    structural_candidate = (
        pass_count == len(pairs)
        and zero_critical_omissions
        and median_reduction >= minimum_context_reduction
    )
    empirical_value_candidate = (
        structural_candidate
        and observed_count >= minimum_observed_pairs
        and median(tool_deltas) <= 0
        and median(owner_deltas) <= 0
    )
    truth_state = (
        "EMPIRICAL_VALUE_CANDIDATE"
        if empirical_value_candidate
        else "STRUCTURAL_CANDIDATE"
        if structural_candidate
        else "MEASUREMENT_HOLD"
    )
    return CampaignMeasurement(
        pair_count=len(pairs),
        observed_pair_count=observed_count,
        hosted_shadow_pair_count=hosted_shadow_count,
        structural_pass_count=pass_count,
        zero_critical_omissions=zero_critical_omissions,
        median_context_reduction=median_reduction,
        median_tool_round_trip_delta=median(tool_deltas),
        median_owner_intervention_delta=median(owner_deltas),
        structural_candidate=structural_candidate,
        empirical_value_candidate=empirical_value_candidate,
        stable_promotion_allowed=False,
        truth_state=truth_state,
    )


def compile_control_slice(
    oracle: MissionOracle,
    *,
    constitutional_core: Iterable[str] = CONSTITUTIONAL_CORE,
) -> frozenset[str]:
    """Return the smallest typed control set required by the mission oracle.

    This is a selection function only. It does not mutate doctrine, grant provider
    authority, execute an effect, or delete cold historical proof.
    """

    return frozenset(constitutional_core) | oracle.required_controls


def default_mission_oracles() -> tuple[MissionOracle, ...]:
    """Privacy-safe synthetic mission classes for the first convergence court."""

    core = CONSTITUTIONAL_CORE
    return (
        MissionOracle(
            "CURRENT_STATE_READ",
            core
            | frozenset(
                {
                    "BUBBLES.STATE.CURRENT_LEASE",
                    "BUBBLES.TRACE.SPINE",
                }
            ),
            critical_controls=frozenset(
                {"SLOS.SOURCE.PROOF_HIERARCHY", "BUBBLES.STATE.CURRENT_LEASE"}
            ),
            require_stale_state_rejection=True,
        ),
        MissionOracle(
            "PROVIDER_EFFECT",
            core
            | frozenset(
                {
                    "SOVARA.EFFECT.GATE",
                    "BUBBLES.EFFECT.IDEMPOTENCY",
                    "SLOS.PROOF.SEMANTIC_READBACK",
                    "SOVARA.RECOVERY.ROLLBACK",
                    "BUBBLES.TRACE.SPINE",
                }
            ),
            critical_controls=frozenset(
                {
                    "SLOS.AUTHORITY.SEPARATION",
                    "SOVARA.EFFECT.GATE",
                    "BUBBLES.EFFECT.IDEMPOTENCY",
                    "SLOS.PROOF.SEMANTIC_READBACK",
                }
            ),
            require_duplicate_suppression=True,
        ),
        MissionOracle(
            "LEGAL_FORENSIC",
            core
            | frozenset(
                {
                    "JARVIS.AO5.FORENSIC",
                    "JARVIS.AO5.EVIDENCE_QUALITY",
                    "JARVIS.AO5.COUNTERFACTUAL",
                    "JARVIS.AO5.TEMPORAL_STATE",
                    "EVIDENCEOPS.PROVENANCE",
                }
            ),
            critical_controls=frozenset(
                {"SLOS.SOURCE.PROOF_HIERARCHY", "EVIDENCEOPS.PROVENANCE"}
            ),
        ),
        MissionOracle(
            "FAILURE_RECOVERY",
            core
            | frozenset(
                {
                    "FAILURE_WIN.RECOVERY",
                    "FAILURE_WIN.MATERIAL_REROUTE",
                    "FAILURE_WIN.CIRCUIT_BREAKER",
                    "BUBBLES.TRACE.SPINE",
                }
            ),
            critical_controls=frozenset(
                {"FAILURE_WIN.MATERIAL_REROUTE", "SLOS.HISTORY.INTEGRITY"}
            ),
        ),
        MissionOracle(
            "EVOLUTION_BENCHMARK",
            core
            | frozenset(
                {
                    "SLOS.EXPERIMENT.IDENTITY",
                    "SLOS.ROBUSTNESS.COURT",
                    "CFBE.CHAMPION_CHALLENGER",
                    "CFBE.VALUE.GATE",
                    "SLOS.PROMOTION.STAGED",
                }
            ),
            critical_controls=frozenset(
                {"SLOS.EXPERIMENT.IDENTITY", "CFBE.VALUE.GATE"}
            ),
        ),
        MissionOracle(
            "CROSS_CHAT_HEARTBEAT",
            core
            | frozenset(
                {
                    "HEARTBEAT.READ_BEFORE_WORK",
                    "HEARTBEAT.CONFLICT_PRESERVATION",
                    "HEARTBEAT.STALE_STATE",
                    "BUBBLES.STATE.CURRENT_LEASE",
                }
            ),
            critical_controls=frozenset(
                {"HEARTBEAT.CONFLICT_PRESERVATION", "BUBBLES.STATE.CURRENT_LEASE"}
            ),
            require_stale_state_rejection=True,
        ),
        MissionOracle(
            "LARGE_TOOL_OUTPUT",
            core
            | frozenset(
                {
                    "BUBBLES.PAYLOAD.FIREWALL",
                    "BUBBLES.PAYLOAD.DIAGNOSTIC_EXTRACTOR",
                    "BUBBLES.PAYLOAD.SECRET_REDACTION",
                }
            ),
            critical_controls=frozenset(
                {"BUBBLES.PAYLOAD.FIREWALL", "BUBBLES.PAYLOAD.SECRET_REDACTION"}
            ),
        ),
        MissionOracle(
            "VISUAL_ARTIFACT_ASSURANCE",
            core
            | frozenset(
                {
                    "SLOS.ARTIFACT.STRUCTURAL_GEOMETRY",
                    "SLOS.ARTIFACT.TEXT_LAYER",
                    "SLOS.ARTIFACT.PERCEPTUAL_FINGERPRINT",
                    "SLOS.ARTIFACT.SEMANTIC_VISUAL_QA",
                }
            ),
            critical_controls=frozenset(
                {
                    "SLOS.ARTIFACT.STRUCTURAL_GEOMETRY",
                    "SLOS.ARTIFACT.SEMANTIC_VISUAL_QA",
                }
            ),
        ),
    )


def full_control_universe(oracles: Sequence[MissionOracle] | None = None) -> frozenset[str]:
    selected = oracles or default_mission_oracles()
    controls: set[str] = set()
    for oracle in selected:
        controls.update(oracle.required_controls)
    return frozenset(controls)


def truth_boundary() -> dict[str, bool]:
    return {
        "source_measurement_is_runtime_latency_proof": False,
        "synthetic_pair_is_owner_value_proof": False,
        "observed_pair_is_stable_release_promotion": False,
        "measurement_court_grants_provider_authority": False,
        "cold_history_may_be_deleted_for_context_reduction": False,
        "stable_slos_v070_is_mutated_by_this_module": False,
    }
