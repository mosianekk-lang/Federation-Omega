import importlib.util
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def load_runtime_module():
    path = Path(__file__).parents[1] / "runtime_service" / "main.py"
    spec = importlib.util.spec_from_file_location(
        "evidenceops_runtime_service", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_uses_verified_canonical_bridge(monkeypatch):
    repo = Path(__file__).parents[2]
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv(
            "EVIDENCEOPS_ACTIVE_MANIFEST",
            str(
                repo
                / "evidenceops"
                / "runtime_service"
                / "active_manifest.json"
            ),
        )
        monkeypatch.setenv(
            "EVIDENCEOPS_STATE_DB", str(Path(td) / "state.db")
        )
        monkeypatch.delenv("KIM_DATAVERSE_URL", raising=False)
        monkeypatch.delenv("KIM_DATAVERSE_ACCESS_TOKEN", raising=False)
        module = load_runtime_module()
        client = TestClient(module.app)

        health = client.get("/health")
        assert health.status_code == 200
        h = health.json()
        assert h["canonical_backend"]["verified"] is True
        assert (
            h["canonical_backend"]["receipt_id"]
            == "RCP-KDV-INPLACE-001"
        )
        assert (
            h["native_microsoft_dataverse"]["status"]
            == "OPTIONAL_PARITY_ROUTE_UNBOUND"
        )

        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True
        assert ready.json()["runtime_write_through_ready"] is False

        response = client.post(
            "/missions",
            json={
                "mission_id": "M1",
                "directive_id": "D1",
                "source_input": (
                    "Complete the EvidenceOps production runtime."
                ),
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["maturity"] == "MISSION_STATE_BOUND"
        assert body["mission_delta"]["owner"] == "WORKFORCE"
        assert body["mission_delta"]["status"] == "ACTIVE_REPAIR"
        assert body["canonical_backend"]["verified"] is True
        assert (
            body["native_microsoft_dataverse"]["status"]
            == "OPTIONAL_PARITY_SYNC_PACKAGE_CREATED"
        )
        assert body["runtime"]["report_only_terminal_allowed"] is False
