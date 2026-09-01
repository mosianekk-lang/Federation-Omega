from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
G0_TEMPLATE = ROOT / "governance" / "sovara_gemini_g0_authority_census_request_template_v1.json"
WORKFLOW = ROOT / ".github" / "workflows" / "sovara-litellm-v2-3-provider-admission.yml"
BOOTSTRAP = ROOT / "sovara" / "gemini" / "bootstrap_gateway.sh"


class SovaraGeminiG0AuthorityCensusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = json.loads(G0_TEMPLATE.read_text(encoding="utf-8"))
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        self.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    def test_dormant_g0_template_is_read_only_authority_census(self) -> None:
        self.assertEqual(self.request["mode"], "G0_READ_ONLY_VERIFY")
        self.assertEqual(self.request["g0_objective"], "ADMIN_AUTHORITY_GRAPH_CENSUS")
        self.assertFalse(self.request["provider_mutation_allowed"])
        self.assertFalse(self.request["model_inference_allowed"])
        self.assertEqual(
            set(self.request["expected_missing_adc_controls"]),
            {
                "aiplatform_user_binding",
                "service_usage_consumer_binding",
                "deployer_cloud_run_developer_binding",
            },
        )

    def test_census_and_adc_receipts_have_separate_streams(self) -> None:
        self.assertIn("admin_authority_census.py >&2 || true", self.bootstrap)
        self.assertIn("PROJECT_IAM_AUTHORITY_CENSUS.json", self.workflow)
        self.assertIn("GEMINI_ADC_VERIFIED.json", self.workflow)

    def test_census_success_never_promotes_adc(self) -> None:
        self.assertIn("'admin_authority_census_verified':census_ok", self.workflow)
        self.assertIn("'adc_gap_preserved':adc_gap_preserved", self.workflow)
        self.assertIn('.adc_verified == false and .adc_gap_preserved == true', self.workflow)
        self.assertIn("expected Gemini ADC gaps remain", self.workflow)

    def test_wif_contract_drift_is_diagnostic_not_verified(self) -> None:
        self.assertIn("FEDOMEGA-WIF-CLOUD-DRIFT-OBSERVED", self.workflow)
        self.assertIn("'hardened_contract_verified':contract_match", self.workflow)
        self.assertIn("'wif_exchange_observed':wif_exchange_observed", self.workflow)
        self.assertIn("'wif_contract_drift_preserved':wif_contract_drift_preserved", self.workflow)
        self.assertIn(".wif_verified == false and .wif_exchange_observed == true and .wif_contract_drift_preserved == true", self.workflow)
        self.assertIn("hardened WIF provider contract remains drifted and explicitly unverified", self.workflow)
        self.assertIn("'g0_identity_adc_verified':wif_ok and adc_ok", self.workflow)

    def test_wif_drift_escape_hatch_is_read_only_admin_census_only(self) -> None:
        self.assertIn("os.environ.get('EXECUTION_SCOPE')=='G0_READ_ONLY_VERIFY'", self.workflow)
        self.assertIn("request.get('g0_objective')=='ADMIN_AUTHORITY_GRAPH_CENSUS'", self.workflow)
        self.assertIn("request.get('provider_mutation_allowed') is False", self.workflow)
        self.assertIn("request.get('model_inference_allowed') is False", self.workflow)
        self.assertIn("if not contract_match and not allow_read_only_drift:", self.workflow)

    def test_hardened_expected_wif_contract_is_not_weakened(self) -> None:
        self.assertIn("assertion.repository_id=='1292795464'", self.workflow)
        self.assertIn("assertion.repository_owner_id=='261966700'", self.workflow)
        self.assertIn("assertion.ref=='refs/heads/main'", self.workflow)
        self.assertIn("assertion.job_workflow_ref=='mosianekk-lang/Federation-Omega/.github/workflows/sovara-litellm-v2-3-provider-admission.yml@refs/heads/main'", self.workflow)
        self.assertIn("(assertion.event_name=='workflow_dispatch' || assertion.event_name=='push')", self.workflow)
        self.assertIn("'attribute.repository_id':'assertion.repository_id'", self.workflow)
        self.assertIn("'attribute.workflow_ref':'assertion.job_workflow_ref'", self.workflow)

    def test_legacy_g0_adc_verification_gate_is_preserved(self) -> None:
        self.assertIn('.adc_verified == true and .adc_apply_mutation_performed == false', self.workflow)
        self.assertIn("G0 WIF and Gemini ADC verification passed", self.workflow)

    def test_authority_census_does_not_enable_provider_mutation(self) -> None:
        census_block = self.workflow.split('ADMIN_AUTHORITY_GRAPH_CENSUS', 1)[1]
        self.assertNotIn("provider_mutation_allowed') is True", census_block.split("elif mode == 'G1_ADC_APPLY_VERIFY'", 1)[0])
        self.assertIn("provider_admission_attempted == false", self.workflow)
        self.assertIn("model_inference_performed == false", self.workflow)


if __name__ == "__main__":
    unittest.main()
