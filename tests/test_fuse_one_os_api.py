"""Behavioral courts for the FUSE-ONE projection over the existing SOL API."""
from __future__ import annotations

import secrets
import asyncio

import pytest
import httpx

from services.fuse_mobile_gateway.runtime import GatewayRuntime, SessionCodec, VerifiedIdentity
from sol_61_runtime.sol_62 import GatewayPolicy, Sol62Runtime, WorkloadIdentityPolicy


class SameThreadClient:
    """ASGI requests share the SQLite runtime's owning thread, as Uvicorn does."""
    def __init__(self, app):
        self.app = app

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def request(self, method, path, **kwargs):
        async def request():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app), base_url="http://fuse.test"
            ) as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(request())


@pytest.fixture
def api(tmp_path, monkeypatch):
    # Import-time runtime state and the test context stay in isolated storage.
    monkeypatch.setenv("SOL62_CLIENT_ROOT", str(tmp_path / "default-sol"))
    monkeypatch.setenv("SOL62_STRATEGY_ROOT", str(tmp_path / "strategy"))
    monkeypatch.setenv("FUSE_GENESIS_HOST_ROOT", str(tmp_path / "genesis"))
    from services.sol62_client_runtime import app as module

    codec = SessionCodec(secrets.token_bytes(32))
    gateway = GatewayRuntime(session_codec=codec)
    runtime = Sol62Runtime(
        tmp_path / "sol",
        gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
        identity_policy=WorkloadIdentityPolicy(
            allowed_issuers={"test-issuer"}, audience="test-audience", subject_prefix="test:"
        ),
    )
    context = module.ServiceContext(gateway=gateway, sol=runtime)
    token, _ = codec.issue(VerifiedIdentity("test:owner"))
    try:
        yield SameThreadClient(module.create_app(context)), {"X-Fuse-Authorization": "Bearer " + token}, context, module
    finally:
        context.close()


