from __future__ import annotations

"""CFBE Estate Coherence + Owner-Value Closure Controller v1.

This is a bounded compiler, not a new top-level system. It composes existing
Federation controls into a desired-state reconciliation pass:

    fresh source -> canonical projection -> lifecycle disposition -> owner value

The design independently applies public patterns associated with Kubernetes
reconciliation, Argo CD self-heal, Backstage catalog lifecycle, Temporal durable
resume, GitHub latest-base validation, DORA metrics, SLSA provenance and
OpenFeature lifecycle hooks. It performs no provider mutation, source merge,
communication or stable promotion.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "CFBE_ESTATE_COHERENCE_VALUE_CLOSURE_V1"
MINIMUM_OWNER_VALUE_PAIRS = 10
DEFAULT_PROJECTION_TTL_SECONDS = 900
DEFAULT_RESTACK_THRESHOLD_COMMITS = 12
DEFAULT_CLOSE_THRESHOLD_COMMITS = 40

LEADER_PATTERNS: tuple[dict[str, str], ...] = (
    {"leader": "Kubernetes", "pattern": "desired/observed-state reconciliation", "harvest": "reconcile until observed state converges"},
    {"leader": "Argo CD", "pattern": "self-heal and bounded retry", "harvest": "repair drift automatically while keeping failed state visible"},
    {"leader": "Backstage", "pattern": "catalog ownership and lifecycle", "harvest": "attach owner, lifecycle and replacement semantics to every canonical surface"},
    {"leader": "Temporal", "pattern": "durable checkpoints and replay safety", "harvest": "resume from a fenced generation without duplicating effects"},
    {"leader": "GitHub", "pattern": "latest-base and merge-queue validation", "harvest": "retest or restack stale changes against current canonical head"},
    {"leader": "DORA", "pattern": "speed and stability metrics", "harvest": "measure projection lag, repair latency and failure rate instead of feature count"},
    {"leader": "SLSA", "pattern": "verifiable provenance", "harvest": "bind closure receipts to exact source and input identity"},
    {"leader": "OpenFeature", "pattern": "before/after/error/finally hooks", "harvest": "separate preflight, action plan, failure classification and final receipt"},
)


class ProjectionState(str, Enum):
    CURRENT = "CURRENT"
    DRIFTED = "DRIFTED"
    STALE = "STALE"
    HISTORICAL = "HISTORICAL"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


class PRDisposition(str, Enum):
    KEEP = "KEEP"
    RESTACK = "RESTACK"
    CLOSE = "CLOSE"
    HOLD = "HOLD"


class CapabilityDecision(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    SPECIALISE = "SPECIALISE"
    MERGE = "MERGE"
    NEW = "NEW"
    HOLD = "HOLD"


class ActionKind(str, Enum):
    RECONCILE_PROJECTION = "RECONCILE_PROJECTION"
    MARK_HISTORICAL = "MARK_HISTORICAL"
    MARK_SUPERSEDED = "MARK_SUPERSEDED"
    RESTACK_PR = "RESTACK_PR"
    CLOSE_PR = "CLOSE_PR"
    HOLD_PR = "HOLD_PR"
    COLLECT_OWNER_VALUE = "COLLECT_OWNER_VALUE"
    REUSE_CAPABILITY = "REUSE_CAPABILITY"
    EXTEND_CAPABILITY = "EXTEND_CAPABILITY"
    SPECIALISE_CAPABILITY = "SPECIALISE_CAPABILITY"
    MERGE_CAPABILITY = "MERGE_CAPABILITY"
    HOLD_NEW_CAPABILITY = "HOLD_NEW_CAPABILITY"
    ADMIT_NEW_CAPABILITY = "ADMIT_NEW_CAPABILITY"


@dataclass(frozen=True, slots=True)
class SurfaceObservation:
    surface_id: str
    owner: str
    lifecycle: str
    requires_current_source: bool
    observed_source_sha: str | None
    observed_at_sast: str
    ttl_seconds: int = DEFAULT_PROJECTION_TTL_SECONDS
    intentionally_historical: bool = False
    superseded_by: str | None = None
    proof_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SurfaceObservation":
        return cls(
            surface_id=str(value.get("surface_id") or "").strip(),
            owner=str(value.get("owner") or "").strip(),
            lifecycle=str(value.get("lifecycle") or "").strip(),
            requires_current_source=value.get("requires_current_source") is True,
            observed_source_sha=_none_or_text(value.get("observed_source_sha")),
            observed_at_sast=str(value.get("observed_at_sast") or "").strip(),
            ttl_seconds=int(value.get("ttl_seconds", DEFAULT_PROJECTION_TTL_SECONDS)),
            intentionally_historical=value.get("intentionally_historical") is True,
            superseded_by=_none_or_text(value.get("superseded_by")),
            proof_refs=_items(value.get("proof_refs")),
        )

    def validate(self) -> "SurfaceObservation":
        if not self.surface_id or not self.owner or not self.lifecycle:
            raise ValueError("SURFACE_ID_OWNER_LIFECYCLE_REQUIRED")
        _parse_timestamp(self.observed_at_sast)
        if self.ttl_seconds <= 0:
            raise ValueError("SURFACE_TTL_POSITIVE_REQUIRED")
        if self.observed_source_sha is not None and not _is_sha(self.observed_source_sha):
            raise ValueError("SURFACE_SOURCE_SHA_INVALID")
        if self.superseded_by == self.surface_id:
            raise ValueError("SURFACE_CANNOT_SUPERSEDE_SELF")
        return self


@dataclass(frozen=True, slots=True)
class PullRequestObservation:
    pr_number: int
    title: str
    base_sha: str
    head_sha: str
    commits_behind_main: int
    unique_capability: bool
    semantic_duplicate: bool = False
    superseded_by_pr: int | None = None
    provider_or_effect_gate_open: bool = False
    exact_head_green: bool = False
    proof_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PullRequestObservation":
        return cls(
            pr_number=int(value.get("pr_number", 0)),
            title=str(value.get("title") or "").strip(),
            base_sha=str(value.get("base_sha") or "").strip(),
            head_sha=str(value.get("head_sha") or "").strip(),
            commits_behind_main=int(value.get("commits_behind_main", 0)),
            unique_capability=value.get("unique_capability") is True,
            semantic_duplicate=value.get("semantic_duplicate") is True,
            superseded_by_pr=int(value["superseded_by_pr"]) if value.get("superseded_by_pr") not in (None, "") else None,
            provider_or_effect_gate_open=value.get("provider_or_effect_gate_open") is True,
            exact_head_green=value.get("exact_head_green") is True,
            proof_refs=_items(value.get("proof_refs")),
        )

    def validate(self) -> "PullRequestObservation":
        if self.pr_number <= 0 or not self.title:
            raise ValueError("PR_IDENTITY_REQUIRED")
        if not _is_sha(self.base_sha) or not _is_sha(self.head_sha):
            raise ValueError("PR_SOURCE_SHA_INVALID")
        if self.commits_behind_main < 0:
            raise ValueError("PR_BEHIND_COUNT_NONNEGATIVE_REQUIRED")
        if self.superseded_by_pr == self.pr_number:
            raise ValueError("PR_CANNOT_SUPERSEDE_SELF")
        return self


@dataclass(frozen=True, slots=True)
class CapabilityProposal:
    proposal_id: str
    gap_id: str
    gap_severity: int
    existing_capability_coverage: float
    composable_existing_capabilities: int
    measurable_owner_value_hypothesis: bool
    architectural_need_for_new_top_level_system: bool = False
    proof_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CapabilityProposal":
        return cls(
            proposal_id=str(value.get("proposal_id") or "").strip(),
            gap_id=str(value.get("gap_id") or "").strip(),
            gap_severity=int(value.get("gap_severity", 0)),
            existing_capability_coverage=float(value.get("existing_capability_coverage", 0)),
            composable_existing_capabilities=int(value.get("composable_existing_capabilities", 0)),
            measurable_owner_value_hypothesis=value.get("measurable_owner_value_hypothesis") is True,
            architectural_need_for_new_top_level_system=value.get("architectural_need_for_new_top_level_system") is True,
            proof_refs=_items(value.get("proof_refs")),
        )

    def validate(self) -> "CapabilityProposal":
        if not self.proposal_id or not self.gap_id:
            raise ValueError("CAPABILITY_PROPOSAL_IDENTITY_REQUIRED")
        if not 1 <= self.gap_severity <= 5:
            raise ValueError("CAPABILITY_GAP_SEVERITY_1_TO_5_REQUIRED")
        if not 0 <= self.existing_capability_coverage <= 1:
            raise ValueError("CAPABILITY_COVERAGE_RANGE_INVALID")
        if self.composable_existing_capabilities < 0:
            raise ValueError("CAPABILITY_COMPOSABLE_COUNT_NONNEGATIVE_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class OwnerValueState:
    observed_pair_count: int
    strict_owner_value_court_verified: bool
    machine_observable_burden_candidate: bool = False
    proof_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "OwnerValueState":
        value = value or {}
        return cls(
            observed_pair_count=int(value.get("observed_pair_count", 0)),
            strict_owner_value_court_verified=value.get("strict_owner_value_court_verified") is True,
            machine_observable_burden_candidate=value.get("machine_observable_burden_candidate") is True,
            proof_refs=_items(value.get("proof_refs")),
        )

    @property
    def proven(self) -> bool:
        return self.observed_pair_count >= MINIMUM_OWNER_VALUE_PAIRS and self.strict_owner_value_court_verified

    def validate(self) -> "OwnerValueState":
        if self.observed_pair_count < 0:
            raise ValueError("OWNER_VALUE_PAIR_COUNT_NONNEGATIVE_REQUIRED")
        if self.strict_owner_value_court_verified and self.observed_pair_count < MINIMUM_OWNER_VALUE_PAIRS:
            raise ValueError("OWNER_VALUE_COURT_SUBMINIMUM_COHORT_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ReconciliationAction:
    priority: int
    kind: ActionKind
    target_id: str
    reason: str
    expected_state: str
    proof_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "kind": self.kind.value,
            "target_id": self.target_id,
            "reason": self.reason,
            "expected_state": self.expected_state,
            "proof_refs": list(self.proof_refs),
        }


@dataclass(frozen=True, slots=True)
class CoherenceMetrics:
    total_surfaces: int
    current_surfaces: int
    drifted_surfaces: int
    stale_surfaces: int
    historical_surfaces: int
    superseded_surfaces: int
    unknown_surfaces: int
    stale_prs_to_restack: int
    prs_to_close: int
    prs_on_hold: int
    owner_value_pair_deficit: int
    current_source_convergence_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ClosureReceipt:
    schema: str
    generation: int
    source_main_sha: str
    observed_at_sast: str
    actions: tuple[ReconciliationAction, ...]
    metrics: CoherenceMetrics
    pr_dispositions: tuple[tuple[int, PRDisposition], ...]
    capability_decisions: tuple[tuple[str, CapabilityDecision], ...]
    owner_value_proven: bool
    stable_promotion_authorized: bool
    provider_effect_authorized: bool
    external_effect: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "generation": self.generation,
            "source_main_sha": self.source_main_sha,
            "observed_at_sast": self.observed_at_sast,
            "actions": [item.to_dict() for item in self.actions],
            "metrics": self.metrics.to_dict(),
            "pr_dispositions": [{"pr_number": n, "disposition": d.value} for n, d in self.pr_dispositions],
            "capability_decisions": [{"proposal_id": p, "decision": d.value} for p, d in self.capability_decisions],
            "owner_value_proven": self.owner_value_proven,
            "stable_promotion_authorized": self.stable_promotion_authorized,
            "provider_effect_authorized": self.provider_effect_authorized,
            "external_effect": self.external_effect,
            "truth_boundary": list(self.truth_boundary),
        }
        if include_hash:
            payload["receipt_sha256"] = self.receipt_sha256
        return payload


def classify_surface(surface: SurfaceObservation, *, current_main_sha: str, now_sast: str) -> ProjectionState:
    surface.validate()
    if not _is_sha(current_main_sha):
        raise ValueError("CURRENT_MAIN_SHA_REQUIRED")
    now = _parse_timestamp(now_sast)
    observed = _parse_timestamp(surface.observed_at_sast)
    if surface.superseded_by:
        return ProjectionState.SUPERSEDED
    if surface.intentionally_historical:
        return ProjectionState.HISTORICAL
    if max(0.0, (now - observed).total_seconds()) > surface.ttl_seconds:
        return ProjectionState.STALE
    if surface.requires_current_source:
        if surface.observed_source_sha is None:
            return ProjectionState.UNKNOWN
        if surface.observed_source_sha != current_main_sha:
            return ProjectionState.DRIFTED
    return ProjectionState.CURRENT


def classify_pr(item: PullRequestObservation, *, restack_threshold_commits: int = DEFAULT_RESTACK_THRESHOLD_COMMITS, close_threshold_commits: int = DEFAULT_CLOSE_THRESHOLD_COMMITS) -> PRDisposition:
    item.validate()
    if restack_threshold_commits <= 0 or close_threshold_commits < restack_threshold_commits:
        raise ValueError("PR_DISPOSITION_THRESHOLDS_INVALID")
    if item.superseded_by_pr is not None or item.semantic_duplicate:
        return PRDisposition.CLOSE
    if item.provider_or_effect_gate_open:
        return PRDisposition.HOLD
    if not item.unique_capability and item.commits_behind_main >= close_threshold_commits:
        return PRDisposition.CLOSE
    if item.commits_behind_main >= restack_threshold_commits:
        return PRDisposition.RESTACK if item.unique_capability else PRDisposition.CLOSE
    return PRDisposition.KEEP


def decide_capability(item: CapabilityProposal, *, owner_value: OwnerValueState) -> CapabilityDecision:
    item.validate()
    owner_value.validate()
    if item.existing_capability_coverage >= 0.80:
        return CapabilityDecision.REUSE
    if not item.measurable_owner_value_hypothesis:
        return CapabilityDecision.HOLD
    if item.existing_capability_coverage >= 0.50:
        return CapabilityDecision.EXTEND
    if item.composable_existing_capabilities >= 2:
        return CapabilityDecision.MERGE
    if item.existing_capability_coverage > 0:
        return CapabilityDecision.SPECIALISE
    if item.architectural_need_for_new_top_level_system and owner_value.proven:
        return CapabilityDecision.NEW
    return CapabilityDecision.HOLD


def reconcile_estate(*, generation: int, previous_generation: int, source_main_sha: str, observed_at_sast: str, surfaces: Sequence[Mapping[str, Any]] = (), pull_requests: Sequence[Mapping[str, Any]] = (), capability_proposals: Sequence[Mapping[str, Any]] = (), owner_value_state: Mapping[str, Any] | None = None) -> ClosureReceipt:
    if generation <= previous_generation:
        raise ValueError("RECONCILIATION_GENERATION_FENCE_REJECTED")
    if not _is_sha(source_main_sha):
        raise ValueError("RECONCILIATION_CURRENT_MAIN_SHA_INVALID")
    _parse_timestamp(observed_at_sast)

    owner_value = OwnerValueState.from_mapping(owner_value_state).validate()
    surface_items = tuple(SurfaceObservation.from_mapping(x).validate() for x in surfaces)
    pr_items = tuple(PullRequestObservation.from_mapping(x).validate() for x in pull_requests)
    proposal_items = tuple(CapabilityProposal.from_mapping(x).validate() for x in capability_proposals)
    surface_states = tuple((x, classify_surface(x, current_main_sha=source_main_sha, now_sast=observed_at_sast)) for x in surface_items)
    pr_states = tuple((x, classify_pr(x)) for x in pr_items)
    capability_states = tuple((x, decide_capability(x, owner_value=owner_value)) for x in proposal_items)

    actions: list[ReconciliationAction] = []
    for surface, state in surface_states:
        if state in {ProjectionState.DRIFTED, ProjectionState.STALE, ProjectionState.UNKNOWN}:
            actions.append(ReconciliationAction(10, ActionKind.RECONCILE_PROJECTION, surface.surface_id, f"CANONICAL_SURFACE_{state.value}", ProjectionState.CURRENT.value, surface.proof_refs))
        elif state is ProjectionState.HISTORICAL:
            actions.append(ReconciliationAction(30, ActionKind.MARK_HISTORICAL, surface.surface_id, "HISTORICAL_SURFACE_MUST_NOT_DRIVE_PRESENT_TENSE_CLAIMS", state.value, surface.proof_refs))
        elif state is ProjectionState.SUPERSEDED:
            actions.append(ReconciliationAction(20, ActionKind.MARK_SUPERSEDED, surface.surface_id, f"SUPERSEDED_BY_{surface.superseded_by}", state.value, surface.proof_refs))

    for pr, disposition in pr_states:
        target = f"PR-{pr.pr_number}"
        if disposition is PRDisposition.RESTACK:
            actions.append(ReconciliationAction(40, ActionKind.RESTACK_PR, target, "UNIQUE_CAPABILITY_ON_STALE_BASE", "CURRENT_MAIN_RETEST_REQUIRED", pr.proof_refs))
        elif disposition is PRDisposition.CLOSE:
            reason = f"SUPERSEDED_BY_PR_{pr.superseded_by_pr}" if pr.superseded_by_pr else "DUPLICATE_OR_LOW_VALUE_STALE_PR"
            actions.append(ReconciliationAction(50, ActionKind.CLOSE_PR, target, reason, "CLOSED_OR_ARCHIVED", pr.proof_refs))
        elif disposition is PRDisposition.HOLD:
            actions.append(ReconciliationAction(60, ActionKind.HOLD_PR, target, "PROVIDER_OR_EFFECT_GATE_OPEN", "HOLD_NO_PROMOTION", pr.proof_refs))

    action_by_decision = {
        CapabilityDecision.REUSE: ActionKind.REUSE_CAPABILITY,
        CapabilityDecision.EXTEND: ActionKind.EXTEND_CAPABILITY,
        CapabilityDecision.SPECIALISE: ActionKind.SPECIALISE_CAPABILITY,
        CapabilityDecision.MERGE: ActionKind.MERGE_CAPABILITY,
        CapabilityDecision.NEW: ActionKind.ADMIT_NEW_CAPABILITY,
        CapabilityDecision.HOLD: ActionKind.HOLD_NEW_CAPABILITY,
    }
    for proposal, decision in capability_states:
        actions.append(ReconciliationAction(25 if decision is CapabilityDecision.HOLD else 70, action_by_decision[decision], proposal.proposal_id, f"GAP_{proposal.gap_id}_DECISION_{decision.value}", decision.value, proposal.proof_refs))

    deficit = max(0, MINIMUM_OWNER_VALUE_PAIRS - owner_value.observed_pair_count)
    if not owner_value.proven:
        reason = "STRICT_OWNER_VALUE_COURT_REQUIRED" if owner_value.observed_pair_count >= MINIMUM_OWNER_VALUE_PAIRS else f"OWNER_VALUE_PAIR_DEFICIT_{deficit}"
        actions.append(ReconciliationAction(15, ActionKind.COLLECT_OWNER_VALUE, "OWNER_VALUE", reason, "MINIMUM_10_MATCHED_PAIRS_PLUS_STRICT_COURT", owner_value.proof_refs))

    counts = {state: 0 for state in ProjectionState}
    for _, state in surface_states:
        counts[state] += 1
    ratio = counts[ProjectionState.CURRENT] / len(surface_items) if surface_items else 1.0
    metrics = CoherenceMetrics(
        total_surfaces=len(surface_items),
        current_surfaces=counts[ProjectionState.CURRENT],
        drifted_surfaces=counts[ProjectionState.DRIFTED],
        stale_surfaces=counts[ProjectionState.STALE],
        historical_surfaces=counts[ProjectionState.HISTORICAL],
        superseded_surfaces=counts[ProjectionState.SUPERSEDED],
        unknown_surfaces=counts[ProjectionState.UNKNOWN],
        stale_prs_to_restack=sum(1 for _, d in pr_states if d is PRDisposition.RESTACK),
        prs_to_close=sum(1 for _, d in pr_states if d is PRDisposition.CLOSE),
        prs_on_hold=sum(1 for _, d in pr_states if d is PRDisposition.HOLD),
        owner_value_pair_deficit=deficit,
        current_source_convergence_ratio=round(ratio, 6),
    )
    sorted_actions = tuple(sorted(actions, key=lambda x: (x.priority, x.kind.value, x.target_id)))
    truth_boundary = (
        "This controller emits reconciliation plans and receipts only.",
        "A current source SHA does not prove provider deployment or external effect.",
        "Historical evidence remains append-only and is never overwritten to manufacture currentness.",
        "Owner value requires measured matched pairs and strict court verification; feature count is not value.",
        "New top-level systems are last-resort and require a real gap plus strict owner-value proof.",
        "Provider mutation, source merge, communication and stable promotion require separate authority.",
    )
    provisional = ClosureReceipt(
        SCHEMA,
        generation,
        source_main_sha,
        observed_at_sast,
        sorted_actions,
        metrics,
        tuple(sorted(((x.pr_number, d) for x, d in pr_states), key=lambda pair: pair[0])),
        tuple(sorted(((x.proposal_id, d) for x, d in capability_states), key=lambda pair: pair[0])),
        owner_value.proven,
        False,
        False,
        False,
        truth_boundary,
        "",
    )
    digest = canonical_hash(provisional.to_dict(include_hash=False))
    return ClosureReceipt(
        provisional.schema,
        provisional.generation,
        provisional.source_main_sha,
        provisional.observed_at_sast,
        provisional.actions,
        provisional.metrics,
        provisional.pr_dispositions,
        provisional.capability_decisions,
        provisional.owner_value_proven,
        provisional.stable_promotion_authorized,
        provisional.provider_effect_authorized,
        provisional.external_effect,
        provisional.truth_boundary,
        digest,
    )


def benchmark_dimensions() -> tuple[dict[str, Any], ...]:
    rows = (
        ("Desired-state reconciliation", 2, 5, "Kubernetes / Argo CD"),
        ("Freshness and as-of semantics", 3, 5, "Kubernetes / Federation bitemporal controls"),
        ("Self-heal with bounded retry", 3, 5, "Argo CD / Bubbles"),
        ("Catalog ownership and lifecycle", 3, 5, "Backstage"),
        ("Durable checkpoint and replay safety", 4, 5, "Temporal / Bubbles"),
        ("Current-head change safety", 2, 5, "GitHub merge queue"),
        ("PR entropy and supersession", 1, 5, "Backstage lifecycle / GitHub"),
        ("Supply-chain provenance", 4, 5, "SLSA / GitHub attestations"),
        ("Owner-burden measurement", 2, 5, "DORA + existing burden court"),
        ("Strict owner-value promotion gate", 2, 5, "existing owner-value court"),
        ("Cognitive-load minimization", 2, 5, "owner-value objective"),
        ("No-new-system anti-bloat discipline", 4, 5, "CFBE reuse hierarchy"),
    )
    return tuple({"dimension": name, "baseline": baseline, "target": target, "leader_reference": leader} for name, baseline, target, leader in rows)


def benchmark_score(rows: Iterable[Mapping[str, Any]] | None = None) -> dict[str, float]:
    rows = tuple(rows or benchmark_dimensions())
    maximum = 5 * len(rows)
    baseline = sum(float(row["baseline"]) for row in rows)
    target = sum(float(row["target"]) for row in rows)
    return {"baseline_percent": round(100 * baseline / maximum, 2), "target_percent": round(100 * target / maximum, 2)}


def canonical_hash(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")).hexdigest()


def _none_or_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _items(value: Any) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in (value or ()) if str(item).strip())


def _is_sha(value: str) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


def _parse_timestamp(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("TIMESTAMP_REQUIRED")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "ActionKind", "CapabilityDecision", "CapabilityProposal", "ClosureReceipt",
    "CoherenceMetrics", "LEADER_PATTERNS", "OwnerValueState", "PRDisposition",
    "ProjectionState", "PullRequestObservation", "ReconciliationAction", "SCHEMA",
    "SurfaceObservation", "benchmark_dimensions", "benchmark_score", "classify_pr",
    "classify_surface", "decide_capability", "reconcile_estate",
]
