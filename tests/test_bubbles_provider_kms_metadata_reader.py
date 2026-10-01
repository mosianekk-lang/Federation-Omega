import json
from pathlib import Path
import unittest

from tools.github_airlock import analyse_workflow


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/bubbles-provider-authority-recovery-probe.yml"
WORKFLOW = ROOT / WORKFLOW_PATH
POLICY = ROOT / "governance/github_airlock_policy.json"
KMS_TITLE = "[FO-READ] FUSE_PROVIDER_METADATA_KMS_P256_V1"
SOVARA_TITLE = "SOVARA_GCP_AUTHORITY_PROBE_V2"


class BubblesProviderKMSMetadataReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORKFLOW.exists():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.probe = cls.text.split("  probe:\n", 1)[1].split("\n  kms-p256-metadata:\n", 1)[0]
        cls.kms = cls.text.split("\n  kms-p256-metadata:\n", 1)[1]

    def test_existing_airlock_governance_is_reused_without_policy_expansion(self):
        self.assertIn(WORKFLOW_PATH, self.policy["active_workflow_allowlist"])
        self.assertEqual(self.policy["allowed_events"][WORKFLOW_PATH], ["issues", "workflow_dispatch"])
        self.assertIn(WORKFLOW_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, self.policy["provider_mutation_workflow_allowlist"])
        findings = analyse_workflow(WORKFLOW_PATH, self.text, self.policy)
        self.assertEqual({row.rule for row in findings}, set())

    def test_issue_titles_isolate_broad_probe_from_kms_reader(self):
        self.assertIn(SOVARA_TITLE, self.probe)
        self.assertNotIn(KMS_TITLE, self.probe)
        self.assertIn(KMS_TITLE, self.kms)
        self.assertNotIn(SOVARA_TITLE, self.kms)
        self.assertIn("github.event_name == 'issues'", self.kms)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.kms)

    def test_kms_job_uses_only_read_metadata_and_public_key_operations(self):
        for required in (
            "services','list",
            "config.name=cloudkms.googleapis.com",
            "kms','keyrings','list",
            "kms','keys','list",
            "kms','keys','versions','list",
            "kms','keys','versions','get-public-key",
            "EC_SIGN_P256_SHA256",
            "ASYMMETRIC_SIGN",
            "--public-key-format=pem",
            "openssl','pkey','-pubin",
            "public_jwk_sha256",
            "raw_public_pem_recorded':False",
        ):
            self.assertIn(required, self.kms)

        for forbidden in (
            "secrets.FO_ADMIN_TOKEN",
            "secrets.ARCHON_ADMIN_TOKEN",
            "gcloud','secrets",
            "secrets','versions','access",
            "kms','keyrings','create",
            "kms','keys','create",
            "kms','keys','versions','create",
            "kms','keys','versions','destroy",
            "kms','keys','versions','disable",
            "kms','keys','versions','enable",
            "add-iam-policy-binding",
            "set-iam-policy",
            "services','enable",
            "run','deploy",
            "/execute",
            "ARCHON_ADMIN_URL",
            "DIRECT_FO_TOKEN",
            "DIRECT_ARCHON_TOKEN",
        ):
            self.assertNotIn(forbidden, self.kms)

    def test_denial_classifier_is_bounded_and_raw_error_is_not_persisted(self):
        for marker in (
            "def classify_error(stderr:str)",
            "API_DISABLED_OR_NOT_USED",
            "PERMISSION_DENIED",
            "RESOURCE_OR_LOCATION_INVALID",
            "OTHER_REDACTED_ERROR",
            "cloudkms_api_enabled",
            "cloudkms_service_error_sha256",
            "cloudkms_service_error_class",
            "keyrings_error_class",
            "'raw_error_recorded':False",
        ):
            self.assertIn(marker, self.kms)
        self.assertNotIn("'stderr':p.stderr", self.kms)
        self.assertNotIn("'stderr':p.stderr.strip", self.kms)

    def test_receipt_hard_floors_remain_false(self):
        for marker in (
            "'secret_values_recorded':False",
            "'private_key_accessed':False",
            "'provider_mutation_performed':False",
            "'iam_mutation_performed':False",
            "'service_enablement_performed':False",
            "'deployment_performed':False",
            "'traffic_change_performed':False",
            "'customer_effect':False",
            "'owner_pc_effect':False",
        ):
            self.assertIn(marker, self.kms)

    def test_locations_and_candidate_contract_are_exact(self):
        self.assertIn("locations=('global','africa-south1')", self.kms)
        self.assertIn("'query':'KMS_P256_SIGNERS'", self.kms)
        self.assertIn("'schema':'FUSE-PROVIDER-METADATA-RECEIPT-V2'", self.kms)
        self.assertIn("candidate_count", self.kms)
        self.assertIn("visible_enabled_p256_version_count", self.kms)
        for state in (
            "KMS_API_DISABLED_OR_NOT_ENABLED",
            "KMS_METADATA_PERMISSION_DENIED",
            "REUSABLE_P256_CANDIDATES_FOUND",
            "NO_REUSABLE_P256_CANDIDATES",
            "P256_VERSIONS_VISIBLE_PUBLIC_KEY_READ_INCOMPLETE",
            "KMS_METADATA_READ_PARTIAL_OR_DENIED",
        ):
            self.assertIn(state, self.kms)


if __name__ == "__main__":
    unittest.main()
