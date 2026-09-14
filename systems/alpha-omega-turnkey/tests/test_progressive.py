from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_omega.progressive import (
    EffectClass,
    FormationInnovationEngine,
    HashLinkedLearningLedger,
    ProgressiveAlphaOmega,
    UnitState,
)


def concept(**extra):
    raw = {
        "title": "Progressive Workflow",
        "description": "Build a proof-bound multi-stream workflow orchestrator",
        "preferred_surfaces": ["github", "google_drive"],
        "required_capabilities": ["scheduler", "proof plane", "learning ledger"],
    }
    raw.update(extra)
    return raw


def complete_until(engine: ProgressiveAlphaOmega, plan, stop_stage: str | None = None):
    seen = []
    while True:
        decision = engine.next_wave(plan)
        if not decision.runnable:
            break
        engine.start_wave(plan, decision)
        for unit_id in decision.runnable:
            unit = plan.unit(unit_id)
            seen.append(unit.stage)
            if stop_stage and unit.stage == stop_stage:
                return seen
            engine.record_result(
                plan,
                unit_id,
                success=True,
                output_refs=(f"out:{unit_id}",),
                proof_refs=(f"proof:{unit_id}",),
                duration_ms=10.0,
            )
    return seen


def test_formation_generates_four_materially_distinct_routes():
    routes = FormationInnovationEngine().form_routes(concept())
    assert len(routes) == 4
    assert len({route.kind for route in routes}) == 4
    assert len({route.path_id for route in routes}) == 4


def test_reuse_route_wins_when_verified_reuse_exists():
    formation = FormationInnovationEngine()
    routes = formation.form_routes(concept(existing_capabilities=["proven scheduler"]))
    selected = formation.select_route(routes)
    assert selected.kind.value == "REUSE_OPTIMISE"
    assert selected.eligible


def test_reuse_route_is_ineligible_without_reuse_candidate():
    routes = FormationInnovationEngine().form_routes(
        {
            "title": "New",
            "description": "Build a novel deterministic component",
            "preferred_surfaces": [],
            "existing_capabilities": [],
        }
    )
    reuse = next(route for route in routes if route.kind.value == "REUSE_OPTIMISE")
    assert not reuse.eligible
    assert "NO_VERIFIED_REUSE_CANDIDATE" in reuse.rejection_reasons


