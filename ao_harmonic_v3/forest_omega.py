from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from evidenceops.lex_omega.forest_first import ForestFirstJusticeGate, ForestFirstRequest
from evidenceops.lex_omega.forest_first_anticipatory import (
    AnticipatoryContext,
    ForestFirstAnticipatoryEngine,
)
from evidenceops.lex_omega.forest_first_creator_mode import (
    ForestFirstCreatorMode,
    WorkItem,
)

from .horizon import HorizonOmega
from .science_and_routes import (
    FederationDigitalTwin,
    FormationEngine,
    Hypothesis,
    OmegaScientia,
    Route,
    Scenario,
)


FOREST_FIRST_OMEGA_ID = "FOREST-FIRST-OMEGA-V1"
ARCHITECTURE_CYCLE = (
    "ROOTS",
    "FOREST",
    "HORIZON",
    "TREES",
    "PATHS",
    "DECISION",
    "OMEGA",
    "READBACK",
    "LEARNING",
)


@dataclass(frozen=True)
class ForestOmegaContext:
    matter_id: str
    objective: str
    desired_outcome: str
    high_stakes: bool = False
    consequential_action_planned: bool = False
    consequence: float = 0.6
    uncertainty: float = 0.5
    dependency_density: float = 0.5
    adversarial_complexity: float = 0.5
    root_hypotheses: tuple[str, ...] = ()
    tree_facts: tuple[str, ...] = ()
    evidence_dependencies: tuple[str, ...] = ()
    cross_lane_risks: tuple[str, ...] = ()
    route_alternatives: tuple[dict[str, Any], ...] = ()
    work_items: tuple[WorkItem, ...] = ()
    credible_risk_signal_present: bool = False
    legal_route_complete: bool = True
    teach_back_complete: bool = True
    jfrie_bound: bool = True
    deadline_state_verified: bool = True
    evidence_preservation_current: bool = True
    continuity_checkpoint_current: bool = True
    best_current_version_gate_passed: bool = True
    repeated_failure_detected: bool = False
    material_user_correction_received: bool = False
    avoidable_manual_user_work_detected: bool = False
    reusable_lesson_candidate_present: bool = False
    provider_readback_required_but_missing: bool = False
    route_failure_detected: bool = False
    objective_exhausted: bool = False
    owner_only_dependency: bool = False
    material_strategy_change: bool = False
    immediate_response: str = "Environment or opponent responds to the selected path"
    strongest_pivot: str = "A stronger counter-route, objection or dependency is introduced"
    decision_maker_response: str = "Decision-maker tests proof, authority, fairness, reversibility and consequences"
    fallback: str = "Preserve the strongest reversible route and recompute after new evidence"
    trigger_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForestOmegaResult:
    engine_id: str
    matter_id: str
    architecture_cycle: tuple[str, ...]
    roots: tuple[dict[str, Any], ...]
    forest: dict[str, Any]
    horizon: dict[str, Any]
    trees: dict[str, Any]
    paths: tuple[dict[str, Any], ...]
    decision: dict[str, Any]
    omega: dict[str, Any]
    readback: dict[str, Any]
    learning: dict[str, Any]
    anticipatory: dict[str, Any]
    creator_mode: dict[str, Any]
    justice_gate: dict[str, Any] | None
    route_recovery: dict[str, Any]
    user_interrupt_required: bool
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    truth_class: str = "STRATEGIC_SIMULATION_AND_CONTROL_STATE_NOT_FACT"


