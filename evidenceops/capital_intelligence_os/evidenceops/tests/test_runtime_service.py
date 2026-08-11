import importlib.util
import json
import sys
import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


def load_runtime_module():
    path = Path(__file__).parents[1] / "runtime_service" / "main.py"
    name = f"evidenceops_runtime_service_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configure_base(monkeypatch, state_db):
    repo = Path(__file__).parents[2]
    monkeypatch.setenv(
        "EVIDENCEOPS_ACTIVE_MANIFEST",
        str(repo / "evidenceops" / "runtime_service" / "active_manifest.json"),
    )
    monkeypatch.setenv("EVIDENCEOPS_STATE_DB", str(state_db))
    monkeypatch.delenv("KIM_DATAVERSE_URL", raising=False)
    monkeypatch.delenv("KIM_DATAVERSE_ACCESS_TOKEN", raising=False)


def test_public_runtime_does_not_claim_unresolved_private_backend(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        configure_base(monkeypatch, Path(td) / "state.db")
        monkeypatch.delenv("KIM_CANONICAL_BACKEND_ID", raising=False)
        monkeypatch.delenv("KIM_CANONICAL_RECEIPT_ID", raising=False)
        monkeypatch.delenv("KIM_CANONICAL_BACKEND_STATUS", raising=False)
        module = load_runtime_module()
        client = TestClient(module.app)

        health = client.get("/health")
        assert health.status_code == 200
        backend = health.json()["canonical_backend"]
        assert backend["verified"] is False
        assert backend["configured"] is False
        assert backend["status"] == "PRIVATE_REFERENCE_UNRESOLVED"
        assert backend["private_values_echoed"] is False

        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is False

        response = client.post(
            "/missions",
            json={
                "mission_id": "M-UNBOUND",
                "directive_id": "D-UNBOUND",
                "source_input": "Keep unresolved boundaries workforce-owned.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["maturity"] == "DOCTRINE_ACTIVE"
        assert body["mission_delta"]["owner"] == "WORKFORCE"
        assert body["mission_delta"]["status"] == "ACTIVE_REPAIR"


def test_private_references_verify_without_being_echoed(monkeypatch):
    private_id = "ci-private-backend-reference"
    private_receipt = "ci-private-receipt-reference"
    with tempfile.TemporaryDirectory() as td:
        configure_base(monkeypatch, Path(td) / "state.db")
        monkeypatch.setenv("KIM_CANONICAL_BACKEND_ID", private_id)
        monkeypatch.setenv("KIM_CANONICAL_RECEIPT_ID", private_receipt)
        monkeypatch.setenv(
            "KIM_CANONICAL_BACKEND_STATUS", "WRITE_AND_READBACK_VERIFIED"
        )
        module = load_runtime_module()
        client = TestClient(module.app)

        health = client.get("/health")
        assert health.status_code == 200
        payload = health.json()
        backend = payload["canonical_backend"]
        assert backend["verified"] is True
        assert backend["configured"] is True
        assert backend["identifier_present"] is True
        assert backend["receipt_present"] is True
        assert backend["private_values_echoed"] is False
        serialised = json.dumps(payload)
        assert private_id not in serialised
        assert private_receipt not in serialised

        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True
        assert ready.json()["runtime_write_through_ready"] is False

        response = client.post(
            "/missions",
            json={
                "mission_id": "M-BOUND",
                "directive_id": "D-BOUND",
                "source_input": "Complete the EvidenceOps production runtime.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["maturity"] == "MISSION_STATE_BOUND"
        assert body["mission_delta"]["owner"] == "WORKFORCE"
        assert body["mission_delta"]["status"] == "ACTIVE_REPAIR"
        assert body["canonical_backend"]["verified"] is True
        assert body["runtime"]["report_only_terminal_allowed"] is False
