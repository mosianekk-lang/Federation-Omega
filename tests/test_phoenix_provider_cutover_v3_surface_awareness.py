from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AWARENESS_PATH = ROOT / "governance" / "federation_surface_awareness_v1.json"
BOOTSTRAP_PATH = ROOT / "governance" / "federation_awareness_bootstrap_v1.json"
NODE_PATH = ROOT / "governance" / "federation_node_bootstrap_v2.json"
AGENTS_PATH = ROOT / "AGENTS.md"
COPILOT_PATH = ROOT / ".github" / "copilot-instructions.md"
PRIVATE_HASH = "8961706e5d0e9d1e379ce24b89bb7cf8546cf126adc88e1c93c152d2a979f438"


class FederationSurfaceAwarenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.awareness = json.loads(AWARENESS_PATH.read_text(encoding="utf-8"))
        cls.bootstrap = json.loads(BOOTSTRAP_PATH.read_text(encoding="utf-8"))
        cls.node = json.loads(NODE_PATH.read_text(encoding="utf-8"))
        cls.agents = AGENTS_PATH.read_text(encoding="utf-8")
        cls.copilot = COPILOT_PATH.read_text(encoding="utf-8")

    def test_public_contract_binds_private_manifest_by_alias_and_hash(self) -> None:
        self.assertEqual("FEDOMEGA-SURFACE-AWARENESS-V1", self.awareness["schema"])
        private = self.awareness["private_manifest"]
        self.assertEqual("FEDERATION_AWARENESS_PRIVATE_V1", private["alias"])
        self.assertEqual(PRIVATE_HASH, private["logical_sha256"])
        self.assertFalse(private["exact_pointer_publicly_stored"])
        self.assertTrue(private["runtime_readback_required"])

    def test_required_surfaces_and_engines_are_present(self) -> None:
        aliases = set(self.awareness["mandatory_surface_aliases"])
        required = {
            "FEDERATION_OMEGA_CONTROL_PLANE",
            "KIM_DATAVERSE_PRIVATE_CANONICAL_BRIDGE_V2",
            "FEDERATION_AWARENESS_PRIVATE_V1",
            "FEDERATION_FULL_OPERATING_SURFACE_INDEX",
            "FEDERATION_STARTUP_REGISTER",
            "FEDERATION_DIRECT_RUNTIME",
            "FEDERATION_CONTINUOUS_LEARNING",
            "SOVEREIGN_FEDERATION_CLOUDOPS",
            "FORMATION_INNOVATION_ENGINE",
            "ALPHA_TO_OMEGA_FOUNDRY",
            "NEXT_FRONTIER_AI_BIBLE",
            "SECONDARY_BRAIN",
            "GMAIL_CONTINUITY_CORPUS",
        }
        self.assertTrue(required.issubset(aliases))

    def test_bootstrap_loads_current_source_private_awareness_and_route_state_first(self) -> None:
        actions = [row["action"] for row in self.bootstrap["bootstrap_sequence"]]
        self.assertEqual(
            [
                "READ_CURRENT_GITHUB_MAIN_HEAD",
                "LOAD_AND_VERIFY_PUBLIC_AWARENESS_CONTRACT",
                "RESOLVE_PRIVATE_MANIFEST_ALIAS_THROUGH_KIM_DATAVERSE",
                "VERIFY_PRIVATE_MANIFEST_LOGICAL_SHA256",
                "READ_KIM_DATAVERSE_CONTROL_BOUNDARIES_ALIASES_AND_CURRENT_RECEIPT",
                "READ_FULL_OPERATING_SURFACE_INDEX_CANONICAL_STATE_AND_ROUTE_AUTHORITY",
            ],
            actions[:6],
        )
        self.assertEqual("NCB-002", self.bootstrap["startup_block"])
        self.assertIn("RESOLVE_CREDENTIALS_BY_NON_SECRET_HANDLE_ONLY", actions)

    def test_credentials_and_provider_authority_fail_closed(self) -> None:
        credentials = self.awareness["credential_contract"]
        self.assertFalse(credentials["credential_value_recorded"])
        self.assertFalse(credentials["raw_credential_request_allowed"])
        self.assertTrue(credentials["availability_must_be_revalidated"])
        self.assertTrue(credentials["authority_must_be_revalidated"])
        self.assertFalse(
            self.awareness["truth_boundary"][
                "provider_authority_inferred_from_stored_reference"
            ]
        )
        self.assertTrue(
            self.awareness["truth_boundary"][
                "provider_activation_requires_native_readback"
            ]
        )

    def test_public_awareness_files_contain_no_private_exact_pointers_or_secret_values(self) -> None:
        public_text = AWARENESS_PATH.read_text(encoding="utf-8") + BOOTSTRAP_PATH.read_text(
            encoding="utf-8"
        )
        private_values = (
            "1KfJVGnlgsdiXC_LOqtB0uSyCf94XdDXrhkxK5vNHM00",
            "1dnbLsLf97_dfX12Bd_rNfIhHp01Sf5Rl_pnqKFgJuds",
            "1XThhZmYI7FpphUFaM9aep3E0KG-criq4HV74C5aH534",
            "1FEFyNY-QJowLNc9T5fliCMUtK1XlZN3oyB2j-H1AUfw",
            "19fbb0ce6ae8e1ae",
        )
        for value in private_values:
            self.assertNotIn(value, public_text)
        secret_patterns = (
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
            re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
        )
        self.assertFalse(any(pattern.search(public_text) for pattern in secret_patterns))

    def test_node_and_agent_bootstraps_require_awareness(self) -> None:
        awareness = self.node["surface_awareness"]
        self.assertEqual("2.2.0", self.node["version"])
        self.assertEqual("Kim Kagiso Mosiane", self.node["owner"])
        self.assertTrue(awareness["required"])
        self.assertEqual(
            "governance/federation_surface_awareness_v1.json",
            awareness["public_contract"],
        )
        self.assertEqual("FEDERATION_AWARENESS_PRIVATE_V1", awareness["private_manifest_alias"])
        for text in (self.agents, self.copilot):
            self.assertIn("federation_surface_awareness_v1.json", text)
            self.assertIn("federation_awareness_bootstrap_v1.json", text)
            self.assertIn("FEDERATION_AWARENESS_PRIVATE_V1", text)
            self.assertIn("provider", text.lower())
            self.assertIn("readback", text.lower())

    def test_continuity_truth_boundary_rejects_hidden_memory_and_runtime_inference(self) -> None:
        truth = self.awareness["truth_boundary"]
        self.assertFalse(truth["hidden_cross_chat_access_claimed"])
        self.assertFalse(truth["background_runtime_claimed"])
        self.assertFalse(truth["gmail_message_proves_current_runtime"])
        self.assertFalse(truth["bridge_bound_means_all_providers_bound"])
        self.assertTrue(self.bootstrap["continuity_rules"]["gmail_is_source_evidence_only"])
        self.assertFalse(
            self.bootstrap["continuity_rules"]["hidden_closed_chat_access_claimed"]
        )


if __name__ == "__main__":
    unittest.main()
