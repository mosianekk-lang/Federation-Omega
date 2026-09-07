from __future__ import annotations

import unittest

from ops.sovara_ai_studio_semantic_canary import execute_semantic_canary, select_model


REQUEST = {
    "project_id": "sov-hybrid-suite",
    "project_number": "257649435135",
    "provider": "GOOGLE_GEMINI_MULTI_ROUTE_CANARY",
    "credential_mode": "GOOGLE_WIF_SECRET_MANAGER_TRANSIENT_ACCESS",
    "credential_reference": "gcp_secret_name:gemini-api-key",
    "credential_secret_name": "gemini-api-key",
    "resolution_surface": "google_cloud",
    "workload_identity_provider": "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
    "service_account": "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
    "preferred_execution_order": ["VERTEX_OAUTH_ADC", "DEVELOPER_API_SECRET_MANAGER"],
    "vertex_oauth_challenger": {
        "enabled": True,
        "credential_mode": "GOOGLE_WIF_OAUTH_ACCESS_TOKEN",
        "location": "global",
        "publisher": "google",
        "preferred_models": ["gemini-2.5-flash", "gemini-2.5-flash-lite"],
        "service_usage_permissions_required": ["serviceusage.services.get", "serviceusage.services.use"],
        "vertex_permissions_required": ["aiplatform.publisherModels.get", "aiplatform.publisherModels.predict"],
    },
    "developer_api_secret_manager_fallback": {
        "enabled": True,
        "credential_mode": "GOOGLE_WIF_SECRET_MANAGER_TRANSIENT_ACCESS",
        "credential_reference": "gcp_secret_name:gemini-api-key",
        "credential_secret_name": "gemini-api-key",
    },
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
        self.assertEqual("AUTH_UNAVAILABLE", receipt["vertex_oauth_adc_challenger"]["state"])
        self.assertEqual("SKIPPED_AUTH_UNAVAILABLE", receipt["developer_api_secret_manager_fallback"]["state"])
        self.assertFalse(receipt["secret_value_recorded"])
        self.assertFalse(receipt["provider_mutation_performed"])

    def test_vertex_success_skips_secret_manager_fallback(self) -> None:
        commands: list[list[str]] = []
        bearer_calls: list[tuple[str, str, object]] = []

        def command_runner(args: list[str]) -> dict[str, object]:
            commands.append(args)
            if args[:3] == ["gcloud", "auth", "list"]:
                return ok("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com\n")
            if args[:3] == ["gcloud", "auth", "print-access-token"]:
                return ok("ya29.token\n")
            raise AssertionError(args)

        def bearer_factory(_token: str):
            def caller(url: str, method: str, payload):
                bearer_calls.append((url, method, payload))
                if url.endswith(":testIamPermissions") and "serviceusage.googleapis.com" in url:
                    return 200, {"permissions": ["serviceusage.services.get", "serviceusage.services.use"]}, {}
                if url.endswith("/services/aiplatform.googleapis.com"):
                    return 200, {"state": "ENABLED"}, {}
                if url.endswith(":testIamPermissions") and "aiplatform.googleapis.com" in url:
                    return 200, {"permissions": ["aiplatform.publisherModels.get", "aiplatform.publisherModels.predict"]}, {}
                if url.endswith("/publishers/google/models/gemini-2.5-flash"):
                    return 200, {
                        "name": "publishers/google/models/gemini-2.5-flash",
                        "versionId": "vertex-stable",
                        "displayName": "Gemini 2.5 Flash",
                        "launchStage": "GA",
                        "supportedActions": ["generateContent"],
                    }, {}
                if url.endswith(":generateContent"):
                    nonce = payload["contents"][0]["parts"][0]["text"].split(": ", 1)[1]
                    return 200, {
                        "candidates": [{"content": {"parts": [{"text": nonce}]}}],
                        "modelVersion": "gemini-2.5-flash-vertex-001",
                        "responseId": "vertex-resp-123",
                        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 3, "totalTokenCount": 13},
                    }, {"x-request-id": "vertex-header-456"}
                raise AssertionError((url, method, payload))

            return caller

        def api_key_factory(_api_key: str):
            raise AssertionError("Developer API fallback must not run when Vertex succeeds")

        receipt = execute_semantic_canary(
            REQUEST,
            env=ENV,
            command_runner=command_runner,
            bearer_http_caller_factory=bearer_factory,
            api_key_http_caller_factory=api_key_factory,
        )

        self.assertEqual("VERIFIED_SCOPED", receipt["state"])
        self.assertEqual("VERTEX_OAUTH_ADC", receipt["selected_route"])
        self.assertTrue(receipt["semantic_verified"])
        self.assertEqual("gemini-2.5-flash", receipt["selected_model"])
        self.assertEqual("PREFERRED_VERTEX_MODEL_READBACK", receipt["selected_model_source"])
        self.assertEqual("gemini-2.5-flash-vertex-001", receipt["provider_model_version"])
        self.assertEqual("vertex-resp-123", receipt["provider_request_id_or_equivalent"])
        self.assertEqual({"promptTokenCount": 10, "candidatesTokenCount": 3, "totalTokenCount": 13}, receipt["usage_metadata"])
        self.assertEqual("SKIPPED_PREFERRED_ROUTE_VERIFIED", receipt["developer_api_secret_manager_fallback"]["state"])
        self.assertFalse(any(call[:3] == ["gcloud", "secrets", "describe"] for call in commands))
        self.assertEqual(5, len(bearer_calls))

    def test_vertex_missing_permission_is_preserved_and_fallback_can_verify(self) -> None:
        commands: list[list[str]] = []
        bearer_calls: list[tuple[str, str, object]] = []
        api_calls: list[tuple[str, str, object]] = []

        def command_runner(args: list[str]) -> dict[str, object]:
            commands.append(args)
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

        def bearer_factory(_token: str):
            def caller(url: str, method: str, payload):
                bearer_calls.append((url, method, payload))
                if url.endswith(":testIamPermissions") and "serviceusage.googleapis.com" in url:
                    return 200, {"permissions": ["serviceusage.services.get", "serviceusage.services.use"]}, {}
                if url.endswith("/services/aiplatform.googleapis.com"):
                    return 200, {"state": "ENABLED"}, {}
                if url.endswith(":testIamPermissions") and "aiplatform.googleapis.com" in url:
                    return 200, {"permissions": ["aiplatform.publisherModels.get"]}, {}
                raise AssertionError((url, method, payload))

            return caller

        def api_key_factory(_api_key: str):
            def caller(url: str, method: str, payload):
                api_calls.append((url, method, payload))
                if method == "GET":
                    return 200, {
                        "models": [
                            {
                                "name": "models/gemini-2.5-flash",
                                "displayName": "Gemini 2.5 Flash",
                                "supportedGenerationMethods": ["generateContent"],
                            }
                        ]
                    }, {}
                nonce = payload["contents"][0]["parts"][0]["text"].split(": ", 1)[1]
                return 200, {
                    "candidates": [{"content": {"parts": [{"text": nonce}]}}],
                    "modelVersion": "gemini-2.5-flash-001",
                    "responseId": "resp-123",
                    "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4, "totalTokenCount": 16},
                }, {"x-request-id": "header-456"}

            return caller

        receipt = execute_semantic_canary(
            REQUEST,
            env=ENV,
            command_runner=command_runner,
            bearer_http_caller_factory=bearer_factory,
            api_key_http_caller_factory=api_key_factory,
        )

        self.assertEqual("VERIFIED_SCOPED", receipt["state"])
        self.assertEqual("DEVELOPER_API_SECRET_MANAGER", receipt["selected_route"])
        self.assertTrue(receipt["semantic_verified"])
        self.assertEqual(["aiplatform.publisherModels.predict"], receipt["vertex_oauth_adc_challenger"]["vertex_missing_permissions"])
        self.assertEqual("VERTEX_PERMISSION_HELD", receipt["vertex_oauth_adc_challenger"]["state"])
        self.assertTrue(receipt["developer_api_secret_manager_fallback"]["secret_access_attempted"])
        self.assertEqual("VERIFIED_SCOPED", receipt["developer_api_secret_manager_fallback"]["state"])
        self.assertEqual("gemini-2.5-flash", receipt["selected_model"])
        self.assertEqual("PREFERRED_PROVIDER_DISCOVERED", receipt["selected_model_source"])
        self.assertEqual(3, len(bearer_calls))
        self.assertEqual(2, len(api_calls))
        self.assertTrue(any(args[:4] == ["gcloud", "secrets", "versions", "access"] for args in commands))

    def test_fails_closed_when_secret_access_is_unavailable(self) -> None:
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
                return fail(1, "PERMISSION_DENIED: secret accessor missing")
            raise AssertionError(args)

        def bearer_factory(_token: str):
            def caller(url: str, method: str, payload):
                if url.endswith(":testIamPermissions") and "serviceusage.googleapis.com" in url:
                    return 200, {"permissions": ["serviceusage.services.get", "serviceusage.services.use"]}, {}
                if url.endswith("/services/aiplatform.googleapis.com"):
                    return 200, {"state": "ENABLED"}, {}
                if url.endswith(":testIamPermissions") and "aiplatform.googleapis.com" in url:
                    return 200, {"permissions": ["aiplatform.publisherModels.get"]}, {}
                raise AssertionError((url, method, payload))

            return caller

        def api_key_factory(_api_key: str):
            raise AssertionError("Developer API HTTP calls must not happen without a resolved secret value")

        receipt = execute_semantic_canary(
            REQUEST,
            env=ENV,
            command_runner=command_runner,
            bearer_http_caller_factory=bearer_factory,
            api_key_http_caller_factory=api_key_factory,
        )

        self.assertEqual("CREDENTIAL_PERMISSION_UNAVAILABLE", receipt["state"])
        self.assertFalse(receipt["semantic_verified"])
        self.assertEqual(["aiplatform.publisherModels.predict"], receipt["vertex_oauth_adc_challenger"]["vertex_missing_permissions"])
        self.assertTrue(receipt["developer_api_secret_manager_fallback"]["secret_access_attempted"])
        self.assertFalse(receipt["developer_api_secret_manager_fallback"]["credential_present"])
        self.assertIsNotNone(receipt["developer_api_secret_manager_fallback"]["secret_access_error_sha256"])
        self.assertFalse(receipt["secret_value_recorded"])
        self.assertFalse(receipt["case_data_processed"])
        self.assertFalse(receipt["provider_mutation_performed"])

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
