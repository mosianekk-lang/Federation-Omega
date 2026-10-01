import os
import unittest
from unittest.mock import patch

from frontier_convergence.gemini_adapter import GeminiAdapter
from services.gemini_gateway.interactions_v2 import (
    InteractionsError,
    VertexInteractionsClient,
    normalize_interaction_response,
)
from services.gemini_gateway.app import (
    CANONICAL_PROJECT_ID,
    Gateway,
    GatewayError,
    MetadataIdentity,
    VertexGeminiClient,
    sha256,
)


class FakeIdentity:
    def snapshot(self):
        return {
            "project_id": CANONICAL_PROJECT_ID,
            "project_number": "257649435135",
            "service_account": "sv-gemini-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
            "authority_mode": "CLOUD_RUN_SERVICE_ACCOUNT_ADC",
        }

    def access_token(self):
        return "opaque-test-token"


class FakeClient:
    location = "global"
    model = "gemini-2.5-flash"

    def __init__(self, text):
        self.text = text

    def generate(self, **kwargs):
        nonce_token = self.text
        return {
            "provider": "GOOGLE_VERTEX_AI_GEMINI",
            "provider_request_id": "resp-123",
            "model_identity": "gemini-2.5-flash-001",
            "configured_model": self.model,
            "finish_state": "STOP",
            "usage": {"promptTokenCount": 5, "candidatesTokenCount": 5, "totalTokenCount": 10},
            "latency_ms": 12,
            "provider_identity": FakeIdentity().snapshot(),
            "request_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "text": nonce_token,
        }


class FakeInteractionsClient:
    location = "global"
    model = "gemini-3.8-flash"

    def __init__(self, text):
        self.text = text

    def interact(self, **kwargs):
        return {
            "provider": "GOOGLE_VERTEX_AI_INTERACTIONS",
            "protocol": "VERTEX_AI_INTERACTIONS_REST",
            "provider_request_id": "int-123",
            "interaction_id": "int-123",
            "interaction_status": "completed",
            "model_identity": "gemini-3.8-flash",
            "model_identity_source": "BOUND_REQUEST",
            "configured_model": self.model,
            "finish_state": "completed",
            "usage": {"total_tokens": 10, "total_input_tokens": 5, "total_output_tokens": 5},
            "latency_ms": 10,
            "provider_identity": FakeIdentity().snapshot(),
            "request_sha256": "c" * 64,
            "response_sha256": "d" * 64,
            "store": False,
            "text": self.text,
        }


