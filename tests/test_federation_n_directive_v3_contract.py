from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NDirectiveV3ContractTests(unittest.TestCase):
    def test_n_v3_preserves_authority_and_adds_parallel_prompt_fabric(self):
        text = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        required = (
            "policy_id: FEDOMEGA-N-DIRECTIVE-V3",
            "version: 3.0.0",
            "authority_ceiling: A1_INTERNAL",
            "external_effect_default: false",
            "compile unfinished work into a finite dependency DAG",
            "execute the maximum useful parallelism for effect-free independent work",
            "must_serialize:",
            "provider mutations",
            "repeated_fingerprint_threshold: 2",
            "MATERIALLY_DIFFERENT_ROUTE_REQUIRED",
            "evaluate prompt friction with the CFBE Prompt Scientist",
            "critical regression",
            "PRODUCTION_VERIFIED",
            "ten_x_is_a_measured_target_not_a_prompt_claim: true",
        )
        for marker in required:
            self.assertIn(marker, text)

    def test_compiler_contract_is_safe_by_default(self):
        contract = json.loads((ROOT / "governance/cfbe_parallel_mission_compiler_v4.json").read_text())
        self.assertEqual(contract["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(contract["external_effect_default"])
        self.assertTrue(contract["composition"]["does_not_create_second_sovereign_scheduler"])
        self.assertFalse(contract["truth_boundary"]["stored_source_proves_runtime"])
        self.assertEqual(contract["failure_recovery"]["same_fingerprint_threshold"], 2)

    def test_architecture_contract_records_v3_composition_without_global_instruction_dependency(self):
        text = (ROOT / "docs/architecture/CFBE_PARALLEL_PROMPT_FABRIC_V4.md").read_text()
        self.assertIn("CFBE Parallel Prompt Fabric v4", text)
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V3", text)
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V2@2.1.0", text)
        self.assertIn("rollback/historical compatibility", text)
        self.assertIn("Prompt Scientist", text)
        self.assertIn("PRODUCTION_VERIFIED", text)
        self.assertIn("10x", text)

    def test_node_bootstrap_v3_composes_v2_and_requires_v3_engines(self):
        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        self.assertTrue(bootstrap["predecessor_must_pass"])
        self.assertEqual(bootstrap["predecessor_bootstrap"], "governance/federation_node_bootstrap_v2.json")
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V2", bootstrap["inherited_policies"])
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V3", bootstrap["inherited_policies"])
        self.assertIn("CFBE-PARALLEL-MISSION-COMPILER-V4", bootstrap["inherited_policies"])
        self.assertIn("CFBE-PROMPT-SCIENTIST-V1", bootstrap["inherited_policies"])
        self.assertFalse(bootstrap["authority"]["external_effect_default"])
        self.assertFalse(bootstrap["prompt_evolution"]["constitutional_invariants_mutable"])
        self.assertTrue(bootstrap["activation"]["requires_merged_main_readback"])
        self.assertTrue(bootstrap["activation"]["master_bible_reconciliation_required"])

    def test_prompt_scientist_contract_has_exact_100_point_score_and_absolute_veto(self):
        contract = json.loads((ROOT / "governance/cfbe_prompt_scientist_v1.json").read_text())
        self.assertEqual(sum(contract["score_weights"].values()), 100)
        self.assertTrue(contract["promotion"]["critical_regression_is_absolute_veto"])
        self.assertTrue(contract["promotion"]["rollback_to_incumbent_required"])
        self.assertFalse(contract["truth_boundary"]["autonomous_model_weight_retraining_claimed"])


if __name__ == "__main__":
    unittest.main()
