from federation_consolidation.human_first_omega import (
    ActionProposal,
    HumanMissionContract,
    RecoveryState,
    batch_requires_human,
    evaluate,
    human_value_score,
    outcome_first_decision,
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
    action = ActionProposal(action_id="A1", description="Read and reconcile internal state", requested_owner_interrupt=True)
    decision = evaluate(contract(), action)
    assert decision.allow is True
    assert decision.human_required is False
    assert decision.suppress_interrupt is True
    assert decision.mode == "AUTO_CONTINUE_SILENT"


def test_unapproved_external_effect_is_held_for_human_even_with_readback_plan():
    action = ActionProposal(action_id="A2", description="Send an external message", authority_required="A2_EXTERNAL_REVERSIBLE", external_effect=True, effect_class="EXTERNAL_MESSAGE_SEND", authorization_ref="OWNER:NOT-IN-CONTRACT", readback_plan_present=True)
    decision = evaluate(contract(), action)
    assert decision.allow is False
    assert decision.human_required is True
    assert "EXTERNAL_EFFECT_REQUIRES_OWNER_AUTHORIZATION" in decision.reasons
    assert "AUTHORITY_CEILING_EXCEEDED" in decision.reasons


def test_scoped_preauthorized_reversible_external_effect_can_continue():
    approved = contract(authority_ceiling="A2_EXTERNAL_REVERSIBLE", authorized_external_effect_classes=("SOURCE_GOVERNANCE_WRITE",), authorization_refs=("OWNER:PROCEED:20260904",))
    action = ActionProposal(action_id="A2-PREAUTH", description="Apply the already-authorized reversible source governance write", authority_required="A2_EXTERNAL_REVERSIBLE", external_effect=True, effect_class="SOURCE_GOVERNANCE_WRITE", authorization_ref="OWNER:PROCEED:20260904", readback_plan_present=True)
    decision = evaluate(approved, action)
    assert decision.allow is True
    assert decision.human_required is False
    assert decision.mode == "AUTO_CONTINUE"


def test_mismatched_effect_class_or_authorization_ref_fails_closed():
    approved = contract(authority_ceiling="A2_EXTERNAL_REVERSIBLE", authorized_external_effect_classes=("SOURCE_GOVERNANCE_WRITE",), authorization_refs=("OWNER:PROCEED:20260904",))
    wrong_class = ActionProposal(action_id="WRONG-CLASS", description="Different effect class", authority_required="A2_EXTERNAL_REVERSIBLE", external_effect=True, effect_class="EXTERNAL_MESSAGE_SEND", authorization_ref="OWNER:PROCEED:20260904", readback_plan_present=True)
    wrong_ref = ActionProposal(action_id="WRONG-REF", description="Different authorization reference", authority_required="A2_EXTERNAL_REVERSIBLE", external_effect=True, effect_class="SOURCE_GOVERNANCE_WRITE", authorization_ref="OWNER:DIFFERENT", readback_plan_present=True)
    assert "EXTERNAL_EFFECT_REQUIRES_OWNER_AUTHORIZATION" in evaluate(approved, wrong_class).reasons
    assert "EXTERNAL_EFFECT_REQUIRES_OWNER_AUTHORIZATION" in evaluate(approved, wrong_ref).reasons


def test_external_effect_without_readback_plan_fails_closed_even_if_preauthorized():
    approved = contract(authority_ceiling="A2_EXTERNAL_REVERSIBLE", authorized_external_effect_classes=("SOURCE_GOVERNANCE_WRITE",), authorization_refs=("OWNER:PROCEED:20260904",))
    action = ActionProposal(action_id="A3", description="Preauthorized external effect without verification plan", authority_required="A2_EXTERNAL_REVERSIBLE", external_effect=True, effect_class="SOURCE_GOVERNANCE_WRITE", authorization_ref="OWNER:PROCEED:20260904", readback_plan_present=False)
    decision = evaluate(approved, action)
    assert decision.human_required is True
    assert "READBACK_PLAN_REQUIRED" in decision.reasons


def test_consequential_action_remains_human_gated_despite_other_preauthorization():
    approved = contract(authority_ceiling="A3_CONSEQUENTIAL", authorized_external_effect_classes=("SOURCE_GOVERNANCE_WRITE",), authorization_refs=("OWNER:PROCEED:20260904",))
    action = ActionProposal(action_id="A3-CONSEQUENTIAL", description="Consequential action", authority_required="A3_CONSEQUENTIAL", external_effect=True, effect_class="SOURCE_GOVERNANCE_WRITE", authorization_ref="OWNER:PROCEED:20260904", consequential=True, readback_plan_present=True)
    decision = evaluate(approved, action)
    assert decision.human_required is True
    assert "CONSEQUENTIAL_ACTION" in decision.reasons


def test_objective_change_never_happens_silently():
    action = ActionProposal(action_id="A4", description="Change the user's mission objective", material_objective_change=True)
    decision = evaluate(contract(), action)
    assert decision.human_required is True
    assert "MATERIAL_OBJECTIVE_CHANGE" in decision.reasons


def test_owner_fact_and_privacy_expansion_require_human_judgment():
    action = ActionProposal(action_id="A5", description="Use new sensitive context and infer an owner-only fact", owner_only_fact_or_value_judgment=True, privacy_envelope_expansion=True)
    decision = evaluate(contract(), action)
    assert decision.human_required is True
    assert "OWNER_ONLY_FACT_OR_VALUE_JUDGMENT" in decision.reasons
    assert "PRIVACY_ENVELOPE_EXPANSION" in decision.reasons


def test_cognitive_budget_prevents_burden_dumping():
    action = ActionProposal(action_id="A6", description="Push thirty minutes of system debugging to the owner", expected_owner_minutes=30)
    decision = evaluate(contract(cognitive_budget_minutes=10), action)
    assert decision.human_required is True
    assert "OWNER_COGNITIVE_BUDGET_EXCEEDED" in decision.reasons


def test_batch_only_surfaces_true_human_decisions():
    safe = ActionProposal(action_id="SAFE", description="Internal QA")
    consequential = ActionProposal(action_id="HOLD", description="Irreversible action", irreversible=True)
    held = batch_requires_human(contract(), (safe, consequential))
    assert [item.action_id for item in held] == ["HOLD"]


def test_human_value_score_rewards_outcome_and_burden_reduction():
    score = human_value_score(mission_progress=20, outcome_quality=15, option_preservation=10, comprehension=10, proof_confidence=10, avoided_work=15, avoided_surprise=10, owner_minutes=3, debug_minutes=0, unnecessary_interruptions=0, financial_cost=0, privacy_exposure=0, irreversibility=0)
    assert score > 80


def test_invalid_contract_blocks_execution():
    bad = contract(intent="", success_conditions=())
    decision = evaluate(bad, ActionProposal(action_id="A7", description="Anything"))
    assert decision.allow is False
    assert decision.human_required is True
    assert "INTENT_REQUIRED" in decision.reasons
    assert "SUCCESS_CONDITION_REQUIRED" in decision.reasons


def test_recoverable_problem_is_not_dumped_on_owner_before_repair_exhaustion():
    state = RecoveryState(issue_id="CONNECTOR-TRANSIENT", issue_summary="Temporary provider failure", attempts=("retry-one",), best_next_route="retry with alternate adapter")
    decision = outcome_first_decision(state)
    assert decision.owner_visible is False
    assert decision.human_required is False
    assert decision.continue_recovery is True
    assert decision.report_mode == "CONTINUE_RECOVERY_SILENT"
    assert decision.headline == ""


def test_verified_solution_is_reported_as_outcome_not_problem():
    state = RecoveryState(issue_id="CONNECTOR-TRANSIENT", issue_summary="Temporary provider failure", resolved=True, verified=True, solution_summary="Alternate adapter restored provider readback", attempts=("retry-one", "alternate-adapter"))
    decision = outcome_first_decision(state)
    assert decision.owner_visible is True
    assert decision.human_required is False
    assert decision.continue_recovery is False
    assert decision.report_mode == "REPORT_VERIFIED_SOLUTION_OUTCOME"
    assert decision.headline == "Resolved: CONNECTOR-TRANSIENT"
    assert decision.details == ("Solution: Alternate adapter restored provider readback",)


def test_unverified_repair_continues_recovery_instead_of_claiming_success():
    state = RecoveryState(issue_id="WRITE-UNKNOWN", issue_summary="Provider write returned ambiguous state", resolved=True, verified=False, solution_summary="Write retry returned 200 but native state is not read back yet")
    decision = outcome_first_decision(state)
    assert decision.owner_visible is False
    assert decision.continue_recovery is True
    assert decision.report_mode == "CONTINUE_RECOVERY_SILENT"


def test_exhausted_recovery_escalates_precisely_with_attempts_and_next_route():
    state = RecoveryState(issue_id="AUTHORITY-GAP", issue_summary="Current identity lacks required provider authority", attempts=("primary-route", "existing-fallback"), exact_blocker="No authorized identity can perform the required effect", best_next_route="Owner may authorize a new provider identity binding", recovery_exhausted=True, owner_decision_required=True, owner_decision_request="Authorize or decline the new provider identity binding")
    decision = outcome_first_decision(state)
    assert decision.owner_visible is True
    assert decision.human_required is True
    assert decision.continue_recovery is False
    assert decision.report_mode == "ESCALATE_PRECISE_UNRESOLVED_DECISION"
    assert "Repairs attempted: primary-route; existing-fallback" in decision.details
    assert "Remaining blocker: No authorized identity can perform the required effect" in decision.details
    assert "Owner decision: Authorize or decline the new provider identity binding" in decision.details


def test_material_residual_risk_is_never_hidden_even_after_verified_solution():
    state = RecoveryState(issue_id="PARTIAL-RECOVERY", issue_summary="Service recovered with remaining integrity risk", resolved=True, verified=True, solution_summary="Primary service restored", residual_risk="Historical queue integrity still requires adjudication", material_residual_risk=True, owner_decision_request="Choose whether to quarantine or adjudicate the historical queue")
    decision = outcome_first_decision(state)
    assert decision.owner_visible is True
    assert decision.human_required is True
    assert decision.report_mode == "REPORT_OUTCOME_WITH_MATERIAL_ESCALATION"
    assert "MATERIAL_RESIDUAL_RISK" in decision.reasons
    assert "Residual risk: Historical queue integrity still requires adjudication" in decision.details


def test_authority_privacy_irreversibility_and_objective_conflict_force_escalation():
    state = RecoveryState(issue_id="BOUNDARY-TEST", issue_summary="Recovery would cross multiple owner-reserved boundaries", authority_expansion_required=True, privacy_expansion_required=True, irreversible_action_required=True, objective_conflict=True)
    decision = outcome_first_decision(state)
    assert decision.human_required is True
    assert set(decision.reasons) == {"AUTHORITY_EXPANSION_REQUIRED", "PRIVACY_EXPANSION_REQUIRED", "IRREVERSIBLE_ACTION_REQUIRED", "OBJECTIVE_CONFLICT"}
