import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "evidenceops/runtime/boundary_resolution_controller.py"

spec = importlib.util.spec_from_file_location(
    "boundary_resolution_controller", MODULE_PATH
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _state():
    return json.loads(
        (ROOT / "evidenceops/runtime/boundary_resolution_state.json").read_text()
    )


def _boundary(boundary_id):
    return next(
        item
        for item in _state()["boundaries"]
        if item["boundary_id"] == boundary_id
    )


def clear_private_runtime(monkeypatch):
    for name in [
        "KIM_CANONICAL_BACKEND_ID",
        "KIM_CANONICAL_RECEIPT_ID",
        "KIM_CANONICAL_BACKEND_STATUS",
        "EVIDENCEOPS_CHAT_BRIDGE_URL",
        "EVIDENCEOPS_CLOUD_RUN_URL",
        "EVIDENCEOPS_RUNTIME_DEPLOYMENT_RECEIPT",
        "EVIDENCEOPS_RUNTIME_HEALTH_VERIFIED",
        "EVIDENCEOPS_RUNTIME_WRITEBACK_RECEIPT",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_boundaries_are_workforce_owned_and_not_report_only():
    for boundary in _state()["boundaries"]:
        assert boundary["owner"] == "WORKFORCE"
        assert boundary["report_only_terminal_allowed"] is False
        assert boundary["state"] in {
            "ACTIVE_REPAIR",
            "PARTIALLY_RESOLVED",
            "RESOLVED_IN_PLACE",
            "RESOLVED",
        }


def test_private_control_plane_is_verified_but_runtime_binding_is_explicit(
    monkeypatch,
):
    clear_private_runtime(monkeypatch)
    routes = module.discover_routes()
    inplace = routes["dataverse"]["in_place"]
    assert inplace["descriptor_present"] is True
    assert inplace["control_plane_verified"] is True
    assert inplace["runtime_bound"] is False
    assert inplace["receipt_ref"] == "KIM_CANONICAL_RECEIPT_ID"
    assert inplace["private_values_echoed"] is False

    evaluation = module.evaluate_boundary(
        _boundary("BND-KIM-DATAVERSE"), routes
    )
    assert evaluation["resolved"] is True
    assert evaluation["status"] == "RESOLVED_IN_PLACE"
    assert evaluation["runtime_bound"] is False
    assert evaluation["next_action"] == "VERIFY_RUNTIME_WRITE_THROUGH"


def test_private_runtime_references_bind_without_disclosure(monkeypatch):
    clear_private_runtime(monkeypatch)
    monkeypatch.setenv("KIM_CANONICAL_BACKEND_ID", "private-backend-ci")
    monkeypatch.setenv("KIM_CANONICAL_RECEIPT_ID", "private-receipt-ci")
    monkeypatch.setenv(
        "KIM_CANONICAL_BACKEND_STATUS", "WRITE_AND_READBACK_VERIFIED"
    )
    routes = module.discover_routes()
    inplace = routes["dataverse"]["in_place"]
    assert inplace["runtime_bound"] is True
    serialised = json.dumps(routes)
    assert "private-backend-ci" not in serialised
    assert "private-receipt-ci" not in serialised


def test_chat_alignment_distribution_remains_actionable(monkeypatch):
    clear_private_runtime(monkeypatch)
    boundary = _boundary("BND-CHAT-ALIGNMENT")
    assert boundary["state"] == "PARTIALLY_RESOLVED"
    assert (
        boundary["distribution_receipt_ref"]
        == "KIM_CHAT_DISTRIBUTION_RECEIPT_ID"
    )

    evaluation = module.evaluate_boundary(boundary, module.discover_routes())
    assert evaluation["resolved"] is False
    assert evaluation["status"] == "WAITING_CAPABILITY"
    assert (
        evaluation["next_action"]
        == "DISCOVER_OR_BIND_AUTHORISED_CHAT_BRIDGE"
    )


def test_sovereign_runtime_stays_active_repair_without_deployment_receipts(
    monkeypatch,
):
    clear_private_runtime(monkeypatch)
    evaluation = module.evaluate_boundary(
        _boundary("BND-SOVEREIGN-RUNTIME"), module.discover_routes()
    )
    assert evaluation["resolved"] is False
    assert evaluation["status"] == "ACTIVE_REPAIR"
    assert evaluation["ready_for_live_attempt"] is True
