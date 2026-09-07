from __future__ import annotations

import unittest

from bubbles.strategic_fuse_vertex_direct_wif_v1 import (
    ACTION,
    EXECUTOR_ROUTE,
    MODEL_METADATA_ROUTE,
    MODEL_METADATA_VIEW,
    MODEL_RESOURCE_NAME,
    MODEL_URL,
    SERVICE_URL,
    TARGET,
    run_direct_wif_a0,
)


class StrategicFuseVertexDirectWifTests(unittest.TestCase):
    def good_get(self, url, token):
        self.assertEqual("token", token)
        if url == SERVICE_URL:
            return 200, {"name": "projects/257649435135/services/aiplatform.googleapis.com", "state": "ENABLED"}
        if url == MODEL_URL:
            return 200, {
                "name": "publishers/google/models/gemini-2.5-flash",
                "versionId": "001",
                "launchStage": "GA",
                "supportedActions": {"viewRestApi": {}},
            }
        raise AssertionError(url)

    def run_good(self):
        return run_direct_wif_a0(
            source_ref="main:abc",
            token_fn=lambda: "token",
            principal_fn=lambda: "deployer@example.iam.gserviceaccount.com",
            get_fn=self.good_get,
        )

    def test_success_requires_service_and_exact_model_readback(self):
        receipt = self.run_good()
        self.assertEqual("VERTEX_A0_DIRECT_WIF_READBACK_VERIFIED", receipt["state"])
        self.assertTrue(receipt["provider_native_capability_readback_verified"])
        self.assertTrue(receipt["provider_authenticated"])
        self.assertEqual("ENABLED", receipt["service_state"])
        self.assertEqual(200, receipt["model_http_status"])
        self.assertEqual(MODEL_RESOURCE_NAME, receipt["model_readback"]["name"])
        self.assertEqual(MODEL_METADATA_ROUTE, receipt["model_metadata_route"])
        self.assertEqual(MODEL_METADATA_VIEW, receipt["model_metadata_view"])
        self.assertEqual(TARGET, receipt["target"])
        self.assertEqual(ACTION, receipt["action"])
        self.assertEqual(EXECUTOR_ROUTE, receipt["executor_route"])

    def test_success_is_strictly_no_inference_no_effect(self):
        receipt = self.run_good()
        self.assertFalse(receipt["semantic_execution_attempted"])
        self.assertFalse(receipt["generate_content_called"])
        self.assertEqual(0, receipt["incremental_cost"])
        self.assertFalse(receipt["provider_mutation_attempted"])
        self.assertFalse(receipt["iam_mutation_attempted"])
        self.assertFalse(receipt["deployment_attempted"])
        self.assertFalse(receipt["traffic_change_attempted"])
        self.assertFalse(receipt["secret_payload_accessed"])
        self.assertFalse(receipt["credential_value_recorded"])
        self.assertEqual("NONE", receipt["authority_delta"])

    def test_model_metadata_url_uses_documented_model_garden_get_not_inference_resource(self):
        self.assertEqual(
            "https://aiplatform.googleapis.com/v1/publishers/google/models/"
            "gemini-2.5-flash?view=PUBLISHER_MODEL_VERSION_VIEW_BASIC",
            MODEL_URL,
        )
        self.assertNotIn("/projects/", MODEL_URL)
        self.assertNotIn(":generateContent", MODEL_URL)

    def test_missing_token_is_preserved_as_hold(self):
        def missing():
            raise RuntimeError("WIF access token unavailable")
        receipt = run_direct_wif_a0(
            source_ref="main:abc",
            token_fn=missing,
            principal_fn=lambda: "",
            get_fn=self.good_get,
        )
        self.assertEqual("HELD_WIF_ACCESS_TOKEN_UNAVAILABLE", receipt["state"])
        self.assertFalse(receipt["provider_native_capability_readback_verified"])
        self.assertTrue(receipt["failure_fingerprint"].startswith("sha256:"))

    def test_403_service_read_is_authority_hold(self):
        receipt = run_direct_wif_a0(
            source_ref="main:abc",
            token_fn=lambda: "token",
            principal_fn=lambda: "p",
            get_fn=lambda *_: (403, {"error": {"status": "PERMISSION_DENIED"}}),
        )
        self.assertEqual("HELD_DIRECT_WIF_PROVIDER_AUTHORITY", receipt["state"])
        self.assertFalse(receipt["provider_authenticated"])

    def test_disabled_service_blocks_model_read(self):
        calls = []
        def get(url, token):
            calls.append(url)
            return 200, {"state": "DISABLED"}
        receipt = run_direct_wif_a0(
            source_ref="main:abc", token_fn=lambda: "token", principal_fn=lambda: "p", get_fn=get
        )
        self.assertEqual([SERVICE_URL], calls)
        self.assertEqual("HELD_VERTEX_SERVICE_READBACK", receipt["state"])
        self.assertFalse(receipt["provider_native_capability_readback_verified"])

    def test_wrong_model_identity_blocks_promotion(self):
        def get(url, token):
            if url == SERVICE_URL:
                return 200, {"state": "ENABLED"}
            return 200, {"name": "publishers/google/models/wrong"}
        receipt = run_direct_wif_a0(
            source_ref="main:abc", token_fn=lambda: "token", principal_fn=lambda: "p", get_fn=get
        )
        self.assertEqual("HELD_VERTEX_MODEL_READBACK", receipt["state"])
        self.assertFalse(receipt["provider_native_capability_readback_verified"])

    def test_project_scoped_inference_style_name_cannot_fake_metadata_success(self):
        def get(url, token):
            if url == SERVICE_URL:
                return 200, {"state": "ENABLED"}
            return 200, {
                "name": "projects/sov-hybrid-suite/locations/global/publishers/google/models/gemini-2.5-flash"
            }
        receipt = run_direct_wif_a0(
            source_ref="main:abc", token_fn=lambda: "token", principal_fn=lambda: "p", get_fn=get
        )
        self.assertEqual("HELD_VERTEX_MODEL_READBACK", receipt["state"])

    def test_403_model_read_is_authority_hold(self):
        def get(url, token):
            if url == SERVICE_URL:
                return 200, {"state": "ENABLED"}
            return 403, {"error": {"status": "PERMISSION_DENIED"}}
        receipt = run_direct_wif_a0(
            source_ref="main:abc", token_fn=lambda: "token", principal_fn=lambda: "p", get_fn=get
        )
        self.assertEqual("HELD_DIRECT_WIF_PROVIDER_AUTHORITY", receipt["state"])
        self.assertFalse(receipt["provider_native_capability_readback_verified"])

    def test_same_evidence_has_stable_receipt_digest(self):
        first = self.run_good()
        second = self.run_good()
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_source_ref_required(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_REF_REQUIRED"):
            run_direct_wif_a0(source_ref="")

    def test_only_two_get_endpoints_are_used(self):
        calls = []
        def get(url, token):
            calls.append(url)
            return self.good_get(url, token)
        receipt = run_direct_wif_a0(
            source_ref="main:abc", token_fn=lambda: "token", principal_fn=lambda: "p", get_fn=get
        )
        self.assertTrue(receipt["provider_native_capability_readback_verified"])
        self.assertEqual([SERVICE_URL, MODEL_URL], calls)
        self.assertNotIn(":generateContent", " ".join(calls))


if __name__ == "__main__":
    unittest.main()
