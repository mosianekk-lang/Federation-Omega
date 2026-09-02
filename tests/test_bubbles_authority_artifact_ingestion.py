from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "superior-logic-maturation-shadow.yml"


class BubblesAuthorityArtifactIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORKFLOW.exists():
            raise unittest.SkipTest(
                "workflow-free Phoenix Core export intentionally excludes repository workflow controls"
            )
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_host_uses_existing_actions_read_authority_only(self) -> None:
        self.assertIn("contents: read", self.workflow)
        self.assertIn("actions: read", self.workflow)
        self.assertNotIn("id-token: write", self.workflow)
        self.assertIn("bubbles-provider-authority-recovery-probe.yml", self.workflow)
        self.assertIn("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", self.workflow)
        self.assertIn("pattern: bubbles-provider-authority-recovery-*", self.workflow)

    def test_hardened_receipt_is_safety_and_freshness_gated(self) -> None:
        self.assertIn("BUBBLES-PROVIDER-AUTHORITY-RECOVERY-PROBE-V2", self.workflow)
        self.assertIn("raw_authenticated_response_bodies_recorded", self.workflow)
        self.assertIn("secret_values_recorded", self.workflow)
        self.assertIn("mutation_attempted", self.workflow)
        self.assertIn("age_seconds <= 86400", self.workflow)
        self.assertIn("UNSAFE_AUTHORITY_RECEIPT_OMITTED", self.workflow)
        self.assertIn("STALE_AUTHORITY_RECEIPT_OMITTED", self.workflow)

    def test_safe_receipt_is_passed_to_existing_activation_compiler(self) -> None:
        self.assertIn("--provider-authority-receipt runtime-output/bubbles-provider-authority-receipt.json", self.workflow)
        self.assertIn("authority_receipt_ingested", self.workflow)
        self.assertIn("provider-surface-receipt runtime-output/bubbles-provider-surface-receipt.json", self.workflow)

    def test_ingestion_does_not_add_repository_or_provider_mutation(self) -> None:
        self.assertNotIn("git push", self.workflow)
        self.assertNotIn("git commit", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("gh api --method post", self.workflow.lower())
        self.assertNotIn("gh api --method put", self.workflow.lower())
        self.assertNotIn("gh api --method patch", self.workflow.lower())
        self.assertNotIn("gh api --method delete", self.workflow.lower())


if __name__ == "__main__":
    unittest.main()
