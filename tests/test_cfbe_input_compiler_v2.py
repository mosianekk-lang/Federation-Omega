from __future__ import annotations

import pytest

from federation.cfbe_input_compiler_v2 import (
    InputContext,
    IntentKind,
    compile_owner_input,
)


def test_n_reuses_verified_active_mission_and_does_not_reask_owner():
    context = InputContext(
        active_mission_id="MISSION-42",
        active_objective="Repair Federation coherence",
        available_capabilities=("cfbe-omega", "omega-one"),
    )
    result = compile_owner_input("n", context)
    assert result.intent.kind is IntentKind.CONTINUE
    assert result.mission_ir.mission_id == "MISSION-42"
    assert result.mission_ir.objective == "Repair Federation coherence"
    assert not result.intent.owner_clarification_required
    assert "choose-highest-value-safe-path" in result.workstream_hints
    assert "omega-one" in result.capability_hints


def test_n_without_verified_active_mission_fails_closed_to_clarification_signal():
    result = compile_owner_input("n")
    assert result.intent.kind is IntentKind.CONTINUE
    assert result.intent.owner_clarification_required
    assert result.intent.clarification_reason == "CONTINUATION_HAS_NO_VERIFIED_ACTIVE_MISSION"
    assert result.mission_ir.effect_class == "NO_EFFECT"


def test_fix_expands_into_root_cause_repair_and_recurrence_work():
    result = compile_owner_input("fix the stalled workflow")
    assert result.intent.kind is IntentKind.FIX
    assert "root cause" in result.intent.desired_result.casefold()
    assert "minimum-safe-repair" in result.workstream_hints
    assert "prevent-recurrence" in result.workstream_hints
    assert "recovery" in result.capability_hints


def test_better_triggers_cfbe_challenger_instead_of_cosmetic_rewrite():
    result = compile_owner_input("better")
    assert result.intent.kind is IntentKind.IMPROVE
    assert "cfbe-omega" in result.capability_hints
    assert "benchmark-challengers" in result.workstream_hints
    assert "material improvement" in " ".join(result.intent.success_criteria)


def test_is_this_best_compiles_champion_challenger_mission():
    context = InputContext(active_objective="Current orchestration solution")
    result = compile_owner_input("is this the best?", context)
    assert result.intent.kind is IntentKind.CHALLENGE
    assert "generate-alternatives" in result.workstream_hints
    assert "cfbe-challenge" in result.workstream_hints
    assert result.mission_ir.effect_class == "NO_EFFECT"


def test_do_all_means_safe_dependency_ordered_execution_not_unbounded_authority():
    context = InputContext(active_objective="Complete the active build")
    result = compile_owner_input("do all", context)
    assert result.intent.kind is IntentKind.EXECUTE_ALL
    assert "parallelize-independent-lanes" in result.workstream_hints
    assert result.mission_ir.effect_class == "NO_EFFECT"
    assert result.mission_ir.authority_requirements == ()


def test_build_supplies_expert_engineering_capabilities():
    result = compile_owner_input("build an app that tracks evidence")
    assert result.intent.kind is IntentKind.BUILD
    assert {"architecture", "software", "testing"}.issubset(set(result.capability_hints))
    assert "reuse-before-build" in result.workstream_hints
    assert "requirements inferred safely" in result.intent.success_criteria


def test_consequential_send_does_not_inherit_authority():
    result = compile_owner_input("send this email to the employer")
    assert result.mission_ir.effect_class == "CONSEQUENTIAL_EFFECT"
    assert result.mission_ir.owner_approval_required
    assert "explicit_owner_authority_for_exact_effect" in result.mission_ir.authority_requirements
    assert "receiver_specific_readback" in result.mission_ir.proof_requirements
    mapping = result.mission_ir.canonical_mapping()
    assert mapping["truth_boundary"]["provider_effect_authorized"] is False
    assert mapping["truth_boundary"]["publication_authorized"] is False


def test_reversible_internal_branch_is_bounded_but_still_requires_route_authority():
    result = compile_owner_input("create a branch for the repair")
    assert result.mission_ir.effect_class == "BOUNDED_EFFECT"
    assert not result.mission_ir.owner_approval_required
    assert result.mission_ir.authority_requirements == ("existing_bounded_route_authority",)


def test_compilation_is_deterministic_for_same_input_and_context():
    context = InputContext(active_mission_id="M1", active_objective="Improve evidence quality")
    first = compile_owner_input("n", context)
    second = compile_owner_input("n", context)
    assert first.digest() == second.digest()
    assert first.mission_ir.digest() == second.mission_ir.digest()


def test_empty_input_is_rejected():
    with pytest.raises(ValueError, match="CFBE_INPUT_REQUIRED"):
        compile_owner_input("   ")


def test_truth_boundary_refuses_retraining_and_execution_claims():
    result = compile_owner_input("investigate this")
    assert "compiler_does_not_claim_autonomous_model_retraining" in result.truth_boundary
    assert "compiler_does_not_execute_or_schedule_work" in result.truth_boundary
    assert result.owner_burden_policy == "NO_AVOIDABLE_OWNER_WORK"
