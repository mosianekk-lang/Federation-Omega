from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from statistics import median
from time import perf_counter_ns
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "CFBE-FIDELITY-COMPOSITE-ROUTER-1"
GOAL_CLASS = "CFBE_FIDELITY_FOUR_SURFACE"
PROOF_THRESHOLD = "SEMANTIC_PROVIDER_READBACK"
SURFACE_ORDER = ("github", "drive", "gmail", "canva")


@dataclass(frozen=True)
class SurfacePolicy:
    surface: str
    route_id: str
    authority_requirement: str
    proof_requirements: tuple[str, ...]
    effect_class: str = "READ_ONLY"
    external_effect_authorized: bool = False


@dataclass(frozen=True)
class GoalEnvelope:
    goal_id: str
    goal_class: str = GOAL_CLASS
    surfaces: tuple[str, ...] = SURFACE_ORDER
    effect_class: str = "READ_ONLY"
    proof_threshold: str = PROOF_THRESHOLD
    stable_promotion_requested: bool = False


@dataclass(frozen=True)
class ResolutionReceipt:
    schema: str
    goal_id: str
    state: str
    mode: str
    bundle_id: str | None
    lanes: tuple[SurfacePolicy, ...]
    rejection_reasons: tuple[str, ...]
    semantic_digest: str
    serving_route_changed: bool = False
    external_effects_authorized: bool = False
    stable_promotion_allowed: bool = False


