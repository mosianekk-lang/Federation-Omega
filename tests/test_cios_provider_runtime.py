from __future__ import annotations

import json
import socket
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from evidenceops.capital_intelligence_os.provider_runtime import (
    ProviderRuntimeApplication,
    ProviderRuntimeConfig,
    ProviderRuntimeServer,
)


SHA = "a" * 40
TOKEN = "forge-provider-runtime-test-token-000001"


def _config(root: Path, *, port: int = 8080) -> ProviderRuntimeConfig:
    return ProviderRuntimeConfig(
        bearer_token=TOKEN,
        db_path=str(root / "cios.sqlite"),
        audit_path=str(root / "audit.sqlite"),
        expected_source_sha=SHA,
        runtime_source_sha=SHA,
        runtime_identity="test-runtime@example.invalid",
        host="127.0.0.1",
        port=port,
    )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "X-Tenant-ID": "TENANT-TEST",
        "X-User-ID": "USER-TEST",
    }


class CIOSProviderRuntimeTests(unittest.TestCase):
    def test_configuration_fails_closed_on_source_drift_or_memory_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                ProviderRuntimeConfig(
                    bearer_token=TOKEN,
                    db_path=":memory:",
                    audit_path=str(root / "audit.sqlite"),
                    expected_source_sha=SHA,
                    runtime_source_sha="b" * 40,
                    runtime_identity="runtime",
                )

    def test_health_is_authenticated_and_never_self_certifies_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = ProviderRuntimeApplication(_config(Path(tmp)))
            try:
                denied, _ = app.handle("GET", "/health", {}, b"")
                self.assertEqual(401, denied)
                status, payload = app.handle("GET", "/health", _headers(), b"")
                self.assertEqual(200, status)
                self.assertEqual("PROVIDER_CANDIDATE", payload["runtime_mode"])
                self.assertEqual(SHA, payload["runtime_source_sha"])
                self.assertFalse(payload["provider_identity_readback_verified"])
                self.assertFalse(payload["provider_deployment_verified"])
                self.assertFalse(payload["external_effects_enabled"])
                self.assertTrue(payload["database_quick_check"])
                self.assertTrue(payload["audit_chain_valid"])
            finally:
                app.close()

    def test_consequential_financial_routes_remain_unexposed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = ProviderRuntimeApplication(_config(Path(tmp)))
            try:
                status, payload = app.handle("POST", "/trade", _headers(), b"{}")
                self.assertEqual(403, status)
                self.assertEqual("CONSEQUENTIAL_ROUTE_NOT_EXPOSED", payload["error"])
            finally:
                app.close()

    def test_event_and_audit_persist_across_runtime_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config(root)
            body = json.dumps(
                {
                    "event_type": "PROVIDER_RUNTIME_TEST",
                    "source": "forge-test",
                    "subject_id": "subject-1",
                    "payload": {"safe": True},
                    "domain": "GOVERNANCE",
                    "information_class": "PUBLIC",
                    "materiality": 0.1,
                    "event_id": "forge-provider-runtime-event-1",
                    "occurred_at": "2026-08-12T10:00:00+00:00",
                }
            ).encode()
            headers = {**_headers(), "Idempotency-Key": "forge-provider-runtime-event-1"}
            app = ProviderRuntimeApplication(config)
            try:
                status, _ = app.handle("POST", "/v1/events", headers, body)
                self.assertEqual(200, status)
            finally:
                app.close()
            reopened = ProviderRuntimeApplication(config)
            try:
                self.assertTrue(reopened.store.quick_check())
                self.assertTrue(reopened.audit.verify())
                events = reopened.store.load_events("TENANT-TEST")
                self.assertTrue(any(event.event_id == "forge-provider-runtime-event-1" for event in events))
            finally:
                reopened.close()

    def test_real_http_canary_serves_authenticated_semantic_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            app = ProviderRuntimeApplication(_config(root, port=port))
            server = ProviderRuntimeServer(app)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/health",
                    headers=_headers(),
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read())
                self.assertEqual("PROVIDER_CANDIDATE", payload["runtime_mode"])
                self.assertTrue(payload["database_quick_check"])
                self.assertFalse(payload["provider_deployment_verified"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                app.close()

    def test_runtime_container_uses_dedicated_entrypoint(self) -> None:
        dockerfile = Path("evidenceops/capital_intelligence_os/Dockerfile.runtime")
        if not dockerfile.exists():
            self.skipTest("deployment Dockerfiles are intentionally excluded from the standalone core export")
        text = dockerfile.read_text(encoding="utf-8")
        self.assertIn("USER 10001", text)
        self.assertIn("evidenceops.capital_intelligence_os.provider_runtime", text)
        self.assertNotIn("verify_release", text)


if __name__ == "__main__":
    unittest.main()
