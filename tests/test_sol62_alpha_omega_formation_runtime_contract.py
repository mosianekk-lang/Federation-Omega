from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Sol62AlphaOmegaFormationRuntimeContractTests(unittest.TestCase):
    def test_runtime_has_real_formation_and_alpha_omega_bindings(self):
        binding = (ROOT / "services" / "sol62_client_runtime" / "alpha_omega_formation_binding.py").read_text(encoding="utf-8")
        self.assertIn("EvidenceOpsAlgorithmFoundry", binding)
        self.assertIn("compile_of50_formation_decision", binding)
        self.assertIn("AlphaOmegaEngine", binding)
        self.assertIn("compile_of50_alpha_omega_packet", binding)
        self.assertIn('AUTHORITY_CEILING = "A1_INTERNAL"', binding)
        self.assertIn('"external_effect_created": False', binding)
        self.assertIn('"provider_execution_verified": False', binding)
        self.assertIn('"source_admitted": False', binding)

    def test_runtime_api_exposes_and_persists_strategy(self):
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"/v1/missions/{mission_id}/strategy"', app)
        self.assertIn('"sol62.strategy.receipt"', app)
        self.assertIn("SOL62_ALPHA_OMEGA_FORMATION_STRATEGY_COMPILED", app)
        self.assertIn("SOL62_ALPHA_OMEGA_FORMATION_WAKE_PREPASS", app)
        self.assertIn('reason="MISSION_WAKE_PREPASS"', app)

    def test_harvester_embeds_strategy_receipt_in_build_packet(self):
        harvester = (ROOT / "services" / "sol62_client_runtime" / "autonomous_harvester.py").read_text(encoding="utf-8")
        self.assertIn("Sol62AlphaOmegaFormationBinding", harvester)
        self.assertIn('"alpha_omega_formation"', harvester)
        self.assertIn("strategy_receipt = self.strategy.compile", harvester)
        self.assertIn('"source_mutation_authority_granted": False', harvester)
        self.assertIn('"provider_effect_authority_granted": False', harvester)

    def test_planning_never_promotes_to_execution_proof(self):
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"planning_is_execution_proof": False', app)
        self.assertIn('"external_effect": False', app)
        self.assertIn('"authority_widened": False', app)


if __name__ == "__main__":
    unittest.main()
