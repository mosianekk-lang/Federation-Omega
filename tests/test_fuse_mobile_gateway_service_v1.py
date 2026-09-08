from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from federation.mobile_gateway.fuse_mobile_v1 import Capability
from services.fuse_mobile_gateway.app import create_app
from services.fuse_mobile_gateway.runtime import (
    ExecutionResult,
    GatewayRuntime,
    SessionCodec,
    SourceOnlyCapabilityHealth,
    VerifiedIdentity,
)


class FakeIdentityVerifier:
    async def verify(self, credential: str) -> VerifiedIdentity:
        if credential != "bootstrap-owner-token":
            raise AssertionError("unexpected test credential")
        return VerifiedIdentity("owner:kim")


class FakeHealth:
    async def capabilities(self, identity: VerifiedIdentity) -> tuple[Capability, ...]:
        self.identity = identity
        return (
            Capability(
                "GOOGLE-AI-STUDIO-GEMINI-DEVELOPER-API",
                "MODEL_PROVIDER",
                "sovara-ai-studio",
                health="VERIFIED_SCOPED",
                authority="A2_ACTION_SPECIFIC",
                freshness_ttl_seconds=300,
            ),
            Capability(
                "OPENROUTER-PROCESSOR-MESH",
                "MODEL_ROUTER",
                "sovara-openrouter",
                health="CONFIGURED",
                authority="UNPROVEN",
            ),
            Capability("KDV", "DATA_PLANE", "kdv", health="HEALTHY", authority="READ_ONLY"),
        )


class FakeExecutor:
    def __init__(self):
        self.calls = []

    async def execute(self, *, request, decision, identity) -> ExecutionResult:
        self.calls.append((request, decision, identity))
        return ExecutionResult(
            text="verified response",
            trace_id="trace-001",
            provider="GOOGLE_AI_STUDIO",
            model="provider-discovered-gemini",
            source_refs=("KDV:canary",),
        )


def ready_runtime() -> tuple[GatewayRuntime, FakeExecutor]:
    executor = FakeExecutor()
    runtime = GatewayRuntime(
        session_codec=SessionCodec(b"fuse-mobile-test-session-secret-32bytes-minimum"),
        identity_verifier=FakeIdentityVerifier(),
        health_provider=FakeHealth(),
        chat_executor=executor,
    )
    return runtime, executor


def issue_session(client: TestClient) -> str:
    response = client.post("/v1/session", headers={"Authorization": "Bearer bootstrap-owner-token"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


class FuseMobileGatewayServiceV1Tests(unittest.TestCase):
    def test_default_runtime_is_source_ready_but_not_runtime_ready(self) -> None:
        client = TestClient(create_app())
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "SOURCE_READY_RUNTIME_BINDING_REQUIRED")
        self.assertFalse(body["session_ready"])
        self.assertFalse(body["execution_ready"])
        self.assertFalse(body["provider_credentials_in_client"])

    def test_session_issuance_fails_closed_without_runtime_bindings(self) -> None:
        client = TestClient(create_app())
        response = client.post("/v1/session", headers={"Authorization": "Bearer anything"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["reason"], "SESSION_SIGNER_UNBOUND")

    def test_authenticated_manifest_exposes_ai_studio_without_secret_material(self) -> None:
        runtime, _ = ready_runtime()
        client = TestClient(create_app(runtime))
        token = issue_session(client)
        response = client.get("/v1/capabilities", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = {capability["capability_id"] for capability in body["capabilities"]}
        self.assertIn("GOOGLE-AI-STUDIO-GEMINI-DEVELOPER-API", ids)
        self.assertIn("GOOGLE_AI_STUDIO", body["model_scopes"])
        raw = response.text.lower()
        for forbidden in ("gemini_api_key", "openrouter_api_key", "sk-", "authorization: bearer"):
            self.assertNotIn(forbidden, raw)

    def test_source_only_health_keeps_ai_studio_configured_not_runtime_verified(self) -> None:
        provider = SourceOnlyCapabilityHealth()
        capabilities = __import__("asyncio").run(provider.capabilities(VerifiedIdentity("owner:kim")))
        ai_studio = next(c for c in capabilities if c.capability_id.startswith("GOOGLE-AI-STUDIO"))
        self.assertEqual(ai_studio.health, "CONFIGURED")
        self.assertNotEqual(ai_studio.authority, "A2_PROVIDER_VERIFIED")

    def test_tampered_session_is_rejected(self) -> None:
        runtime, _ = ready_runtime()
        client = TestClient(create_app(runtime))
        token = issue_session(client)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        response = client.get("/v1/capabilities", headers={"Authorization": f"Bearer {tampered}"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["reason"], "SESSION_SIGNATURE_INVALID")

    def test_safe_chat_executes_but_configured_only_openrouter_falls_back(self) -> None:
        runtime, executor = ready_runtime()
        client = TestClient(create_app(runtime))
        token = issue_session(client)
        response = client.post(
            "/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "intent": "compare the routes",
                "mode": "THINK",
                "requested_models": ["openrouter:auto"],
                "effect_class": "READ_ONLY",
                "verification": "HIGH",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trace_id"], "trace-001")
        self.assertEqual(response.json()["provider"], "GOOGLE_AI_STUDIO")
        self.assertEqual(len(executor.calls), 1)
        decision = executor.calls[0][1]
        self.assertIn("PROVIDER_FALLBACK", decision.components)
        self.assertNotIn("sovara.creative.openrouter_processor_mesh", decision.components)

    def test_consequential_effect_is_held_before_executor(self) -> None:
        runtime, executor = ready_runtime()
        client = TestClient(create_app(runtime))
        token = issue_session(client)
        response = client.post(
            "/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "intent": "send this email",
                "mode": "EXECUTE",
                "effect_class": "EXTERNAL_COMMUNICATION",
                "verification": "HIGH",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["reason"], "OWNER_EFFECT_APPROVAL_REQUIRED")
        self.assertEqual(executor.calls, [])


if __name__ == "__main__":
    unittest.main()
