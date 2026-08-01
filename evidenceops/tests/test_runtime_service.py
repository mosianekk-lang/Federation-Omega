import importlib.util
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def load_runtime_module():
    path = Path(__file__).parents[1] / "runtime_service" / "main.py"
    spec = importlib.util.spec_from_file_location("evidenceops_runtime_service", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runtime_creates_workforce_owned_delta(monkeypatch):
    repo = Path(__file__).parents[2]
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv(
            "EVIDENCEOPS_ACTIVE_MANIFEST",
            str(repo / "evidenceops" / "runtime" / "ACTIVE_SOVEREIGN_TRANSLATOR.json"),
        )
        monkeypatch.setenv("EVIDENCEOPS_STATE_DB", str(Path(td) / "state.db"))
        monkeypatch.delenv("KIM_DATAVERSE_URL", raising=False)
        monkeypatch.delenv("KIM_DATAVERSE_ACCESS_TOKEN", raising=False)
        module = load_runtime_module()
        client = TestClient(module.app)
        assert client.get("/health").status_code == 200
        response = client.post(
            "/missions",
            json={
                "mission_id": "M1",
                "directive_id": "D1",
                "source_input": "Complete the EvidenceOps production runtime.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["mission_delta"]["owner"] == "WORKFORCE"
        assert body["mission_delta"]["status"] == "ACTIVE_REPAIR"
        assert body["dataverse"]["status"] == "SYNC_PACKAGE_CREATED"
        assert body["runtime"]["report_only_terminal_allowed"] is False
