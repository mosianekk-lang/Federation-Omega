import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "evidenceops/runtime/boundary_resolution_controller.py"

spec = importlib.util.spec_from_file_location("boundary_resolution_controller", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _state():
    return json.loads((ROOT / "evidenceops/runtime/boundary_resolution_state.json").read_text())


def test_boundaries_are_workforce_owned_and_not_report_only():
    for boundary in _state()["boundaries"]:
        assert boundary["owner"] == "WORKFORCE"
        assert boundary["report_only_terminal_allowed"] is False
        assert boundary["state"] in {"ACTIVE_REPAIR", "RESOLVED_IN_PLACE", "RESOLVED"}


def test_kim_dataverse_in_place_bridge_is_verified():
    routes = module.discover_routes()
    assert routes["dataverse"]["in_place"]["configured"] is True
    assert routes["dataverse"]["in_place"]["verified"] is True
    assert routes["dataverse"]["in_place"]["receipt_id"] == "RCP-KDV-INPLACE-001"

    boundary = next(b for b in _state()["boundaries"] if b["boundary_id"] == "BND-KIM-DATAVERSE")
    evaluation = module.evaluate_boundary(boundary, routes)
    assert evaluation["resolved"] is True
    assert evaluation["status"] == "RESOLVED_IN_PLACE"
    assert evaluation["receipt_id"] == "RCP-KDV-INPLACE-001"


def test_chat_alignment_remains_actionable_without_bridge(monkeypatch):
    monkeypatch.delenv("EVIDENCEOPS_CHAT_BRIDGE_URL", raising=False)
    routes = module.discover_routes()
    boundary = next(b for b in _state()["boundaries"] if b["boundary_id"] == "BND-CHAT-ALIGNMENT")
    evaluation = module.evaluate_boundary(boundary, routes)
    assert evaluation["resolved"] is False
    assert evaluation["status"] == "WAITING_CAPABILITY"
    assert evaluation["next_action"] == "DISCOVER_OR_BIND_AUTHORISED_CHAT_BRIDGE"
