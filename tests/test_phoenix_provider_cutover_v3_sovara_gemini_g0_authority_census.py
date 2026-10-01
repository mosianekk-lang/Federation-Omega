from __future__ import annotations

import ast
import json
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
G0_TEMPLATE = ROOT / "governance" / "sovara_gemini_g0_authority_census_request_template_v1.json"
WORKFLOW = ROOT / ".github" / "workflows" / "sovara-litellm-v2-3-provider-admission.yml"
BOOTSTRAP = ROOT / "sovara" / "gemini" / "bootstrap_gateway.sh"
CENSUS = ROOT / "sovara" / "gemini" / "admin_authority_census.py"
LIVE_REQUEST = ROOT / "governance" / "sovara_gemini_collaboration_request_v1.json"


class SovaraGeminiG0AuthorityCensusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = json.loads(G0_TEMPLATE.read_text(encoding="utf-8"))
        self.live_request = json.loads(LIVE_REQUEST.read_text(encoding="utf-8"))
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        self.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.census = CENSUS.read_text(encoding="utf-8")

    def workflow_guard(self, name: str, **bindings):
        """Evaluate the actual bounded workflow expression without its effects."""
        marker = "          " + name + "=("
        self.assertEqual(1, self.workflow.count(marker), name)
        start = self.workflow.index(marker)
        end = self.workflow.index("\n          )", start) + len("\n          )")
        assignment = ast.parse(textwrap.dedent(self.workflow[start:end])).body[0]
        self.assertIsInstance(assignment, ast.Assign)
        self.assertEqual(name, assignment.targets[0].id)
        expression = compile(ast.Expression(assignment.value), "<admitted-workflow-guard>", "eval")
        return eval(expression, {"__builtins__": {"bool": bool, "str": str}}, bindings)

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
        self.assertIn("scope=os.environ.get('EXECUTION_SCOPE')", self.workflow)
        request = dict(self.request)
        guard = lambda **extra: self.workflow_guard("allow_read_only_drift",
            scope="G0_READ_ONLY_VERIFY", request=dict(request, **extra))
        self.assertIs(True, guard())
        for field in ("provider_mutation_allowed", "model_inference_allowed"):
            for invalid in (True, 0, "false", None):
                self.assertIs(False, guard(**{field: invalid}))
        self.assertIs(False, guard(g0_objective="OTHER"))
        self.assertIs(False, self.workflow_guard("allow_read_only_drift",
            scope="G3_PRIVATE_GATEWAY_CANARY", request=request))

    def test_g3_transport_alternative_is_separate_and_bounded(self) -> None:
        context = {"scope": "G3_PRIVATE_GATEWAY_CANARY", "request": self.live_request,
                   "issuer_verified": True, "repository_scope_verified": True,
                   "transport_mapping_verified": True}
        self.assertIs(True, self.workflow_guard("g3_deployment_transport_sufficient", **context))
        for field in ("issuer_verified", "repository_scope_verified", "transport_mapping_verified"):
            self.assertIs(False, self.workflow_guard("g3_deployment_transport_sufficient", **dict(context, **{field: False})))
        for changes in ({"runtime_service_account": "unapproved@example.invalid"},
                        {"deployment_scope": "PRODUCTION"}, {"production_traffic_allowed": True},
                        {"production_traffic_allowed": 0}, {"production_traffic_allowed": "false"},
                        {"production_traffic_allowed": None}):
            self.assertIs(False, self.workflow_guard("g3_deployment_transport_sufficient",
                **dict(context, request=dict(self.live_request, **changes))))
        self.assertIs(False, self.workflow_guard("g3_deployment_transport_sufficient",
            **dict(context, scope="G0_READ_ONLY_VERIFY")))
        deny = "if not contract_match and not allow_read_only_drift and not g3_deployment_transport_sufficient:"
        self.assertIn(deny, self.workflow)
        predicate = ast.parse(deny + "\n    pass").body[0].test
        compiled = compile(ast.Expression(predicate), "<admitted-workflow-denial>", "eval")
        for contract in (False, True):
            for g0 in (False, True):
                for g3 in (False, True):
                    actual = eval(compiled, {"__builtins__": {}}, {"contract_match": contract,
                        "allow_read_only_drift": g0, "g3_deployment_transport_sufficient": g3})
                    self.assertIs(not (contract or g0 or g3), actual)

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

    def test_mobile_phase_a_permission_is_observed_not_executed(self) -> None:
        self.assertIn('"serviceusage.services.enable"', self.census)
        self.assertIn('"serviceusage_services_enable"', self.census)
        self.assertIn('"verified_reusable_serviceusage_enable_service_accounts"', self.census)
        self.assertIn('"phase_a_api_enable_authority_ready"', self.census)
        self.assertIn('"phase_a_api_enable_permission_observation_only": True', self.census)
        self.assertIn('"provider_mutation_performed": False', self.census)
        self.assertIn('"iam_mutation_performed": False', self.census)
        self.assertIn('"api_mutation_performed": False', self.census)
        self.assertNotIn('gcloud services enable', self.census)

    def test_live_request_keeps_g3_private_zero_production_boundary(self) -> None:
        self.assertEqual(self.live_request["mode"], "G3_PRIVATE_GATEWAY_CANARY")
        self.assertEqual(self.live_request["deployment_scope"], "PRIVATE_ZERO_TRAFFIC_CANARY")
        self.assertEqual(self.live_request["runtime_service_account"],
                         "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com")
        self.assertEqual(self.live_request["expected_workflow"], WORKFLOW.relative_to(ROOT).as_posix())
        for field in ("execute", "provider_mutation_allowed", "model_inference_allowed"):
            self.assertIs(True, self.live_request[field])
        for field in ("promote", "case_data_allowed", "external_communication_allowed", "production_traffic_allowed"):
            self.assertIs(False, self.live_request[field])
        self.assertEqual({"services/gemini_gateway/app.py", "services/gemini_gateway/interactions_v2.py",
                          "sovara/gemini/private_gateway_canary.sh"}, set(self.live_request["source_scope"]))
        self.assertEqual({"GITHUB_WIF_EXCHANGE_OBSERVED", "G3_BOUNDED_REPOSITORY_DEPLOYMENT_TRANSPORT",
            "WIF_HARDENING_DEBT_PRESERVED_WHEN_OPEN", "RUNTIME_ADC_VERIFIED", "RUNTIME_AIPLATFORM_USER",
            "IMMUTABLE_IMAGE_DIGEST", "COLD_START_CREATE_DELETE_PERMISSION_PREFLIGHT",
            "V1_GENERATECONTENT_EXACT_NONCE", "V2_INTERACTIONS_38_EXACT_NONCE", "INTERACTION_ID",
            "INTERACTION_STATUS_COMPLETED", "USAGE_METADATA", "STORE_FALSE", "RUNTIME_SERVICE_ACCOUNT_READBACK",
            "ZERO_CANONICAL_PRODUCTION_TRAFFIC", "EPHEMERAL_CANARY_DELETE_READBACK_WHEN_PRODUCTION_SERVICE_ABSENT"},
            set(self.live_request["required_provider_proofs"]))
        self.assertIn("No production service creation, production traffic promotion, public unauthenticated access",
                      self.live_request["truth_boundary"])

    def test_g3_receipt_requires_cleanup_privacy_and_zero_normal_traffic(self) -> None:
        receipt = {"receipt": "FEDOMEGA-GEMINI-GATEWAY-CANARY-VERIFIED", "state": "VERIFIED",
            "project_id": "sov-hybrid-suite", "project_number": "257649435135",
            "runtime_service_account": "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
            "normal_traffic_percent": 0, "provider_request_id": "synthetic-request", "model_identity": "synthetic-model",
            "production_promotion_performed": False, "case_data_processed": False, "cleanup_verified": True,
            "ephemeral_service": True, "ephemeral_service_deleted": True, "receipt_sha256": "synthetic-receipt"}
        self.assertIs(True, self.workflow_guard("g3_ok", g3=receipt, g3_code=0))
        for changes in ({"normal_traffic_percent": 1}, {"production_promotion_performed": True},
                        {"case_data_processed": True}, {"cleanup_verified": False}, {"cleanup_verified": "true"},
                        {"ephemeral_service_deleted": False}, {"provider_request_id": ""},
                        {"runtime_service_account": "unapproved@example.invalid"}):
            self.assertFalse(self.workflow_guard("g3_ok", g3=dict(receipt, **changes), g3_code=0))
        self.assertIs(False, self.workflow_guard("g3_ok", g3=receipt, g3_code=1))
        self.assertIn('.adc_verified == true and .gemini_private_canary_verified == true', self.workflow)
        self.assertIn('.gemini_private_canary_ephemeral_service_deleted == true and .gemini_private_canary_production_service_mutated == false', self.workflow)


if __name__ == "__main__":
    unittest.main()
