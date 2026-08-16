from __future__ import annotations

from dataclasses import dataclass, asdict
from math import ceil
from typing import Iterable

from .science_and_routes import FederationDigitalTwin, Scenario


@dataclass(frozen=True)
class HorizonNode:
    step: int
    kind: str
    proposition: str
    probability: float
    consequence: float
    evidence_dependencies: tuple[str, ...] = ()
    fallback: str | None = None


@dataclass(frozen=True)
class HorizonRun:
    engine: str
    profile: str
    objective: str
    adaptive_depth: int
    minimum_depth: int
    nodes: tuple[HorizonNode, ...]
    scenarios: tuple[dict, ...]
    surface_route_failure: bool
    truth_class: str = "SIMULATION_HYPOTHESIS"


class HorizonOmega:
    """Federation-wide adaptive foresight and strategic simulation organ.

    HORIZON-Ω is a generic AO-HARMONIC capability. It has no external authority.
    It extends lookahead according to consequence, uncertainty, dependencies and
    adversarial complexity. The old "10-step" Lex rule is retained as a minimum
    legal profile floor, not a ceiling.
    """

    ENGINE_ID = "HORIZON-OMEGA-V1"
    MIN_CONSEQUENTIAL_DEPTH = 10
    MIN_ROUTINE_DEPTH = 4
    MAX_DEPTH = 64

    def adaptive_depth(
        self,
        *,
        consequential: bool,
        consequence: float = 0.5,
        uncertainty: float = 0.5,
        dependency_density: float = 0.5,
        adversarial_complexity: float = 0.5,
        requested_depth: int | None = None,
    ) -> int:
        floor = self.MIN_CONSEQUENTIAL_DEPTH if consequential else self.MIN_ROUTINE_DEPTH
        weighted = (
            0.35 * max(0.0, min(1.0, consequence))
            + 0.25 * max(0.0, min(1.0, uncertainty))
            + 0.20 * max(0.0, min(1.0, dependency_density))
            + 0.20 * max(0.0, min(1.0, adversarial_complexity))
        )
        adaptive = floor + ceil(weighted * 22)
        if requested_depth is not None:
            adaptive = max(adaptive, requested_depth)
        return min(self.MAX_DEPTH, max(floor, adaptive))

    @staticmethod
    def should_surface_route_failure(
        *,
        objective_exhausted: bool,
        owner_only: bool = False,
        material_strategy_change: bool = False,
    ) -> bool:
        """Route failures remain internal unless they become objective-level."""
        return bool(objective_exhausted or owner_only or material_strategy_change)

    @staticmethod
    def reroute(alternatives: Iterable[dict]) -> dict | None:
        viable = [r for r in alternatives if r.get("available", False) and r.get("authorised", True)]
        if not viable:
            return None
        return max(
            viable,
            key=lambda r: (
                float(r.get("proof_strength", 0.0)),
                float(r.get("reversibility", 0.0)),
                float(r.get("information_gain", 0.0)),
                -float(r.get("owner_burden", 0.0)),
            ),
        )

    def simulate(
        self,
        *,
        objective: str,
        profile: str = "FEDERATION_GENERAL",
        consequential: bool = True,
        consequence: float = 0.8,
        uncertainty: float = 0.6,
        dependency_density: float = 0.6,
        adversarial_complexity: float = 0.6,
        immediate_response: str = "Environment or opponent responds to the selected move",
        strongest_pivot: str = "A less convenient but stronger counter-route is selected",
        decision_maker_response: str = "Decision-maker tests proof, authority, reversibility and consequences",
        evidence_dependencies: Iterable[str] = (),
        cross_lane_risks: Iterable[str] = (),
        fallback: str = "Preserve the strongest reversible route and recompute after new evidence",
        requested_depth: int | None = None,
    ) -> HorizonRun:
        depth = self.adaptive_depth(
            consequential=consequential,
            consequence=consequence,
            uncertainty=uncertainty,
            dependency_density=dependency_density,
            adversarial_complexity=adversarial_complexity,
            requested_depth=requested_depth,
        )
        evidence = tuple(evidence_dependencies)
        cross = ", ".join(cross_lane_risks) or "secondary-order effects"

        base = [
            HorizonNode(1, "OBJECTIVE", objective, 1.0, consequence),
            HorizonNode(2, "GATE", "Verify authority, prerequisites, proof and success condition", 0.95, consequence),
            HorizonNode(3, "MOST_LIKELY_RESPONSE", immediate_response, 0.65, consequence, evidence),
            HorizonNode(4, "STRONGEST_PIVOT", strongest_pivot, 0.30, min(1.0, consequence + 0.15), evidence),
            HorizonNode(5, "DECISION_MAKER_TWIN", decision_maker_response, 0.75, consequence),
            HorizonNode(6, "EVIDENCE_AHEAD", "Secure decision-changing proof before the predicted dependency becomes contested", 0.80, consequence, evidence),
            HorizonNode(7, "COLLATERAL_EFFECTS", f"Check downstream and cross-lane consequences: {cross}", 0.50, consequence),
            HorizonNode(8, "COUNTERMOVE", "Pre-build the strongest lawful counter-route before execution", 0.70, consequence, fallback=fallback),
            HorizonNode(9, "WORST_CASE_RECOVERY", "Assume the preferred route fails; preserve state, rollback, alternate route and review/recovery options", 0.20, 1.0, fallback=fallback),
            HorizonNode(10, "PIVOT_TRIGGER", "Define the evidence, state or threshold that forces recomputation or stop", 1.0, consequence),
        ]

        extension_kinds = (
            "SECOND_ORDER_RESPONSE",
            "DEPENDENCY_PROPAGATION",
            "COUNTERFACTUAL_BRANCH",
            "RESOURCE_CONSTRAINT",
            "PROOF_DEGRADATION",
            "ADVERSARIAL_SURPRISE",
            "RECOVERY_BRANCH",
            "OPTION_VALUE_CHECK",
        )
        nodes = list(base)
        for step in range(11, depth + 1):
            kind = extension_kinds[(step - 11) % len(extension_kinds)]
            nodes.append(
                HorizonNode(
                    step,
                    kind,
                    f"Extend simulation horizon: {kind.lower().replace('_', ' ')}; recompute if this branch changes the preferred route",
                    max(0.05, 0.45 - 0.01 * (step - 11)),
                    consequence,
                    evidence,
                    fallback=fallback if "RECOVERY" in kind or "OPTION" in kind else None,
                )
            )

        twin = FederationDigitalTwin().simulate(
            objective,
            [
                Scenario("MOST_LIKELY", consequence=consequence, regret=0.25, notes=immediate_response),
                Scenario("STRONGEST", consequence=min(1.0, consequence + 0.15), regret=0.55, notes=strongest_pivot),
                Scenario("SURPRISE_HIGH_IMPACT", consequence=1.0, regret=0.9, notes="Low-probability branch that could dominate outcome if ignored"),
                Scenario("FAILURE_RECOVERY", consequence=0.7, regret=0.35, notes=fallback),
            ],
        )
        return HorizonRun(
            engine=self.ENGINE_ID,
            profile=profile,
            objective=objective,
            adaptive_depth=depth,
            minimum_depth=self.MIN_CONSEQUENTIAL_DEPTH if consequential else self.MIN_ROUTINE_DEPTH,
            nodes=tuple(nodes),
            scenarios=tuple(twin["scenarios"]),
            surface_route_failure=False,
        )

    @staticmethod
    def as_dict(run: HorizonRun) -> dict:
        return {
            **asdict(run),
            "nodes": [asdict(n) for n in run.nodes],
            "scenarios": list(run.scenarios),
        }
