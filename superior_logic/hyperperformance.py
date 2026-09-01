from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .digital_twin import FederationDigitalTwin, RouteCandidate
from .evidence_distillation import EvidenceDistiller, EvidenceReceipt
from .mission_ir import HyperSchedule, MissionCompiler, MissionIR, MissionNode
from .shadow_evolution import PromotionDecision, ShadowEvolutionEngine, TrialScore


@dataclass(frozen=True)
class CounterfactualRoute:
    route: RouteCandidate
    expected_value: float
    expected_regret: float


@dataclass(frozen=True)
class MissionPlan:
    ir: MissionIR
    schedule: HyperSchedule
    routes: tuple[CounterfactualRoute, ...]
    no_action_value: float


class HyperperformanceController:
    """Fan-in control plane for MissionIR, route synthesis, evidence and shadow learning.

    This class intentionally has no provider/tool execution methods. It prepares and
    evaluates plans; external effects remain owned by the existing authority/effect plane.
    """

    def __init__(
        self,
        *,
        twin: FederationDigitalTwin | None = None,
        evolution: ShadowEvolutionEngine | None = None,
    ) -> None:
        self.compiler = MissionCompiler()
        self.twin = twin or FederationDigitalTwin()
        self.evolution = evolution or ShadowEvolutionEngine()
        self.distiller = EvidenceDistiller()

    def plan(
        self,
        *,
        mission_id: str,
        objective: str,
        success_condition: str,
        nodes: Sequence[MissionNode],
        operation: str,
        target_class: str,
        max_parallelism: int = 8,
        max_risk: float = 1.0,
        min_proof_strength: float = 0.0,
        require_reversible: bool = False,
        allowed_authorities: Iterable[str] | None = None,
        no_action_value: float = 0.0,
        authoritative_sources: Iterable[str] = (),
        constraints: Iterable[str] = (),
        terminal_proofs: Iterable[str] = (),
    ) -> MissionPlan:
        ir = self.compiler.compile(
            mission_id=mission_id,
            objective=objective,
            success_condition=success_condition,
            nodes=nodes,
            authoritative_sources=authoritative_sources,
            constraints=constraints,
            terminal_proofs=terminal_proofs,
        )
        schedule = self.compiler.schedule(ir, max_parallelism=max_parallelism)
        routes = self.twin.synthesize(
            operation=operation,
            target_class=target_class,
            max_risk=max_risk,
            min_proof_strength=min_proof_strength,
            require_reversible=require_reversible,
            allowed_authorities=allowed_authorities,
            limit=8,
        )
        counterfactuals = tuple(
            CounterfactualRoute(
                route=route,
                expected_value=route.fitness,
                expected_regret=max(no_action_value - route.fitness, 0.0),
            )
            for route in routes
        )
        return MissionPlan(ir=ir, schedule=schedule, routes=counterfactuals, no_action_value=no_action_value)

    @staticmethod
    def choose(plan: MissionPlan) -> RouteCandidate | None:
        if not plan.routes:
            return None
        best = max(plan.routes, key=lambda row: (row.expected_value, -row.expected_regret, row.route.capability_id))
        if best.expected_value <= plan.no_action_value:
            return None
        return best.route

    def distill_evidence(self, **kwargs) -> EvidenceReceipt:
        return self.distiller.distill(**kwargs)

    def record_shadow_trial(self, trial: TrialScore) -> None:
        self.evolution.record(trial)

    def evaluate_challenger(self, **kwargs) -> PromotionDecision:
        return self.evolution.compare(**kwargs)


__all__ = ["CounterfactualRoute", "HyperperformanceController", "MissionPlan"]