def test_catalog_requires_verified_session_before_source_read(api, monkeypatch):
    client, _, _, module = api
    def unexpected_read():
        pytest.fail("unauthorized request read the catalog")
    monkeypatch.setattr(module, "build_unified_service_catalog", unexpected_read)
    assert client.get("/v1/os/catalog").status_code == 401
    assert client.get("/v1/os/catalog", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_catalog_reports_source_gaps_without_provider_promotion(api):
    client, headers, context, _ = api
    before = context.sol.verify_integrity()
    response = client.get("/v1/os/catalog", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["counts"]["registered_services"] == 35
    assert result["counts"]["source_supported"] == 16
    assert result["counts"]["source_missing"] == 19
    assert result["counts"]["runtime_assessed"] == 0
    assert all(row["callable_now"] is None for row in result["services"])
    assert all(row["runtime_readiness"] == "NOT_ASSESSED" for row in result["services"])
    assert context.sol.verify_integrity() == before
    assert context.gateway.execution_ready is False


def test_bearer_header_compatibility_and_catalog_repeated_read(api):
    client, headers, _, _ = api
    bearer = {"Authorization": headers["X-Fuse-Authorization"]}
    assert client.get("/v1/os/catalog", headers=bearer).json() == client.get(
        "/v1/os/catalog", headers=bearer
    ).json()


def test_catalog_corruption_is_held_and_does_not_leak_paths(api, monkeypatch):
    client, headers, _, module = api
    def damaged():
        raise ValueError("private/server/path/invalid-source")
    monkeypatch.setattr(module, "build_unified_service_catalog", damaged)
    response = client.get("/v1/os/catalog", headers=headers)
    assert response.status_code == 503
    assert response.json() == {"detail": {"status": "HELD", "reason": "FUSE_OS_CATALOG_INVALID"}}
    assert "private/server" not in response.text


def test_unknown_mission_stays_404_and_does_not_become_new_mission(api):
    client, headers, _, _ = api
    response = client.get("/v1/missions/does-not-exist", headers=headers)
    assert response.status_code in (404, 403)


def test_new_read_surface_does_not_enable_provider_executor(api):
    client, headers, _, _ = api
    assert client.get("/v1/os/catalog", headers=headers).status_code == 200
    health = client.get("/health").json()
    assert health["fuse_execution_ready"] is False
    assert health["worker_identity_ready"] is False


def test_same_owner_create_retry_preserves_state_without_new_events(api):
    client, headers, context, _ = api
    body = {"mission_id": "retry-mission", "objective": "Preserve this objective"}
    first = client.post("/v1/missions", headers=headers, json=body)
    assert first.status_code == 200
    before = context.sol.control.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    second = client.post("/v1/missions", headers=headers, json=body)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert context.sol.control.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before


def test_create_cannot_reassign_an_existing_other_owner_mission(api):
    client, headers, context, _ = api
    body = {"mission_id": "owner-mission", "objective": "Owner-specific objective"}
    assert client.post("/v1/missions", headers=headers, json=body).status_code == 200
    other, _ = context.gateway.session_codec.issue(VerifiedIdentity("test:other"))
    other_headers = {"Authorization": "Bearer " + other}
    before = context.sol.control.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    response = client.post("/v1/missions", headers=other_headers, json=body)
    assert response.status_code == 409
    assert client.get("/v1/missions/owner-mission", headers=other_headers).status_code == 404
    assert client.get("/v1/missions/owner-mission", headers=headers).status_code == 200
    assert context.sol.control.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before


def test_create_retry_with_changed_objective_is_conflict(api):
    client, headers, _, _ = api
    body = {"mission_id": "immutable-intent", "objective": "Original objective"}
    assert client.post("/v1/missions", headers=headers, json=body).status_code == 200
    response = client.post("/v1/missions", headers=headers, json={**body, "objective": "Changed objective"})
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "MISSION_ID_CONFLICT"


def test_owned_mission_store_busy_is_recoverable_hold_without_partial_state(api):
    import sqlite3
    client, headers, context, _ = api
    holder = sqlite3.connect(context.sol.control.path, isolation_level=None)
    context.sol.control.db.execute("PRAGMA busy_timeout=30")
    try:
        holder.execute("BEGIN IMMEDIATE")
        response = client.post("/v1/missions", headers=headers, json={"mission_id": "busy-owned", "objective": "Atomic creation"})
        assert response.status_code == 503
        assert response.json() == {"detail": {"status": "HELD", "reason": "MISSION_STORE_BUSY"}}
        assert context.sol.control.get_state("sol62.mission", "busy-owned") is None
        assert context.sol.control.get_state("sol62.client.mission", "busy-owned") is None
    finally:
        holder.execute("ROLLBACK")
        holder.close()
        context.sol.control.db.execute("PRAGMA busy_timeout=10000")
    response = client.post("/v1/missions", headers=headers, json={"mission_id": "busy-owned", "objective": "Atomic creation"})
    assert response.status_code == 200


def test_api_mid_admission_failure_leaves_no_orphan_or_event(api, monkeypatch):
    client, headers, context, _ = api
    before = context.sol.control.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    original = context.sol.control.append_event
    def fail(aggregate, kind, payload):
        result = original(aggregate, kind, payload)
        if kind == "SOL62_OWNER_INTENT_BOUND":
            raise RuntimeError("injected atomic registration failure")
        return result
    monkeypatch.setattr(context.sol.control, "append_event", fail)
    with pytest.raises(RuntimeError, match="injected"):
        client.post("/v1/missions", headers=headers, json={"mission_id": "rolled-back", "objective": "Complete admission"})
    assert context.sol.control.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before
    assert context.sol.control.db.execute("SELECT COUNT(*) FROM state WHERE item_key=? OR item_key=?", ("rolled-back", "rolled-back|MISSION")).fetchone()[0] == 0
