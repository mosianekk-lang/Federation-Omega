from __future__ import annotations

import asyncio
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.fuse_mobile_gateway.app import create_app
from services.fuse_mobile_gateway.bindings import (
    DEVICE_TOKEN_PREFIX,
    DeviceCredentialManager,
    DeviceRecord,
    KDVSnapshot,
    KDVSheetsReader,
    VertexKDVChatExecutor,
    runtime_from_environment,
)
from services.fuse_mobile_gateway.runtime import (
    ExecutionResult,
    GatewayRuntime,
    RuntimeBindingError,
    SessionCodec,
    VerifiedIdentity,
)


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self.consumed: set[str] = set()
        self.devices: dict[str, DeviceRecord] = {}
        self.last_enrollment_hash: str | None = None
        self.last_device_hash: str | None = None

    async def consume_enrollment(self, *, enrollment_hash: str, subject: str, device_hash: str) -> None:
        if enrollment_hash in self.consumed:
            raise RuntimeBindingError("OWNER_ENROLLMENT_ALREADY_CONSUMED")
        self.consumed.add(enrollment_hash)
        self.devices[device_hash] = DeviceRecord(subject=subject, active=True)
        self.last_enrollment_hash = enrollment_hash
        self.last_device_hash = device_hash

    async def get_device(self, device_hash: str) -> DeviceRecord | None:
        return self.devices.get(device_hash)

    async def revoke_device(self, device_hash: str) -> None:
        record = self.devices.get(device_hash)
        if record is not None:
            self.devices[device_hash] = DeviceRecord(subject=record.subject, active=False)


class StaticHealth:
    async def capabilities(self, identity: VerifiedIdentity):
        del identity
        return ()


class StaticExecutor:
    async def execute(self, *, request, decision, identity) -> ExecutionResult:
        del request, decision, identity
        return ExecutionResult(text="ok", trace_id="trace-static")


class FakeKDV:
    def __init__(self, snapshot: KDVSnapshot) -> None:
        self.snapshot = snapshot

    async def read(self) -> KDVSnapshot:
        return self.snapshot


class FakeVertex:
    def __init__(self) -> None:
        self.prompt = ""

    def generate(self, *, prompt: str, temperature: float, max_output_tokens: int):
        self.prompt = prompt
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        return {
            "text": "grounded answer",
            "provider": "GOOGLE_VERTEX_AI_GEMINI",
            "provider_request_id": "provider-req-123",
            "model_identity": "gemini-2.5-flash-001",
        }


