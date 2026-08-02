from __future__ import annotations

import io
import logging
import secrets
import tempfile
import threading
import unittest
from dataclasses import dataclass
from pathlib import Path

from secure_capability_box import (
    ActionClass,
    AuthorityClass,
    AuthorizationDenied,
    CapabilityRequest,
    CapabilityTokenCodec,
    ExpiredHandle,
    IntegrityFailure,
    InvalidHandle,
    LeastPrivilegePolicy,
    OperationConflict,
    PolicyRule,
    ReplayDetected,
    RevokedHandle,
    SecretReference,
    SecureBoxStore,
    SecureCapabilityBroker,
    WorkloadIdentity,
)
from secure_capability_box.errors import ConnectorFailure
from secure_capability_box.connectors.federation_omega import FederationOmegaConnector
from secure_capability_box.providers.google_secret_manager import GoogleSecretManagerProvider


class Clock:
    def __init__(self, value: int = 1_800_000_000) -> None:
        self.value = value

    def __call__(self) -> float:
        return float(self.value)


class InspectableProvider:
    name = "test-provider"

    def __init__(self, secret_value: bytes) -> None:
        self.buffer = bytearray(secret_value)

    def access(self, reference):
        return self.buffer

    def readiness(self):
        return {"state": "TEST_ONLY", "production_ready": False}


class RecordingConnector:
    name = "test-connector"

    def __init__(self) -> None:
        self.calls = 0
        self.observed = None

    def execute(self, *, action, credential, payload, correlation_id):
        self.calls += 1
        self.observed = bytes(credential)
        return {"state": "SUCCESS", "action": action, "correlation_id": correlation_id}

    def readiness(self):
        return {"state": "TEST_ONLY", "production_ready": False}


def make_request(operation_id="operation-0001", *, action="STATUS", ttl=120):
    return CapabilityRequest(
        mission_id="EESBE-24",
        mission_version=8,
        operation_id=operation_id,
        identity=WorkloadIdentity("workload:test", "federation-omega", AuthorityClass.A1),
        secret=SecretReference("test-provider", "PRIVATE_RUNTIME_CONFIG", "1"),
        connector="test-connector",
        action=action,
        ttl_seconds=ttl,
    )


class SecureCapabilityBoxTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.provider = InspectableProvider(b"ephemeral-fixture-value")
        self.connector = RecordingConnector()
        self.store = SecureBoxStore(Path(self.tempdir.name) / "box.sqlite", clock=self.clock)
        self.codec = CapabilityTokenCodec(secrets.token_bytes(32), key_id="test-kid", clock=self.clock)
        self.policy = LeastPrivilegePolicy([
            PolicyRule(
                connector="test-connector",
                action="STATUS",
                resource_prefix="test-provider:PRIVATE_RUNTIME_CONFIG:",
                minimum_authority=AuthorityClass.A1,
                action_class=ActionClass.READ,
            )
        ])
        self.broker = SecureCapabilityBroker(
            token_codec=self.codec,
            policy=self.policy,
            store=self.store,
            providers=[self.provider],
            connectors=[self.connector],
        )

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def execute(self, token, payload=None):
        return self.broker.execute(
            token,
            subject="workload:test",
            audience="federation-omega",
            payload=payload,
        )

    def test_issue_execute_zeroizes_and_returns_digest_only(self):
        receipt = self.execute(self.broker.issue(make_request()))
        self.assertEqual(receipt.state, "COMPLETED")
        self.assertEqual(self.connector.calls, 1)
        self.assertEqual(self.connector.observed, b"ephemeral-fixture-value")
        self.assertEqual(self.provider.buffer, bytearray(len(self.provider.buffer)))
        self.assertNotIn("ephemeral", str(receipt.as_dict()))

    def test_handle_is_bound_to_subject_and_audience(self):
        token = self.broker.issue(make_request())
        with self.assertRaises(InvalidHandle):
            self.broker.execute(token, subject="workload:other", audience="federation-omega")
        with self.assertRaises(InvalidHandle):
            self.broker.execute(token, subject="workload:test", audience="other")

    def test_tampered_handle_is_rejected(self):
        token = self.broker.issue(make_request())
        parts = token.split(".")
        parts[1] = ("A" if parts[1][0] != "A" else "B") + parts[1][1:]
        with self.assertRaises(InvalidHandle):
            self.execute(".".join(parts))

    def test_expired_handle_is_rejected(self):
        token = self.broker.issue(make_request(ttl=1))
        self.clock.value += 2
        with self.assertRaises(ExpiredHandle):
            self.execute(token)

    def test_revoked_handle_is_rejected(self):
        token = self.broker.issue(make_request())
        self.broker.revoke(token, subject="workload:test", audience="federation-omega", reason="test")
        with self.assertRaises(RevokedHandle):
            self.execute(token)

    def test_consumed_handle_replay_is_rejected(self):
        token = self.broker.issue(make_request())
        self.execute(token)
        with self.assertRaises(ReplayDetected):
            self.execute(token, {"different": True})

    def test_new_handle_replays_completed_operation_without_connector_call(self):
        receipt = self.execute(self.broker.issue(make_request()))
        second = self.broker.issue(make_request())
        replay = self.execute(second)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.result_digest, receipt.result_digest)
        self.assertEqual(self.connector.calls, 1)
        with self.assertRaises(ReplayDetected):
            self.execute(second)

    def test_operation_id_conflict_fails_closed(self):
        self.execute(self.broker.issue(make_request()), {"query": "one"})
        with self.assertRaises(OperationConflict):
            self.execute(self.broker.issue(make_request()), {"query": "two"})

    def test_policy_denies_unlisted_and_consequential_actions(self):
        with self.assertRaises(AuthorizationDenied):
            self.broker.issue(make_request(action="DELETE"))
        consequential = LeastPrivilegePolicy([
            PolicyRule("test-connector", "DEPLOY", "test-provider:", AuthorityClass.A1, ActionClass.DEPLOY)
        ])
        with self.assertRaises(AuthorizationDenied):
            consequential.authorize(make_request(action="DEPLOY"))

    def test_audit_chain_detects_tampering(self):
        self.execute(self.broker.issue(make_request()))
        self.assertTrue(self.store.verify_audit())
        self.store.conn.execute("UPDATE audit_events SET event_json=? WHERE sequence=1", ('{"type":"CHANGED"}',))
        with self.assertRaises(IntegrityFailure):
            self.store.verify_audit()

    def test_metadata_snapshot_restore_preserves_integrity(self):
        self.execute(self.broker.issue(make_request()))
        snapshot = self.store.snapshot()
        restored = SecureBoxStore.restore(Path(self.tempdir.name) / "restored.sqlite", snapshot)
        try:
            self.assertTrue(restored.verify_audit())
            self.assertEqual(restored.snapshot(), snapshot)
            self.assertNotIn("ephemeral-fixture-value", str(snapshot))
        finally:
            restored.close()

    def test_concurrent_consumption_executes_once(self):
        token = self.broker.issue(make_request())
        barrier = threading.Barrier(2)
        outcomes = []

        def run():
            barrier.wait()
            try:
                outcomes.append(self.execute(token).state)
            except Exception as exc:
                outcomes.append(type(exc).__name__)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["COMPLETED", "ReplayDetected"])
        self.assertEqual(self.connector.calls, 1)

    def test_secret_does_not_enter_logs_or_audit(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("evidenceops.secure_capability_box")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            self.execute(self.broker.issue(make_request()))
        finally:
            logger.removeHandler(handler)
        self.assertNotIn("ephemeral-fixture-value", stream.getvalue())
        self.assertNotIn("ephemeral-fixture-value", str(self.store.audit_rows()))

    def test_readiness_does_not_claim_test_provider_is_production(self):
        status = self.broker.readiness()
        self.assertEqual(status["state"], "NOT_PRODUCTION_READY")
        self.assertFalse(status["production_ready"])

    def test_connector_failure_is_sanitized_and_reconcilable(self):
        sensitive_marker = "fixture-sensitive-marker"

        class FailingConnector(RecordingConnector):
            def execute(self, **kwargs):
                raise ConnectorFailure(sensitive_marker)

        self.broker.connectors["test-connector"] = FailingConnector()
        token = self.broker.issue(make_request())
        with self.assertRaises(ConnectorFailure) as caught:
            self.execute(token)
        self.assertNotIn(sensitive_marker, str(caught.exception))
        self.assertEqual(
            [item["operation_id"] for item in self.store.incomplete_operations()],
            ["operation-0001"],
        )


@dataclass
class FakeResponse:
    status_code: int
    value: dict

    def json(self):
        return self.value


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.headers = None
        self.url = None

    def request(self, method, url, **kwargs):
        self.headers = kwargs["headers"]
        self.url = url
        return self.response


class FederationConnectorTests(unittest.TestCase):
    def test_checks_semantic_success_and_removes_local_credential_reference(self):
        transport = FakeTransport(FakeResponse(200, {"state": "SUCCESS", "action": "STATUS"}))
        connector = FederationOmegaConnector("https://operator.example", transport=transport)
        result = connector.execute(
            action="STATUS",
            credential=memoryview(bytearray(b"fixture-token")),
            payload={},
            correlation_id="operation-0001",
        )
        self.assertEqual(result["state"], "SUCCESS")
        self.assertEqual(transport.url, "https://operator.example/execute")
        self.assertIsNone(transport.headers.get("x-fo-admin-token"))

    def test_accepts_live_operator_ok_boolean(self):
        transport = FakeTransport(FakeResponse(200, {"ok": True, "action": "STATUS"}))
        connector = FederationOmegaConnector("https://operator.example", transport=transport)
        result = connector.execute(
            action="STATUS",
            credential=memoryview(bytearray(b"fixture-token")),
            payload={},
            correlation_id="operation-0002",
        )
        self.assertTrue(result["ok"])


class GoogleSecretManagerProviderTests(unittest.TestCase):
    class Payload:
        data = b"provider-fixture"
        data_crc32c = None

    class Response:
        payload = None

    class Client:
        def __init__(self):
            self.request = None

        def access_secret_version(self, *, request):
            self.request = request
            response = GoogleSecretManagerProviderTests.Response()
            response.payload = GoogleSecretManagerProviderTests.Payload()
            return response

    def test_accesses_exact_version_without_disclosing_value(self):
        client = self.Client()
        provider = GoogleSecretManagerProvider(client=client)
        value = provider.access(SecretReference(
            "google-secret-manager",
            "projects/PRIVATE_RUNTIME_CONFIG/secrets/PRIVATE_RUNTIME_CONFIG",
            "7",
        ))
        self.assertEqual(value, bytearray(b"provider-fixture"))
        self.assertEqual(
            client.request,
            {"name": "projects/PRIVATE_RUNTIME_CONFIG/secrets/PRIVATE_RUNTIME_CONFIG/versions/7"},
        )


if __name__ == "__main__":
    unittest.main()
