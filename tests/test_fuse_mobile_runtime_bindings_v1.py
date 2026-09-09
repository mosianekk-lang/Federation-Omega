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
    IAP_EXPECTED_AUDIENCE,
    IAP_ISSUER,
    SESSION_TOKEN_PREFIX,
    DeviceCredentialManager,
    DeviceRecord,
    IAPOwnerIdentityVerifier,
    KDVSnapshot,
    KDVSheetsReader,
    OpaqueSessionManager,
    SessionRecord,
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

    async def put_device(self, *, subject: str, device_hash: str) -> None:
        self.devices[device_hash] = DeviceRecord(subject=subject, active=True)
        self.last_device_hash = device_hash

    async def get_device(self, device_hash: str) -> DeviceRecord | None:
        return self.devices.get(device_hash)

    async def revoke_device(self, device_hash: str) -> None:
        record = self.devices.get(device_hash)
        if record is not None:
            self.devices[device_hash] = DeviceRecord(subject=record.subject, active=False)


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self.last_session_hash: str | None = None

    async def put_session(
        self,
        *,
        session_hash: str,
        subject: str,
        device_hash: str,
        issued_at_epoch: int,
        expires_at_epoch: int,
    ) -> None:
        del issued_at_epoch
        self.sessions[session_hash] = SessionRecord(subject, device_hash, expires_at_epoch)
        self.last_session_hash = session_hash

    async def get_session(self, session_hash: str) -> SessionRecord | None:
        return self.sessions.get(session_hash)


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
        expected_device_hash = hashlib.sha256(device_token.encode()).hexdigest()
        self.assertEqual(repository.last_device_hash, expected_device_hash)
        self.assertEqual(identity.claims["device_hash"], expected_device_hash)
        self.assertNotEqual(repository.last_device_hash, device_token)

        verified = asyncio.run(manager.verify(device_token))
        self.assertEqual(verified.subject, "owner:kim")
        self.assertEqual(verified.claims["device_hash"], expected_device_hash)
        with self.assertRaisesRegex(RuntimeBindingError, "OWNER_ENROLLMENT_ALREADY_CONSUMED"):
            asyncio.run(manager.enroll(bootstrap))

        asyncio.run(manager.revoke(device_token, expected_subject="owner:kim"))
        with self.assertRaisesRegex(RuntimeBindingError, "DEVICE_CREDENTIAL_INVALID"):
            asyncio.run(manager.verify(device_token))

    def test_iap_owner_enrollment_uses_signed_assertion_and_hash_only_device_state(self) -> None:
        owner_email = "owner@example.com"
        email_hash = hashlib.sha256(owner_email.encode()).hexdigest()
        device_token = DEVICE_TOKEN_PREFIX + ("I" * 48)
        session_token = SESSION_TOKEN_PREFIX + ("J" * 48)
        devices = InMemoryDeviceRepository()
        sessions = InMemorySessionRepository()
        manager = DeviceCredentialManager(
            devices,
            owner_subject="owner:kim",
            token_factory=lambda: device_token,
        )

        def verify(assertion: str, audience: str):
            self.assertEqual(assertion, "signed-iap-assertion")
            self.assertEqual(audience, IAP_EXPECTED_AUDIENCE)
            return {
                "iss": IAP_ISSUER,
                "aud": audience,
                "email": owner_email,
                "sub": "accounts.google.com:owner-123",
            }

        runtime = GatewayRuntime(
            session_manager=OpaqueSessionManager(sessions, devices, token_factory=lambda: session_token),
            identity_verifier=manager,
            owner_identity_verifier=IAPOwnerIdentityVerifier(
                owner_subject="owner:kim",
                owner_email_sha256=email_hash,
                verify_fn=verify,
            ),
            device_manager=manager,
            health_provider=StaticHealth(),
            chat_executor=StaticExecutor(),
        )
        response = TestClient(create_app(runtime)).post(
            "/v1/enroll",
            headers={"X-Goog-IAP-JWT-Assertion": "signed-iap-assertion"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["subject"], "owner:kim")
        self.assertEqual(payload["owner_identity_source"], "GOOGLE_IAP")
        self.assertEqual(payload["device_token"], device_token)
        self.assertEqual(payload["access_token"], session_token)
        expected_device_hash = hashlib.sha256(device_token.encode()).hexdigest()
        self.assertEqual(devices.last_device_hash, expected_device_hash)
        self.assertNotIn(device_token, devices.devices)
        self.assertIn(expected_device_hash, devices.devices)

    def test_iap_owner_enrollment_rejects_wrong_owner_email(self) -> None:
        owner_hash = hashlib.sha256(b"owner@example.com").hexdigest()
        devices = InMemoryDeviceRepository()
        sessions = InMemorySessionRepository()
        manager = DeviceCredentialManager(devices, owner_subject="owner:kim")
        verifier = IAPOwnerIdentityVerifier(
            owner_subject="owner:kim",
            owner_email_sha256=owner_hash,
            verify_fn=lambda assertion, audience: {
                "iss": IAP_ISSUER,
                "aud": audience,
                "email": "other@example.com",
                "sub": "other-subject",
            },
        )
        runtime = GatewayRuntime(
            session_manager=OpaqueSessionManager(sessions, devices),
            identity_verifier=manager,
            owner_identity_verifier=verifier,
            device_manager=manager,
            health_provider=StaticHealth(),
            chat_executor=StaticExecutor(),
        )
        response = TestClient(create_app(runtime)).post(
            "/v1/enroll",
            headers={"X-Goog-IAP-JWT-Assertion": "signed-but-wrong-owner"},
        )
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()["detail"]["reason"], "IAP_OWNER_EMAIL_INVALID")
        self.assertEqual(devices.devices, {})

    def test_opaque_sessions_store_only_hash_expire_and_require_device_binding(self) -> None:
        devices = InMemoryDeviceRepository()
        sessions = InMemorySessionRepository()
        device_hash = hashlib.sha256(b"device-a").hexdigest()
        devices.devices[device_hash] = DeviceRecord("owner:kim", True)
        now = [1_000]
        token = SESSION_TOKEN_PREFIX + ("S" * 48)
        manager = OpaqueSessionManager(
            sessions,
            devices,
            ttl_seconds=900,
            token_factory=lambda: token,
            clock=lambda: now[0],
        )
        identity = VerifiedIdentity("owner:kim", {"device_hash": device_hash})
        issued, expires = asyncio.run(manager.issue(identity))
        self.assertEqual(issued, token)
        self.assertEqual(expires, 1_900)
        expected_hash = hashlib.sha256(token.encode()).hexdigest()
        self.assertEqual(sessions.last_session_hash, expected_hash)
        self.assertNotIn(token, sessions.sessions)
        self.assertEqual(asyncio.run(manager.verify(token)).subject, "owner:kim")

        now[0] = 1_900
        with self.assertRaisesRegex(RuntimeBindingError, "SESSION_EXPIRED"):
            asyncio.run(manager.verify(token))
        with self.assertRaisesRegex(RuntimeBindingError, "SESSION_DEVICE_BINDING_REQUIRED"):
            asyncio.run(manager.issue(VerifiedIdentity("owner:kim")))

    def test_gateway_secretless_enroll_session_and_revoke_invalidates_existing_session(self) -> None:
        bootstrap = "owner-enrollment-" + ("Y" * 48)
        expected_hash = hashlib.sha256(bootstrap.encode()).hexdigest()
        device_token = DEVICE_TOKEN_PREFIX + ("E" * 48)
        session_tokens = iter(
            [SESSION_TOKEN_PREFIX + ("A" * 48), SESSION_TOKEN_PREFIX + ("B" * 48)]
        )
        devices = InMemoryDeviceRepository()
        sessions = InMemorySessionRepository()
        manager = DeviceCredentialManager(
            devices,
            owner_subject="owner:kim",
            enrollment_sha256=expected_hash,
            token_factory=lambda: device_token,
        )
        session_manager = OpaqueSessionManager(
            sessions,
            devices,
            token_factory=lambda: next(session_tokens),
        )
        runtime = GatewayRuntime(
            session_manager=session_manager,
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
        enrollment_session = payload["access_token"]
        self.assertTrue(enrollment_session.startswith(SESSION_TOKEN_PREFIX))

        session = client.post("/v1/session", headers={"Authorization": f"Bearer {device_token}"})
        self.assertEqual(session.status_code, 200, session.text)
        existing_session = session.json()["access_token"]
        self.assertEqual(session.json()["subject"], "owner:kim")
        before = client.get("/v1/federation/health", headers={"Authorization": f"Bearer {existing_session}"})
        self.assertEqual(before.status_code, 200, before.text)

        revoke = client.post(
            "/v1/device/revoke",
            headers={"Authorization": f"Bearer {enrollment_session}"},
            json={"device_token": device_token},
        )
        self.assertEqual(revoke.status_code, 200, revoke.text)
        self.assertEqual(revoke.json()["status"], "REVOKED")

        rejected_existing = client.get(
            "/v1/federation/health",
            headers={"Authorization": f"Bearer {existing_session}"},
        )
        self.assertEqual(rejected_existing.status_code, 401, rejected_existing.text)
        self.assertEqual(rejected_existing.json()["detail"]["reason"], "SESSION_DEVICE_REVOKED")

        rejected_new = client.post("/v1/session", headers={"Authorization": f"Bearer {device_token}"})
        self.assertEqual(rejected_new.status_code, 401, rejected_new.text)
        self.assertEqual(rejected_new.json()["detail"]["reason"], "DEVICE_CREDENTIAL_INVALID")

    def test_legacy_hmac_codec_remains_compatible_for_deterministic_tests(self) -> None:
        codec = SessionCodec(b"fuse-mobile-runtime-test-secret-32bytes-minimum")
        token, expires = codec.issue(VerifiedIdentity("owner:kim"), now=100)
        self.assertEqual(expires, 1000)
        self.assertEqual(codec.verify(token, now=999).subject, "owner:kim")

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
            executor.execute(request=Request(), decision=Decision(), identity=VerifiedIdentity("owner:kim"))
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
            "FUSE_MOBILE_OWNER_SUBJECT": "",
            "FUSE_MOBILE_OWNER_ENROLLMENT_SHA256": "",
            "FUSE_MOBILE_OWNER_EMAIL_SHA256": "",
        }
        with patch.dict(os.environ, env, clear=False):
            runtime = runtime_from_environment()
        self.assertFalse(runtime.enrollment_ready)
        self.assertFalse(runtime.iap_enrollment_ready)
        self.assertFalse(runtime.session_ready)
        self.assertFalse(runtime.execution_ready)


if __name__ == "__main__":
    unittest.main()
