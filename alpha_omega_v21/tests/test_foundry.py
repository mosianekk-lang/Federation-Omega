from alpha_omega_foundry import OperationsFabric, SolutionFoundry


def test_operational_release(tmp_path):
    receipt = SolutionFoundry(tmp_path).operational_release(
        {
            "title": "Test System",
            "description": "Build a working operational system",
            "users": ["owner"],
            "outcomes": ["verified operation"],
        }
    )
    assert receipt["state"] == "OPERATIONAL_VERIFIED_LOCAL"
    assert receipt["artifact"]["state"] == "ARTIFACT_VERIFIED"
    assert receipt["readback"]["pass"]
    assert receipt["health"]["pass"]
    assert receipt["persistence"]["pass"]
    assert receipt["rollback"]["target_absent"]


def test_operations_fabric(tmp_path):
    operations = OperationsFabric(tmp_path)
    assert operations.detect_drift({"a": 1}, {"a": 2})["drift"]
    failure = operations.classify_failure("rate limit timeout")
    assert failure["category"] == "TRANSIENT"
    assert operations.choose_repair(failure)["automatic"]
    assert operations.learn({"event": 1}, {"ok": True})["lesson_id"].startswith("LRN-")
    assert operations.retirement_decision(
        {"value_score": 0.1, "failure_rate": 0.4, "replacement_ready": True}
    )["retire"]


def test_portfolio_order(tmp_path):
    ranked = SolutionFoundry(tmp_path).score_portfolio(
        [
            {"title": "A", "description": "a", "value": 1, "risk": 9},
            {
                "title": "B",
                "description": "b",
                "value": 10,
                "urgency": 10,
                "reuse": 10,
                "risk": 1,
                "complexity": 1,
            },
        ]
    )
    assert ranked[0]["idea"]["title"] == "B"
