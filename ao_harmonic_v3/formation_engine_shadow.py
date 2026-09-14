from __future__ import annotations

import formation_omega

from formation_omega.autonomic_fabric import (
    ActionCandidate,
    AuthorityCeiling,
    MissionStateVector,
    MissionSwarmPlanner,
    MonotonicClosureGate,
    ProofDirectedScheduler,
    SwarmRole,
)
from formation_omega.mission_convergence import (
    MissionConvergenceEngine,
    MissionSpec,
    ProofEntry,
    ProofStatus,
    WorkItem,
    WorkStatus,
)
from formation_omega.reconciliation_fabric_v2 import (
    DesiredMissionState,
    ObservedMissionState,
    StateReconciler,
)
from formation_omega.source_convergence import (
    ChangeCapsule,
    SourceConvergenceClass,
    classify_convergence,
    reanchor_manifest,
)
from formation_omega.strategic_ecology import (
    MissionCandidate,
    PortfolioAllocator,
    ResourceEnvelope,
)

from .formation_engine_compatibility import (
    BEHAVIOR_AXES,
    formation_engine_disposition,
    public_api_status,
)

C5_SHADOW_VERSION = "1.0.0"


def _row(scenario_id: str, checks: dict[str, bool]) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "checks": checks,
        "pass_state": all(checks.values()),
    }


def _mission(mission_id: str, criteria: tuple[str, ...] = ("Verified closure",)) -> MissionSpec:
    return MissionSpec.create(
        mission_id=mission_id,
        objective="Preserve Formation mission-execution behavior under Forest-First consolidation",
        success_criteria=criteria,
        authority_ceiling="A1",
        constraints=("proof before claim", "no external effect"),
        required_proof_axes=("source", "rollback"),
        rollback_required=True,
    )


def _action(action_id: str, **overrides: object) -> ActionCandidate:
    body: dict[str, object] = {
        "action_id": action_id,
        "objective": "Increase verified closure",
        "closure_leverage": 0.8,
        "information_gain": 0.7,
        "success_probability": 0.9,
        "reversibility": 0.9,
        "cost": 0.1,
        "risk": 0.1,
        "latency": 0.1,
    }
    body.update(overrides)
    return ActionCandidate(**body)


def _strategic_mission(mission_id: str, **overrides: object) -> MissionCandidate:
    body: dict[str, object] = {
        "mission_id": mission_id,
        "objective_id": "FOREST-C5",
        "summary": f"Mission {mission_id} preserve Formation behavior",
        "outcome_value": 0.8,
        "unlock_leverage": 0.5,
        "success_probability": 0.9,
        "learning_value": 0.5,
        "reusability": 0.5,
        "cost": 0.1,
        "risk": 0.1,
        "latency": 0.1,
        "required_capabilities": (),
        "produces_capabilities": (),
        "resource_demand": {"attention": 0.2},
    }
    body.update(overrides)
    return MissionCandidate(**body)


