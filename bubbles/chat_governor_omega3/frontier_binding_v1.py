from __future__ import annotations

"""Load-bearing ChatGov/FUSE frontier binding v1.

This module composes the already-admitted frontier controls behind one subordinate
ChatGov surface.  It does not create a second orchestrator or authority plane.

Only explicitly NO_EFFECT / READ_ONLY work may use the single-flight execution
wrapper.  Every other control here is decision/qualification logic and remains
non-effectful until the existing SOVARA/SOL/provider authority path executes and
proves any external change separately.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Callable

from .frontier_extensions_v1 import (
    CheckpointInterruptLedger,
    ContextMessageRouter,
    CriticalPathJoinPlanner,
    SingleFlightReadCoordinator,
)
from .frontier_runtime_v2 import (
    CausalAblationAnalyzer,
    DependencyResultCache,
    GenerationRolloutGovernor,
    MissionGenerationRouter,
    QueuePressureGovernor,
)
from .frontier_resilience_v3 import (
    ChaosCourtCompiler,
    DeadlineBudgetCompiler,
    GracefulDegradationGovernor,
    PowerOfTwoLoadSelector,
    ProviderOutlierGovernor,
    ShuffleShardPlanner,
)
from .frontier_evolution_v4 import (
    IndependentHarnessGate,
    InterveningChangeReconciler,
    ParetoPolicyOptimizer,
    TrajectoryCrystallizer,
)

SAFE_SINGLEFLIGHT_EFFECTS = frozenset({"NO_EFFECT", "READ_ONLY"})


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class FrontierBindingReceipt:
    schema: str
    version: str
    bound_layers: tuple[str, ...]
    load_bearing_paths: tuple[str, ...]
    effectful_singleflight_forbidden: bool
    provider_effect_authorized: bool
    traffic_change_authorized: bool
    source_promotion_authorized: bool
    skill_promotion_authorized: bool
    receipt_sha256: str


class FrontierControlPlane:
    """One composed home for the admitted frontier controls.

    The class owns reusable control objects, not provider execution authority.  Its
    only execution wrapper is ``execute_safe_read`` and that wrapper rejects every
    effect class except NO_EFFECT and READ_ONLY before calling user code.
    """

    def __init__(
        self,
        *,
        singleflight_ttl_seconds: float = 0.0,
        max_ongoing: int = 8,
        max_queued: int = 64,
        queue_count: int = 32,
        shard_size: int = 4,
    ) -> None:
        self.singleflight = SingleFlightReadCoordinator(
            reuse_ttl_seconds=singleflight_ttl_seconds
        )
        self.context_router = ContextMessageRouter()
        self.join_planner = CriticalPathJoinPlanner()
        self.interrupt_ledger = CheckpointInterruptLedger()

        self.dependency_cache = DependencyResultCache()
        self.queue_pressure = QueuePressureGovernor(
            max_ongoing=max_ongoing,
            max_queued=max_queued,
        )
        self.generation_rollout = GenerationRolloutGovernor()
        self.mission_generation = MissionGenerationRouter()
        self.causal_ablation = CausalAblationAnalyzer()

        self.load_selector = PowerOfTwoLoadSelector()
        self.provider_outliers = ProviderOutlierGovernor()
        self.shuffle_shards = ShuffleShardPlanner(
            queue_count=queue_count,
            shard_size=shard_size,
        )
        self.deadline_budget = DeadlineBudgetCompiler()
        self.graceful_degradation = GracefulDegradationGovernor()
        self.chaos_courts = ChaosCourtCompiler()

        self.trajectory_crystallizer = TrajectoryCrystallizer()
        self.pareto_optimizer = ParetoPolicyOptimizer()
        self.independent_harness = IndependentHarnessGate()
        self.intervening_changes = InterveningChangeReconciler()

    def execute_safe_read(
        self,
        *,
        key: str,
        fn: Callable[[], Any],
        effect_class: str,
    ) -> Any:
        """Execute/coalesce one explicitly safe operation.

        Authority is checked *before* the coordinator is invoked so an effectful
        callback cannot be accidentally hidden behind duplicate suppression.
        """
        effect = str(effect_class).strip().upper()
        if effect not in SAFE_SINGLEFLIGHT_EFFECTS:
            raise ValueError("FRONTIER_SINGLEFLIGHT_EFFECT_CLASS_FORBIDDEN")
        return self.singleflight.run(key, fn, effect_class=effect)

    def receipt(self) -> FrontierBindingReceipt:
        return frontier_binding_receipt()


def frontier_binding_receipt() -> FrontierBindingReceipt:
    body = {
        "schema": "CHATGOV-FRONTIER-BINDING-V1",
        "version": "1.0.0",
        "bound_layers": (
            "FRONTIER_EXTENSIONS_V1",
            "FRONTIER_RUNTIME_V2",
            "FRONTIER_RESILIENCE_V3",
            "FRONTIER_EVOLUTION_V4",
        ),
        "load_bearing_paths": (
            "CONNECTOR_GATEWAY_EXPLICIT_SAFE_READ_SINGLEFLIGHT",
            "EXPORTED_FRONTIER_CONTROL_PLANE",
        ),
        "effectful_singleflight_forbidden": True,
        "provider_effect_authorized": False,
        "traffic_change_authorized": False,
        "source_promotion_authorized": False,
        "skill_promotion_authorized": False,
    }
    return FrontierBindingReceipt(**body, receipt_sha256=_digest(body))


__all__ = [
    "FrontierBindingReceipt",
    "FrontierControlPlane",
    "SAFE_SINGLEFLIGHT_EFFECTS",
    "frontier_binding_receipt",
]
