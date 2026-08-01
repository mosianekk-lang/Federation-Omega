import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "evidenceops/runtime/boundary_resolution_controller.py"

spec = importlib.util.spec_from_file_location("boundary_resolution_controller", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_boundaries_are_workforce_owned_and_not_report_only():
    state = json.loads((ROOT / "evidenceops/runtime/boundary_resolution_state.json").read_text())
    for boundary in state["boundaries"]:
        assert boundary["owner"] == "WORKFORCE"
        assert boundary["state"] == "ACTIVE_REPAIR"
        assert boundary["report_only_terminal_allowed"] is False


def test_controller_emits_actionable_next_steps(monkeypatch):
    monkeypatch.delenv("EVIDENCEOPS_CHAT_BRIDGE_URL", raising=False)
    monkeypatch.delenv("KIM_DATAVERSE_URL", raising=False)
    monkeypatch.delenv("KIM_DATAVERSE_CLIENT_ID", raising=False)
    monkeypatch.delenv("KIM_DATAVERSE_SECRET_REF", raising=False)
    state = json.loads((ROOT / "evidenceops/runtime/boundary_resolution_state.json").read_text())
    routes = module.discover_routes()
    evaluations = [module.evaluate_boundary(b, routes) for b in state["boundaries"]]
    assert all(e["status"] in {"WAITING_CAPABILITY", "READY_TO_ATTEMPT"} for e in evaluations)
    assert all(e.get("next_action") for e in evaluations)
