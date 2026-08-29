from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sovara" / "gemini" / "private_gateway_canary.sh"
README = ROOT / "services" / "gemini_gateway" / "README.md"
APP = ROOT / "services" / "gemini_gateway" / "app.py"


class SovaraGeminiPrivateGatewayCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")
        cls.app = APP.read_text(encoding="utf-8")

    def test_canary_script_is_valid_bash(self) -> None:
        completed = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_canonical_runtime_identity_is_superior_logic_runtime(self) -> None:
        expected = "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com"
        self.assertIn(expected, self.script)
        self.assertIn(expected, self.readme)
        self.assertNotIn("sv-gemini-runtime@sov-hybrid-suite.iam.gserviceaccount.com", self.script)
        self.assertNotIn("sv-gemini-runtime@sov-hybrid-suite.iam.gserviceaccount.com", self.readme)

    def test_provider_effect_requires_verified_adc_and_explicit_execution_binding(self) -> None:
        self.assertIn("FEDOMEGA-GEMINI-ADC-VERIFIED", self.script)
        self.assertIn("DEPLOY_PRIVATE_ZERO_TRAFFIC_GEMINI_CANARY_V1", self.script)
        self.assertIn("SOVARA_G3_PRIVATE_CANARY_EXECUTE", self.script)
        adc_gate = self.script.index("FEDOMEGA-GEMINI-ADC-VERIFIED")
        docker_build = self.script.index("docker build")
        deploy = self.script.index("gcloud run deploy")
        self.assertLess(adc_gate, docker_build)
        self.assertLess(adc_gate, deploy)

    def test_deploy_is_private_zero_traffic_and_digest_bound(self) -> None:
        self.assertIn("--no-traffic", self.script)
        self.assertIn("--no-allow-unauthenticated", self.script)
        self.assertIn("--tag \"$CANARY_TAG\"", self.script)
        self.assertIn("IMAGE_DIGEST_REF", self.script)
        self.assertIn("--image \"$IMAGE_DIGEST_REF\"", self.script)
        self.assertIn("normal_traffic_percent", self.script)
        self.assertIn("if canary_percent != 0", self.script)

    def test_canary_requires_provider_native_runtime_identity_and_semantic_proof(self) -> None:
        self.assertIn("/health", self.script)
        self.assertIn("/ready", self.script)
        self.assertIn("/v1/handshake", self.script)
        self.assertIn("provider_request_id", self.script)
        self.assertIn("model_identity", self.script)
        self.assertIn("semantic_nonce_sha256", self.script)
        self.assertIn("FEDOMEGA-GEMINI-GATEWAY-CANARY-VERIFIED", self.script)
        self.assertIn("EXPECTED_RUNTIME_SERVICE_ACCOUNT", self.app)
        self.assertIn("RUNTIME_IDENTITY_MISMATCH", self.app)

    def test_canary_does_not_promote_production_traffic(self) -> None:
        self.assertIn("production_promotion_performed':False", self.script)
        self.assertNotIn("update-traffic", self.script)
        self.assertNotIn("--to-latest", self.script)

    def test_no_static_provider_key_dependency_is_introduced(self) -> None:
        forbidden = (
            "GOOGLE_APPLICATION_CREDENTIALS=",
            "GEMINI_API_KEY",
            "service-account-key",
            "--key-file",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.script)


if __name__ == "__main__":
    unittest.main()
