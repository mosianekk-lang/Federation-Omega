from __future__ import annotations

"""Hypercube Bottleneck Resolver v1.

A deterministic, no-effect constraint-to-commercial-advantage compiler.

The resolver does not stop at identifying a bottleneck.  It:
1. scores the constraint against system throughput and owner/commercial value;
2. harvests reusable internal mechanisms;
3. harvests clean-room market mechanisms (not vendor code);
4. composes cross-market alternatives;
5. invents residual algorithms when reuse/composition is insufficient;
6. ranks a diverse Pareto-style route portfolio;
7. emits an executable improvement plan and commercial-product opportunity.

External effects, repository writes, deployments, provider authority, credentials,
billing authority and stable self-promotion remain outside this module.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from itertools import combinations
import json
from typing import Iterable, Mapping, Sequence


SCHEMA = "FUSE-HYPERCUBE-BOTTLENECK-RESOLVER-V1"
VERSION = "1.0.0"
AUTHORITY_CEILING = "A1_INTERNAL"


class BottleneckKind(str, Enum):
    SERIAL_DEPENDENCY = "SERIAL_DEPENDENCY"
    CI_FEEDBACK = "CI_FEEDBACK"
    QUEUE_CAPACITY = "QUEUE_CAPACITY"
    PROOF_EVIDENCE = "PROOF_EVIDENCE"
    PROVIDER_RUNTIME = "PROVIDER_RUNTIME"
    AUTHORITY = "AUTHORITY"
    MANUAL_OWNER_BURDEN = "MANUAL_OWNER_BURDEN"
    ARCHITECTURAL_DUPLICATION = "ARCHITECTURAL_DUPLICATION"
    COST_RESOURCE = "COST_RESOURCE"
    EXTERNAL_BOUNDARY = "EXTERNAL_BOUNDARY"
    UNKNOWN = "UNKNOWN"


class RouteFamily(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    COMPOSE = "COMPOSE"
    REPURPOSE = "REPURPOSE"
    BUILD_RESIDUAL = "BUILD_RESIDUAL"
    MARKET_COMPOSITE = "MARKET_COMPOSITE"
    INVENT_ALGORITHM = "INVENT_ALGORITHM"
    RETIRE_REDUNDANCY = "RETIRE_REDUNDANCY"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class MarketPattern:
    pattern_id: str
    source_family: str
    mechanism: str
    tags: tuple[str, ...]
    commercial_effect: tuple[str, ...]
    clean_room_only: bool = True


MARKET_PATTERNS: tuple[MarketPattern, ...] = (
    MarketPattern(
        "STACK_AWARE_MERGE_QUEUE",
        "GitHub + Graphite",
        "Bottom-up stack admission, cascading rebase, queue-aware ordered merge, parallel validation and batching.",
        ("stack", "serial", "merge", "ci", "dependency"),
        ("lower merge latency", "less rebase toil", "higher trunk stability"),
    ),
    MarketPattern(
        "DYNAMIC_PIPELINE_COMPILATION",
        "Buildkite",
        "Generate execution steps at runtime from current evidence, route work to fitting queues, and replace pending work when conditions change.",
        ("ci", "queue", "dynamic", "routing", "parallel"),
        ("adaptive pipelines", "lower idle time", "resource-fit execution"),
    ),
    MarketPattern(
        "REMOTE_CACHE_EXECUTION_DEDUP",
        "Bazel + BuildBuddy",
        "Content-addressed action caching, remote execution, warm workers, duplicate-action merging and horizontal executor scaling.",
        ("ci", "cache", "latency", "compute", "dedup", "parallel"),
        ("shorter build latency", "lower compute cost", "elastic execution"),
    ),
    MarketPattern(
        "DURABLE_WORKFLOW_REPLAY",
        "Temporal",
        "Persist workflow state so execution resumes from durable history after process, network or infrastructure failure.",
        ("runtime", "recovery", "durable", "retry", "continuity"),
        ("crash-resilient workflows", "lower recovery burden", "long-running automation"),
    ),
    MarketPattern(
        "TEST_IMPACT_SELECTION",
        "Modern CI / test-intelligence systems",
        "Select the smallest proof/test set implied by the changed dependency graph while preserving fallback-to-full safety.",
        ("ci", "test", "proof", "latency", "dependency"),
        ("faster feedback", "lower CI spend", "targeted assurance"),
    ),
    MarketPattern(
        "TELEMETRY_CORRELATION",
        "OpenTelemetry",
        "Correlate traces, metrics and logs through consistent context so bottlenecks can be localized across distributed stages.",
        ("observability", "proof", "runtime", "latency", "unknown"),
        ("bottleneck observability", "faster diagnosis", "vendor-neutral telemetry"),
    ),
    MarketPattern(
        "THROUGHPUT_INSTABILITY_SCORECARD",
        "DORA",
        "Measure lead time, deployment throughput, failed-deployment recovery, change failure and rework to optimize system outcomes rather than local speed.",
        ("commercial", "delivery", "quality", "latency", "reliability"),
        ("outcome-level optimization", "commercial delivery telemetry", "quality-speed balance"),
    ),
    MarketPattern(
        "CONCURRENCY_GROUP_ROUTING",
        "Buildkite-style queue control",
        "Protect shared resources with explicit concurrency groups while allowing independent lanes to execute in parallel.",
        ("queue", "parallel", "resource", "shared_state", "ci"),
        ("higher safe parallelism", "lower collision rate", "predictable queueing"),
    ),
    MarketPattern(
        "SPECULATIVE_PARALLEL_VALIDATION",
        "Stack-aware CI systems",
        "Validate likely future stack states concurrently, retaining exact-head proof before promotion.",
        ("stack", "ci", "parallel", "speculative", "dependency"),
        ("lower serial waiting", "faster stacked delivery", "unchanged admission rigor"),
    ),
    MarketPattern(
        "SHADOW_CHAMPION_CHALLENGER",
        "Modern experimentation platforms",
        "Run reversible challenger routes against a frozen acceptance oracle; promote only measured non-regression and positive value.",
        ("experiment", "market", "quality", "risk", "unknown"),
        ("continuous improvement", "measured differentiation", "safe innovation"),
    ),
)


@dataclass(frozen=True, slots=True)
class BottleneckSignal:
    bottleneck_id: str
    kind: BottleneckKind
    summary: str
    evidence_refs: tuple[str, ...]
    throughput_drag: float
    latency_share: float
    queue_wait_share: float
    failure_recurrence: float
    dependency_centrality: float
    owner_burden: float
    cost_pressure: float
    proof_gap: float
    risk: float
    commercial_leverage: float
    differentiation_potential: float
    internal_coverage: float
    external_boundary: bool = False
    affected_missions: int = 1
    internal_capabilities: tuple[str, ...] = ()

    def validate(self) -> "BottleneckSignal":
        if not self.bottleneck_id.strip():
            raise ValueError("HYPERCUBE_BOTTLENECK_ID_REQUIRED")
        if not self.summary.strip():
            raise ValueError("HYPERCUBE_BOTTLENECK_SUMMARY_REQUIRED")
        if not self.evidence_refs:
            raise ValueError("HYPERCUBE_BOTTLENECK_EVIDENCE_REQUIRED")
        for name in (
            "throughput_drag",
            "latency_share",
            "queue_wait_share",
            "failure_recurrence",
            "dependency_centrality",
            "owner_burden",
            "cost_pressure",
            "proof_gap",
            "risk",
            "commercial_leverage",
            "differentiation_potential",
            "internal_coverage",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"HYPERCUBE_{name.upper()}_OUT_OF_RANGE")
        if self.affected_missions < 1:
            raise ValueError("HYPERCUBE_AFFECTED_MISSIONS_POSITIVE")
        return self


@dataclass(frozen=True, slots=True)
class ResolutionCandidate:
    candidate_id: str
    family: RouteFamily
    name: str
    mechanism_ids: tuple[str, ...]
    internal_capabilities: tuple[str, ...]
    expected_relief: float
    throughput_gain: float
    latency_gain: float
    quality_gain: float
    reliability_gain: float
    commercial_gain: float
    differentiation_gain: float
    evidence_gain: float
    reversibility: float
    novelty: float
    implementation_cost: float
    time_to_value: float
    risk: float
    owner_burden: float
    score: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BottleneckResolution:
    schema: str
    version: str
    bottleneck_id: str
    bottleneck_score: float
    action_state: str
    selected: ResolutionCandidate
    portfolio: tuple[ResolutionCandidate, ...]
    product_features: tuple[str, ...]
    commercial_product_score: float
    system_upgrade_candidate: bool
    next_actions: tuple[str, ...]
    market_harvest: tuple[str, ...]
    internal_harvest: tuple[str, ...]
    invention_required: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    receipt_sha256: str


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bottleneck_score(signal: BottleneckSignal) -> float:
    impact = (
        0.21 * signal.throughput_drag
        + 0.15 * signal.latency_share
        + 0.10 * signal.queue_wait_share
        + 0.12 * signal.failure_recurrence
        + 0.13 * signal.dependency_centrality
        + 0.10 * signal.owner_burden
        + 0.07 * signal.cost_pressure
        + 0.12 * signal.proof_gap
    )
    leverage = (
        0.55
        + 0.20 * signal.commercial_leverage
        + 0.15 * signal.differentiation_potential
        + 0.10 * min(signal.affected_missions / 5.0, 1.0)
    )
    return round(_clip(impact * leverage), 9)


_KIND_TAGS: Mapping[BottleneckKind, tuple[str, ...]] = {
    BottleneckKind.SERIAL_DEPENDENCY: ("stack", "serial", "merge", "dependency", "parallel"),
    BottleneckKind.CI_FEEDBACK: ("ci", "cache", "test", "latency", "parallel"),
    BottleneckKind.QUEUE_CAPACITY: ("queue", "parallel", "resource", "dynamic"),
    BottleneckKind.PROOF_EVIDENCE: ("proof", "test", "observability", "dependency"),
    BottleneckKind.PROVIDER_RUNTIME: ("runtime", "durable", "observability", "recovery"),
    BottleneckKind.AUTHORITY: ("runtime", "risk", "dependency"),
    BottleneckKind.MANUAL_OWNER_BURDEN: ("dynamic", "durable", "observability", "parallel"),
    BottleneckKind.ARCHITECTURAL_DUPLICATION: ("dedup", "cache", "dependency", "quality"),
    BottleneckKind.COST_RESOURCE: ("compute", "cache", "queue", "resource"),
    BottleneckKind.EXTERNAL_BOUNDARY: ("runtime", "durable", "experiment", "observability"),
    BottleneckKind.UNKNOWN: ("unknown", "observability", "experiment", "quality"),
}


def _relevance(signal: BottleneckSignal, pattern: MarketPattern) -> float:
    wanted = set(_KIND_TAGS[signal.kind])
    overlap = len(wanted.intersection(pattern.tags))
    if not wanted:
        return 0.0
    return overlap / len(wanted)


def _candidate_score(candidate: Mapping[str, float]) -> float:
    benefit = (
        0.20 * candidate["expected_relief"]
        + 0.13 * candidate["throughput_gain"]
        + 0.10 * candidate["latency_gain"]
        + 0.10 * candidate["quality_gain"]
        + 0.10 * candidate["reliability_gain"]
        + 0.12 * candidate["commercial_gain"]
        + 0.10 * candidate["differentiation_gain"]
        + 0.07 * candidate["evidence_gain"]
        + 0.05 * candidate["reversibility"]
        + 0.03 * candidate["novelty"]
    )
    penalty = (
        0.34 * candidate["implementation_cost"]
        + 0.24 * candidate["time_to_value"]
        + 0.26 * candidate["risk"]
        + 0.16 * candidate["owner_burden"]
    )
    return round(_clip(benefit - 0.55 * penalty), 9)


def _make_candidate(
    signal: BottleneckSignal,
    *,
    family: RouteFamily,
    name: str,
    patterns: Sequence[MarketPattern],
    internal: Iterable[str] = (),
    innovation_bonus: float = 0.0,
    cost_bias: float = 0.0,
    risk_bias: float = 0.0,
) -> ResolutionCandidate:
    rel = max((_relevance(signal, item) for item in patterns), default=0.25)
    diversity = min(len({tag for item in patterns for tag in item.tags}) / 12.0, 1.0)
    internal_tuple = tuple(sorted({str(item) for item in internal if str(item)}))
    reuse = min(signal.internal_coverage + 0.08 * len(internal_tuple), 1.0)
    expected_relief = _clip(0.38 + 0.42 * rel + 0.20 * signal.throughput_drag + innovation_bonus)
    throughput_gain = _clip(0.20 + 0.48 * signal.throughput_drag + 0.22 * rel + innovation_bonus)
    latency_gain = _clip(0.16 + 0.48 * signal.latency_share + 0.20 * rel + innovation_bonus)
    quality_gain = _clip(0.18 + 0.34 * signal.proof_gap + 0.20 * diversity + 0.10 * signal.failure_recurrence)
    reliability_gain = _clip(0.18 + 0.36 * signal.failure_recurrence + 0.22 * diversity + 0.08 * rel)
    commercial_gain = _clip(
        0.18 + 0.45 * signal.commercial_leverage + 0.18 * expected_relief + 0.12 * diversity + innovation_bonus
    )
    differentiation_gain = _clip(
        0.12 + 0.50 * signal.differentiation_potential + 0.18 * diversity + innovation_bonus
    )
    evidence_gain = _clip(0.18 + 0.50 * signal.proof_gap + 0.16 * diversity)
    reversibility = _clip(0.88 - 0.24 * signal.risk - 0.15 * risk_bias)
    novelty = _clip(
        0.18
        + 0.15 * len(patterns)
        + 0.28 * signal.differentiation_potential
        + innovation_bonus
    )
    implementation_cost = _clip(
        0.14
        + 0.18 * len(patterns)
        + 0.30 * (1.0 - reuse)
        + cost_bias
    )
    time_to_value = _clip(
        0.12 + 0.18 * len(patterns) + 0.24 * (1.0 - reuse) + 0.12 * signal.external_boundary
    )
    risk = _clip(0.10 + 0.34 * signal.risk + 0.12 * len(patterns) + risk_bias)
    owner_burden = _clip(0.08 + 0.20 * implementation_cost - 0.20 * signal.owner_burden)
    values = {
        "expected_relief": expected_relief,
        "throughput_gain": throughput_gain,
        "latency_gain": latency_gain,
        "quality_gain": quality_gain,
        "reliability_gain": reliability_gain,
        "commercial_gain": commercial_gain,
        "differentiation_gain": differentiation_gain,
        "evidence_gain": evidence_gain,
        "reversibility": reversibility,
        "novelty": novelty,
        "implementation_cost": implementation_cost,
        "time_to_value": time_to_value,
        "risk": risk,
        "owner_burden": owner_burden,
    }
    score = _candidate_score(values)
    reasons = ["BOTTLENECK_RELIEF", "PROOF_BEFORE_PROMOTION", "COMMERCIAL_UPLIFT_SCORING"]
    if len(patterns) > 1:
        reasons.append("CROSS_MARKET_COMPOSITION")
    if internal_tuple:
        reasons.append("INTERNAL_CAPABILITY_REUSE")
    if family is RouteFamily.INVENT_ALGORITHM:
        reasons.extend(("RESIDUAL_GAP_REQUIRES_INVENTION", "CLEAN_ROOM_MECHANISM_SYNTHESIS"))
    if signal.external_boundary:
        reasons.append("EXTERNAL_BOUNDARY_PRESERVED")
    return ResolutionCandidate(
        candidate_id="HBR-" + _hash(
            {
                "bottleneck": signal.bottleneck_id,
                "family": family.value,
                "name": name,
                "patterns": [p.pattern_id for p in patterns],
                "internal": internal_tuple,
            }
        )[:18].upper(),
        family=family,
        name=name,
        mechanism_ids=tuple(p.pattern_id for p in patterns),
        internal_capabilities=internal_tuple,
        score=score,
        reason_codes=tuple(reasons),
        **{k: round(v, 9) for k, v in values.items()},
    )


def _dominates(left: ResolutionCandidate, right: ResolutionCandidate) -> bool:
    benefits = (
        "expected_relief",
        "throughput_gain",
        "latency_gain",
        "quality_gain",
        "reliability_gain",
        "commercial_gain",
        "differentiation_gain",
        "evidence_gain",
        "reversibility",
        "novelty",
    )
    penalties = ("implementation_cost", "time_to_value", "risk", "owner_burden")
    no_worse = all(getattr(left, name) >= getattr(right, name) for name in benefits) and all(
        getattr(left, name) <= getattr(right, name) for name in penalties
    )
    strictly_better = any(getattr(left, name) > getattr(right, name) for name in benefits) or any(
        getattr(left, name) < getattr(right, name) for name in penalties
    )
    return bool(no_worse and strictly_better)


def _pareto_front(candidates: Sequence[ResolutionCandidate]) -> tuple[ResolutionCandidate, ...]:
    front = []
    for candidate in candidates:
        if any(
            other.candidate_id != candidate.candidate_id and _dominates(other, candidate)
            for other in candidates
        ):
            continue
        front.append(candidate)
    return tuple(sorted(front, key=lambda item: (-item.score, item.candidate_id)))


def _feature_set(signal: BottleneckSignal, selected: ResolutionCandidate) -> tuple[str, ...]:
    features = {
        "Always-on bottleneck radar",
        "Evidence-bound bottleneck diagnosis",
        "Automatic alternative-route harvest",
        "Commercial-uplift-aware route ranking",
        "Shadow benchmark before promotion",
        "Bottleneck-to-learning flywheel",
    }
    tags = {tag for pattern in MARKET_PATTERNS if pattern.pattern_id in selected.mechanism_ids for tag in pattern.tags}
    if "stack" in tags:
        features.add("Stack-aware convergence queue")
    if "cache" in tags:
        features.add("Content-addressed work reuse and duplicate suppression")
    if "parallel" in tags:
        features.add("Adaptive safe parallelism")
    if "durable" in tags:
        features.add("Crash-resilient mission continuation")
    if "observability" in tags:
        features.add("Cross-stage trace/metric/log correlation")
    if "test" in tags or signal.kind is BottleneckKind.PROOF_EVIDENCE:
        features.add("Change-impact proof selection")
    if selected.family in {RouteFamily.MARKET_COMPOSITE, RouteFamily.INVENT_ALGORITHM}:
        features.add("Provider-neutral composite optimization")
    if signal.external_boundary:
        features.add("External-boundary-aware graceful degradation")
    return tuple(sorted(features))


class HypercubeBottleneckResolver:
    """Detect, harvest, compose, invent and rank bottleneck-removal routes."""

    def resolve(self, signal: BottleneckSignal) -> BottleneckResolution:
        signal = signal.validate()
        bottleneck_score = _bottleneck_score(signal)
        relevant = sorted(
            MARKET_PATTERNS,
            key=lambda item: (-_relevance(signal, item), item.pattern_id),
        )
        relevant = tuple(item for item in relevant if _relevance(signal, item) > 0)[:6]
        if not relevant:
            relevant = (next(item for item in MARKET_PATTERNS if item.pattern_id == "SHADOW_CHAMPION_CHALLENGER"),)

        internal = tuple(sorted(set(signal.internal_capabilities)))
        candidates: list[ResolutionCandidate] = []

        if internal:
            candidates.append(
                _make_candidate(
                    signal,
                    family=RouteFamily.REUSE if signal.internal_coverage >= 0.65 else RouteFamily.EXTEND,
                    name="Internal estate first-route repair",
                    patterns=(relevant[0],),
                    internal=internal,
                    cost_bias=-0.08,
                    risk_bias=-0.04,
                )
            )

        for pattern in relevant[:4]:
            candidates.append(
                _make_candidate(
                    signal,
                    family=RouteFamily.REPURPOSE,
                    name=f"Repurpose {pattern.pattern_id}",
                    patterns=(pattern,),
                    internal=internal[:3],
                )
            )

        for left, right in list(combinations(relevant[:5], 2))[:6]:
            candidates.append(
                _make_candidate(
                    signal,
                    family=RouteFamily.MARKET_COMPOSITE,
                    name=f"Composite {left.pattern_id} + {right.pattern_id}",
                    patterns=(left, right),
                    internal=internal[:4],
                    innovation_bonus=0.05,
                    cost_bias=0.04,
                )
            )

        if len(relevant) >= 3:
            candidates.append(
                _make_candidate(
                    signal,
                    family=RouteFamily.INVENT_ALGORITHM,
                    name="Hypercube residual algorithm synthesis",
                    patterns=relevant[:3],
                    internal=internal[:5],
                    innovation_bonus=0.12,
                    cost_bias=0.08,
                    risk_bias=0.04,
                )
            )

        if signal.kind is BottleneckKind.ARCHITECTURAL_DUPLICATION:
            candidates.append(
                _make_candidate(
                    signal,
                    family=RouteFamily.RETIRE_REDUNDANCY,
                    name="Retire duplicate control path and converge on stable contract",
                    patterns=tuple(item for item in relevant if "dedup" in item.tags)[:2] or relevant[:1],
                    internal=internal,
                    cost_bias=-0.05,
                    risk_bias=-0.02,
                )
            )

        # Deduplicate exact candidate IDs, then keep a Pareto-efficient frontier
        # before score ranking.  Dominated "faster but worse everywhere" routes cannot
        # crowd out commercially stronger alternatives.
        unique = {candidate.candidate_id: candidate for candidate in candidates}
        pareto = _pareto_front(tuple(unique.values()))
        ranked = list(pareto or tuple(sorted(unique.values(), key=lambda item: (-item.score, item.candidate_id))))

        # Diversity court: top portfolio should not be one mechanism family only.
        portfolio: list[ResolutionCandidate] = []
        seen_families: set[RouteFamily] = set()
        for candidate in ranked:
            if len(portfolio) >= 6:
                break
            if candidate.family not in seen_families or len(portfolio) >= 3:
                portfolio.append(candidate)
                seen_families.add(candidate.family)
        if not portfolio:
            raise ValueError("HYPERCUBE_NO_RESOLUTION_CANDIDATE")

        # Severe / weakly covered constraints always retain a clean-room invention
        # challenger even when a simpler candidate currently ranks first.
        force_invention = bottleneck_score >= 0.65 or signal.internal_coverage < 0.30
        invention = next(
            (item for item in ranked if item.family is RouteFamily.INVENT_ALGORITHM),
            None,
        )
        if force_invention and invention is not None and all(
            item.candidate_id != invention.candidate_id for item in portfolio
        ):
            if len(portfolio) >= 6:
                portfolio[-1] = invention
            else:
                portfolio.append(invention)
            portfolio.sort(key=lambda item: (-item.score, item.candidate_id))

        selected = portfolio[0]
        invention_required = bool(
            selected.family is RouteFamily.INVENT_ALGORITHM
            or (
                bottleneck_score >= 0.65
                and max(item.score for item in portfolio if item.family is not RouteFamily.INVENT_ALGORITHM) < 0.45
            )
        )

        product_features = _feature_set(signal, selected)
        commercial_product_score = round(
            _clip(
                0.35 * selected.commercial_gain
                + 0.25 * selected.differentiation_gain
                + 0.15 * selected.reliability_gain
                + 0.10 * selected.quality_gain
                + 0.10 * (1.0 - selected.owner_burden)
                + 0.05 * selected.evidence_gain
            ),
            9,
        )
        system_upgrade_candidate = bool(
            signal.failure_recurrence >= 0.45
            or signal.affected_missions >= 2
            or commercial_product_score >= 0.62
        )

        next_actions = (
            "CAPTURE_BASELINE_THROUGHPUT_LATENCY_FAILURE_COST_OWNER_BURDEN",
            "RUN_TOP_DIVERSE_ROUTES_IN_SHADOW_OR_DETERMINISTIC_COURT",
            "COMPARE_AGAINST_FROZEN_ACCEPTANCE_AND_COMMERCIAL_VALUE_ORACLE",
            "PROMOTE_ONLY_NONREGRESSIVE_POSITIVE_VALUE_ROUTE",
            "REGISTER_RECURRING_BOTTLENECK_AS_REUSABLE_CAPABILITY_OR_PRODUCT_FEATURE",
            "REMEASURE_AND_REPEAT_UNTIL_BOTTLENECK_NO_LONGER_DOMINATES",
        )
        body = {
            "schema": SCHEMA,
            "version": VERSION,
            "bottleneck_id": signal.bottleneck_id,
            "bottleneck_score": bottleneck_score,
            "action_state": "RESOLUTION_READY",
            "selected": asdict(selected),
            "portfolio": [asdict(item) for item in portfolio],
            "product_features": list(product_features),
            "commercial_product_score": commercial_product_score,
            "system_upgrade_candidate": system_upgrade_candidate,
            "next_actions": list(next_actions),
            "market_harvest": [item.pattern_id for item in relevant],
            "internal_harvest": list(internal),
            "invention_required": invention_required,
            "external_effect_authorized": False,
            "stable_self_promotion_allowed": False,
        }
        return BottleneckResolution(
            schema=SCHEMA,
            version=VERSION,
            bottleneck_id=signal.bottleneck_id,
            bottleneck_score=bottleneck_score,
            action_state="RESOLUTION_READY",
            selected=selected,
            portfolio=tuple(portfolio),
            product_features=product_features,
            commercial_product_score=commercial_product_score,
            system_upgrade_candidate=system_upgrade_candidate,
            next_actions=next_actions,
            market_harvest=tuple(item.pattern_id for item in relevant),
            internal_harvest=internal,
            invention_required=invention_required,
            external_effect_authorized=False,
            stable_self_promotion_allowed=False,
            receipt_sha256=_hash(body),
        )

    def resolve_many(self, signals: Sequence[BottleneckSignal]) -> tuple[BottleneckResolution, ...]:
        results = tuple(self.resolve(item) for item in signals)
        return tuple(
            sorted(
                results,
                key=lambda item: (
                    -item.bottleneck_score,
                    -item.commercial_product_score,
                    item.bottleneck_id,
                ),
            )
        )


__all__ = [
    "AUTHORITY_CEILING",
    "BottleneckKind",
    "BottleneckResolution",
    "BottleneckSignal",
    "HypercubeBottleneckResolver",
    "MARKET_PATTERNS",
    "MarketPattern",
    "ResolutionCandidate",
    "RouteFamily",
    "SCHEMA",
    "VERSION",
]