class GeminiGatewayTests(unittest.TestCase):
    def test_planner_defaults_to_cloud_run_adc(self):
        plan = GeminiAdapter.compile_call(
            mission_id="M",
            model_ref="gemini-2.5-flash",
            contents="hello",
        )
        self.assertEqual(plan.credential_reference, "CLOUD_RUN_ADC")
        self.assertEqual(plan.protocol, "VERTEX_AI_GENERATE_CONTENT_REST")

    def test_handshake_requires_exact_nonce(self):
        nonce = "CG-TEST-001"
        gateway = Gateway(identity=FakeIdentity(), client=FakeClient(f"HANDSHAKE_RECEIPT:{nonce}"))
        receipt = gateway.handshake({"semantic_nonce": nonce})
        self.assertEqual(receipt["status"], "VERIFIED")
        self.assertEqual(receipt["semantic_nonce"], nonce)
        self.assertTrue(receipt["semantic_verified"])
        self.assertEqual(receipt["provider_identity"]["project_id"], CANONICAL_PROJECT_ID)
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

    def test_handshake_fails_closed_on_wrong_semantics(self):
        gateway = Gateway(identity=FakeIdentity(), client=FakeClient("wrong"))
        with self.assertRaises(GatewayError) as ctx:
            gateway.handshake({"semantic_nonce": "CG-TEST-002"})
        self.assertEqual(ctx.exception.code, "SEMANTIC_NONCE_MISMATCH")

    def test_handshake_rejects_missing_or_whitespace_nonce(self):
        gateway = Gateway(identity=FakeIdentity(), client=FakeClient("unused"))
        with self.assertRaises(GatewayError):
            gateway.handshake({})
        with self.assertRaises(GatewayError):
            gateway.handshake({"semantic_nonce": "bad nonce"})

    def test_vertex_requires_provider_identity_fields(self):
        identity = FakeIdentity()

        def fetch_json(request):
            return 200, {
                "responseId": "r-1",
                "modelVersion": "gemini-2.5-flash-001",
                "candidates": [{
                    "content": {"parts": [{"text": "ok"}]},
                    "finishReason": "STOP",
                }],
                "usageMetadata": {"totalTokenCount": 3},
            }

        client = VertexGeminiClient(identity, fetch_json=fetch_json)
        result = client.generate(prompt="hello")
        self.assertEqual(result["provider_request_id"], "r-1")
        self.assertEqual(result["text"], "ok")
        self.assertNotIn("opaque-test-token", str(result))

    def test_vertex_fails_when_response_identity_missing(self):
        identity = FakeIdentity()

        def fetch_json(request):
            return 200, {
                "candidates": [{
                    "content": {"parts": [{"text": "ok"}]},
                    "finishReason": "STOP",
                }],
                "usageMetadata": {"totalTokenCount": 3},
            }

        client = VertexGeminiClient(identity, fetch_json=fetch_json)
        with self.assertRaises(GatewayError) as ctx:
            client.generate(prompt="hello")
        self.assertEqual(ctx.exception.code, "VERTEX_PROVIDER_IDENTITY_INCOMPLETE")

    def test_non_global_location_is_rejected(self):
        with self.assertRaises(GatewayError) as ctx:
            VertexGeminiClient(FakeIdentity(), location="us-central1")
        self.assertEqual(ctx.exception.code, "NON_CANONICAL_VERTEX_LOCATION")

    def test_health_does_not_claim_provider_execution(self):
        gateway = Gateway(identity=FakeIdentity(), client=FakeClient("unused"))
        self.assertFalse(gateway.health()["provider_execution_verified"])
    def test_interactions_handshake_requires_exact_nonce(self):
        nonce = "GV2-TEST-001"
        client = FakeInteractionsClient(f"INTERACTIONS_HANDSHAKE_RECEIPT:{nonce}")
        gateway = Gateway(
            identity=FakeIdentity(),
            client=FakeClient("unused"),
            interactions_client=client,
        )
        receipt = gateway.interactions_handshake({"semantic_nonce": nonce})
        self.assertEqual(receipt["schema"], "SOVARA_GEMINI_INTERACTIONS_HANDSHAKE_RECEIPT_V2")
        self.assertEqual(receipt["status"], "VERIFIED")
        self.assertEqual(receipt["protocol"], "VERTEX_AI_INTERACTIONS_REST")
        self.assertEqual(receipt["interaction_id"], "int-123")
        self.assertEqual(receipt["interaction_status"], "completed")
        self.assertEqual(receipt["model_identity"], "gemini-3.8-flash")
        self.assertIs(receipt["store"], False)
        self.assertTrue(receipt["semantic_verified"])
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

    def test_interactions_handshake_fails_closed_on_wrong_semantics(self):
        gateway = Gateway(
            identity=FakeIdentity(),
            client=FakeClient("unused"),
            interactions_client=FakeInteractionsClient("wrong"),
        )
        with self.assertRaises(GatewayError) as ctx:
            gateway.interactions_handshake({"semantic_nonce": "GV2-TEST-002"})
        self.assertEqual(ctx.exception.code, "INTERACTIONS_SEMANTIC_NONCE_MISMATCH")

    def test_vertex_interactions_client_uses_stateless_request_and_no_token_readback(self):
        captured = {}

        def fetch_json(request):
            captured["url"] = request.full_url
            captured["body"] = request.data.decode("utf-8")
            captured["authorization"] = request.headers.get("Authorization")
            return 200, {
                "id": "int-live-1",
                "status": "completed",
                "steps": [{
                    "type": "model_output",
                    "content": [{"type": "text", "text": "ok"}],
                }],
                "usage": {
                    "total_tokens": 3,
                    "total_input_tokens": 2,
                    "total_output_tokens": 1,
                },
            }

        client = VertexInteractionsClient(FakeIdentity(), fetch_json=fetch_json)
        result = client.interact(prompt="hello")
        self.assertIn("/v1beta1/projects/sov-hybrid-suite/locations/global/interactions", captured["url"])
        self.assertIn('"model":"gemini-3.8-flash"', captured["body"])
        self.assertIn('"store":false', captured["body"])
        self.assertEqual(captured["authorization"], "Bearer opaque-test-token")
        self.assertEqual(result["interaction_id"], "int-live-1")
        self.assertEqual(result["text"], "ok")
        self.assertIs(result["store"], False)
        self.assertNotIn("opaque-test-token", str(result))

    def test_interactions_normalizer_fails_closed_on_ambiguity(self):
        with self.assertRaises(InteractionsError) as ctx:
            normalize_interaction_response([
                {"id": "a", "status": "completed", "steps": [], "usage": {}},
                {"id": "b", "status": "completed", "steps": [], "usage": {}},
            ])
        self.assertEqual(ctx.exception.code, "INTERACTIONS_RESPONSE_AMBIGUOUS")

    def test_receipt_hash_is_stable(self):
        self.assertEqual(sha256({"b": 2, "a": 1}), sha256({"a": 1, "b": 2}))


if __name__ == "__main__":
    unittest.main()
