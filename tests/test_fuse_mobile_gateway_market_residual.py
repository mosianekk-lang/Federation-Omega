from services.fuse_mobile_gateway.market_residual import (
    ActionIntent,
    BrowserTask,
    CarrierSnapshot,
    CheckpointRef,
    MarketResult,
    PerceptionFrame,
    assess_market_results,
    browser_route_receipt,
    choose_browser_carrier,
    compile_replay_event,
    market_residual_status,
    prepare_computer_use,
    reconcile_computer_use,
    selective_restore_plan,
    validate_checkpoints,
    verify_replay_chain,
)


def carrier(name, **overrides):
    values = dict(
        carrier_id=name,
        kind="cloud",
        current=True,
        callable=True,
        authorized=True,
        privacy_ok=True,
        durable=True,
        background_capable=True,
        owner_takeover=True,
        latency_ms=100,
    )
    values.update(overrides)
    return CarrierSnapshot(**values)


def result(system, task="t", env="e", **overrides):
    values = dict(
        system_id=system,
        task_id=task,
        environment_id=env,
        outcome_score=1.0,
        reliability_score=1.0,
        latency_ms=100,
        owner_interventions=0,
        proof_strength=1.0,
        privacy_pass=True,
        authority_pass=True,
    )
    values.update(overrides)
    return MarketResult(**values)


def test_status_adds_no_roots():
    status = market_residual_status()
    assert status["state_roots_added"] == 0
    assert status["authority_roots_added"] == 0


def test_browser_prefers_low_latency_when_other_hard_signals_equal():
    task = BrowserTask("M", "T", "https://example.com")
    assert choose_browser_carrier(task, [carrier("a", latency_ms=200), carrier("b", latency_ms=50)]).carrier_id == "b"


def test_browser_holds_unauthorized():
    task = BrowserTask("M", "T", "x")
    chosen = choose_browser_carrier(task, [carrier("x", authorized=False)])
    assert browser_route_receipt(task, chosen)["status"] == "HELD"


def test_browser_never_auto_routes_consequential():
    task = BrowserTask("M", "T", "x", effect_class="CONSEQUENTIAL")
    assert choose_browser_carrier(task, [carrier("x")]) is None


def test_browser_receipt_is_route_only():
    task = BrowserTask("M", "T", "x")
    receipt = browser_route_receipt(task, carrier("x"))
    assert receipt["status"] == "ROUTED"
    assert "NO_BROWSER_EFFECT_EXECUTED" in receipt["truth_boundary"]


def test_computer_use_requires_fresh_perception():
    perception = PerceptionFrame("M", "F", "screen", "digest", fresh=False)
    intent = ActionIntent("M", "T", "A", "click", "READ_ONLY", "button", "done")
    assert prepare_computer_use(perception, intent, authority_granted=True)["reason"] == "STALE_PERCEPTION"


def test_computer_use_requires_consequential_authority():
    perception = PerceptionFrame("M", "F", "screen", "digest")
    intent = ActionIntent("M", "T", "A", "submit", "CONSEQUENTIAL", "button", "done")
    assert prepare_computer_use(perception, intent, authority_granted=False)["reason"] == "ACTION_AUTHORITY_REQUIRED"


def test_computer_use_semantic_success():
    intent = ActionIntent("M", "T", "A", "click", "READ_ONLY", "button", "done")
    assert reconcile_computer_use(intent, "done", effect_observed=True)["status"] == "SEMANTIC_SUCCESS"


def test_computer_use_unknown_effect_needs_readback():
    intent = ActionIntent("M", "T", "A", "click", "READ_ONLY", "button", "done")
    assert reconcile_computer_use(intent, "unknown", effect_observed=False)["status"] == "READBACK_REQUIRED"


def test_replay_redacts_secret_and_verifies_without_own_store():
    e1 = compile_replay_event(mission_id="M", kind="ACTION", message="api_key=abcdef123456789", observed_at=1.0)
    assert "abcdef" not in e1["message"]
    e2 = compile_replay_event(
        mission_id="M",
        kind="READBACK",
        message="ok",
        previous_sha256=e1["chain_sha256"],
        observed_at=2.0,
    )
    assert verify_replay_chain([e1, e2])["status"] == "PASS"


def test_replay_detects_tamper():
    e1 = compile_replay_event(mission_id="M", kind="ACTION", message="ok", observed_at=1.0)
    e1["message"] = "evil"
    assert verify_replay_chain([e1])["status"] == "FAIL"


def test_checkpoint_secret_fails():
    checkpoint = CheckpointRef("c", "m", "t", "s", "h", True, True, True, True)
    assert validate_checkpoints([checkpoint])["status"] == "FAIL"


def test_checkpoint_selective_restore_plan():
    checkpoint = CheckpointRef("c", "m", "t", "s", "h", True, True, True, False)
    assert validate_checkpoints([checkpoint])["status"] == "PASS"
    assert selective_restore_plan([checkpoint], "c", conversation=True, task_state=True)["status"] == "RESTORE_PLAN_READY"


def test_checkpoint_missing_component_holds():
    checkpoint = CheckpointRef("c", "m", "t", "s", "h", False, False, True, False)
    assert selective_restore_plan([checkpoint], "c", conversation=True)["status"] == "HELD"


def test_market_requires_challenger():
    assert assess_market_results([result("FUSE")])["reason"] == "CHALLENGER_REQUIRED"


def test_market_requires_matched_cohort():
    assert assess_market_results([result("FUSE", task="t1"), result("X", task="t2")])["reason"] == "UNMATCHED_COHORT"


def test_market_hard_gate_failure():
    assert assess_market_results([result("FUSE"), result("X", privacy_pass=False)])["reason"] == "HARD_GATE_FAILURE"


def test_market_measures_without_self_award():
    measured = assess_market_results([result("FUSE", outcome_score=0.9), result("X", outcome_score=0.8)])
    assert measured["status"] == "MEASURED_MATCHED_COHORT"
    assert measured["market_leadership_proven"] is False


def test_market_independent_judge_input_still_not_self_award():
    measured = assess_market_results([result("FUSE"), result("X")], independent_judge=True)
    assert measured["status"] == "INDEPENDENT_JUDGE_INPUT_READY"
    assert measured["market_leadership_proven"] is False
