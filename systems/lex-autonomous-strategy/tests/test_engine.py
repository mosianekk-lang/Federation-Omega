from lex_strategy.engine import LexAutonomousStrategyEngine


def base_packet():
    return {
        "matter_id": "TEST-1",
        "objective": "Protect the legal position while closing decisive proof gaps",
        "forum": "TEST FORUM",
        "unknowns": [
            {
                "unknown_id": "U1",
                "question": "What does the primary record say?",
                "decision_impact": 1.0,
                "information_gain": 1.0,
                "urgency": 0.8,
                "source_hints": ["Drive"]
            }
        ],
        "sources": [
            {"name": "Drive primary corpus", "available": True, "authority": "PRIMARY", "freshness": "CURRENT", "cost": 1, "latency": 1}
        ],
        "cross_lane_risks": ["waiver"],
        "opponent_capabilities": ["jurisdiction objection"]
    }


def test_access_before_ask_blocks_owner_request_while_route_exists(tmp_path):
    engine = LexAutonomousStrategyEngine(tmp_path)
    run = engine.run(base_packet())
    assert run.ask_owner_allowed is False
    assert run.access_resolution["routes"]
    assert run.action_queue[0].action_type == "RETRIEVE"
    assert run.action_queue[0].owner_approval_required is False


def test_ten_step_forecast_is_mandatory(tmp_path):
    engine = LexAutonomousStrategyEngine(tmp_path)
    run = engine.run(base_packet())
    assert len(run.forecast_tree) == 10
    assert [n.step for n in run.forecast_tree] == list(range(1, 11))


def test_default_selection_has_no_external_effect(tmp_path):
    engine = LexAutonomousStrategyEngine(tmp_path)
    run = engine.run(base_packet())
    assert run.selected_strategy is not None
    assert run.selected_strategy.external_effect is False
    assert run.truth_boundary["external_effect"] is False
    assert run.truth_boundary["consequential_actions_owner_reserved"] is True


def test_owner_only_unknown_can_be_asked(tmp_path):
    packet = base_packet()
    packet["unknowns"] = [{
        "unknown_id": "OWNER-1",
        "question": "Which remedy does the owner prefer?",
        "owner_only": True,
        "decision_impact": 0.5,
        "information_gain": 0.2,
        "urgency": 0.2
    }]
    engine = LexAutonomousStrategyEngine(tmp_path)
    run = engine.run(packet)
    assert run.ask_owner_allowed is True


def test_missing_non_owner_capability_creates_ao_cra_build(tmp_path):
    packet = base_packet()
    packet["sources"] = []
    engine = LexAutonomousStrategyEngine(tmp_path)
    run = engine.run(packet)
    assert run.ask_owner_allowed is True
    assert run.ao_cra_builds
    assert run.ao_cra_builds[0]["classification"] == "UNRESOLVED_ENGINEERING_BUILD"


def test_learning_ledger_is_hash_linked(tmp_path):
    engine = LexAutonomousStrategyEngine(tmp_path)
    engine.run(base_packet())
    engine.run(base_packet())
    lines = [__import__("json").loads(x) for x in (tmp_path / "learning-ledger.jsonl").read_text().splitlines() if x.strip()]
    assert len(lines) == 2
    assert lines[0]["previous_hash"] == "GENESIS"
    assert lines[1]["previous_hash"] == lines[0]["entry_hash"]
