import json
from pathlib import Path
import unittest

from tools.github_airlock import analyse_workflow


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/fuse-mobile-iap-phase-a-v1.yml"
WORKFLOW = ROOT / WORKFLOW_PATH
POLICY = ROOT / "governance/github_airlock_policy.json"
TITLE = "[FO-DISPATCH] FUSE_MOBILE_IAP_PHASE_A_V1"
ACTION = "FUSE_ACTION=ENABLE_CLOUDKMS_API_ONLY"
KMS_API = "cloudkms.googleapis.com"


class FuseKMSApiEnableV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORKFLOW.exists():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.iap = cls.text.split("  enable-iap-phase-a:\n", 1)[1].split("\n  enable-cloudkms-api-only:\n", 1)[0]
        cls.kms = cls.text.split("\n  enable-cloudkms-api-only:\n", 1)[1]

    def test_reuses_existing_airlocked_provider_gateway_without_policy_expansion(self):
        p = self.policy
        self.assertIn(WORKFLOW_PATH, p["active_workflow_allowlist"])
        self.assertEqual(p["allowed_events"][WORKFLOW_PATH], ["issues"])
        self.assertIn(WORKFLOW_PATH, p["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, p["provider_mutation_workflow_allowlist"])
        self.assertEqual(p["provider_mutation_exact_issue_titles"][WORKFLOW_PATH], TITLE)
        findings = analyse_workflow(WORKFLOW_PATH, self.text, p)
        self.assertEqual({row.rule for row in findings}, set())

    def test_iap_and_kms_jobs_are_mutually_exclusive_and_legacy_default_is_preserved(self):
        self.assertIn(TITLE, self.iap)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.iap)
        self.assertIn("!contains(github.event.issue.body, 'FUSE_ACTION=ENABLE_CLOUDKMS_API_ONLY')", self.iap)
        self.assertIn(TITLE, self.kms)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.kms)
        self.assertIn("contains(github.event.issue.body, 'FUSE_ACTION=ENABLE_CLOUDKMS_API_ONLY')", self.kms)
        self.assertIn("gcloud run services update", self.iap)
        self.assertIn("add-iam-policy-binding", self.iap)
        self.assertNotIn("gcloud run services", self.kms)
        self.assertNotIn("add-iam-policy-binding", self.kms)

    def test_kms_job_targets_exactly_one_service_with_bounded_reversible_enablement(self):
        self.assertIn("KMS_API: cloudkms.googleapis.com", self.text)
        self.assertIn('gcloud services enable "$KMS_API"', self.kms)
        self.assertIn('gcloud services disable "$KMS_API"', self.kms)
        self.assertIn("if [[ \"$API_ENABLED_BEFORE\" == \"true\" ]]", self.kms)
        self.assertIn("if [[ \"$MUTATION_PERFORMED\" == \"true\" ]] && [[ \"$API_ENABLED_AFTER\" != \"true\" ]]", self.kms)
        self.assertIn("rollback_only_on_failed_postread':True", self.kms)
        self.assertIn("'service':'cloudkms.googleapis.com'", self.kms)
        self.assertNotIn("gcloud services enable \\", self.kms)

    def test_kms_job_has_no_key_iam_secret_deployment_or_traffic_authority(self):
        forbidden = (
            "gcloud kms",
            "kms keyrings",
            "kms keys",
            "add-iam-policy-binding",
            "remove-iam-policy-binding",
            "set-iam-policy",
            "gcloud secrets",
            "secrets versions access",
            "gcloud run",
            "--allow-unauthenticated",
            "update-traffic",
            "allUsers",
            "aiplatform.googleapis.com",
            "vertex",
        )
        for marker in forbidden:
            self.assertNotIn(marker, self.kms)

    def test_provider_native_pre_post_readback_and_project_fence_are_required(self):
        self.assertIn("gcloud projects describe", self.kms)
        self.assertIn('"$(cat "$ROOT/project-number.txt")" == "$PROJECT_NUMBER"', self.kms)
        self.assertGreaterEqual(self.kms.count("gcloud services list --enabled"), 2)
        self.assertIn("API_ENABLED_BEFORE=false", self.kms)
        self.assertIn("API_ENABLED_AFTER=false", self.kms)
        self.assertIn("CLOUDKMS_API_ENABLE_VERIFIED", self.kms)
        self.assertIn("post']['service_enabled'] is True", self.kms)

    def test_receipt_proves_exact_effect_and_hard_floors(self):
        for marker in (
            "'schema':'FUSE-CLOUDKMS-API-ENABLE-RECEIPT-V1'",
            "'authority_class':'A2_REVERSIBLE_PROVIDER_CONFIGURATION'",
            "'provider_mutation_performed':mutated or rolled_back",
            "'service_enablement_performed':mutated",
            "'iam_mutation_performed':False",
            "'kms_key_operation_performed':False",
            "'secret_read_or_mutation_performed':False",
            "'deployment_performed':False",
            "'traffic_change_performed':False",
            "'customer_effect':False",
            "'owner_pc_effect':False",
            "'raw_error_text_recorded':False",
        ):
            self.assertIn(marker, self.kms)

    def test_existing_iap_airlock_markers_remain_present(self):
        for marker in self.policy["provider_mutation_required_markers"][WORKFLOW_PATH]:
            self.assertIn(marker, self.text)
        for marker in self.policy["provider_mutation_forbidden_markers"][WORKFLOW_PATH]:
            self.assertNotIn(marker, self.text)


if __name__ == "__main__":
    unittest.main()