class ForestFirstOmega:
    """Integrated strategic-perception organ for AO-HARMONIC.

    Forest-First Ω does not replace the existing Forest-First Justice Gate,
    anticipatory engine, Creator Mode, HORIZON-Ω, Ω-SCIENTIA or Formation.
    It composes them into one objective-preserving cycle:

        ROOTS -> FOREST -> HORIZON -> TREES -> PATHS -> DECISION -> OMEGA
        -> READBACK -> LEARNING

    It is A1-internal by default. It never grants external authority and never
    promotes a simulation, user risk signal or pattern hypothesis into fact.
    """

    ENGINE_ID = FOREST_FIRST_OMEGA_ID

    def __init__(
        self,
        *,
        horizon: HorizonOmega | None = None,
        scientia: OmegaScientia | None = None,
        formation: FormationEngine | None = None,
        digital_twin: FederationDigitalTwin | None = None,
    ) -> None:
        self.horizon = horizon or HorizonOmega()
        self.scientia = scientia or OmegaScientia()
        self.formation = formation or FormationEngine()
        self.digital_twin = digital_twin or FederationDigitalTwin()
        self.anticipatory = ForestFirstAnticipatoryEngine()
        self.creator = ForestFirstCreatorMode()
        self.justice = ForestFirstJusticeGate()

    def _roots(self, context: ForestOmegaContext) -> tuple[dict[str, Any], ...]:
        hypotheses = context.root_hypotheses or (
            "The immediate event may be part of a larger causal or strategic pattern",
        )
        challenged: list[dict[str, Any]] = []
        for index, statement in enumerate(hypotheses, 1):
            challenged.append(
                self.scientia.challenge(
                    Hypothesis(
                        hypothesis_id=f"ROOT-{index}",
                        statement=statement,
                        supporting_observations=list(context.tree_facts),
                        predicted_evidence=list(context.evidence_dependencies),
                        falsifiers=[
                            "A verified primary record materially contradicts the proposed causal or strategic pattern",
                            "A simpler competing explanation explains the same observations with stronger proof",
                        ],
                        confidence=0.5,
                    )
                )
            )
        return tuple(challenged)

    @staticmethod
    def _forest(context: ForestOmegaContext) -> dict[str, Any]:
        return {
            "matter_id": context.matter_id,
            "objective": context.objective,
            "desired_outcome": context.desired_outcome,
            "forest_alarm": context.credible_risk_signal_present,
            "protective_threshold": "ACT_ON_RISK",
            "accusation_threshold": "ACCUSE_ON_PROOF",
            "cross_lane_risks": list(context.cross_lane_risks),
            "evidence_at_risk": list(context.evidence_dependencies),
            "question": "What larger outcome or system dynamic makes the present event strategically important?",
            "truth_boundary": "RISK_MODEL_NOT_FINDING_OF_WRONGDOING",
        }

    @staticmethod
    def _trees(context: ForestOmegaContext) -> dict[str, Any]:
        return {
            "facts": list(context.tree_facts),
            "evidence_dependencies": list(context.evidence_dependencies),
            "rule": "SOURCE_BEFORE_CLAIM",
            "state": "INPUT_FACTS_REQUIRE_THEIR_OWN_PROVENANCE_AND_TRUTH_CLASS",
        }

    @staticmethod
    def _route_from_dict(raw: dict[str, Any], index: int) -> Route:
        return Route(
            route_id=str(raw.get("route_id", f"FFO-ROUTE-{index}")),
            route_type=str(raw.get("route_type", "REROUTE")),
            feasibility=float(raw.get("feasibility", 0.5)),
            proof_strength=float(raw.get("proof_strength", 0.5)),
            reversibility=float(raw.get("reversibility", 0.5)),
            speed=float(raw.get("speed", 0.5)),
            strategic_value=float(raw.get("strategic_value", 0.5)),
            owner_burden=float(raw.get("owner_burden", 0.0)),
            privacy_cost=float(raw.get("privacy_cost", 0.0)),
            maintenance_cost=float(raw.get("maintenance_cost", 0.0)),
        )

    def _paths(self, alternatives: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        routes = [self._route_from_dict(raw, index) for index, raw in enumerate(alternatives, 1)]
        return tuple(asdict(route) for route in self.formation.rank(routes))

    def run(
        self,
        context: ForestOmegaContext,
        *,
        justice_request: ForestFirstRequest | None = None,
    ) -> ForestOmegaResult:
        roots = self._roots(context)
        forest = self._forest(context)
        trees = self._trees(context)

        horizon_run = self.horizon.simulate(
            objective=context.objective,
            profile="FOREST_FIRST_OMEGA",
            consequential=context.high_stakes or context.consequential_action_planned,
            consequence=context.consequence,
            uncertainty=context.uncertainty,
            dependency_density=context.dependency_density,
            adversarial_complexity=context.adversarial_complexity,
            immediate_response=context.immediate_response,
            strongest_pivot=context.strongest_pivot,
            decision_maker_response=context.decision_maker_response,
            evidence_dependencies=context.evidence_dependencies,
            cross_lane_risks=context.cross_lane_risks,
            fallback=context.fallback,
        )
        horizon = self.horizon.as_dict(horizon_run)

        anticipatory_report = self.anticipatory.evaluate(
            AnticipatoryContext(
                high_stakes=context.high_stakes,
                credible_risk_signal_present=context.credible_risk_signal_present,
                consequential_action_planned=context.consequential_action_planned,
                legal_route_complete=context.legal_route_complete,
                teach_back_complete=context.teach_back_complete,
                jfrie_bound=context.jfrie_bound,
                deadline_state_verified=context.deadline_state_verified,
                evidence_preservation_current=context.evidence_preservation_current,
                continuity_checkpoint_current=context.continuity_checkpoint_current,
                best_current_version_gate_passed=context.best_current_version_gate_passed,
                repeated_failure_detected=context.repeated_failure_detected,
                material_user_correction_received=context.material_user_correction_received,
                avoidable_manual_user_work_detected=context.avoidable_manual_user_work_detected,
                reusable_lesson_candidate_present=context.reusable_lesson_candidate_present,
                provider_readback_required_but_missing=context.provider_readback_required_but_missing,
                trigger_refs=context.trigger_refs,
            )
        )
        anticipatory = asdict(anticipatory_report)

        creator_report = self.creator.route(context.work_items)
        creator_mode = asdict(creator_report)

        paths = self._paths(context.route_alternatives)
        selected_path = paths[0] if paths else None

        rerouted = None
        if context.route_failure_detected:
            rerouted = self.horizon.reroute(context.route_alternatives)
        surface_route_failure = self.horizon.should_surface_route_failure(
            objective_exhausted=context.objective_exhausted,
            owner_only=context.owner_only_dependency,
            material_strategy_change=context.material_strategy_change,
        )
        route_recovery = {
            "route_failure_detected": context.route_failure_detected,
            "rerouted_to": rerouted,
            "surface_to_owner": surface_route_failure,
            "rule": "ROUTE_FAILURE_IS_NOT_OBJECTIVE_FAILURE",
        }

        justice_result = self.justice.evaluate(justice_request) if justice_request is not None else None
        justice_gate = asdict(justice_result) if justice_result is not None else None

        owner_hold = bool(
            context.consequential_action_planned
            or anticipatory_report.user_interrupt_required
            or context.owner_only_dependency
        )
        if justice_result is not None and justice_result.release_state.value != "PASS":
            owner_hold = True

        decision = {
            "selected_path": selected_path,
            "reroute": rerouted,
            "owner_hold": owner_hold,
            "minimum_sufficient_action": True,
            "prefer_reversible_option_value": True,
            "surface_route_failure": surface_route_failure,
            "decision_rule": "SELECT_HIGHEST_VALUE_LAWFUL_REVERSIBLE_PATH_THAT_IMPROVES_THE_WHOLE_FOREST",
        }

        omega = {
            "desired_state": context.desired_outcome,
            "success_requires": [
                "objective materially advanced",
                "proof and authority remain within verified scope",
                "cross-lane damage avoided",
                "owner burden minimised",
                "rollback or recovery preserved where feasible",
            ],
            "stop_or_pivot": "Recompute when HORIZON trigger, contradictory evidence, authority change or objective exhaustion occurs",
        }

        twin = self.digital_twin.simulate(
            context.objective,
            [
                Scenario("PREFERRED_PATH_SUCCEEDS", context.consequence, 0.15, "Preferred path advances the desired outcome"),
                Scenario("PREFERRED_PATH_FAILS", min(1.0, context.consequence + 0.1), 0.55, context.fallback),
                Scenario("SURPRISE_HIGH_IMPACT", 1.0, 0.9, "Unexpected branch dominates if unprepared"),
            ],
        )

        readback = {
            "required_after_effectful_execution": True,
            "provider_target_semantic_readback_required": True,
            "state_delta_required_for_success_claim": True,
            "simulation_readback": twin,
            "external_effect_executed": False,
        }

        learning = {
            "candidate_required": bool(
                context.repeated_failure_detected
                or context.material_user_correction_received
                or context.reusable_lesson_candidate_present
            ),
            "promotion_pipeline": [
                "OBSERVATION",
                "LESSON_CANDIDATE",
                "VERIFIED_LESSON",
                "REGRESSION_OR_ADVERSARIAL_TEST",
                "CANONICAL_RULE",
                "EXECUTABLE_CONTROL",
                "RESTORE_INHERITANCE",
                "MEASURED_OPERATIONAL_LEARNING",
            ],
            "backcast_success_claims": "PROHIBITED",
            "misses_preserved": True,
        }

        user_interrupt = bool(
            anticipatory_report.user_interrupt_required
            or creator_report.user_required_count
            or context.owner_only_dependency
            or context.consequential_action_planned
        )

        return ForestOmegaResult(
            engine_id=self.ENGINE_ID,
            matter_id=context.matter_id,
            architecture_cycle=ARCHITECTURE_CYCLE,
            roots=roots,
            forest=forest,
            horizon=horizon,
            trees=trees,
            paths=paths,
            decision=decision,
            omega=omega,
            readback=readback,
            learning=learning,
            anticipatory=anticipatory,
            creator_mode=creator_mode,
            justice_gate=justice_gate,
            route_recovery=route_recovery,
            user_interrupt_required=user_interrupt,
        )


__all__ = [
    "ARCHITECTURE_CYCLE",
    "FOREST_FIRST_OMEGA_ID",
    "ForestFirstOmega",
    "ForestOmegaContext",
    "ForestOmegaResult",
]
