from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "governance" / "federation_awareness_bootstrap_v1.json"


class FederationBootstrapV15Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(BOOTSTRAP.read_text(encoding="utf-8"))

    def test_controller_is_bound_without_claiming_empirical_stage16(self) -> None:
        self.assertEqual("1.5.0", self.payload["version"])
        self.assertEqual("NCB-004", self.payload["autonomous_evolution_startup_block"])
        self.assertEqual(
            "governance/federation_autonomous_controller_v1.json",
            self.payload["federation_autonomous_controller_contract"],
        )
        self.assertEqual(
            "evidenceops.caseforge.federation_autonomous_controller",
            self.payload["federation_autonomous_controller_source"],
        )
        rules = self.payload["federation_evolution_rules"]
        self.assertTrue(rules["stages_16_to_20_controller_source_loaded"])
        self.assertTrue(rules["controller_source_is_not_stage16_attestation"])
        self.assertTrue(rules["current_chat_does_not_qualify_stage16"])
        self.assertEqual(
            ["NEW_CHAT", "RESTORED_CHAT", "NON_CHAT_RUNTIME"],
            rules["stage16_qualifying_activation_kinds"],
        )
        self.assertFalse(rules["stage_count_alone_proves_maturity"])
        self.assertFalse(rules["universal_chat_runtime_interception_claimed"])

    def test_bootstrap_requires_controller_private_readback_and_strict_maturity(self) -> None:
        actions = [item["action"] for item in self.payload["bootstrap_sequence"]]
        self.assertIn("LOAD_AUTONOMOUS_EVOLUTION_CONTROLLER_AND_STAGE16_20_CONTRACTS", actions)
        self.assertIn("READ_AUTONOMOUS_EVOLUTION_PRIVATE_CONTROL_PLANES_AND_CURRENT_TWIN_STATE", actions)
        self.assertIn("IF_ELIGIBLE_EVALUATE_RUNTIME_ATTESTATION_WITHOUT_SELF_CERTIFICATION", actions)
        self.assertIn("CLASSIFY_MATURITY_ONLY_THROUGH_STRICT_MATURITY_PROOF_GATE", actions)
        completion = self.payload["completion"]
        self.assertTrue(completion["requires_autonomous_controller_source_readback"])
        self.assertTrue(completion["requires_stage16_empirical_receipt_before_stage16_completion"])
        self.assertTrue(completion["requires_regression_execution_receipt_before_stage17_completion"])
        self.assertTrue(completion["requires_existing_governor_receipt_before_stage18_promotion"])
        self.assertTrue(completion["requires_strict_maturity_receipt_before_stage20_dominance_language"])

    def test_existing_governance_boundaries_remain(self) -> None:
        self.assertFalse(self.payload["credential_rules"]["raw_values_in_public_source"])
        self.assertTrue(self.payload["credential_rules"]["fresh_provider_readback_required"])
        self.assertFalse(self.payload["continuity_rules"]["hidden_closed_chat_access_claimed"])
        self.assertFalse(self.payload["continuity_rules"]["universal_chat_runtime_interception_claimed"])
        self.assertTrue(self.payload["formation_rules"]["provider_gated_effects_held"])
        self.assertTrue(self.payload["formation_rules"]["proof_before_promotion"])


if __name__ == "__main__":
    unittest.main()
