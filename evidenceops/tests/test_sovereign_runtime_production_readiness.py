import json
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_manifest_matches_private_bridge_descriptor():
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
    assert backend["type"] == "PRIVATE_IN_PLACE_BRIDGE"
    assert backend["identifier_ref"] == "KIM_CANONICAL_BACKEND_ID"
    assert backend["receipt_ref"] == "KIM_CANONICAL_RECEIPT_ID"
    assert backend["status_ref"] == "KIM_CANONICAL_BACKEND_STATUS"
    assert backend["private_control_plane_status"] == "WRITE_AND_READBACK_VERIFIED"
    assert backend["public_runtime_default"] == "PRIVATE_REFERENCE_UNRESOLVED"
    assert "spreadsheet_id" not in backend
    assert "receipt_id" not in backend

    assert bridge["identifier_ref"] == backend["identifier_ref"]
    assert bridge["receipt_ref"] == backend["receipt_ref"]
    assert bridge["status_ref"] == backend["status_ref"]
    assert bridge["public_repository_safe"] is True
    assert "spreadsheet_id" not in bridge
    assert "parent_folder_id" not in bridge
    assert "receipt_id" not in bridge

    kdv = next(
        item
        for item in boundary["boundaries"]
        if item["boundary_id"] == "BND-KIM-DATAVERSE"
    )
    assert kdv["state"] == "RESOLVED_IN_PLACE"
    assert kdv["identifier_ref"] == backend["identifier_ref"]
    assert kdv["receipt_ref"] == backend["receipt_ref"]
    assert kdv["public_runtime_default"] == "PRIVATE_REFERENCE_UNRESOLVED"

    runtime_boundary = next(
        item
        for item in boundary["boundaries"]
        if item["boundary_id"] == "BND-SOVEREIGN-RUNTIME"
    )
    assert runtime_boundary["owner"] == "WORKFORCE"
    assert runtime_boundary["state"] == "ACTIVE_REPAIR"
    assert runtime_boundary["report_only_terminal_allowed"] is False

    serialised = json.dumps(
        {"canonical": canonical, "bridge": bridge, "boundary": boundary},
        sort_keys=True,
    )
    assert "PRIVATE_RUNTIME_CONFIG" not in serialised
    assert "PRIVATE_RECEIPT_REFERENCE" not in serialised
    assert canonical["mission_delta_owner"] == "WORKFORCE"
    assert canonical["report_only_terminal_allowed"] is False
