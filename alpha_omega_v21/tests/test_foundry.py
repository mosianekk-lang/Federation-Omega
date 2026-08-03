import json
from pathlib import Path

from alpha_omega_foundry import (
    GoogleDriveManifestAdapter,
    OperationsFabric,
    SolutionFoundry,
)


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


def test_google_drive_manifest_adapter_receipt():
    receipt_path = Path("provider_receipts/google_drive_manifest_20260803.json")
    adapter = GoogleDriveManifestAdapter(receipt_path)
    assert adapter.discover()["available"]
    assert adapter.validate_authority()["authorised"]
    assert adapter.snapshot()["state"] == "INVENTORY_CAPTURED"
    assert adapter.deploy()["state"] == "DOCUMENT_CREATED"
    assert adapter.execute()["state"] == "CONTENT_WRITTEN"
    assert adapter.read_back()["pass"]
    assert adapter.health_check()["pass"]
    assert adapter.persistence_check()["pass"]
    assert adapter.rollback()["target_absent"]
    proof = adapter.proof_receipt()
    assert proof["state"] == "OPERATIONAL_VERIFIED_MANIFEST"
    assert all(proof["gates"].values())
    assert proof["binary_package_state"] == "PROVIDER_BLOCKED_FILE_EGRESS"


def test_google_drive_manifest_adapter_rejects_failed_gate(tmp_path):
    source = Path("provider_receipts/google_drive_manifest_20260803.json")
    receipt = json.loads(source.read_text(encoding="utf-8"))
    receipt["readback"]["pass"] = False
    failed = tmp_path / "failed_drive_receipt.json"
    failed.write_text(json.dumps(receipt), encoding="utf-8")
    proof = GoogleDriveManifestAdapter(failed).proof_receipt()
    assert proof["state"] == "FAILED"
    assert proof["gates"]["readback"] is False
