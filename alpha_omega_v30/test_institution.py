from institution import (
    ActionContract,
    AlphaOmegaInstitution,
    CausalMultiversePlanner,
    CyberneticController,
    Invariant,
    RealityState,
    ReliabilityModel,
)


def test_release_eligible_when_all_gates_pass():
    state = {"deployed": True, "rollback": True}
    reality = RealityState(state, state, state, state, state)
    contract = ActionContract(
        "ACT-1",
        "deploy release",
        ["tests", "snapshot", "authority"],
        ["create_revision", "shift_canary"],
        ["delete_last_good", "expose_secret"],
        ["deployment_receipt", "health_readback", "rollback_report"],
    )
    result = AlphaOmegaInstitution().evaluate_release(
        reality,
        contract,
        {"tests": True, "snapshot": True, "authority": True},
        ["create_revision", "shift_canary"],
        state,
        [Invariant("ROLLBACK_EXISTS", lambda s: s["rollback"])],
        {
            "architect": "APPROVE",
            "builder": "APPROVE",
            "security": "APPROVE",
            "verifier": "APPROVE",
            "operations": "APPROVE",
            "evidence": "APPROVE",
        },
    )
    assert result["eligible"] is True


def test_forbidden_effect_blocks_release():
    contract = ActionContract("A", "x", [], ["create"], ["delete"], [])
    assert contract.validate({}, ["delete"])["valid"] is False


def test_hysteresis_and_ultrastability():
    controller = CyberneticController(1.0, 0.8, 0.95)
    assert controller.step(0.7)["mode"] == "DEGRADED"
    assert controller.step(0.9)["mode"] == "DEGRADED"
    assert controller.step(0.96)["mode"] == "HEALTHY"
    controller.record_repair(False)
    controller.record_repair(False)
    adapted = controller.record_repair(False)
    assert adapted["adapted"] is True
    assert adapted["gain"] == 0.25


def test_multiverse_selects_best_weighted_candidate():
    result = CausalMultiversePlanner().select(
        [
            {"id": "cheap", "metrics": {"value": 0.7, "resilience": 0.5}},
            {"id": "strong", "metrics": {"value": 0.8, "resilience": 0.9}},
        ],
        {"value": 0.4, "resilience": 0.6},
    )
    assert result["id"] == "strong"


def test_reliability_model_detects_false_completion():
    model = ReliabilityModel()
    model.record(0.95, False, claimed_complete=True)
    report = model.report()
    assert report["false_completions"] == 1
    assert report["calibration_error"] > 0.9
