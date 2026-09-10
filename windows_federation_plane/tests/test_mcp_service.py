from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
import time
import unittest

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from federation_windows_plane.mcp_service import build_server
from federation_windows_plane.firestore_relay import _assert_receipt_matches_task
from federation_windows_plane.oidc_auth import OIDCTokenVerifier
from federation_windows_plane.relay_agent import _dpapi, _signed_headers
from federation_windows_plane.relay_protocol import sign_request


def _b64int(value: int) -> str:
    size = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(size, "big")).decode().rstrip("=")


class FakeRelay:
    def list_devices(self):
        return []


class MCPServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = cls.private_key.public_key().public_numbers()
        key = jwt.PyJWK.from_dict({
            "kty": "RSA", "kid": "test-key", "use": "sig", "alg": "RS256",
            "n": _b64int(numbers.n), "e": _b64int(numbers.e),
        })
        cls.signing_key = SimpleNamespace(key=key.key)

    def verifier(self):
        verifier = OIDCTokenVerifier(
            issuer="https://issuer.example", audience="https://relay.example/mcp",
            jwks_url="https://issuer.example/jwks",
        )
        verifier._jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: self.signing_key)
        return verifier

    def token(self, **changes):
        now = int(time.time())
        claims = {
            "iss": "https://issuer.example", "aud": "https://relay.example/mcp",
            "sub": "owner-kim", "azp": "chatgpt", "iat": now - 1,
            "exp": now + 300, "scope": "fuse.windows",
        }
        claims.update(changes)
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": "test-key"})

    def test_oidc_verifier_accepts_exact_issuer_audience_and_scope(self):
        access = asyncio.run(self.verifier().verify_token(self.token()))
        self.assertIsNotNone(access)
        self.assertEqual(access.subject, "owner-kim")
        self.assertEqual(access.resource, "https://relay.example/mcp")
        self.assertIn("fuse.windows", access.scopes)

    def test_oidc_verifier_rejects_wrong_audience(self):
        access = asyncio.run(self.verifier().verify_token(self.token(aud="https://attacker.example")))
        self.assertIsNone(access)

    def test_mcp_tools_publish_conservative_annotations(self):
        server = build_server(
            relay=FakeRelay(), issuer="https://issuer.example",
            resource_url="https://relay.example/mcp", jwks_url="https://issuer.example/jwks",
        )
        tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
        self.assertEqual(set(tools), {
            "fuse_relay_health", "fuse_list_windows_devices",
            "fuse_issue_windows_enrollment", "fuse_submit_windows_task",
            "fuse_windows_task_status",
        })
        self.assertTrue(tools["fuse_relay_health"].annotations.read_only_hint)
        self.assertFalse(tools["fuse_submit_windows_task"].annotations.destructive_hint)
        self.assertFalse(tools["fuse_submit_windows_task"].annotations.open_world_hint)

    def test_agent_signature_binds_exact_body(self):
        credential = {"device_id": "dev_123", "device_secret": "s" * 48}
        body = b'{"task_id":"task-1"}'
        headers = _signed_headers(credential, method="POST", path="/agent/complete", body=body)
        expected = sign_request(
            credential["device_secret"], method="POST", path="/agent/complete",
            timestamp=headers["x-fuse-timestamp"], nonce=headers["x-fuse-nonce"], body=body,
        )
        self.assertEqual(headers["x-fuse-signature"], expected)
        tampered = sign_request(
            credential["device_secret"], method="POST", path="/agent/complete",
            timestamp=headers["x-fuse-timestamp"], nonce=headers["x-fuse-nonce"], body=b"{}",
        )
        self.assertNotEqual(headers["x-fuse-signature"], tampered)

    def test_credentials_fail_closed_without_windows_dpapi(self):
        import os
        if os.name != "nt":
            with self.assertRaisesRegex(RuntimeError, "WINDOWS_DPAPI_REQUIRED"):
                _dpapi(b"secret", protect=True)

    def test_receipt_cannot_substitute_task_parameters(self):
        task = {
            "task_id": "task-1", "correlation_id": "corr-1",
            "task_type": "run_test", "parameters": {"target": "safe"},
        }
        receipt = {
            "task_id": "task-1", "correlation_id": "corr-1",
            "task_type": "run_test", "task": {**task, "parameters": {"target": "other"}},
        }
        with self.assertRaisesRegex(ValueError, "RECEIPT_TASK_MISMATCH"):
            _assert_receipt_matches_task(receipt, task)

    def test_receipt_accepts_exact_task_envelope(self):
        task = {
            "task_id": "task-1", "correlation_id": "corr-1",
            "task_type": "run_test", "parameters": {"target": "safe"},
        }
        _assert_receipt_matches_task({"task": dict(task)}, task)


if __name__ == "__main__":
    unittest.main()
