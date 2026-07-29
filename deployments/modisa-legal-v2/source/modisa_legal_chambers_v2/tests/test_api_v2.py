from fastapi.testclient import TestClient

from modisa_v2.api import create_app


def test_health_reports_verified_offline_planes(settings):
    client = TestClient(create_app(settings))
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.0.0"
    assert body["database_ready"] is True
    assert body["proof_ledger_ready"] is True
    assert body["evidence_encryption_ready"] is True
    assert body["durable_workflow_ready"] is True
    assert body["status"] == "degraded"  # live SDK/API key are deliberately absent here


def test_openapi_schema_builds(settings):
    schema = create_app(settings).openapi()
    assert schema["info"]["version"] == "2.0.0"
    assert "/v2/missions" in schema["paths"]
    assert len(schema["paths"]) >= 20
