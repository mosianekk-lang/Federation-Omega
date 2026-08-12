import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "ops" / "fogas_v23_security_contract.json"


class FOGASV23SecurityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_verified_hashes_are_bound(self):
        self.assertEqual(
            self.data["source_sha256"],
            "46b5244823e662c99a37984ab10ef2244e3af215b50a9774e1b812750b1220d3",
        )
        self.assertEqual(
            self.data["package_sha256"],
            "3372d73fd5a54f6d823f250e814404773c334686534c35560fdbd19e83b3be9a",
        )

    def test_private_pointer_and_secret_values_are_not_public(self):
        self.assertFalse(self.data["private_artifact_pointer_publicly_stored"])
        text = CONTRACT.read_text(encoding="utf-8").lower()
        self.assertNotIn("1bimvstr5ndwppzjswoiryok0mqj4l2rq", text)
        self.assertNotIn("fo_gas_gateway_approval_key=", text)

    def test_v23_is_read_only_and_secret_safe(self):
        props = self.data["v23_security_properties"]
        self.assertTrue(props["owner_execution_required"])
        self.assertFalse(props["dry_run_queue_requires_approval_secret"])
        self.assertTrue(props["operational_approval_columns_scrubbed"])
        self.assertFalse(props["plaintext_approval_storage_in_sheets"])
        self.assertFalse(props["rotation_returns_secret"])
        self.assertTrue(props["rotation_records_fingerprint_only"])
        self.assertFalse(props["webhook_enabled"])
        self.assertFalse(props["live_mutations_enabled"])
        self.assertTrue(props["approval_cell_cleared_after_processing"])

    def test_provider_state_is_not_overpromoted(self):
        provider = self.data["current_provider_state"]
        self.assertTrue(provider["processor_reachable"])
        self.assertFalse(provider["provider_source_update_authority"])
        self.assertFalse(provider["direct_apps_script_api_exposed"])
        self.assertFalse(provider["live_mutations_enabled"])
        self.assertTrue(provider["security_hold"])
        self.assertEqual(self.data["source_state"], "STATICALLY_VERIFIED_STAGED_NOT_DEPLOYED")

    def test_post_deploy_proof_is_mandatory(self):
        required = set(self.data["required_post_deploy_gates"])
        self.assertIn("RUN_ROTATE_FO_GAS_APPROVAL_SECRET_V23", required)
        self.assertIn("NO_PLAINTEXT_APPROVAL_IN_CONFIG_INBOX_OR_BULK_QUEUE", required)
        self.assertIn("OWNER_ONLY_READ_ONLY_DRY_RUN_CANARY", required)
        self.assertIn("LIVE_MUTATION_REJECTION_CANARY", required)
        self.assertIn("PROCESS_V23_COMPLETE_READBACK", required)


if __name__ == "__main__":
    unittest.main()
