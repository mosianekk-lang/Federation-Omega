from __future__ import annotations

import json
from pathlib import Path
import unittest


BOOTSTRAP = Path("governance/federation_awareness_bootstrap_v1.json")


class FederationAutonomousBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(BOOTSTRAP.read_text(encoding="utf-8"))

    def test_ncb004_and_controller_are_bound(self) -> None:
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

    def test_source_binding_never_preproves_empirical_maturity(self) -> None:
        rules = self.payload["federation_evolution_rules"]
        self.assertTrue(rules["source_controller_does_not_prove_empirical_stages"])
        self.assertTrue(rules["stage_count_alone_proves_maturity"] is False)
        self.assertTrue(rules["current_chat_cannot_preprove_cross_chat_runtime_attestation"])
        self.assertFalse(rules["universal_chat_runtime_interception_claimed"])

    def test_provider_and_authority_boundaries_remain_closed(self) -> None:
        rules = self.payload["federation_evolution_rules"]
        self.assertTrue(rules["external_or_provider_effects_remain_separately_authorized"])
        self.assertTrue(rules["provider_readback_regression_and_rollback_required_for_dominance_candidate"])
        self.assertTrue(self.payload["credential_rules"]["fresh_provider_readback_required"])

    def test_bootstrap_sequence_loads_controller_before_evolution_execution(self) -> None:
        actions = [item["action"] for item in self.payload["bootstrap_sequence"]]
        controller_index = actions.index("LOAD_AUTONOMOUS_EVOLUTION_NCB_004_CONTROLLER_AND_FRESH_SOURCE_READBACK")
        evolution_index = actions.index("EVALUATE_CURRENT_SYSTEM_EVOLUTION_STAGE_AND_RUN_NEXT_SAFE_STAGE")
        self.assertLess(controller_index, evolution_index)


if __name__ == "__main__":
    unittest.main()
