from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/fuse-mobile-iap-phase-a-v1.yml"
WORKFLOW = ROOT / WORKFLOW_PATH
POLICY = ROOT / "governance/github_airlock_policy.json"
TITLE = "[FO-DISPATCH] FUSE_MOBILE_IAP_PHASE_A_V1"


class FuseMobileIapPhaseAV1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW.is_file():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.lower = cls.text.lower()
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_owner_only_one_use_issue_gate(self) -> None:
        self.assertIn("issues:\n    types: [opened]", self.text)
        self.assertIn(f"github.event.issue.title == '{TITLE}'", self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)
        self.assertNotIn("workflow_dispatch:", self.text)
        self.assertNotIn("\npush:", self.text)
        self.assertNotIn("\nschedule:", self.text)

    def test_keyless_identity_and_exact_target(self) -> None:
        self.assertIn("id-token: write", self.text)
        self.assertIn("PROJECT_ID: sov-hybrid-suite", self.text)
        self.assertIn("PROJECT_NUMBER: '257649435135'", self.text)
        self.assertIn("REGION: africa-south1", self.text)
        self.assertIn("SERVICE: fuse-mobile-gateway", self.text)
        self.assertIn(
            "DEPLOYER_SA: superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            self.text,
        )
        self.assertIn(
            "IAP_SERVICE_AGENT: service-257649435135@gcp-sa-iap.iam.gserviceaccount.com",
            self.text,
        )
        self.assertIn("persist-credentials: false", self.text)

    def test_phase_a_contains_only_required_provider_mutations(self) -> None:
        self.assertIn('gcloud services enable "$IAP_API"', self.text)
        self.assertIn('gcloud run services update "$SERVICE"', self.text)
        self.assertIn("--iap --quiet", self.text)
        self.assertIn('gcloud run services add-iam-policy-binding "$SERVICE"', self.text)
        self.assertIn('--member="serviceAccount:$IAP_SERVICE_AGENT"', self.text)
        self.assertIn('--role="roles/run.invoker"', self.text)

        forbidden = (
            "--allow-unauthenticated",
            "update-traffic",
            "gcloud run deploy",
            "gcloud iap web add-iam-policy-binding",
            "gcloud iap oauth-clients",
            "gcloud secrets versions access",
            "--update-env-vars",
            "--set-env-vars",
        )
        for marker in forbidden:
            self.assertNotIn(marker, self.lower)

    def test_readback_guards_privacy_and_traffic(self) -> None:
        required = (
            '"cloud_run_iap_enabled"',
            '"iap_service_agent_invoker_present"',
            '"public_invoker_present"',
            '"traffic_change_performed"',
            '"oauth_mutation_performed": False',
            '"owner_access_grant_performed": False',
            '"programmatic_client_allowlist_mutation_performed": False',
            '"secret_read_or_mutation_performed": False',
            '"service_invocation_performed": False',
            '"model_inference_performed": False',
            '"raw_error_text_recorded": False',
            '"credential_value_recorded": False',
            '"state": "PHASE_A_VERIFIED"',
        )
        for marker in required:
            self.assertIn(marker, self.text)
        self.assertIn("traffic_unchanged", self.text)
        self.assertIn('members & {"allUsers", "allAuthenticatedUsers"}', self.text)

    def test_airlock_registers_exact_effect_gateway(self) -> None:
        policy = self.policy
        self.assertIn(WORKFLOW_PATH, policy["active_workflow_allowlist"])
        self.assertEqual(policy["allowed_events"][WORKFLOW_PATH], ["issues"])
        self.assertIn(WORKFLOW_PATH, policy["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, policy["provider_mutation_workflow_allowlist"])
        self.assertEqual(
            policy["provider_mutation_exact_issue_titles"][WORKFLOW_PATH],
            TITLE,
        )
        self.assertIn(WORKFLOW_PATH, policy["execution_quarantine"]["keep_active"])

        required = set(policy["provider_mutation_required_markers"][WORKFLOW_PATH])
        self.assertTrue({
            "gcloud services enable",
            "iap.googleapis.com",
            "gcloud run services update",
            "--iap",
            "gcp-sa-iap.iam.gserviceaccount.com",
            "roles/run.invoker",
            "public_invoker_present",
            "traffic_change_performed",
            "oauth_mutation_performed",
            "owner_access_grant_performed",
        }.issubset(required))

        forbidden = set(policy["provider_mutation_forbidden_markers"][WORKFLOW_PATH])
        self.assertTrue({
            "--allow-unauthenticated",
            "update-traffic",
            "gcloud run deploy",
            "gcloud iap web add-iam-policy-binding",
            "gcloud iap oauth-clients",
            "gcloud secrets versions access",
            "--update-env-vars",
            "--set-env-vars",
        }.issubset(forbidden))

    def test_read_only_currentness_court_keeps_no_mutation_authority(self) -> None:
        currentness = ".github/workflows/fuse-mobile-provider-currentness-v1.yml"
        self.assertNotIn(currentness, self.policy["provider_mutation_workflow_allowlist"])


if __name__ == "__main__":
    unittest.main()
