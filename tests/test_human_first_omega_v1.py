from federation_consolidation.human_first_omega import (
    ActionProposal,
    HumanMissionContract,
    batch_requires_human,
    evaluate,
    human_value_score,
)


def contract(**overrides):
    base = dict(
        mission_id="MISSION-001",
        owner="Kim Kagiso Mosiane",
        intent="Protect the actual human objective while reducing avoidable owner burden.",
        success_conditions=("Verified objective progress",),
        authority_ceiling="A1_INTERNAL",
        interruption_budget=1,
        cognitive_budget_minutes=10,
    )
    base.update(overrides)
    return HumanMissionContract(**base)


def test_safe_internal_action_continues_without_human_interrupt():
    action = ActionProposal(
        action_id="A1",
        description="Read and reconcile internal state",
        requested_owner_interrupt=True,
    )
    decision = evaluate(contract(), action)
    assert decision.allow is True
    assert decision.human_required is False
    assert decision.suppress_interrupt is True
    assert decision.mode == "AUTO_CONTINUE_SILENT"


def test_external_effect_is_held_for_human_even_with_readback_plan():
    action = ActionProposal(
        action_id="A2",
        description="Send an external message",
        authority_required="A2_EXTERNAL_REVERSIBLE",
        external_effect=True,
        readback_plan_present=True,
    )
    decision = evaluate(contract(), action)
    assert decision.allow is False
    assert decision.human_required is True
    assert "EXTERNAL_EFFECT" in decision.reasons
    assert "AUTHORITY_CEILING_EXCEEDED" in decision.reasons


def test_external_effect_without_readback_plan_fails_closed():
    action = ActionProposal(
        action_id="A3",
        description="External effect without verification",
        authority_required="A2_EXTERNAL_REVERSIBLE",
        external_effect=True,
    )
    decision = evaluate(contract(), action)
    assert "READBACK_PLAN_REQUIRED" in decision.reasons


def test_objective_change_never_happens_silently():
    action = ActionProposal(
        action_id="A4",
        description="Change the user's mission objective",
        material_objective_change=True,
    )
    decision = evaluate(contract(), action)
    assert decision.human_required is True
    assert "MATERIAL_OBJECTIVE_CHANGE" in decision.reasons


def test_owner_fact_and_privacy_expansion_require_human_judgment():
    action = ActionProposal(
        action_id="A5",
        description="Use new sensitive context and infer an owner-only fact",
        owner_only_fact_or_value_judgment=True,
        privacy_envelope_expansion=True,
    )
    decision = evaluate(contract(), action)
    assert decision.human_required is True
    assert "OWNER_ONLY_FACT_OR_VALUE_JUDGMENT" in decision.reasons
    assert "PRIVACY_ENVELOPE_EXPANSION" in decision.reasons


def test_cognitive_budget_prevents_burden_dumping():
    action = ActionProposal(
        action_id="A6",
        description="Push thirty minutes of system debugging to the owner",
        expected_owner_minutes=30,
    )
    decision = evaluate(contract(cognitive_budget_minutes=10), action)
    assert decision.human_required is True
    assert "OWNER_COGNITIVE_BUDGET_EXCEEDED" in decision.reasons


def test_batch_only_surfaces_true_human_decisions():
    safe = ActionProposal(action_id="SAFE", description="Internal QA")
    consequential = ActionProposal(
        action_id="HOLD", description="Irreversible action", irreversible=True
    )
    held = batch_requires_human(contract(), (safe, consequential))
    assert [item.action_id for item in held] == ["HOLD"]


def test_human_value_score_rewards_outcome_and_burden_reduction():
    score = human_value_score(
        mission_progress=20,
        outcome_quality=15,
        option_preservation=10,
        comprehension=10,
        proof_confidence=10,
        avoided_work=15,
        avoided_surprise=10,
        owner_minutes=3,
        debug_minutes=0,
        unnecessary_interruptions=0,
        financial_cost=0,
        privacy_exposure=0,
        irreversibility=0,
    )
    assert score > 80


def test_invalid_contract_blocks_execution():
    bad = contract(intent="", success_conditions=())
    decision = evaluate(bad, ActionProposal(action_id="A7", description="Anything"))
    assert decision.allow is False
    assert decision.human_required is True
    assert "INTENT_REQUIRED" in decision.reasons
    assert "SUCCESS_CONDITION_REQUIRED" in decision.reasons
