"""Federation AAA chat-to-workflow learning primitives.

AAA means ABSTRACT -> ADAPT -> ACTIVATE. The implementation converts repeated
operational evidence into deterministic execution controls. It is deliberately
provider-neutral and A1_INTERNAL: it does not grant credentials, provider
authority, or consequential-effect permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping, Sequence

from .powerhouse import FormationOmega, ProofState, precedence_rank


class AAAError(ValueError):
    """Raised when an AAA input is internally inconsistent."""


class RouteOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    BLOCKED = "BLOCKED"
    NO_MATERIAL_CHANGE = "NO_MATERIAL_CHANGE"
    NEAR_MISS = "NEAR_MISS"


class CapabilityStage(str, Enum):
    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    CALLABLE = "CALLABLE"
    AUTHORITY_BOUND = "AUTHORITY_BOUND"
    SEMANTICALLY_VERIFIED = "SEMANTICALLY_VERIFIED"


@dataclass(frozen=True)
class EvidenceObservation:
    """One bounded statement about the same claim from one evidence layer."""

    observation_id: str
    claim_key: str
    value: object
    source_layer: str
    observed_at: str
    proof_state: ProofState
    current: bool = True
    semantic_readback: bool = False

    def timestamp(self) -> datetime:
        raw = self.observed_at.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Contradiction:
    claim_key: str
    selected_observation_id: str
    conflicting_observation_ids: tuple[str, ...]
    selected_value: object
    conflicting_values: tuple[object, ...]
    requires_correction: bool = True


@dataclass(frozen=True)
class TruthResolution:
    claim_key: str
    selected: EvidenceObservation
    contradiction: Contradiction | None
    promotion_allowed: bool
    reason: str


@dataclass(frozen=True)
class RouteAttempt:
    route_id: str
    objective: str
    route_fingerprint: str
    precondition_fingerprint: str
    outcome: RouteOutcome
    attempted_at: str
    owner_burden: float = 0.0
    proof_quality: float = 0.0


@dataclass(frozen=True)
class RouteRetryDecision:
    route_id: str
    retry_allowed: bool
    material_precondition_change: bool
    reason: str


@dataclass(frozen=True)
class CapabilityState:
    """Separate existence, execution, authority and semantic proof."""

    capability: str
    present: bool
    callable_now: bool
    authority_bound: bool
    semantic_verified: bool

    def __post_init__(self) -> None:
        if self.callable_now and not self.present:
            raise AAAError("callable_now requires present")
        if self.authority_bound and not self.callable_now:
            raise AAAError("authority_bound requires callable_now")
        if self.semantic_verified and not self.authority_bound:
            raise AAAError("semantic_verified requires authority_bound")

    @property
    def stage(self) -> CapabilityStage:
        if self.semantic_verified:
            return CapabilityStage.SEMANTICALLY_VERIFIED
        if self.authority_bound:
            return CapabilityStage.AUTHORITY_BOUND
        if self.callable_now:
            return CapabilityStage.CALLABLE
        if self.present:
            return CapabilityStage.PRESENT
        return CapabilityStage.ABSENT


@dataclass(frozen=True)
class SourceCapabilitySnapshot:
    source_id: str
    capabilities: frozenset[str]
    global_functions: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceUpgradeDecision:
    allowed: bool
    missing_capabilities: tuple[str, ...]
    duplicate_global_functions: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class AAALearningEvent:
    event_id: str
    category: str
    objective: str
    result: str
    evidence_ids: tuple[str, ...] = ()
    route_fingerprint: str = ""
    precondition_fingerprint: str = ""
    owner_burden: float = 0.0


@dataclass(frozen=True)
class AAALearningGene:
    gene_id: str
    category: str
    invariant: str
    activation: str
    evidence_ids: tuple[str, ...]
    sample_count: int
    confidence: str


@dataclass(frozen=True)
class AAACycleReport:
    abstracted_genes: tuple[AAALearningGene, ...]
    activated_controls: tuple[str, ...]
    held_controls: tuple[str, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _observation_sort_key(observation: EvidenceObservation) -> tuple[object, ...]:
    # Current evidence beats stale evidence. Inside the same freshness class,
    # Formation-Omega precedence controls, then proof strength and recency.
    return (
        0 if observation.current else 1,
        precedence_rank(observation.source_layer),
        -int(observation.proof_state),
        -observation.timestamp().timestamp(),
    )


def resolve_current_truth(observations: Sequence[EvidenceObservation]) -> TruthResolution:
    """Resolve a claim while preserving conflicting evidence as an explicit object.

    Fresh provider/native evidence can control execution without erasing a stale
    conflicting summary. A supported-or-stronger contradiction prevents proof
    promotion until the weaker projection is corrected or reverified.
    """

    if not observations:
        raise AAAError("at least one evidence observation is required")
    claim_keys = {item.claim_key for item in observations}
    if len(claim_keys) != 1:
        raise AAAError("all observations must resolve the same claim_key")

    selected = min(observations, key=_observation_sort_key)
    conflicts = tuple(
        item
        for item in observations
        if item.observation_id != selected.observation_id
        and item.current
        and item.proof_state >= ProofState.SUPPORTED
        and item.value != selected.value
    )

    contradiction = None
    if conflicts:
        contradiction = Contradiction(
            claim_key=selected.claim_key,
            selected_observation_id=selected.observation_id,
            conflicting_observation_ids=tuple(item.observation_id for item in conflicts),
            selected_value=selected.value,
            conflicting_values=tuple(item.value for item in conflicts),
        )

    return TruthResolution(
        claim_key=selected.claim_key,
        selected=selected,
        contradiction=contradiction,
        promotion_allowed=contradiction is None,
        reason=(
            "Highest-precedence current evidence selected; conflicting current evidence requires correction before promotion."
            if contradiction
            else "Highest-precedence current evidence selected with no supported contradiction."
        ),
    )


def route_retry_decision(
    current: RouteAttempt,
    history: Iterable[RouteAttempt],
) -> RouteRetryDecision:
    """Reject unchanged retry loops while allowing a materially changed re-probe."""

    prior = [
        item
        for item in history
        if item.objective == current.objective
        and item.route_fingerprint == current.route_fingerprint
    ]
    if not prior:
        return RouteRetryDecision(current.route_id, True, True, "Route has not been tried for this objective.")

    latest = max(prior, key=lambda item: datetime.fromisoformat(item.attempted_at.replace("Z", "+00:00")))
    preconditions_changed = latest.precondition_fingerprint != current.precondition_fingerprint
    unchanged_bad_outcome = latest.outcome in {
        RouteOutcome.FAILURE,
        RouteOutcome.BLOCKED,
        RouteOutcome.NO_MATERIAL_CHANGE,
    }

    if unchanged_bad_outcome and not preconditions_changed:
        return RouteRetryDecision(
            current.route_id,
            False,
            False,
            "Unchanged route fingerprint already failed/blocked; choose a materially different route or wait for a verified precondition change.",
        )

    return RouteRetryDecision(
        current.route_id,
        True,
        preconditions_changed,
        (
            "Verified preconditions changed; a bounded re-probe is admissible."
            if preconditions_changed
            else "Prior route outcome does not require suppression."
        ),
    )


def source_upgrade_decision(
    live: SourceCapabilitySnapshot,
    candidate: SourceCapabilitySnapshot,
    *,
    explicitly_retired: Iterable[str] = (),
) -> SourceUpgradeDecision:
    """Protect the fresh live capability floor before source replacement."""

    retired = frozenset(explicitly_retired)
    protected_live = live.capabilities - retired
    missing = tuple(sorted(protected_live - candidate.capabilities))

    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in candidate.global_functions:
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    duplicate_tuple = tuple(sorted(duplicates))
    allowed = not missing and not duplicate_tuple
    reason_parts: list[str] = []
    if missing:
        reason_parts.append("candidate removes fresh live capabilities")
    if duplicate_tuple:
        reason_parts.append("candidate contains duplicate global functions")
    if not reason_parts:
        reason_parts.append("candidate preserves live capability floor and global namespace uniqueness")

    return SourceUpgradeDecision(
        allowed=allowed,
        missing_capabilities=missing,
        duplicate_global_functions=duplicate_tuple,
        reason="; ".join(reason_parts),
    )


def choose_operational_route(
    objective: str,
    candidate_actions: Sequence[Mapping[str, object]],
    route_history: Iterable[RouteAttempt],
) -> Mapping[str, object]:
    """Formation route choice plus failure-memory suppression.

    Candidate actions may add ``route_fingerprint`` and
    ``precondition_fingerprint``. Ineligible unchanged-failure routes are
    excluded before Formation-Omega's smallest-sufficient decision is applied.
    """

    eligible: list[Mapping[str, object]] = []
    now = datetime.now(timezone.utc).isoformat()
    for candidate in candidate_actions:
        route_fingerprint = str(candidate.get("route_fingerprint") or candidate.get("name") or "")
        precondition_fingerprint = str(candidate.get("precondition_fingerprint") or "")
        if route_fingerprint:
            decision = route_retry_decision(
                RouteAttempt(
                    route_id=str(candidate.get("name") or route_fingerprint),
                    objective=objective,
                    route_fingerprint=route_fingerprint,
                    precondition_fingerprint=precondition_fingerprint,
                    outcome=RouteOutcome.NEAR_MISS,
                    attempted_at=now,
                    owner_burden=float(candidate.get("burden", 0.0)),
                    proof_quality=float(candidate.get("proof_quality", 0.0)),
                ),
                route_history,
            )
            if not decision.retry_allowed:
                continue
        eligible.append(candidate)

    return FormationOmega.smallest_sufficient_decision(objective, tuple(eligible))


_GENE_LIBRARY: Mapping[str, tuple[str, str]] = {
    "EVIDENCE_CONTRADICTION": (
        "Fresh authenticated/native evidence outranks stale projections, while the contradiction remains explicit until corrected.",
        "RESOLVE_CURRENT_TRUTH_AND_HOLD_PROMOTION_ON_SUPPORTED_CONTRADICTION",
    ),
    "UNCHANGED_ROUTE_FAILURE": (
        "Do not repeat the same failed route under unchanged preconditions.",
        "SUPPRESS_ROUTE_FINGERPRINT_UNTIL_PRECONDITION_CHANGE",
    ),
    "CAPABILITY_STATE_AMBIGUITY": (
        "Capability presence, callability, authority binding and semantic proof are separate states.",
        "TRACK_CAPABILITY_STAGE_EXPLICITLY",
    ),
    "SOURCE_CAPABILITY_LOSS": (
        "A source upgrade must preserve the fresh live capability floor unless retirement is explicit.",
        "REJECT_NON_ADDITIVE_SOURCE_REPLACEMENT",
    ),
    "OWNER_BURDEN": (
        "Among complete authorised reversible routes, prefer the lower-owner-burden route.",
        "APPLY_SMALLEST_SUFFICIENT_ROUTE_SELECTION",
    ),
}


def abstract_learning(events: Iterable[AAALearningEvent]) -> tuple[AAALearningGene, ...]:
    """ABSTRACT: turn bounded chat/workflow events into reusable capability genes."""

    groups: dict[str, list[AAALearningEvent]] = {}
    for event in events:
        groups.setdefault(event.category, []).append(event)

    genes: list[AAALearningGene] = []
    for category, grouped in sorted(groups.items()):
        if category not in _GENE_LIBRARY:
            continue
        invariant, activation = _GENE_LIBRARY[category]
        evidence_ids = tuple(sorted({eid for item in grouped for eid in item.evidence_ids}))
        payload = {
            "category": category,
            "invariant": invariant,
            "activation": activation,
            "evidence_ids": evidence_ids,
        }
        genes.append(
            AAALearningGene(
                gene_id="AAA-" + _sha256(payload)[:16].upper(),
                category=category,
                invariant=invariant,
                activation=activation,
                evidence_ids=evidence_ids,
                sample_count=len(grouped),
                confidence="REPEATED" if len(grouped) >= 2 else "SINGLE_CYCLE",
            )
        )
    return tuple(genes)


def adapt_learning(
    genes: Iterable[AAALearningGene],
    receiver_capabilities: Iterable[str],
) -> tuple[AAALearningGene, ...]:
    """ADAPT: keep only genes the receiving system can actually enforce."""

    receiver = frozenset(receiver_capabilities)
    required = {
        "EVIDENCE_CONTRADICTION": "evidence_resolution",
        "UNCHANGED_ROUTE_FAILURE": "route_memory",
        "CAPABILITY_STATE_AMBIGUITY": "capability_registry",
        "SOURCE_CAPABILITY_LOSS": "source_diff",
        "OWNER_BURDEN": "route_selection",
    }
    return tuple(gene for gene in genes if required[gene.category] in receiver)


def activate_learning(
    genes: Iterable[AAALearningGene],
    *,
    tests_passed: bool,
    regression_free: bool,
    external_effect_required: bool = False,
    external_authority_verified: bool = False,
) -> AAACycleReport:
    """ACTIVATE: promote only locally proven controls within the authority ceiling."""

    genes = tuple(genes)
    activated: list[str] = []
    held: list[str] = []

    for gene in genes:
        eligible = tests_passed and regression_free
        if external_effect_required and not external_authority_verified:
            eligible = False
        (activated if eligible else held).append(gene.activation)

    return AAACycleReport(
        abstracted_genes=genes,
        activated_controls=tuple(activated),
        held_controls=tuple(held),
    )


__all__ = [
    "AAAError",
    "AAACycleReport",
    "AAALearningEvent",
    "AAALearningGene",
    "CapabilityStage",
    "CapabilityState",
    "Contradiction",
    "EvidenceObservation",
    "RouteAttempt",
    "RouteOutcome",
    "RouteRetryDecision",
    "SourceCapabilitySnapshot",
    "SourceUpgradeDecision",
    "TruthResolution",
    "abstract_learning",
    "activate_learning",
    "adapt_learning",
    "choose_operational_route",
    "resolve_current_truth",
    "route_retry_decision",
    "source_upgrade_decision",
]
