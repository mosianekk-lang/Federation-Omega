from __future__ import annotations

import unittest

from ops.sovara_ai_studio_semantic_canary import execute_semantic_canary, select_model


REQUEST = {
    "project_id": "sov-hybrid-suite",
    "project_number": "257649435135",
    "provider": "GOOGLE_GEMINI_DEVELOPER_API",
    "credential_mode": "GOOGLE_WIF_SECRET_MANAGER_TRANSIENT_ACCESS",
    "credential_reference": "gcp_secret_name:gemini-api-key",
    "credential_secret_name": "gemini-api-key",
    "resolution_surface": "google_cloud",
    "workload_identity_provider": "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
    "service_account": "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
    "model_policy": {
        "preferred_models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"],
        "allow_dynamic_fallback": True,
        "reject_model_classes": ["embedding", "tts", "image", "robotics", "aqa"],
    },
    "semantic_canary": {"temperature": 0, "max_output_tokens": 32},
}

ENV = {
    "GITHUB_SHA": "0123456789abcdef0123456789abcdef01234567",
    "GITHUB_RUN_ID": "987654321",
    "GITHUB_RUN_ATTEMPT": "2",
}


def ok(stdout: str = "", stderr: str = "") -> dict[str, object]:
    return {"ok": True, "code": 0, "stdout": stdout, "stderr": stderr}


def fail(code: int, stderr: str) -> dict[str, object]:
    return {"ok": False, "code": code, "stdout": "", "stderr": stderr}


