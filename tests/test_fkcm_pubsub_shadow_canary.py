from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/fkcm-pubsub-shadow-canary.yml"


class FkcmPubSubShadowCanaryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_owner_exact_trigger(self):
        self.assertIn("MODISA_FKCM_PUBSUB_SHADOW_CANARY_V1", self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)

    def test_keyless_wif_only(self):
        self.assertIn("google-github-actions/auth@v3", self.text)
        self.assertIn("workloadIdentityPools/github-federation-omega/providers/github", self.text)
        self.assertNotIn("service_account_key", self.text)

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
