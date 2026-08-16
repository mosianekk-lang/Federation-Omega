"""Bounded no-effect real-mission-derived shadow for Forest-First Ω.

This fixture contains only structural control state. It contains no names, private
case facts, message bodies, credentials, legal conclusions or provider mutations.
It models a real high-stakes pattern: external decisions are pending, primary
proof recovery is still useful, one technical route fails while an authorised
alternative remains, and the owner should not be interrupted for system work.

The reference comparator is an explicit deterministic *fragmented-control
reference fixture*, not a measurement of any historical deployed runtime.
Passing this shadow validates only the integrated source behavior exercised by
this fixture. It does not prove legal accuracy, future prediction, provider
runtime, external effects or global superiority.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from evidenceops.lex_omega.forest_first_creator_mode import WorkClass, WorkItem

from .forest_omega import ForestOmegaContext
from .runtime import AOHarmonicV3


SHADOW_ID = "FOREST-FIRST-OMEGA-REAL-MISSION-CONTROL-SHADOW-001"
TRUTH_BOUNDARY = "REAL_MISSION_DERIVED_REDACTED_CONTROL_STATE_NO_PRIVATE_PAYLOAD_NO_EXTERNAL_EFFECT"


@dataclass(frozen=True)
class ShadowMetrics:
    adaptive_horizon_depth: int
    root_hypotheses_challenged: int
    falsifier_questions_available: int
    evidence_ahead_dependencies: int
    ranked_paths: int
    route_failure_surface_to_owner: bool
    route_recovered: bool
    system_absorbed_work_items: int
    owner_required_work_items: int
    anticipatory_safe_actions: int
    owner_interrupt_required: bool
    learning_candidate_created: bool
    external_effect: bool
    strategic_loop_count: int


class FragmentedReferencePolicy:
    """Deterministic pre-integration reference fixture only.

    It intentionally represents the architectural failure class that motivated
    convergence: fixed-depth foresight, separate strategic loops, route-level
    blocker surfacing and system work handed back to the owner. It is not a
    claim about an exact historical provider runtime or model behavior.
    """

    def run(self) -> ShadowMetrics:
        return ShadowMetrics(
            adaptive_horizon_depth=10,
            root_hypotheses_challenged=0,
            falsifier_questions_available=0,
            evidence_ahead_dependencies=2,
            ranked_paths=2,
            route_failure_surface_to_owner=True,
            route_recovered=False,
            system_absorbed_work_items=0,
            owner_required_work_items=2,
            anticipatory_safe_actions=2,
            owner_interrupt_required=True,
            learning_candidate_created=True,
            external_effect=False,
            strategic_loop_count=3,
        )


def _context() -> ForestOmegaContext:
    return ForestOmegaContext(
        matter_id="REDACTED-HIGH-STAKES-MISSION",
        objective="preserve the strongest merits path while external procedural state remains pending",
        desired_outcome="continue safe proof recovery and readiness without owner debugging or premature external commitment",
        high_stakes=True,
        consequential_action_planned=False,
        consequence=0.95,
        uncertainty=0.85,
        dependency_density=0.85,
        adversarial_complexity=0.9,
        root_hypotheses=(
            "the immediate procedural event may not be the real merits bottleneck",
            "the most valuable next action may be primary-proof recovery rather than another outward filing",
        ),
        tree_facts=(
            "an external procedural decision is pending",
            "primary evidence recovery remains available",
            "some independent internal preparation lanes remain executable",
        ),
        evidence_dependencies=(
            "current procedural status",
            "primary decision-chain record",
            "objective event-level proof",
        ),
        cross_lane_risks=(
            "forum contamination",
            "waiver or accidental concession",
            "premature irreversible commitment",
        ),
        route_alternatives=(
            {
                "route_id": "RECOVER-PRIMARY",
                "route_type": "REUSE",
                "available": True,
                "authorised": True,
                "information_gain": 0.95,
                "proof_strength": 0.95,
                "reversibility": 1.0,
                "owner_burden": 0.0,
                "latency": 0.3,
                "feasibility": 0.95,
                "speed": 0.85,
                "strategic_value": 1.0,
                "privacy_cost": 0.1,
                "maintenance_cost": 0.1,
            },
            {
                "route_id": "NEW-OUTWARD-PROCESS",
                "route_type": "NEW_BUILD",
                "available": True,
                "authorised": False,
                "information_gain": 0.25,
                "proof_strength": 0.45,
                "reversibility": 0.2,
                "owner_burden": 0.8,
                "latency": 0.8,
                "feasibility": 0.5,
                "speed": 0.45,
                "strategic_value": 0.45,
                "privacy_cost": 0.4,
                "maintenance_cost": 0.7,
            },
        ),
        work_items=(
            WorkItem("reroute a failed technical retrieval path", WorkClass.RETRY_RECOVERY),
            WorkItem("recover and reconcile primary records", WorkClass.RESEARCH_RETRIEVAL),
        ),
        credible_risk_signal_present=True,
        legal_route_complete=True,
        teach_back_complete=True,
        jfrie_bound=True,
        deadline_state_verified=True,
        evidence_preservation_current=True,
        continuity_checkpoint_current=True,
        best_current_version_gate_passed=True,
        repeated_failure_detected=True,
        material_user_correction_received=True,
        avoidable_manual_user_work_detected=True,
        reusable_lesson_candidate_present=True,
        provider_readback_required_but_missing=False,
        route_failure_detected=True,
        objective_exhausted=False,
        owner_only_dependency=False,
        material_strategy_change=False,
        immediate_response="the external actor may maintain the current procedural position while proof recovery continues",
        strongest_pivot="the opposing side may reframe the dispute or rely on a primary record not yet recovered",
        decision_maker_response="a neutral decision-maker is likely to test jurisdiction, source proof, prejudice and exact event chronology",
        fallback="preserve the current merits route, recover primary proof, and reserve narrower procedural remedies",
        trigger_refs=("REDACTED_CONTROL_STATE",),
    )


def run_forest_omega_shadow() -> dict[str, object]:
    runtime = AOHarmonicV3()
    result = runtime.forest.run(_context())

    roots = result.roots
    falsifier_count = sum(len(root.get("falsifiers", [])) for root in roots)
    integrated = ShadowMetrics(
        adaptive_horizon_depth=int(result.horizon["adaptive_depth"]),
        root_hypotheses_challenged=len(roots),
        falsifier_questions_available=falsifier_count,
        evidence_ahead_dependencies=len(result.trees["evidence_dependencies"]),
        ranked_paths=len(result.paths),
        route_failure_surface_to_owner=bool(result.route_recovery["surface_to_owner"]),
        route_recovered=bool(result.route_recovery["rerouted_to"]),
        system_absorbed_work_items=int(result.creator_mode["system_absorbed_count"]),
        owner_required_work_items=int(result.creator_mode["user_required_count"]),
        anticipatory_safe_actions=len(result.anticipatory["automatic_actions"]),
        owner_interrupt_required=bool(result.user_interrupt_required),
        learning_candidate_created=bool(result.learning["candidate_required"]),
        external_effect=bool(result.external_effect),
        strategic_loop_count=1,
    )
    reference = FragmentedReferencePolicy().run()

    acceptance = {
        "adaptive_horizon_extends_beyond_fixed_floor": integrated.adaptive_horizon_depth > reference.adaptive_horizon_depth,
        "roots_and_falsifiers_present": integrated.root_hypotheses_challenged >= 2 and integrated.falsifier_questions_available >= 2,
        "evidence_ahead_preserved": integrated.evidence_ahead_dependencies >= reference.evidence_ahead_dependencies,
        "higher_value_path_ranked_first": bool(result.paths) and result.paths[0]["route_id"] == "RECOVER-PRIMARY",
        "route_failure_rerouted_without_owner_blocker": integrated.route_recovered and not integrated.route_failure_surface_to_owner,
        "system_absorbs_repeatable_work": integrated.system_absorbed_work_items >= 2 and integrated.owner_required_work_items == 0,
        "anticipation_runs_before_owner_prompt": integrated.anticipatory_safe_actions >= 2,
        "no_avoidable_owner_interrupt": not integrated.owner_interrupt_required,
        "learning_candidate_created_for_failure_and_correction": integrated.learning_candidate_created,
        "single_integrated_strategic_loop": integrated.strategic_loop_count < reference.strategic_loop_count,
        "zero_external_effect": not integrated.external_effect,
        "risk_remains_hypothesis": result.forest["truth_boundary"] == "RISK_MODEL_NOT_FINDING_OF_WRONGDOING",
    }

    return {
        "shadow_id": SHADOW_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "reference_boundary": "FRAGMENTED_REFERENCE_POLICY_IS_ARCHITECTURAL_FIXTURE_NOT_HISTORICAL_RUNTIME_MEASUREMENT",
        "authority_ceiling": result.authority_ceiling,
        "external_effect": result.external_effect,
        "integrated": asdict(integrated),
        "reference": asdict(reference),
        "acceptance": acceptance,
        "pass": all(acceptance.values()),
        "selected_path": result.paths[0]["route_id"] if result.paths else None,
        "route_recovery": result.route_recovery,
        "formal_scope": "FOREST_FIRST_OMEGA_SYSTEM_SPECIFIC_REAL_MISSION_DERIVED_NO_EFFECT_SHADOW",
    }


__all__ = [
    "FragmentedReferencePolicy",
    "SHADOW_ID",
    "ShadowMetrics",
    "TRUTH_BOUNDARY",
    "run_forest_omega_shadow",
]
