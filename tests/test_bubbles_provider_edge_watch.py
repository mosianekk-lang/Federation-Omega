import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "bubbles" / "provider_edge_watch_contract.json"


class BubblesProviderEdgeWatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_identity_and_required_edges(self):
        self.assertEqual(self.data["schema"], "BUBBLES-PROVIDER-EDGE-WATCH-V1")
        ids = {edge["id"] for edge in self.data["edges"]}
        self.assertEqual(
            ids,
            {
                "apps_script_provider_deployment",
                "google_cloud_wif",
                "github_native_governance",
                "private_privileged_executor",
                "google_ai_studio_provider",
            },
        )

    def test_single_edge_never_freezes_bubbles(self):
        policy = self.data["automatic_action_policy"]
        self.assertTrue(policy["continue_unaffected_work"])
        self.assertFalse(policy["freeze_entire_bubbles_on_single_edge"])
        self.assertFalse(policy["duplicate_watcher_creation"])

    def test_legacy_fogas_secret_reuse_is_forbidden(self):
        edge = next(x for x in self.data["edges"] if x["id"] == "apps_script_provider_deployment")
        self.assertIn("reuse_legacy_approval_secret", edge["forbidden"])
        self.assertIn("copy_secret_to_sheet", edge["forbidden"])
        self.assertFalse(self.data["automatic_action_policy"]["secret_value_access_required"])

    def test_wif_requires_plan_least_privilege_and_provider_verification(self):
        edge = next(x for x in self.data["edges"] if x["id"] == "google_cloud_wif")
        self.assertIn("run_wif_plan", edge["activation_order"])
        self.assertIn("apply_least_privilege_only", edge["activation_order"])
        self.assertIn("provider_verify", edge["activation_order"])
        self.assertEqual(edge["required_terminal_receipt"], "FEDOMEGA-WIF-CLOUD-VERIFIED")

    def test_github_fallback_preserves_admitted_commit_truth(self):
        edge = next(x for x in self.data["edges"] if x["id"] == "github_native_governance")
        self.assertEqual(edge["fallback"], "KIM_DATAVERSE_LAST_ADMITTED_COMMIT_POINTER")
        self.assertIn("trust_unadmitted_branch_tip", edge["forbidden"])
        self.assertIn("disable_airlock_or_leak_guard", edge["forbidden"])

    def test_contract_contains_no_private_pointer_or_secret_value_field(self):
        raw = CONTRACT.read_text(encoding="utf-8").lower()
        self.assertNotIn("approvalkey", raw)
        self.assertNotIn("private spreadsheet", raw)
        self.assertNotIn("api_key", raw)
        self.assertNotIn("access_token", raw)


if __name__ == "__main__":
    unittest.main()