class SovaraAIStudioSemanticCanaryRuntimeTests(unittest.TestCase):
    def test_fails_closed_when_wif_runtime_is_unavailable(self) -> None:
        def command_runner(args: list[str]) -> dict[str, object]:
            if args[:3] == ["gcloud", "auth", "list"]:
                return fail(127, "gcloud: command not found")
            if args[:3] == ["gcloud", "auth", "print-access-token"]:
                return fail(127, "gcloud: command not found")
            raise AssertionError(args)

        receipt = execute_semantic_canary(REQUEST, env=ENV, command_runner=command_runner)

        self.assertEqual("AUTH_UNAVAILABLE", receipt["state"])
        self.assertFalse(receipt["semantic_verified"])
        self.assertFalse(receipt["wif_identity_verified"])
        self.assertFalse(receipt["credential_present"])
        self.assertFalse(receipt["secret_access_attempted"])
        self.assertFalse(receipt["secret_value_recorded"])
        self.assertFalse(receipt["provider_mutation_performed"])

    def test_fails_closed_when_secret_access_is_unavailable(self) -> None:
        calls: list[list[str]] = []

        def command_runner(args: list[str]) -> dict[str, object]:
            calls.append(args)
            if args[:3] == ["gcloud", "auth", "list"]:
                return ok("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com\n")
            if args[:3] == ["gcloud", "auth", "print-access-token"]:
                return ok("ya29.token\n")
            if args[:3] == ["gcloud", "secrets", "describe"]:
                return ok('{"name":"projects/257649435135/secrets/gemini-api-key"}')
            if args[:4] == ["gcloud", "secrets", "versions", "list"]:
                return ok('[{"name":"projects/257649435135/secrets/gemini-api-key/versions/1","state":"ENABLED"}]')
            if args[:4] == ["gcloud", "secrets", "versions", "access"]:
                return fail(1, "PERMISSION_DENIED: secret accessor missing")
            raise AssertionError(args)

        http_called = False

        def http_factory(_api_key: str):
            def caller(_url: str, _method: str, _payload):
                nonlocal http_called
                http_called = True
                return 500, {}, {}

            return caller

        receipt = execute_semantic_canary(
            REQUEST,
            env=ENV,
            command_runner=command_runner,
            http_caller_factory=http_factory,
        )

        self.assertEqual("CREDENTIAL_PERMISSION_UNAVAILABLE", receipt["state"])
        self.assertFalse(receipt["semantic_verified"])
        self.assertTrue(receipt["wif_identity_verified"])
        self.assertTrue(receipt["secret_metadata_readable"])
        self.assertTrue(receipt["enabled_secret_version_visible"])
        self.assertTrue(receipt["secret_access_attempted"])
        self.assertFalse(receipt["credential_present"])
        self.assertFalse(receipt["secret_value_recorded"])
        self.assertFalse(receipt["case_data_processed"])
        self.assertFalse(receipt["provider_mutation_performed"])
        self.assertIsNotNone(receipt["secret_access_error_sha256"])
        self.assertFalse(http_called)
        self.assertTrue(any("--secret=gemini-api-key" in part for call in calls for part in call))

    def test_verifies_exact_nonce_and_receipt_fields(self) -> None:
        calls: list[tuple[str, str, object]] = []

        def command_runner(args: list[str]) -> dict[str, object]:
            if args[:3] == ["gcloud", "auth", "list"]:
                return ok("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com\n")
            if args[:3] == ["gcloud", "auth", "print-access-token"]:
                return ok("ya29.token\n")
            if args[:3] == ["gcloud", "secrets", "describe"]:
                return ok('{"name":"projects/257649435135/secrets/gemini-api-key"}')
            if args[:4] == ["gcloud", "secrets", "versions", "list"]:
                return ok('[{"name":"projects/257649435135/secrets/gemini-api-key/versions/1","state":"ENABLED"}]')
            if args[:4] == ["gcloud", "secrets", "versions", "access"]:
                return ok("not-a-real-key\n")
            raise AssertionError(args)

        def http_factory(_api_key: str):
            def caller(url: str, method: str, payload):
                calls.append((url, method, payload))
                if method == "GET":
                    return (
                        200,
                        {
                            "models": [
                                {
                                    "name": "models/gemini-2.5-flash",
                                    "displayName": "Gemini 2.5 Flash",
                                    "supportedGenerationMethods": ["generateContent"],
                                }
                            ]
                        },
                        {},
                    )
                nonce = payload["contents"][0]["parts"][0]["text"].split(": ", 1)[1]
                return (
                    200,
                    {
                        "candidates": [{"content": {"parts": [{"text": nonce}]}}],
                        "modelVersion": "gemini-2.5-flash-001",
                        "responseId": "resp-123",
                        "usageMetadata": {
                            "promptTokenCount": 12,
                            "candidatesTokenCount": 4,
                            "totalTokenCount": 16,
                        },
                    },
                    {"x-request-id": "header-456"},
                )

            return caller

        receipt = execute_semantic_canary(
            REQUEST,
            env=ENV,
            command_runner=command_runner,
            http_caller_factory=http_factory,
        )

        self.assertEqual("VERIFIED_SCOPED", receipt["state"])
        self.assertTrue(receipt["semantic_verified"])
        self.assertEqual("gemini-2.5-flash", receipt["selected_model"])
        self.assertEqual("PREFERRED_PROVIDER_DISCOVERED", receipt["selected_model_source"])
        self.assertEqual("gemini-2.5-flash-001", receipt["provider_model_version"])
        self.assertEqual("resp-123", receipt["provider_request_id_or_equivalent"])
        self.assertEqual(200, receipt["models_list_http_status"])
        self.assertEqual(200, receipt["generate_http_status"])
        self.assertEqual({"promptTokenCount": 12, "candidatesTokenCount": 4, "totalTokenCount": 16}, receipt["usage_metadata"])
        self.assertFalse(receipt["secret_value_recorded"])
        self.assertFalse(receipt["case_data_processed"])
        self.assertFalse(receipt["provider_mutation_performed"])
        self.assertIsNotNone(receipt["nonce_sha256"])
        self.assertEqual(2, len(calls))
        self.assertTrue(calls[0][0].startswith("https://generativelanguage.googleapis.com/v1beta/models?"))
        self.assertTrue(calls[1][0].endswith("/models/gemini-2.5-flash:generateContent"))

    def test_dynamic_fallback_prefers_latest_stable_flash_model(self) -> None:
        selected, source, count = select_model(
            [
                {
                    "name": "models/gemini-2.5-flash-preview",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.7-flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.8-pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
            ],
            REQUEST,
        )

        self.assertEqual(3, count)
        self.assertEqual("DYNAMIC_PROVIDER_DISCOVERY", source)
        self.assertEqual("gemini-3.7-flash", selected["short"])


if __name__ == "__main__":
    unittest.main()
