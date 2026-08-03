from alpha_omega_foundry.outcomes import OutcomeCostGovernor


def test_outcome_cost_governor(tmp_path):
    governor = OutcomeCostGovernor(tmp_path)
    outcome = governor.verify_outcomes(
        {"availability": 0.99, "completion_rate": 0.9},
        {"availability": 1.0, "completion_rate": 0.95},
    )
    goodhart = governor.goodhart_check(
        {"completion_target": True},
        {"quality_preserved": True, "safety_preserved": True},
    )
    cost = governor.evaluate_cost(
        {"compute": 20, "storage": 5, "owner_attention": 2},
        {"compute": 30, "storage": 10, "owner_attention": 4},
    )
    value = governor.value_score(outcome["score"], 1.0, 0.9, 0.1)
    decision = governor.decide(outcome, goodhart, cost, value)
    receipt = governor.record("SYS-TEST", outcome, goodhart, cost, value, decision)
    assert outcome["pass"] is True
    assert goodhart["pass"] is True
    assert cost["pass"] is True
    assert decision["action"] == "PROMOTE_AND_MAINTAIN"
    assert receipt["receipt_id"].startswith("RCP-OC-")
    assert governor.ledger.exists()


def test_goodhart_and_budget_blocks(tmp_path):
    governor = OutcomeCostGovernor(tmp_path)
    outcome = governor.verify_outcomes({"target": 1}, {"target": 1})
    goodhart = governor.goodhart_check({"target": True}, {"quality": False})
    cost = governor.evaluate_cost({"compute": 50}, {"compute": 10})
    decision = governor.decide(outcome, goodhart, cost, 0.9)
    assert goodhart["gaming_risk"] is True
    assert decision["action"] == "HOLD_AND_REDESIGN_MEASURES"