class FuseMobileRuntimeBindingsV1Tests(unittest.TestCase):
    def test_one_use_enrollment_stores_only_hash_and_revocation_blocks_new_sessions(self) -> None:
        bootstrap = "owner-enrollment-" + ("Z" * 48)
        expected_hash = hashlib.sha256(bootstrap.encode()).hexdigest()
        device_token = DEVICE_TOKEN_PREFIX + ("D" * 48)
        repository = InMemoryDeviceRepository()
        manager = DeviceCredentialManager(
            repository,
            owner_subject="owner:kim",
            enrollment_sha256=expected_hash,
            token_factory=lambda: device_token,
        )

        identity, issued = asyncio.run(manager.enroll(bootstrap))
        self.assertEqual(identity.subject, "owner:kim")
        self.assertEqual(issued, device_token)
        self.assertEqual(repository.last_enrollment_hash, expected_hash)
        self.assertEqual(repository.last_device_hash, hashlib.sha256(device_token.encode()).hexdigest())
        self.assertNotEqual(repository.last_device_hash, device_token)

        verified = asyncio.run(manager.verify(device_token))
        self.assertEqual(verified.subject, "owner:kim")
        with self.assertRaisesRegex(RuntimeBindingError, "OWNER_ENROLLMENT_ALREADY_CONSUMED"):
            asyncio.run(manager.enroll(bootstrap))

        asyncio.run(manager.revoke(device_token, expected_subject="owner:kim"))
        with self.assertRaisesRegex(RuntimeBindingError, "DEVICE_CREDENTIAL_INVALID"):
            asyncio.run(manager.verify(device_token))

    def test_gateway_enroll_session_and_revoke_flow_is_fail_closed(self) -> None:
        bootstrap = "owner-enrollment-" + ("Y" * 48)
        expected_hash = hashlib.sha256(bootstrap.encode()).hexdigest()
        device_token = DEVICE_TOKEN_PREFIX + ("E" * 48)
        repository = InMemoryDeviceRepository()
        manager = DeviceCredentialManager(
            repository,
            owner_subject="owner:kim",
            enrollment_sha256=expected_hash,
            token_factory=lambda: device_token,
        )
        runtime = GatewayRuntime(
            session_codec=SessionCodec(b"fuse-mobile-runtime-test-secret-32bytes-minimum"),
            identity_verifier=manager,
            device_manager=manager,
            health_provider=StaticHealth(),
            chat_executor=StaticExecutor(),
        )
        client = TestClient(create_app(runtime))

        enroll = client.post("/v1/enroll", headers={"Authorization": f"Bearer {bootstrap}"})
        self.assertEqual(enroll.status_code, 200, enroll.text)
        payload = enroll.json()
        self.assertEqual(payload["device_token"], device_token)
        self.assertFalse(payload["device_token_recoverable"])
        access = payload["access_token"]

        session = client.post("/v1/session", headers={"Authorization": f"Bearer {device_token}"})
        self.assertEqual(session.status_code, 200, session.text)
        self.assertEqual(session.json()["subject"], "owner:kim")

        revoke = client.post(
            "/v1/device/revoke",
            headers={"Authorization": f"Bearer {access}"},
            json={"device_token": device_token},
        )
        self.assertEqual(revoke.status_code, 200, revoke.text)
        self.assertEqual(revoke.json()["status"], "REVOKED")

        rejected = client.post("/v1/session", headers={"Authorization": f"Bearer {device_token}"})
        self.assertEqual(rejected.status_code, 401, rejected.text)
        self.assertEqual(rejected.json()["detail"]["reason"], "DEVICE_CREDENTIAL_INVALID")

    def test_kdv_rows_preserve_freshness_and_do_not_flatten_expired_state(self) -> None:
        now = datetime(2026, 9, 9, 0, 10, tzinfo=timezone(timedelta(hours=2)))
        values = [
            ["Projection_ID", "State", "Observed_At_SAST", "Expires_At_SAST", "Next_Action"],
            ["old", "OLD_STATE", "2026-09-08T22:00:00+02:00", "2026-09-08T22:30:00+02:00", "REREAD"],
            ["new", "CURRENT_STATE", "2026-09-09T00:05:00+02:00", "2026-09-09T00:35:00+02:00", "CONTINUE"],
        ]
        rows, fresh, stale = KDVSheetsReader._rows(values, now=now)
        self.assertEqual(fresh, 1)
        self.assertEqual(stale, 1)
        by_id = {row["Projection_ID"]: row for row in rows}
        self.assertEqual(by_id["old"]["_runtime_freshness"], "STALE")
        self.assertEqual(by_id["new"]["_runtime_freshness"], "FRESH")

    def test_vertex_executor_carries_kdv_provenance_and_stale_warning(self) -> None:
        snapshot = KDVSnapshot(
            source_ref="KDV:test:FUSE_MISSION_CURRENTNESS!A1:N3",
            range_name="FUSE_MISSION_CURRENTNESS!A1:N3",
            observed_at="2026-09-09T00:10:00+02:00",
            rows=(
                {"Projection_ID": "old", "State": "OLD", "_runtime_freshness": "STALE"},
                {"Projection_ID": "new", "State": "CURRENT", "_runtime_freshness": "FRESH"},
            ),
            fresh_count=1,
            stale_count=1,
        )
        vertex = FakeVertex()
        executor = VertexKDVChatExecutor(FakeKDV(snapshot), vertex)

        class Request:
            intent = "What is my current FUSE mission?"

        class Decision:
            strategy = "THINK"
            components = ("FUSE", "KDV")

        result = asyncio.run(
            executor.execute(
                request=Request(),
                decision=Decision(),
                identity=VerifiedIdentity("owner:kim"),
            )
        )
        self.assertEqual(result.trace_id, "provider-req-123")
        self.assertEqual(result.provider, "GOOGLE_VERTEX_AI_GEMINI")
        self.assertEqual(result.model, "gemini-2.5-flash-001")
        self.assertEqual(result.source_refs, (snapshot.source_ref,))
        self.assertIn("Rows marked STALE are historical evidence only", vertex.prompt)
        self.assertIn("What is my current FUSE mission?", vertex.prompt)
        self.assertIn('"stale_count": 1', vertex.prompt)

    def test_no_runtime_environment_preserves_source_only_fail_closed_state(self) -> None:
        env = {
            "FUSE_MOBILE_SESSION_SECRET_B64": "",
            "FUSE_MOBILE_OWNER_SUBJECT": "",
            "FUSE_MOBILE_OWNER_ENROLLMENT_SHA256": "",
        }
        with patch.dict(os.environ, env, clear=False):
            runtime = runtime_from_environment()
        self.assertFalse(runtime.enrollment_ready)
        self.assertFalse(runtime.session_ready)
        self.assertFalse(runtime.execution_ready)


if __name__ == "__main__":
    unittest.main()
