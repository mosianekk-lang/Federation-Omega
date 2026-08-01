import json
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_manifest_matches_verified_kim_dataverse_bridge():
    repo = Path(__file__).parents[2]
    canonical = read_json(
        repo / "evidenceops/runtime/ACTIVE_SOVEREIGN_TRANSLATOR.json"
    )
    runtime = read_json(
        repo / "evidenceops/runtime_service/active_manifest.json"
    )
    bridge = read_json(
        repo / "evidenceops/runtime/kim_dataverse_inplace_bridge.json"
    )
    boundary = read_json(
        repo / "evidenceops/runtime/boundary_resolution_state.json"
    )

    assert runtime == canonical
    backend = canonical["canonical_backend"]
    assert backend["status"] == "WRITE_AND_READBACK_VERIFIED"
    assert backend["spreadsheet_id"] == bridge["spreadsheet_id"]
    assert backend["receipt_id"] == bridge["receipt_id"]
    assert bridge["write_verified"] is True
    assert bridge["readback_verified"] is True

    kdv = next(
        item
        for item in boundary["boundaries"]
        if item["boundary_id"] == "BND-KIM-DATAVERSE"
    )
    assert kdv["state"] == "RESOLVED_IN_PLACE"
    assert kdv["spreadsheet_id"] == backend["spreadsheet_id"]
    assert kdv["receipt_id"] == backend["receipt_id"]

    assert canonical["mission_delta_owner"] == "WORKFORCE"
    assert canonical["report_only_terminal_allowed"] is False
