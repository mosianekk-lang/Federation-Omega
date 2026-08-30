from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "governance" / "sovara_gemini_collaboration_request_v1.json"
CENSUS = ROOT / "sovara" / "gemini" / "admin_authority_census.py"

SPEC = importlib.util.spec_from_file_location("sovara_admin_authority_census", CENSUS)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SovaraGeminiDeploymentReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = json.loads(REQUEST.read_text(encoding="utf-8"))
        self.source = CENSUS.read_text(encoding="utf-8")

    def test_request_remains_strictly_read_only(self) -> None:
        self.assertEqual(self.request["mode"], "G0_READ_ONLY_VERIFY")
        self.assertEqual(self.request["g0_objective"], "ADMIN_AUTHORITY_GRAPH_CENSUS")
        self.assertTrue(self.request["deployment_readiness_probe"])
        self.assertTrue(self.request["admin_actas_census_probe"])
        self.assertTrue(self.request["admin_actas_census_scope"]["read_only"])
        self.assertTrue(self.request["privileged_control_runtime_census"])
        self.assertTrue(self.request["privileged_control_runtime_scope"]["read_only"])
        self.assertFalse(self.request["provider_mutation_allowed"])
        self.assertFalse(self.request["model_inference_allowed"])
        self.assertFalse(self.request["promote"])

    def test_exact_three_adc_gaps_remain_explicit(self) -> None:
        self.assertEqual(
            set(self.request["expected_missing_adc_controls"]),
            {
                "aiplatform_user_binding",
                "service_usage_consumer_binding",
                "deployer_cloud_run_developer_binding",
            },
        )

    def test_deployment_permission_probe_is_exact_and_bounded(self) -> None:
        self.assertEqual(
            MODULE.DEPLOYMENT_PROJECT_PERMISSIONS,
            [
                "run.services.create",
                "run.services.get",
                "run.services.update",
                "run.operations.get",
                "run.routes.invoke",
            ],
        )
        self.assertEqual(
            MODULE.AR_TEST_PERMISSIONS,
            [
                "artifactregistry.repositories.downloadArtifacts",
                "artifactregistry.repositories.uploadArtifacts",
            ],
        )
        self.assertEqual(MODULE.RUNTIME_SA, "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com")
        self.assertEqual(MODULE.DEPLOYER_SA, "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com")

    def test_authority_receipt_schema_remains_backward_compatible(self) -> None:
        self.assertIn('"schema": "SOVARA_PROJECT_IAM_AUTHORITY_GRAPH_V1"', self.source)
        self.assertIn('"schema_revision": 2', self.source)
        self.assertIn('"private_gateway_canary_preflight_ready"', self.source)
        self.assertIn('"provider_mutation_performed": False', self.source)
        self.assertIn('"credential_values_recorded": False', self.source)
        self.assertIn('"secret_payload_accessed": False', self.source)


if __name__ == "__main__":
    unittest.main()
