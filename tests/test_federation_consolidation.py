from __future__ import annotations
import json
from pathlib import Path
import tempfile

from federation_consolidation.engine import FederationConsolidator, digest

DATA = Path(__file__).parents[1] / "federation_consolidation" / "data"

def engine():
    return FederationConsolidator(DATA)

def test_registry_is_unique_and_complete():
    result = engine().validate_registry()
    assert result.valid, result.errors
    assert result.metrics["system_count"] == 20
    assert result.metrics["unique_system_ids"] == 20
    assert result.metrics["systems_with_one_system_of_record"] == 20

def test_maturity_axes_are_separate():
    state = engine().load("canonical_state.json")
    for system in state["systems"]:
        assert "adoption_state" in system
        assert "maturity_state" in system
        assert "propagation_state" in system

def test_routes_are_bounded():
    result = engine().validate_routes()
    assert result.valid, result.errors
    routes = engine().load("route_registry.json")["routes"]
    assert routes[0]["name"] == "Direct Google Connector"
    assert all("forbidden" in route and route["forbidden"] for route in routes)

def test_all_open_prs_are_classified():
    result = engine().validate_pr_triage()
    assert result.valid, result.errors
    assert result.metrics["classified_open_prs"] == 19

def test_lineage_has_single_parent():
    result = engine().validate_lineage()
    assert result.valid, result.errors

def test_alpha_omega_gate_passes():
    result = engine().alpha_omega_release_gate()
    assert result["eligible"], json.dumps(result, indent=2)

def test_end_to_end_readback_restart_and_rollback():
    with tempfile.TemporaryDirectory() as tmp:
        result = engine().e2e_canary(tmp)
        assert result["passed"]
        assert result["readback_verified"]
        assert result["restart_verified"]
        assert result["rollback_verified"]
        assert len(result["receipt"]["receipt_hash"]) == 64

def test_reconciliation_canary():
    with tempfile.TemporaryDirectory() as tmp:
        result = engine().reconciliation_canary(tmp)
        assert result["valid"]
        assert result["persistence_verified"]

def test_succession_truth_boundary_remains_held_for_drive_until_readback():
    with tempfile.TemporaryDirectory() as tmp:
        result = engine().succession_bundle("TEST-COMMIT", Path(tmp) / "bundle.json")
        bundle = result["bundle"]
        assert bundle["maturity_status"] == "READINESS_VERIFIED_INSTITUTIONAL_COMPLETION_BLOCKED"
        assert "P3:DRIVE_READBACK_REQUIRED" in bundle["blockers"]
        assert result["persisted"]["readback_verified"]

def test_health_score_matches_audit():
    snapshot = engine().load("health_snapshot.json")
    assert snapshot["weighted_overall_score_10"] == 6.8

def test_evidenceops_p09_collision_is_forbidden():
    state = engine().load("canonical_state.json")
    evidenceops = next(item for item in state["systems"] if item["system_id"] == "FO-SYS-006")
    assert evidenceops["owner_workstream"] == "HB-CHAT-OMX-EOPS-001"
    assert evidenceops["collision_policy"] == "REFERENCE_ONLY_NO_DUPLICATE_P09"

def test_receipt_hash_is_deterministic():
    value = {"b": 2, "a": 1}
    assert digest(value) == digest({"a": 1, "b": 2})