def run_c5_formation_engine_shadow() -> dict[str, object]:
    scenarios: list[dict[str, object]] = []

    api = public_api_status(formation_omega.__all__, formation_omega)
    scenarios.append(
        _row(
            "C5-PUBLIC-API-FREEZE",
            {
                "public_api_preserved": bool(api["public_api_preserved"]),
                "required_api_nonempty": int(api["required_count"]) >= 30,
                "no_missing_exports": not api["missing_exports"],
                "no_missing_attributes": not api["missing_attributes"],
            },
        )
    )

    engine = MissionConvergenceEngine()
    spec = _mission("FOREST-C5-WAVE")
    engine.open_mission(spec)
    engine.set_work_item(
        spec.mission_id,
        WorkItem.create(
            work_id="A",
            lane="source",
            objective="Prepare source candidate A",
            shared_state_key="github-main",
        ),
    )
    engine.set_work_item(
        spec.mission_id,
        WorkItem.create(
            work_id="B",
            lane="source",
            objective="Prepare source candidate B",
            shared_state_key="github-main",
        ),
    )
    engine.set_work_item(
        spec.mission_id,
        WorkItem.create(
            work_id="C",
            lane="proof",
            objective="Prepare independent proof",
        ),
    )
    wave_ids = {item.work_id for item in engine.project(spec.mission_id).ready_work_wave()}
    scenarios.append(
        _row(
            "C5-MISSION-CONVERGENCE",
            {
                "independent_lane_parallelized": "C" in wave_ids,
                "shared_state_serialized": len({"A", "B"} & wave_ids) == 1,
            },
        )
    )

    closure = MissionConvergenceEngine()
    closure_spec = _mission("FOREST-C5-CLOSURE")
    closure.open_mission(closure_spec)
    closure.set_work_item(
        closure_spec.mission_id,
        WorkItem.create(work_id="W", lane="source", objective="Admit source"),
    )
    initially_held = not closure.project(closure_spec.mission_id).closable
    closure.update_work_status(
        closure_spec.mission_id,
        "W",
        WorkStatus.VERIFIED,
        result_refs=("SOURCE-READBACK",),
    )
    for axis in ("source", "rollback"):
        closure.update_proof(
            closure_spec.mission_id,
            ProofEntry.create(
                axis=axis,
                status=ProofStatus.PROVEN,
                evidence_refs=(f"C5:{axis}",),
            ),
        )
    for criterion in closure_spec.success_criteria:
        closure.verify_success(
            closure_spec.mission_id,
            criterion,
            evidence_refs=(f"C5:{criterion}",),
        )
    scenarios.append(
        _row(
            "C5-PROOF-CLOSURE",
            {
                "closure_initially_fail_closed": initially_held,
                "closure_opens_after_required_proof": closure.project(
                    closure_spec.mission_id
                ).closable,
                "rollback_axis_required": "rollback"
                in closure.project(closure_spec.mission_id).proof_vector,
            },
        )
    )

    scheduler = ProofDirectedScheduler()
    external = _action(
        "external",
        external_effect=True,
        authority_ceiling=AuthorityCeiling.A2_BOUNDED_EFFECT,
    )
    ranked = scheduler.rank((external,))
    scenarios.append(
        _row(
            "C5-AUTONOMIC-AUTHORITY",
            {
                "external_effect_held_without_authority": ranked[0].hold_reason
                == "AUTHORITY_CEILING_EXCEEDED",
                "external_effect_not_selected": scheduler.ready_wave((external,)) == (),
            },
        )
    )

    cells = MissionSwarmPlanner().plan(
        mission_id="FOREST-C5-SWARM",
        objective="Preserve independent assurance",
        required_capabilities=("github",),
    )
    witness = next(item for item in cells if item.role == SwarmRole.WITNESS)
    scenarios.append(
        _row(
            "C5-INDEPENDENT-WITNESS",
            {
                "witness_independence_preserved": witness.independence_domain
                == "INDEPENDENT_VERIFICATION",
                "self_certification_prohibited": all(
                    not item.may_self_certify for item in cells
                ),
            },
        )
    )

    gate = MonotonicClosureGate()
    before = MissionStateVector(0.2, 0.2, 0.8, 0.8, 0.2)
    progress = MissionStateVector(0.3, 0.4, 0.8, 0.8, 0.3)
    regression = MissionStateVector(0.4, 0.5, 0.7, 0.8, 0.4)
    scenarios.append(
        _row(
            "C5-MONOTONIC-CLOSURE",
            {
                "measurable_progress_accepted": gate.evaluate(before, progress).accepted,
                "safety_regression_rejected": not gate.evaluate(
                    progress, regression
                ).accepted,
                "noop_rejected": not gate.evaluate(progress, progress).accepted,
            },
        )
    )

    capsule = ChangeCapsule.create(
        change_id="FOREST-C5-REANCHOR",
        mission_id="FOREST-C5-SOURCE",
        base_sha="OLDMAIN",
        candidate_head_sha="CANDIDATE",
        candidate_blobs={
            "formation_omega/source_convergence.py": "candidate-source",
            "tests/test_formation_omega_source_convergence.py": "candidate-test",
        },
        base_blobs={
            "formation_omega/source_convergence.py": "base-source",
            "tests/test_formation_omega_source_convergence.py": "base-test",
        },
        semantic_domains=("FORMATION",),
        required_checks=("AIRLOCK", "BUBBLES", "LEAK_GUARD"),
        proof_boundary="Source admission does not prove provider runtime.",
        rollback_ref="FOREST-C5-OLD-HEAD",
    )
    decision = classify_convergence(
        capsule,
        current_main_sha="NEWMAIN",
        current_blobs=dict(capsule.base_blobs),
    )
    scenarios.append(
        _row(
            "C5-SOURCE-CONVERGENCE",
            {
                "disjoint_stale_classified": decision.classification
                == SourceConvergenceClass.DISJOINT_STALE_BY_ANCESTRY,
                "safe_reanchor_allowed": decision.safe_auto_reanchor,
                "candidate_blobs_preserved": reanchor_manifest(capsule, decision)
                == dict(capsule.candidate_blobs),
            },
        )
    )

    desired = DesiredMissionState.create(
        mission_id="FOREST-C5-RECON",
        objective="Converge source with proof and rollback",
        desired_state="ADMITTED",
        required_checks=("airlock", "bubbles", "leak_guard"),
        required_proof_axes=("source", "rollback"),
        required_capabilities=("github", "mce"),
        rollback_required=True,
    )
    observed = ObservedMissionState(
        mission_id="FOREST-C5-RECON",
        observed_state="CANDIDATE",
        checks={"airlock": True, "bubbles": False, "leak_guard": True},
        proof_axes={"source": True, "rollback": False},
        capabilities={"github": True, "mce": False},
        rollback_available=False,
    )
    delta = StateReconciler.reconcile(desired, observed)
    dimensions = {item.dimension for item in delta.gaps}
    scenarios.append(
        _row(
            "C5-RECONCILIATION",
            {
                "missing_delta_detected": not delta.converged and bool(delta.gaps),
                "proof_gap_preserved": "proof_axis" in dimensions,
                "rollback_gap_preserved": "rollback" in dimensions,
                "capability_gap_preserved": "capability" in dimensions,
            },
        )
    )

    external_mission = _strategic_mission(
        "FOREST-C5-EXTERNAL",
        external_effect=True,
        owner_reserved=True,
        authority_ceiling=AuthorityCeiling.A2_BOUNDED_EFFECT,
    )
    portfolio = PortfolioAllocator().allocate(
        (external_mission,), ResourceEnvelope({"attention": 1.0})
    )
    scenarios.append(
        _row(
            "C5-STRATEGIC-ECOLOGY",
            {
                "external_mission_not_selected": portfolio.selected == (),
                "authority_hold_preserved": dict(portfolio.held).get(
                    "FOREST-C5-EXTERNAL"
                )
                == "AUTHORITY_CEILING_EXCEEDED",
            },
        )
    )

    disposition = formation_engine_disposition()
    scenarios.append(
        _row(
            "C5-AUTHORITY-IDENTITY",
            {
                "formation_kept_as_engine": disposition.keep_as_engine,
                "mission_execution_layer_preserved": disposition.target_authority_layer
                == "MISSION_EXECUTION",
                "sovereign_cognitive_takeover_prohibited": not disposition.sovereign_cognitive_authority,
                "proof_not_inherited": not disposition.proof_inherited,
                "authority_not_inherited": not disposition.authority_inherited,
                "maturity_not_inherited": not disposition.maturity_inherited,
            },
        )
    )

    return {
        "schema": "FOREST-FIRST-C5-FORMATION-ENGINE-SHADOW-V1",
        "version": C5_SHADOW_VERSION,
        "shadow_id": "FOREST-FIRST-CONSOLIDATION-C5-FORMATION-LAST-SHADOW-V1",
        "scenario_count": len(scenarios),
        "semantic_axis_count": len(BEHAVIOR_AXES),
        "required_scenarios": tuple(row["scenario_id"] for row in scenarios),
        "semantic_axes": BEHAVIOR_AXES,
        "scenarios": scenarios,
        "pass": len(scenarios) == 10
        and all(bool(row["pass_state"]) for row in scenarios),
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
        "provider_runtime_proved": False,
        "physical_migration_executed": False,
        "system_retirement_allowed": False,
        "formation_runtime_rewired": False,
        "public_api_superseded": False,
        "formation_authority_expanded": False,
        "cognitive_sovereignty_claimed": False,
        "maturity_inheritance": False,
        "independent_assurance_review": "PENDING",
    }


__all__ = ["C5_SHADOW_VERSION", "run_c5_formation_engine_shadow"]
