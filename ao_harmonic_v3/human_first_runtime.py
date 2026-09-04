"""Human-First Omega binding above Forest-First / AO-HARMONIC.

This module composes the already-admitted Human-First constitutional gate around
Forest-First strategic perception. Forest-First remains free to perform deep
internal reasoning. Human-First decides whether the resulting mission action may
continue silently or genuinely requires human judgment.

Source implementation only: importing or running this module does not execute a
provider effect or prove cross-surface runtime enforcement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from evidenceops.lex_omega.forest_first import ForestFirstRequest
from federation_consolidation.human_first_omega import (
    ActionProposal,
    HumanMissionContract,
    evaluate,
)

from .forest_omega import ForestFirstOmega, ForestOmegaContext, ForestOmegaResult
from .runtime import AOHarmonicV3


HUMAN_FIRST_OMEGA_ID = "HUMAN-FIRST-OMEGA-V1"


@dataclass(frozen=True)
class HumanFirstForestResult:
    engine_id: str
    contract: dict[str, Any]
    gate: dict[str, Any]
    forest: ForestOmegaResult
    user_interrupt_required: bool
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    truth_class: str = "HUMAN_CONTROL_AND_STRATEGIC_SIMULATION_STATE_NOT_FACT"


class HumanFirstForestBinding:
    """Constitutional wrapper around Forest-First strategic perception."""

    ENGINE_ID = HUMAN_FIRST_OMEGA_ID

    def __init__(self, forest: ForestFirstOmega | None = None) -> None:
        self.forest = forest or ForestFirstOmega()

    @staticmethod
    def derive_contract(context: ForestOmegaContext) -> HumanMissionContract:
        return HumanMissionContract(
            mission_id=context.matter_id,
            owner="Kim Kagiso Mosiane",
            intent=context.objective,
            success_conditions=(context.desired_outcome,),
            authority_ceiling="A1_INTERNAL",
            privacy_level="PRIVATE",
            interruption_budget=1,
            cognitive_budget_minutes=10,
            reversibility_required=True,
            proof_required=True,
            stop_conditions=(
                "Objective is materially satisfied",
                "Verified evidence changes the objective or route",
                "Authority boundary requires human judgment",
                "Objective-level exhaustion is reached",
            ),
        )

    @staticmethod
    def derive_action(context: ForestOmegaContext, forest: ForestOmegaResult) -> ActionProposal:
        creator_user_required = bool(forest.creator_mode.get("user_required_count", 0))
        consequential = bool(context.consequential_action_planned or context.material_strategy_change)
        return ActionProposal(
            action_id=f"{context.matter_id}:FOREST_DECISION",
            description="Evaluate Forest-First strategic output under the Human-First constitutional envelope",
            authority_required="A3_CONSEQUENTIAL" if consequential else "A1_INTERNAL",
            external_effect=False,
            irreversible=False,
            material_objective_change=False,
            owner_only_fact_or_value_judgment=bool(context.owner_only_dependency or creator_user_required),
            privacy_envelope_expansion=False,
            consequential=consequential,
            teach_back_required=bool(context.high_stakes and not context.teach_back_complete),
            requested_owner_interrupt=forest.user_interrupt_required,
            expected_owner_minutes=0,
            readback_plan_present=not context.provider_readback_required_but_missing,
        )

    def run(
        self,
        context: ForestOmegaContext,
        *,
        contract: HumanMissionContract | None = None,
        action: ActionProposal | None = None,
        justice_request: ForestFirstRequest | None = None,
    ) -> HumanFirstForestResult:
        # Strategic perception is safe internal work. Run it first; then gate the
        # proposed continuation/action, not the act of thinking itself.
        forest_result = self.forest.run(context, justice_request=justice_request)
        human_contract = contract or self.derive_contract(context)
        action_proposal = action or self.derive_action(context, forest_result)
        decision = evaluate(human_contract, action_proposal)

        gate = asdict(decision)
        gate.update({
            "forest_requested_interrupt": forest_result.user_interrupt_required,
            "forest_interrupt_suppressed": bool(
                forest_result.user_interrupt_required and decision.suppress_interrupt
            ),
            "human_mission_contract_id": human_contract.mission_id,
            "rule": "SAFE_INTERNAL_REASONING_CONTINUES_HUMAN_ONLY_FOR_GENUINE_OWNER_DECISION",
        })

        return HumanFirstForestResult(
            engine_id=self.ENGINE_ID,
            contract=asdict(human_contract),
            gate=gate,
            forest=forest_result,
            user_interrupt_required=decision.human_required,
        )


class HumanFirstAOHarmonicV3(AOHarmonicV3):
    """AO-HARMONIC compatibility runtime with Human-First as parent control plane."""

    HUMAN_CONTROL_PLANE = HUMAN_FIRST_OMEGA_ID

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.human_first = HumanFirstForestBinding(self.forest)

    def run_human_first_forest(
        self,
        context: ForestOmegaContext,
        *,
        contract: HumanMissionContract | None = None,
        action: ActionProposal | None = None,
        justice_request: ForestFirstRequest | None = None,
    ) -> HumanFirstForestResult:
        return self.human_first.run(
            context,
            contract=contract,
            action=action,
            justice_request=justice_request,
        )

    def restore_acceptance_test(self) -> dict[str, object]:
        acceptance = super().restore_acceptance_test()
        required = set(acceptance["required"])
        required.update({
            "HUMAN_FIRST_OMEGA",
            "HUMAN_MISSION_CONTRACT",
            "HUMAN_FIRST_CONSTITUTIONAL_GATE",
        })
        acceptance["required"] = sorted(required)
        acceptance["human_control_plane"] = HUMAN_FIRST_OMEGA_ID
        acceptance["human_first_source_bound"] = True
        acceptance["human_first_provider_runtime_bound"] = False
        acceptance["human_value_improvement_measured"] = False
        acceptance["human_first_rule"] = (
            "SAFE_A0_A1_INTERNAL_WORK_CONTINUES; GENUINE_OWNER_DECISIONS_SURFACE"
        )
        return acceptance


def bootstrap_human_first() -> dict[str, object]:
    runtime = HumanFirstAOHarmonicV3()
    return {
        "runtime": "AO-HARMONIC-GENOME",
        "version": runtime.VERSION,
        "human_control_plane": HUMAN_FIRST_OMEGA_ID,
        "strategic_perception": "FOREST-FIRST-OMEGA",
        "foresight": "HORIZON-OMEGA",
        "acceptance": runtime.restore_acceptance_test(),
        "truth_boundary": {
            "human_first_source_bound": True,
            "human_first_provider_runtime_bound": False,
            "cross_surface_enforcement_proved": False,
            "human_value_improvement_measured": False,
            "external_effect_authority_expanded": False,
        },
    }


__all__ = [
    "HUMAN_FIRST_OMEGA_ID",
    "HumanFirstForestBinding",
    "HumanFirstForestResult",
    "HumanFirstAOHarmonicV3",
    "bootstrap_human_first",
]