POLICIES: Mapping[str, SurfacePolicy] = {
    "github": SurfacePolicy(
        surface="github",
        route_id="GITHUB_REPOSITORY_READ",
        authority_requirement="GITHUB_REPOSITORY_READ",
        proof_requirements=("REPOSITORY_ID", "EXACT_COMMIT_SHA", "SOURCE_READBACK"),
    ),
    "drive": SurfacePolicy(
        surface="drive",
        route_id="GOOGLE_DRIVE_READ",
        authority_requirement="GOOGLE_DRIVE_READ",
        proof_requirements=("FILE_ID", "REVISION_ID", "SEMANTIC_READBACK"),
    ),
    "gmail": SurfacePolicy(
        surface="gmail",
        route_id="GMAIL_METADATA_READ",
        authority_requirement="GMAIL_METADATA_READ",
        proof_requirements=("MESSAGE_ID", "THREAD_ID", "PROVIDER_METADATA_READBACK"),
    ),
    "canva": SurfacePolicy(
        surface="canva",
        route_id="CANVA_DESIGN_READ",
        authority_requirement="CANVA_DESIGN_READ",
        proof_requirements=("DESIGN_ID", "DESIGN_TITLE", "PROVIDER_METADATA_READBACK"),
    ),
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalized_surfaces(surfaces: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(item).strip().lower() for item in surfaces)


def _shared_rejections(goal: GoalEnvelope) -> tuple[str, ...]:
    surfaces = _normalized_surfaces(goal.surfaces)
    reasons: list[str] = []
    if goal.goal_class != GOAL_CLASS:
        reasons.append("GOAL_CLASS_NOT_ADMITTED")
    if goal.effect_class != "READ_ONLY":
        reasons.append("EFFECT_CLASS_EXCEEDS_READ_ONLY")
    if goal.proof_threshold != PROOF_THRESHOLD:
        reasons.append("PROOF_THRESHOLD_WEAKENED")
    if goal.stable_promotion_requested:
        reasons.append("STABLE_PROMOTION_NOT_AUTHORIZED")
    if len(set(surfaces)) != len(surfaces):
        reasons.append("DUPLICATE_SURFACE")
    if set(surfaces) != set(SURFACE_ORDER):
        reasons.append("EXACT_FOUR_SURFACE_SET_REQUIRED")
    return tuple(sorted(set(reasons)))


def _proof_payload(goal: GoalEnvelope, lanes: Sequence[SurfacePolicy], state: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "goal_id": goal.goal_id,
        "goal_class": goal.goal_class,
        "state": state,
        "effect_class": goal.effect_class,
        "proof_threshold": goal.proof_threshold,
        "lanes": [asdict(item) for item in lanes],
        "serving_route_changed": False,
        "external_effects_authorized": False,
        "stable_promotion_allowed": False,
    }


def _receipt(
    goal: GoalEnvelope,
    *,
    mode: str,
    reasons: tuple[str, ...],
    lanes: Sequence[SurfacePolicy],
) -> ResolutionReceipt:
    state = "ELIGIBLE_COMPOSITE_BUNDLE" if not reasons else "NO_ELIGIBLE_ROUTE"
    admitted_lanes = tuple(lanes) if not reasons else ()
    return ResolutionReceipt(
        schema=SCHEMA,
        goal_id=goal.goal_id,
        state=state,
        mode=mode,
        bundle_id="CFBE-FIDELITY-READ-BUNDLE-V1" if not reasons else None,
        lanes=admitted_lanes,
        rejection_reasons=reasons,
        semantic_digest=_digest(_proof_payload(goal, admitted_lanes, state)),
    )


def resolve_unified(goal: GoalEnvelope) -> ResolutionReceipt:
    """Resolve the exact four-surface read goal through one composite bundle.

    The bundle composes routing only. Every surface retains an independent
    authority requirement and proof contract, and no provider effect is granted.
    """

    reasons = _shared_rejections(goal)
    lanes = tuple(POLICIES[surface] for surface in SURFACE_ORDER) if not reasons else ()
    return _receipt(goal, mode="UNIFIED_COMPOSITE", reasons=reasons, lanes=lanes)


def _resolve_one_surface(goal: GoalEnvelope, surface: str) -> tuple[SurfacePolicy | None, tuple[str, ...]]:
    # This models the prior decomposed selector: shared gates are re-evaluated
    # for each independently requested surface before the four receipts are joined.
    reasons = _shared_rejections(goal)
    normalized = str(surface).strip().lower()
    if normalized not in POLICIES:
        reasons = (*reasons, "UNKNOWN_SURFACE")
    return (POLICIES.get(normalized) if not reasons else None), tuple(sorted(set(reasons)))


def resolve_decomposed(goal: GoalEnvelope) -> ResolutionReceipt:
    lanes: list[SurfacePolicy] = []
    reasons: list[str] = []
    for surface in SURFACE_ORDER:
        lane, lane_reasons = _resolve_one_surface(goal, surface)
        reasons.extend(lane_reasons)
        if lane is not None:
            lanes.append(lane)
    normalized_reasons = tuple(sorted(set(reasons)))
    return _receipt(
        goal,
        mode="DECOMPOSED_BASELINE",
        reasons=normalized_reasons,
        lanes=tuple(lanes) if not normalized_reasons else (),
    )


def qualification_suite() -> tuple[GoalEnvelope, ...]:
    return (
        GoalEnvelope("VALID-1"),
        GoalEnvelope("VALID-2", surfaces=("canva", "gmail", "drive", "github")),
        GoalEnvelope("INVALID-GOAL", goal_class="GENERAL_MULTI_SURFACE"),
        GoalEnvelope("INVALID-MISSING", surfaces=("github", "drive", "gmail")),
        GoalEnvelope("INVALID-DUPLICATE", surfaces=("github", "drive", "gmail", "gmail", "canva")),
        GoalEnvelope("INVALID-EFFECT", effect_class="BOUNDED_EFFECT"),
        GoalEnvelope("INVALID-PROOF", proof_threshold="STRUCTURAL_ONLY"),
        GoalEnvelope("INVALID-PROMOTION", stable_promotion_requested=True),
    )


def _assert_semantic_parity(goals: Sequence[GoalEnvelope]) -> str:
    parity: list[dict[str, Any]] = []
    for goal in goals:
        unified = resolve_unified(goal)
        decomposed = resolve_decomposed(goal)
        if unified.state != decomposed.state:
            raise AssertionError((goal, unified, decomposed))
        if unified.semantic_digest != decomposed.semantic_digest:
            raise AssertionError((goal, unified.semantic_digest, decomposed.semantic_digest))
        if unified.rejection_reasons != decomposed.rejection_reasons:
            raise AssertionError((goal, unified.rejection_reasons, decomposed.rejection_reasons))
        parity.append(
            {
                "goal_id": goal.goal_id,
                "state": unified.state,
                "semantic_digest": unified.semantic_digest,
                "rejection_reasons": list(unified.rejection_reasons),
            }
        )
    return _digest(parity)


def benchmark_routes(*, rounds: int = 9, iterations: int = 2_000) -> dict[str, Any]:
    if rounds < 3 or iterations < 1:
        raise ValueError("BENCHMARK_SAMPLE_FLOOR_NOT_MET")
    goals = qualification_suite()
    parity_digest = _assert_semantic_parity(goals)
    unified_samples: list[int] = []
    decomposed_samples: list[int] = []
    for round_index in range(rounds):
        ordered = (resolve_unified, resolve_decomposed)
        if round_index % 2:
            ordered = tuple(reversed(ordered))
        measurements: dict[str, int] = {}
        for resolver in ordered:
            started = perf_counter_ns()
            for _ in range(iterations):
                for goal in goals:
                    resolver(goal)
            measurements[resolver.__name__] = perf_counter_ns() - started
        unified_samples.append(measurements["resolve_unified"])
        decomposed_samples.append(measurements["resolve_decomposed"])
    unified_median = int(median(unified_samples))
    decomposed_median = int(median(decomposed_samples))
    factor = decomposed_median / unified_median if unified_median else None
    return {
        "schema": "CFBE-FIDELITY-ROUTER-BENCHMARK-1",
        "state": "CONTROL_PLANE_BENCHMARK_PASS",
        "suite_case_count": len(goals),
        "rounds": rounds,
        "iterations_per_round": iterations,
        "work_units_per_route_per_round": len(goals) * iterations,
        "semantic_parity": True,
        "semantic_parity_digest": parity_digest,
        "unified_median_ns": unified_median,
        "decomposed_median_ns": decomposed_median,
        "decomposed_over_unified_factor": factor,
        "proof_threshold": PROOF_THRESHOLD,
        "provider_tool_calls_measured": False,
        "provider_latency_measured": False,
        "owner_value_measured": False,
        "stable_promotion_allowed": False,
        "truth_boundary": (
            "This is a like-for-like in-process routing-control benchmark with identical semantic "
            "receipts and rejection gates. It does not measure connector latency, provider runtime, "
            "deployment performance, owner burden, or owner value."
        ),
    }


def main() -> int:
    print(json.dumps(benchmark_routes(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
