from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/fkcm-pubsub-shadow-canary.yml"
AIRLOCK_POLICY = ROOT / "governance/github_airlock_policy.json"
WORKFLOW_PATH = ".github/workflows/fkcm-pubsub-shadow-canary.yml"


class FkcmPubSubShadowCanaryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(AIRLOCK_POLICY.read_text(encoding="utf-8"))

    def test_owner_exact_trigger(self):
        self.assertIn("MODISA_FKCM_PUBSUB_SHADOW_CANARY_V1", self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)
        self.assertRegex(self.text, r"(?m)^\s{0,4}issues\s*:")
        self.assertNotRegex(self.text, r"(?m)^\s{0,4}workflow_dispatch\s*:")

    def test_keyless_wif_only(self):
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.text)
        self.assertIn("workloadIdentityPools/github-federation-omega/providers/github", self.text)
        self.assertNotIn("service_account_key", self.text)

    def test_external_actions_are_immutable(self):
        expected = {
            "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
            "google-github-actions/auth": "7c6bc770dae815cd3e89ee6cdf493a5fab2cc093",
            "google-github-actions/setup-gcloud": "e427ad8a34f8676edf47cf7d7925499adf3eb74f",
            "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
        }
        for action, sha in expected.items():
            self.assertIn(f"{action}@{sha}", self.text)
        for ref in re.findall(r"\buses\s*:\s*([^\s#]+)", self.text):
            if ref.startswith("./"):
                continue
            self.assertRegex(ref.rsplit("@", 1)[-1], r"^[0-9a-fA-F]{40}$")

    def test_airlock_registration_is_exact_and_bounded(self):
        self.assertIn(WORKFLOW_PATH, self.policy["active_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertEqual(self.policy["allowed_events"][WORKFLOW_PATH], ["issues"])
        self.assertIn(WORKFLOW_PATH, self.policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(WORKFLOW_PATH, self.policy.get("provider_mutation_workflow_allowlist", []))
        self.assertNotIn(WORKFLOW_PATH, self.policy.get("actions_write_workflow_allowlist", []))
        self.assertNotIn(WORKFLOW_PATH, self.policy.get("statuses_write_workflow_allowlist", []))

    def test_provider_preflight_is_json_validated_and_explicit(self):
        self.assertIn('gcloud projects describe "$PROJECT_ID" --format=json', self.text)
        self.assertIn('gcloud services list --enabled --project "$PROJECT_ID" --format=json', self.text)
        self.assertIn('gcloud pubsub topics describe "$TOPIC_ID" --project "$PROJECT_ID" --format=json', self.text)
        self.assertIn("project_readback=verified", self.text)
        self.assertIn("service_usage_readback=verified", self.text)
        self.assertIn("topic_readback=verified", self.text)
        self.assertIn("preflight=verified", self.text)
        self.assertIn("project_id_mismatch", self.text)
        self.assertIn("project_number_mismatch", self.text)
        self.assertIn("pubsub_service_not_enabled", self.text)
        self.assertIn("topic_name_mismatch", self.text)
        self.assertNotIn("--format='value(NAME)'", self.text)
        self.assertNotIn("--format='value(config.name)'", self.text)

    def test_existing_topic_is_required_not_created(self):
        self.assertIn('gcloud pubsub topics describe "$TOPIC_ID"', self.text)
        self.assertNotIn("gcloud pubsub topics create", self.text)
        self.assertIn("evidenceops-heartbeat-events", self.text)

    def test_isolated_temporary_subscription_only(self):
        self.assertIn("gcloud pubsub subscriptions create \"$SUB_ID\"", self.text)
        self.assertIn("--message-filter \"$FILTER\"", self.text)
        self.assertIn("gcloud pubsub subscriptions delete \"$SUB_ID\"", self.text)
        self.assertNotIn("evidenceops-heartbeat-operator --", self.text)
        self.assertNotIn("evidenceops-heartbeat-verifier --", self.text)

    def test_publish_consume_and_message_id_equivalence(self):
        self.assertIn("gcloud pubsub topics publish", self.text)
        self.assertIn("gcloud pubsub subscriptions pull", self.text)
        self.assertIn('test "$CONSUMER_MESSAGE_ID" = "$PUBLISH_ID"', self.text)

    def test_no_high_risk_cloud_mutation_commands(self):
        forbidden = [
            "gcloud projects add-iam-policy-binding",
            "gcloud iam service-accounts",
            "gcloud run deploy",
            "gcloud services enable",
            "gcloud secrets versions access",
            "gcloud pubsub topics create",
        ]
        for command in forbidden:
            self.assertNotIn(command, self.text)

    def test_receipt_discloses_bounded_provider_effect(self):
        self.assertIn('"provider_effect":"BOUNDED_PUBLIC_SAFE_HEARTBEAT"', self.text)
        self.assertIn('"temporary_subscription_deleted":True', self.text)
        self.assertIn('"existing_subscriptions_touched":False', self.text)
        self.assertIn('"kdv_cutover":False', self.text)


if __name__ == "__main__":
    unittest.main()
