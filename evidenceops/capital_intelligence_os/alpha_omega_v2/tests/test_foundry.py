import json
from pathlib import Path

from alpha_omega_foundry import (
    GitHubReleaseArtifactAdapter,
    GoogleDriveBinaryAdapter,
    OperationsFabric,
    SolutionFoundry,
)


def _idea() -> dict:
    return {
        "title": "Test System",
        "description": "Build a working operational system",
        "users": ["owner"],
        "outcomes": ["verified operation"],
    }


def _github_environment() -> dict[str, str]:
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "mosianekk-lang/Federation-Omega",
        "GITHUB_WORKFLOW": "Alpha Omega Foundry CI",
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_REF": "refs/pull/1/merge",
    }


def test_operational_release_uses_full_contract(tmp_path):
    receipt = SolutionFoundry(tmp_path).operational_release(_idea())
    assert receipt["state"] == "OPERATIONAL_VERIFIED_LOCAL"
    assert receipt["discover"]["available"]
    assert receipt["authority"]["authorised"]
    assert receipt["snapshot"]["state"] == "SNAPSHOT_CREATED"
    assert receipt["deploy"]["state"] == "DEPLOYED"
    assert receipt["execute"]["state"] == "EXECUTED"
    assert receipt["readback"]["pass"]
    assert receipt["health"]["pass"]
    assert receipt["persistence"]["pass"]
    assert receipt["rollback"]["target_absent"]
    assert receipt["maintenance"]["state"] == "MAINTENANCE_HEALTHY"


def test_github_release_artifact_contract(tmp_path):
    receipt = SolutionFoundry(tmp_path).github_release_artifact(
        _idea(), environment=_github_environment()
    )
    assert receipt["state"] == "PROVIDER_STAGED_VERIFIED"
    assert all(receipt["gates"].values())
    assert (tmp_path / "github_release").is_dir()
    assert list((tmp_path / "github_release").glob("*.zip"))
    assert list((tmp_path / "github_release").glob("*.manifest.json"))
    assert (tmp_path / "provider_receipts" / "github_release_artifact_receipt.json").is_file()


def test_github_release_artifact_fails_closed_without_authority(tmp_path):
    foundry = SolutionFoundry(tmp_path)
    build = foundry.build_solution(_idea())
    adapter = GitHubReleaseArtifactAdapter(tmp_path, environment={})
    receipt = adapter.run_contract(Path(build["package_dir"]), tmp_path / "release")
    assert receipt["state"] == "PROVIDER_BLOCKED"
    assert receipt["gates"]["discover"] is False
    assert receipt["gates"]["authority"] is False


def test_github_artifact_is_deterministic_for_same_source(tmp_path):
    foundry = SolutionFoundry(tmp_path)
    build = foundry.build_solution(_idea())
    source = Path(build["package_dir"])
    env = _github_environment()
    first = GitHubReleaseArtifactAdapter(tmp_path / "first", environment=env)
    second = GitHubReleaseArtifactAdapter(tmp_path / "second", environment=env)
    first_receipt = first.run_contract(source, tmp_path / "first_release")
    second_receipt = second.run_contract(source, tmp_path / "second_release")
    first_manifest = json.loads(
        next((tmp_path / "first_release").glob("*.manifest.json")).read_text(encoding="utf-8")
    )
    second_manifest = json.loads(
        next((tmp_path / "second_release").glob("*.manifest.json")).read_text(encoding="utf-8")
    )
    assert first_receipt["state"] == second_receipt["state"] == "PROVIDER_STAGED_VERIFIED"
    assert first_manifest["sha256"] == second_manifest["sha256"]


def test_operations_fabric_classifies_and_repairs(tmp_path):
    operations = OperationsFabric(tmp_path)
    assert operations.detect_drift({"a": 1}, {"a": 2})["drift"]
    transient = operations.classify_failure("rate limit timeout")
    assert transient["category"] == "TRANSIENT"
    assert operations.choose_repair(transient)["action"] == "RETRY_WITH_BACKOFF"
    integrity = operations.classify_failure("checksum corrupt")
    assert operations.choose_repair(integrity)["action"] == "ROLLBACK_AND_REBUILD"
    authority = operations.classify_failure("permission forbidden")
    assert operations.choose_repair(authority)["automatic"] is False


def test_maintenance_cycle_writes_proof_and_learning(tmp_path):
    operations = OperationsFabric(tmp_path)
    report = operations.maintenance_cycle(
        "SYS-MAINT-001",
        expected={"version": "2.4.0", "provider": "github_actions"},
        actual={"version": "2.4.0", "provider": "github_actions"},
    )
    assert report["state"] == "MAINTENANCE_HEALTHY"
    assert report["drift"]["drift"] is False
    assert report["repair"]["action"] == "NO_ACTION"
    assert operations.heartbeat_file.is_file()
    assert operations.learning_file.is_file()
    assert operations.maintenance_report_file.is_file()
    assert len(operations.heartbeat_file.read_text(encoding="utf-8").splitlines()) == 2


def test_retirement_controls_require_multiple_triggers(tmp_path):
    operations = OperationsFabric(tmp_path)
    assert operations.retirement_decision({"value_score": 0.1})["retire"] is False
    assert operations.retirement_decision(
        {"value_score": 0.1, "failure_rate": 0.5, "replacement_ready": True}
    )["retire"] is True


def test_google_drive_binary_adapter_validates_provider_receipt(tmp_path):
    receipt = {
        "provider": "google_drive_binary",
        "discover": {"available": True},
        "authority": {"authorised": True, "scope": "drive_file_create"},
        "snapshot": {"state": "DESTINATION_INVENTORY_CAPTURED"},
        "deploy": {"state": "BINARY_UPLOADED"},
        "execute": {"state": "PROVIDER_ACCEPTED"},
        "readback": {"pass": True},
        "health": {"pass": True},
        "persistence": {"pass": True},
        "rollback": {"target_absent": True},
        "proof": {"receipt_id": "RCP-DRIVE-1", "drive_file_id": "file-1"},
    }
    path = tmp_path / "drive_receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    proof = GoogleDriveBinaryAdapter(path).proof_receipt()
    assert proof["state"] == "OPERATIONAL_VERIFIED_BINARY"
    assert all(proof["gates"].values())
    assert proof["drive_file_id"] == "file-1"


def test_google_drive_binary_adapter_rejects_failed_readback(tmp_path):
    receipt = {
        "provider": "google_drive_binary",
        "discover": {"available": True},
        "authority": {"authorised": True},
        "snapshot": {"state": "DESTINATION_INVENTORY_CAPTURED"},
        "deploy": {"state": "BINARY_UPLOADED"},
        "execute": {"state": "PROVIDER_ACCEPTED"},
        "readback": {"pass": False},
        "health": {"pass": True},
        "persistence": {"pass": True},
        "rollback": {"target_absent": True},
        "proof": {"receipt_id": "RCP-DRIVE-2", "drive_file_id": "file-2"},
    }
    path = tmp_path / "drive_receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    proof = GoogleDriveBinaryAdapter(path).proof_receipt()
    assert proof["state"] == "FAILED"
    assert proof["gates"]["readback"] is False


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
