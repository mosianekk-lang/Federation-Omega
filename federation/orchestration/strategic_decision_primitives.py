"""Strategic FUSE decision-intelligence primitives.

These are subordinate, provider-neutral and effect-free data contracts/helpers.
They do not create authority, a scheduler, a truth store, or a runtime.

The module intentionally keeps legacy strategic-ledger rows immutable. Current
schemas can be normalized positionally only when their schema is known; legacy
rows are carried as raw values until an exact legacy decoder is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import log
import re
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence


CURRENT_HEADERS: dict[str, tuple[str, ...]] = {
    "Strategic_Signal_Inbox": (
        "Signal_ID", "Observed_At", "Source_Type", "Actor_or_Market", "Signal",
        "Credibility", "Strategic_Impact", "Surprise", "Pattern_Class",
        "Linked_Hypothesis", "Freshness_TTL", "Evidence_Ref", "Status",
        "Next_Action", "Owner_Burden", "Notes",
    ),
    "Strategic_Hypothesis_Ledger": (
        "Hypothesis_ID", "Created_At", "Claim", "Probability", "Evidence_For",
        "Evidence_Against", "Falsifier", "Dependencies", "Horizon",
        "Actor_or_Market", "Strategic_Implication", "Required_Capability",
        "Confidence", "State", "Review_By", "Notes",
    ),
    "Strategic_Opportunity_Book": (
        "Opportunity_ID", "Detected_At", "Problem_or_WhiteSpace", "Market",
        "Timing", "Capability_Fit", "Build_Cost", "Strategic_Value",
        "Commercial_Value", "Defensibility", "Competition", "Information_Gain",
        "Option_Value", "Next_Evidence", "State", "Linked_Action",
    ),
    "Strategic_Forecast_Calibration": (
        "Forecast_ID", "Issued_At", "Target", "Event", "Horizon", "Probability",
        "Confidence", "Leading_Indicators", "Falsifiers", "Outcome_Observed",
        "Resolved_At", "Brier_Component", "Calibration_Bucket", "Model_or_Agent",
        "Learning", "State",
    ),
    "Strategic_Action_Queue": (
        "Action_ID", "Created_At", "Trigger", "Objective", "Action_Class",
        "Authority_Class", "Reversibility", "Expected_Value", "Information_Value",
        "Risk", "Dependencies", "Preferred_Route", "Fallback_Route", "Proof_Gate",
        "State", "Execution_Ref", "Readback_Ref", "Notes",
    ),
    "Strategic_Proof_Ledger": (
        "Proof_ID", "Action_ID", "Proof_Time", "Proof_Class", "Expected_State",
        "Observed_State", "Source_Ref", "Provider_Readback", "Behavioral_Proof",
        "Value_Proof", "Freshness_TTL", "Diff", "Result", "Rollback_Ready",
        "Next_Action", "Notes",
    ),
}

LEGACY_IDS: dict[str, frozenset[str]] = {
    "Strategic_Signal_Inbox": frozenset({"SIG-006", "SIG-007", "SIG-008", "SIG-009"}),
    "Strategic_Hypothesis_Ledger": frozenset({"HYP-005", "HYP-006", "HYP-007", "HYP-008"}),
    "Strategic_Opportunity_Book": frozenset({"OPP-005", "OPP-006", "OPP-007"}),
    "Strategic_Forecast_Calibration": frozenset({"FCT-005", "FCT-006", "FCT-007", "FCT-008"}),
    "Strategic_Action_Queue": frozenset({"AQN-006", "AQN-007", "AQN-008", "AQN-009"}),
    "Strategic_Proof_Ledger": frozenset({"PFL-006", "PFL-007", "PFL-008", "PFL-009", "PFL-010"}),
}


@dataclass(frozen=True)
class NormalizedRecord:
    ledger: str
    record_id: str
    schema_version: str
    normalized: bool
    values: Mapping[str, Any] | None = None
    raw_values: tuple[Any, ...] = ()


def detect_schema_version(ledger: str, record_id: str) -> str:
    if ledger not in CURRENT_HEADERS:
        raise KeyError(f"unknown strategic ledger: {ledger}")
    if record_id in LEGACY_IDS.get(ledger, frozenset()):
        return "legacy_v1"
    return "current_v2"


def normalize_record(ledger: str, record_id: str, values: Sequence[Any]) -> NormalizedRecord:
    """Normalize only rows whose schema is actually known.

    Legacy rows are deliberately *not* zipped against the current header. They
    remain immutable raw history until an exact historical decoder is proven.
    """
    version = detect_schema_version(ledger, record_id)
    if version == "legacy_v1":
        return NormalizedRecord(ledger, record_id, version, False, raw_values=tuple(values))
    header = CURRENT_HEADERS[ledger]
    if len(values) != len(header):
        raise ValueError(f"{ledger} current_v2 expects {len(header)} values, got {len(values)}")
    return NormalizedRecord(ledger, record_id, version, True, dict(zip(header, values)))


class RegretIdentifiability(str, Enum):
    OBSERVED = "OBSERVED"
    ESTIMABLE = "ESTIMABLE"
    WEAKLY_ESTIMABLE = "WEAKLY_ESTIMABLE"
    UNIDENTIFIABLE = "UNIDENTIFIABLE"


@dataclass(frozen=True)
class StrategicDecisionRecord:
    decision_id: str
    mission_id: str
    decision_epoch: str
    source_epoch: str
    world_snapshot_ref: str
    candidate_option_refs: tuple[str, ...]
    selected_option_ref: str
    no_op_baseline_ref: str
    decision_mechanism: str
    alternative_rejection_reasons: Mapping[str, str]
    authority_class: str
    effect_ceiling: str
    proof_refs: tuple[str, ...] = ()
    value_refs: tuple[str, ...] = ()
    decision_scope_completion: str = "OPEN"
    regret_identifiability: RegretIdentifiability = RegretIdentifiability.UNIDENTIFIABLE
    scenario_refs: tuple[str, ...] = ()
    state: str = "FROZEN"

    def __post_init__(self) -> None:
        if not self.decision_id or not self.mission_id:
            raise ValueError("decision_id and mission_id are required")
        if not self.no_op_baseline_ref:
            raise ValueError("no-op baseline is mandatory")
        if self.selected_option_ref not in self.candidate_option_refs:
            raise ValueError("selected option must be one of the frozen candidates")
        if not self.decision_mechanism:
            raise ValueError("decision mechanism is required")


_PHYSICAL_LOCATION = re.compile(r"^(?:row\s*\d+|[A-Z]+\d+(?::[A-Z]+\d+)?|.*![A-Z]+\d+(?::[A-Z]+\d+)?)$", re.I)


@dataclass(frozen=True)
class CrossSurfaceReceiptCheck:
    logical_receipt_id: str
    match_count: int
    semantic_match: bool
    source_identity_match: bool
    fresh: bool

    @property
    def valid(self) -> bool:
        if not self.logical_receipt_id or _PHYSICAL_LOCATION.match(self.logical_receipt_id.strip()):
            return False
        return self.match_count == 1 and self.semantic_match and self.source_identity_match and self.fresh


def can_promote_cross_surface_proof(check: CrossSurfaceReceiptCheck) -> bool:
    return check.valid


@dataclass(frozen=True)
class ForecastSubmission:
    forecaster_id: str
    provider_model_method: str
    probability: float
    confidence: float
    evidence_cutoff: str
    blind_cohort: str
    submission_hash: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be 0..1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be 0..1")
        if not self.blind_cohort:
            raise ValueError("blind cohort is required")
        if not self.submission_hash:
            raise ValueError("submission_hash is required")


def brier_score(probability: float, outcome: bool) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be 0..1")
    return (probability - (1.0 if outcome else 0.0)) ** 2


def log_score(probability: float, outcome: bool, floor: float = 1e-12) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be 0..1")
    p = probability if outcome else 1.0 - probability
    return -log(max(p, floor))


@dataclass(frozen=True)
class ForecastTournamentRecord:
    tournament_id: str
    forecast_id: str
    mission_id: str
    domain: str
    horizon: str
    issued_at: str
    resolve_by: str
    evidence_snapshot_ref: str
    evidence_cutoff: str
    submissions: tuple[ForecastSubmission, ...]
    aggregation_method: str = "mean"

    def __post_init__(self) -> None:
        if len(self.submissions) < 2:
            raise ValueError("blind tournament requires at least two independent submissions")
        forecasters = {s.forecaster_id for s in self.submissions}
        if len(forecasters) != len(self.submissions):
            raise ValueError("forecaster identities must be unique")
        cutoffs = {s.evidence_cutoff for s in self.submissions}
        if cutoffs != {self.evidence_cutoff}:
            raise ValueError("all submissions must share the frozen evidence cutoff")
        cohorts = {s.blind_cohort for s in self.submissions}
        if len(cohorts) != 1:
            raise ValueError("all submissions must belong to the same blind cohort")
        if self.aggregation_method not in {"mean", "median"}:
            raise ValueError("unsupported aggregation method")

    @property
    def aggregate_probability(self) -> float:
        probs = [s.probability for s in self.submissions]
        value = mean(probs) if self.aggregation_method == "mean" else median(probs)
        return round(float(value), 12)

    @property
    def disagreement(self) -> float:
        avg = mean(s.probability for s in self.submissions)
        return round(mean(abs(s.probability - avg) for s in self.submissions), 12)

    def score(self, outcome: bool) -> dict[str, dict[str, float]]:
        return {
            s.forecaster_id: {
                "brier": round(brier_score(s.probability, outcome), 12),
                "log": round(log_score(s.probability, outcome), 12),
            }
            for s in self.submissions
        }


class PortfolioAction(str, Enum):
    SCALE = "SCALE"
    CONTINUE = "CONTINUE"
    TEST = "TEST"
    REDUCE = "REDUCE"
    MERGE = "MERGE"
    WATCH = "WATCH"
    KILL = "KILL"
    RETIRE = "RETIRE"


@dataclass(frozen=True)
class StrategicPortfolioRiskVector:
    opportunity_id: str
    strategic_value: float
    commercial_value: float
    option_value: float
    information_value: float
    reuse_value: float
    direct_owner_value_proven: bool
    commercial_validation_proven: bool
    architecture_overlap: float
    capability_rent: float
    evidence_uncertainty: float
    time_to_value_uncertainty: float

    def __post_init__(self) -> None:
        for name in (
            "strategic_value", "commercial_value", "option_value", "information_value",
            "reuse_value", "architecture_overlap", "capability_rent",
            "evidence_uncertainty", "time_to_value_uncertainty",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be 0..1")

    @property
    def total_sovereign_cost(self) -> float:
        return round(mean((self.architecture_overlap, self.capability_rent, self.evidence_uncertainty, self.time_to_value_uncertainty)), 6)

    def reunderwrite(self) -> PortfolioAction:
        """Return one scarcity action without confusing reuse value with standalone value."""
        if self.direct_owner_value_proven and self.commercial_validation_proven:
            if self.architecture_overlap < 0.35 and self.capability_rent < 0.5:
                return PortfolioAction.SCALE
            return PortfolioAction.CONTINUE
        if self.reuse_value >= 0.65 and self.architecture_overlap >= 0.65:
            return PortfolioAction.MERGE
        if self.reuse_value < 0.25 and self.option_value < 0.35 and self.information_value < 0.35:
            return PortfolioAction.KILL
        if self.capability_rent >= 0.75 and self.evidence_uncertainty >= 0.65:
            return PortfolioAction.REDUCE
        if self.information_value >= 0.65 and self.evidence_uncertainty >= 0.45:
            return PortfolioAction.TEST
        return PortfolioAction.WATCH


@dataclass(frozen=True)
class QualitySettlement:
    decision_quality: bool
    execution_quality: bool
    proof_quality: bool
    value_quality: bool

    @property
    def complete(self) -> bool:
        """No success is inherited across independent quality dimensions."""
        return all((self.decision_quality, self.execution_quality, self.proof_quality, self.value_quality))
