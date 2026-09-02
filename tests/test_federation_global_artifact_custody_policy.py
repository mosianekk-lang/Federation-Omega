from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "federation_global_artifact_custody_policy_v1.json"
BOOTSTRAP_PATH = ROOT / "governance" / "federation_node_bootstrap_v2.json"
AGENT_INSTRUCTIONS_PATH = (
    ROOT / ".github" / "instructions" / "facp-001-global-artifact-custody.instructions.md"
)
AGENTS_PATH = ROOT / "AGENTS.md"


class FederationGlobalArtifactCustodyPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy_text = POLICY_PATH.read_text(encoding="utf-8")
        cls.policy = json.loads(cls.policy_text)
        cls.bootstrap = json.loads(BOOTSTRAP_PATH.read_text(encoding="utf-8"))
        cls.instructions_present = AGENT_INSTRUCTIONS_PATH.exists()
        cls.instructions = (
            AGENT_INSTRUCTIONS_PATH.read_text(encoding="utf-8")
            if cls.instructions_present
            else ""
        )
        cls.agents = AGENTS_PATH.read_text(encoding="utf-8")

    def test_policy_identity_scope_and_authority_are_fail_closed(self) -> None:
        self.assertEqual("FACP-001", self.policy["policy_id"])
        self.assertEqual("1.0.0", self.policy["version"])
        scope = self.policy["scope"]
        self.assertTrue(scope["current_registered_chats_and_nodes"])
        self.assertTrue(scope["future_registered_chats_and_nodes"])
        self.assertEqual(
            "UNBOUND_UNTIL_AUTHORISED_BOOTSTRAP_OR_FIRST_REGISTERED_MATERIAL_DELTA",
            scope["unbootstrapped_native_chats"],
        )
        self.assertFalse(scope["invisible_closed_chat_control_claimed"])
        authority = self.policy["authority"]
        self.assertEqual("A1_INTERNAL", authority["ceiling"])
        self.assertFalse(authority["external_effect_default"])
        self.assertFalse(authority["trust_inheritance"])

    def test_public_contract_uses_private_aliases_not_live_private_urls(self) -> None:
        private = self.policy["private_resolution"]
        self.assertFalse(private["exact_private_pointer_in_public_source"])
        self.assertTrue(private["resolve_through_authorised_private_control_plane"])
        self.assertTrue(private["canonical_vault_alias"].startswith("FEDERATION_"))
        self.assertTrue(private["artifact_registry_alias"].startswith("FEDERATION_"))
        self.assertNotIn("drive.google.com", self.policy_text)
        self.assertNotIn("docs.google.com", self.policy_text)

    def test_store_roles_keep_source_artifacts_pointers_and_history_distinct(self) -> None:
        stores = self.policy["canonical_store_roles"]
        self.assertEqual("GITHUB", stores["software_source"]["store"])
        self.assertEqual(
            "FRESH_PURPOSE_SPECIFIC_BRANCH_AND_PULL_REQUEST",
            stores["software_source"]["route"],
        )
        self.assertFalse(stores["software_source"]["direct_main_mutation"])
        self.assertEqual(
            "OWNER_CONTROLLED_GOOGLE_DRIVE_VAULT",
            stores["artifact_custody"]["store"],
        )
        self.assertEqual(
            "FEDERATION_SYNC_BUS_AND_KIM_DATAVERSE",
            stores["state_and_pointers"]["store"],
        )
        self.assertFalse(stores["state_and_pointers"]["artifact_bytes_stored_here"])
        self.assertEqual("OWNING_LOCAL_BIBLE", stores["detailed_history"]["store"])
        self.assertEqual("MASTER_BIBLE", stores["master_summary"]["store"])
        self.assertFalse(stores["session_sandbox"]["canonical"])
        self.assertFalse(stores["session_sandbox"]["completion_proof"])

    def test_lifecycle_and_standard_work_package_tree_are_complete(self) -> None:
        self.assertEqual(
            {"WORKING", "CURRENT", "SUPERSEDED", "HISTORICAL", "QUARANTINED"},
            set(self.policy["lifecycle_states"]),
        )
        self.assertEqual(
            [
                "00_INDEX_AND_CURRENT",
                "01_QUALIFICATION_PACKETS",
                "02_CANDIDATE_SOURCE_AND_PATCH",
                "03_TESTS_AND_ASSURANCE",
                "04_RECEIPTS_AND_HASHES",
                "05_PROVIDER_PROOF",
                "06_ROLLBACK_AND_RESTORE",
                "99_SUPERSEDED",
            ],
            self.policy["standard_work_package_folders"],
        )
        self.assertEqual(
            "QUARANTINED",
            self.policy["lifecycle_rules"]["zero_byte_or_incomplete_artifact"],
        )
        self.assertTrue(
            self.policy["lifecycle_rules"]["one_current_object_per_artifact_identity"]
        )

    def test_completion_cannot_be_satisfied_by_sandbox_output(self) -> None:
        gate = self.policy["completion_gate"]
        required = set(gate["material_artifact_task_complete_only_when"])
        self.assertFalse(gate["sandbox_only_output_is_complete"])
        self.assertEqual("ARTIFACT_CUSTODY_INCOMPLETE", gate["failed_placement_state"])
        self.assertTrue(gate["failed_placement_requires_blocker_and_next_route"])
        for item in {
            "ARTIFACT_BYTES_CREATED_OR_CONFIRMED",
            "CORRECT_CANONICAL_DESTINATION_RESOLVED",
            "UPLOAD_OR_PROVIDER_STORAGE_COMPLETED",
            "EXACT_FILE_OR_PROVIDER_ID_READ_BACK",
            "LIFECYCLE_STATE_ASSIGNED",
            "ARTIFACT_REGISTRY_ROW_WRITTEN",
            "LOCAL_BIBLE_DELTA_RECORDED",
            "CURRENT_AND_SUPERSEDED_RELATIONSHIP_RECONCILED",
        }:
            self.assertIn(item, required)

    def test_existing_bootstrap_and_root_governance_force_private_state_resolution(self) -> None:
        self.assertTrue(self.bootstrap["required_before_substantive_work"])
        sequence = self.bootstrap["n_directive"]["required_sequence"]
        self.assertIn("LOAD_CURRENT_CANONICAL_STATE_AND_ROUTE_AUTHORITY", sequence)
        self.assertIn("LOAD_LATEST_VERIFIED_CHECKPOINT", sequence)
        self.assertIn("governance/federation_node_bootstrap_v2.json", self.agents)
        self.assertIn("Read the current canonical-state and route-authority records", self.agents)
        self.assertIn("Exact private Drive pointers", self.agents)

    def test_repository_wide_instruction_binds_policy_and_truth_boundary(self) -> None:
        if not self.instructions_present:
            self.assertFalse(
                (ROOT / ".git").exists(),
                "FACP-001 repository-wide instruction is missing from a full repository checkout",
            )
            self.skipTest(
                "workflow-free Phoenix Core export intentionally excludes repository instruction controls"
            )
        self.assertIn('applyTo: "**"', self.instructions)
        self.assertIn("FACP-001", self.instructions)
        self.assertIn(
            "governance/federation_global_artifact_custody_policy_v1.json",
            self.instructions,
        )
        self.assertIn("temporary construction storage", self.instructions)
        self.assertIn("Future nodes inherit", self.instructions)
        self.assertIn("unbootstrapped native chat remains unbound", self.instructions)
        self.assertIn("never mutate `main` directly", self.instructions)


if __name__ == "__main__":
    unittest.main()