def test_compile_plan_creates_parallel_discovery_streams(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    plan = engine.compile_plan(concept())
    first = engine.next_wave(plan)
    assert len(first.runnable) == 1
    engine.start_wave(plan, first)
    engine.record_result(plan, first.runnable[0], success=True, proof_refs=("proof",))
    second = engine.next_wave(plan)
    stages = {plan.unit(unit_id).stage for unit_id in second.runnable}
    assert stages == {"DISCOVERY"}
    assert len(second.runnable) == 4


def test_scheduler_serializes_collision_keys(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    plan = engine.compile_plan(concept(required_capabilities=["same", "same"]))
    units = list(plan.units.values())
    lock = next(unit for unit in units if unit.stage == "INTAKE")
    lock.state = UnitState.SUCCEEDED
    discovery = [unit for unit in units if unit.stage == "DISCOVERY"]
    for unit in discovery:
        unit.collision_keys = ("shared",)
    decision = engine.next_wave(plan)
    assert len(decision.runnable) == 1


def test_blocked_stream_does_not_freeze_unrelated_ready_stream(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept())
    lock = next(unit for unit in plan.units.values() if unit.stage == "INTAKE")
    lock.state = UnitState.SUCCEEDED
    discovery = [unit for unit in plan.units.values() if unit.stage == "DISCOVERY"]
    discovery[0].state = UnitState.FAILED
    decision = engine.next_wave(plan)
    assert len(decision.runnable) == 3
    assert all(plan.unit(unit_id).stream_id != discovery[0].stream_id for unit_id in decision.runnable)


def test_provider_and_consequential_units_are_held_without_authority(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept(desired_effect="PROVIDER"))
    complete_until(engine, plan)
    decision = engine.next_wave(plan)
    provider_units = {
        unit.unit_id for unit in plan.units.values()
        if unit.effect_class in {EffectClass.PROVIDER_EFFECT, EffectClass.CONSEQUENTIAL}
    }
    assert provider_units
    assert provider_units.issubset(set(decision.held) | {u.unit_id for u in plan.units.values() if u.state is UnitState.HELD})


def test_provider_preflight_can_be_reopened_and_admitted_explicitly(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept(desired_effect="PROVIDER"))
    complete_until(engine, plan)
    held = [u.unit_id for u in plan.units.values() if u.state is UnitState.HELD]
    assert held
    engine.reopen_held(plan, held)
    decision = engine.next_wave(
        plan,
        allow_provider_effects=True,
        authorised_effect_classes=(EffectClass.PROVIDER_EFFECT,),
    )
    assert decision.runnable
    assert all(plan.unit(unit_id).effect_class is EffectClass.PROVIDER_EFFECT for unit_id in decision.runnable)


def test_repeated_failure_opens_circuit(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, failure_threshold=2)
    plan = engine.compile_plan(concept())
    first = engine.next_wave(plan)
    unit_id = first.runnable[0]
    engine.start_wave(plan, first)
    state = engine.record_result(plan, unit_id, success=False, failure_fingerprint="same")
    assert state is UnitState.FAILED
    other = next(unit for unit in plan.units.values() if unit.unit_id != unit_id)
    other.state = UnitState.RUNNING
    state = engine.record_result(plan, other.unit_id, success=False, failure_fingerprint="same")
    assert state is UnitState.CIRCUIT_OPEN


def test_learning_ledger_detects_tampering(tmp_path):
    path = tmp_path / "learning.jsonl"
    ledger = HashLinkedLearningLedger(path)
    ledger.append("SUCCESS", {"unit_id": "1", "proof_refs": ["p"]})
    assert ledger.verify()
    event = json.loads(path.read_text(encoding="utf-8"))
    event["payload"]["unit_id"] = "tampered"
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash chain"):
        HashLinkedLearningLedger(path)


def test_verified_reuse_replaces_build_with_verify_and_regression(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    engine.learning.append(
        "SUCCESS",
        {
            "unit_id": "seed",
            "stage": "CAPABILITY_VERIFY",
            "reusable_key": "capability:scheduler",
            "proof_refs": ["proof:seed"],
            "output_refs": ["artifact:seed"],
            "duration_ms": 100.0,
            "reused": False,
        },
    )
    plan = engine.compile_plan(concept(required_capabilities=["scheduler"]))
    stages = {unit.stage for unit in plan.units.values()}
    assert "VERIFY_REUSE" in stages
    assert "REGRESSION" in stages
    scheduler_builds = [
        unit for unit in plan.units.values()
        if unit.stage == "BUILD" and unit.reusable_key == "capability:scheduler"
    ]
    assert not scheduler_builds
    assert plan.created_from["planned_reuse_hits"] == 1
    assert plan.created_from["planned_work_units_avoided"] == 2
    profile = engine.acceleration_profile()
    assert profile.verified_reuse_hits == 0
    regression = next(
        unit for unit in plan.units.values()
        if unit.stage == "REGRESSION" and unit.reusable_key == "capability:scheduler"
    )
    regression.state = UnitState.RUNNING
    engine.record_result(
        plan,
        regression.unit_id,
        success=True,
        proof_refs=("proof:regression",),
        duration_ms=10.0,
        reused=True,
    )
    profile = engine.acceleration_profile()
    assert profile.verified_reuse_hits == 1
    assert profile.work_units_avoided == 2


def test_speedup_is_not_claimed_without_matched_capability_cycles(tmp_path):
    ledger = HashLinkedLearningLedger(tmp_path / "learning.jsonl")
    ledger.append("SUCCESS", {"cycle_id": "baseline-1", "reusable_key": "capability:x", "stage": "BUILD", "duration_ms": 100, "reused": False})
    ledger.append("SUCCESS", {"cycle_id": "reuse-1", "reusable_key": "capability:x", "stage": "VERIFY_REUSE", "duration_ms": 50, "reused": True})
    profile = ledger.acceleration_profile()
    assert profile.measured_speedup_ratio is None
    assert profile.confidence == "UNMEASURED"


def test_speedup_is_measured_from_complete_matched_capability_cycles(tmp_path):
    ledger = HashLinkedLearningLedger(tmp_path / "learning.jsonl")
    baseline_stages = {"BUILD": 40, "TEST": 30, "RED_TEAM": 20, "CAPABILITY_VERIFY": 10}
    reuse_stages = {"VERIFY_REUSE": 30, "REGRESSION": 20}
    for index, key in enumerate(("capability:x", "capability:y"), 1):
        for stage, duration in baseline_stages.items():
            ledger.append("SUCCESS", {"cycle_id": f"baseline-{index}", "reusable_key": key, "stage": stage, "duration_ms": duration})
        for stage, duration in reuse_stages.items():
            ledger.append("SUCCESS", {"cycle_id": f"reuse-{index}", "reusable_key": key, "stage": stage, "duration_ms": duration, "reused": True})
    profile = ledger.acceleration_profile()
    assert profile.measured_speedup_ratio == 2.0
    assert profile.measured_baseline_samples == 2
    assert profile.measured_reuse_samples == 2
    assert profile.confidence == "MEASURED_LOCAL_LOW_SAMPLE"


def test_checkpoint_is_deterministic_for_unchanged_plan(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept())
    one = engine.checkpoint(plan)
    two = engine.checkpoint(plan)
    assert one["payload_sha256"] == two["payload_sha256"]
    assert Path(one["checkpoint"]).exists()
    assert one["ledger_verified"]


def test_run_wave_uses_stage_executors_and_records_proof(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept())
    def executor(unit):
        return {"success": True, "output_refs": [f"output:{unit.unit_id}"], "proof_refs": [f"proof:{unit.unit_id}"], "duration_ms": 5}
    decision = engine.run_wave(plan, {"INTAKE": executor})
    assert decision.runnable
    unit = plan.unit(decision.runnable[0])
    assert unit.state is UnitState.SUCCEEDED
    assert unit.proof_refs


def test_missing_executor_records_failure_not_false_success(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept())
    decision = engine.run_wave(plan, {})
    assert decision.runnable
    unit = plan.unit(decision.runnable[0])
    assert unit.state is UnitState.FAILED
    assert unit.failure_fingerprint == "NO_EXECUTOR:INTAKE"


def test_stable_plan_identifiers_across_recompilation(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    one = engine.compile_plan(concept())
    two = engine.compile_plan(concept())
    assert one.mission_id == two.mission_id
    assert one.selected_path_id == two.selected_path_id
    assert set(one.units) == set(two.units)


def test_route_evaluations_are_materially_parallel_paths(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    plan = engine.compile_plan(concept(existing_capabilities=["existing scheduler"]))
    evaluations = [unit for unit in plan.units.values() if unit.stage == "ROUTE_EVALUATION"]
    assert len(evaluations) == 4
    assert len({unit.path_id for unit in evaluations}) == 4


def test_run_wave_executes_independent_streams_concurrently(tmp_path):
    import threading
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    plan = engine.compile_plan(concept())
    def intake(unit):
        return {"success": True, "proof_refs": [f"proof:{unit.unit_id}"]}
    first = engine.run_wave(plan, {"INTAKE": intake})
    assert len(first.runnable) == 1
    barrier = threading.Barrier(4)
    def discovery(unit):
        barrier.wait(timeout=2)
        return {"success": True, "proof_refs": [f"proof:{unit.unit_id}"]}
    second = engine.run_wave(plan, {"DISCOVERY": discovery})
    assert len(second.runnable) == 4
    assert engine.last_wave_receipt is not None
    assert len(engine.last_wave_receipt.succeeded) == 4
    assert engine.last_wave_receipt.measured_parallelism_ratio is not None
    assert engine.last_wave_receipt.measured_parallelism_ratio > 1.0


def test_executor_exception_becomes_governed_failure(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept())
    def broken(_unit):
        raise RuntimeError("boom")
    decision = engine.run_wave(plan, {"INTAKE": broken})
    unit = plan.unit(decision.runnable[0])
    assert unit.state is UnitState.FAILED
    assert unit.failure_fingerprint == "EXECUTOR_EXCEPTION:INTAKE:RuntimeError"


def test_success_without_proof_fails_closed(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept())
    decision = engine.next_wave(plan)
    engine.start_wave(plan, decision)
    state = engine.record_result(plan, decision.runnable[0], success=True)
    assert state is UnitState.FAILED
    assert plan.unit(decision.runnable[0]).failure_fingerprint == "MISSING_PROOF:INTERNAL_READBACK"


def test_failure_without_explicit_fingerprint_is_stable_and_governed(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept())
    decision = engine.next_wave(plan)
    engine.start_wave(plan, decision)
    state = engine.record_result(plan, decision.runnable[0], success=False)
    assert state is UnitState.FAILED
    assert plan.unit(decision.runnable[0]).failure_fingerprint.startswith("FAIL-")


def test_provider_effect_lanes_remain_serialized_even_when_authorised(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    plan = engine.compile_plan(concept(desired_effect="PROVIDER"))
    provider_units = [unit for unit in plan.units.values() if unit.effect_class is EffectClass.PROVIDER_EFFECT]
    assert len(provider_units) >= 2
    for unit in provider_units:
        unit.dependencies = ()
    decision = engine.next_wave(plan, allow_provider_effects=True, authorised_effect_classes=(EffectClass.PROVIDER_EFFECT,))
    selected_provider = [unit_id for unit_id in decision.runnable if plan.unit(unit_id).effect_class is EffectClass.PROVIDER_EFFECT]
    assert len(selected_provider) == 1


def test_promote_challenger_before_downstream_execution(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    plan = engine.compile_plan(concept(existing_capabilities=["existing scheduler"]))
    challenger = next(route for route in plan.routes if route.path_id != plan.selected_path_id and route.eligible)
    engine.promote_path(plan, challenger.path_id, proof_refs=("proof:route-evaluation",))
    assert plan.selected_path_id == challenger.path_id
    assert all(unit.path_id == challenger.path_id for unit in plan.units.values() if unit.stage not in {"DISCOVERY", "ROUTE_EVALUATION"})


def test_recompilation_does_not_inflate_reuse_metrics(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path)
    engine.learning.append("SUCCESS", {"unit_id": "seed", "stage": "CAPABILITY_VERIFY", "reusable_key": "capability:scheduler", "proof_refs": ["proof:seed"], "output_refs": ["artifact:seed"], "duration_ms": 100.0, "reused": False})
    engine.compile_plan(concept(required_capabilities=["scheduler"]))
    engine.compile_plan(concept(required_capabilities=["scheduler"]))
    profile = engine.acceleration_profile()
    assert profile.verified_reuse_hits == 0
    assert profile.work_units_avoided == 0


def test_run_until_quiescent_completes_all_safe_units(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    plan = engine.compile_plan(concept(required_capabilities=["scheduler", "proof plane"]))
    def executor(unit):
        return {"success": True, "output_refs": [f"out:{unit.unit_id}"], "proof_refs": [f"proof:{unit.unit_id}"]}
    stages = {unit.stage for unit in plan.units.values()}
    receipts = engine.run_until_quiescent(plan, {stage: executor for stage in stages}, max_waves=50)
    assert receipts
    assert engine.complete(plan)
    assert all(receipt.ledger_verified for receipt in receipts)


def test_build_success_alone_is_not_reusable(tmp_path):
    ledger = HashLinkedLearningLedger(tmp_path / "learning.jsonl")
    ledger.append("SUCCESS", {"stage": "BUILD", "reusable_key": "capability:unsafe", "proof_refs": ["proof:build"]})
    assert "capability:unsafe" not in ledger.verified_reuse()


def test_local_canary_runs_real_safe_multistream_scope(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    plan = engine.compile_plan(concept(required_capabilities=["scheduler", "proof plane"]))
    receipt = engine.run_local_canary(plan)
    assert receipt["state"] == "LOCAL_A1_MULTISTREAM_CANARY_VERIFIED"
    assert receipt["safe_scope_complete"]
    assert receipt["ledger_verified"]
    assert Path(receipt["receipt_path"]).exists()
    assert receipt["max_measured_parallelism_ratio"] is not None


def test_verified_first_cycle_compounds_second_cycle_by_reuse(tmp_path):
    engine = ProgressiveAlphaOmega(tmp_path, max_parallel_safe=8)
    first = engine.compile_plan(concept(required_capabilities=["scheduler"]))
    first_receipt = engine.run_local_canary(first)
    assert first_receipt["safe_scope_complete"]
    assert "capability:scheduler" in engine.learning.verified_reuse()
    second = engine.compile_plan(concept(required_capabilities=["scheduler"]))
    assert second.created_from["planned_reuse_hits"] == 1
    assert second.created_from["planned_work_units_avoided"] == 2
    stages = {unit.stage for unit in second.units.values()}
    assert "VERIFY_REUSE" in stages
    assert not any(unit.stage == "BUILD" and unit.reusable_key == "capability:scheduler" for unit in second.units.values())
