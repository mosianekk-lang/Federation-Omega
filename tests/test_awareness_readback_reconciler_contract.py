from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = ROOT / "federation_consolidation" / "awareness_readback_reconciler.py"
CONTRACT = ROOT / "governance" / "federation_awareness_readback_reconciler_v1.json"
FOUNDRY = ROOT / "governance" / "federation_awareness_opportunity_foundry_v1.json"


class ReadbackReconcilerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.foundry = json.loads(FOUNDRY.read_text(encoding="utf-8"))

    def test_contract_binds_implementation_and_foundry(self):
        self.assertEqual(
            "FEDOMEGA-AWARENESS-READBACK-RECONCILER-CONTRACT-1",
            self.contract["schema"],
        )
        self.assertTrue(IMPLEMENTATION.is_file())
        self.assertEqual(
            "federation_consolidation/awareness_readback_reconciler.py",
            self.contract["implementation"],
        )
        binding = self.foundry["readback_reconciler"]
        self.assertEqual(
            "governance/federation_awareness_readback_reconciler_v1.json",
            binding["contract"],
        )
        self.assertTrue(binding["required_after_provider_readback"])

    def test_read_proof_advances_without_authority_expansion(self):
        lifecycle = self.contract["lifecycle_contract"]
        truth = self.contract["truth_boundary"]
        self.assertTrue(lifecycle["read_probe_verified_closes_original_probe"])
        self.assertTrue(lifecycle["read_probe_verified_creates_effectful_successor"])
        self.assertFalse(truth["read_access_proves_write_authority"])
        self.assertFalse(truth["source_merge_proves_provider_deployment"])
        self.assertTrue(truth["provider_effects_require_fresh_authority_and_native_readback"])
        self.assertFalse(
            self.foundry["truth_boundary"]["provider_read_access_proves_effectful_authority"]
        )

    def test_merge_result_proof_is_mandatory(self):
        lifecycle = self.contract["lifecycle_contract"]
        self.assertTrue(lifecycle["merge_result_airlock_required"])
        self.assertTrue(lifecycle["merge_result_leak_guard_required"])
        self.assertTrue(lifecycle["merge_result_phoenix_freeze_required"])

    def test_no_credentials_or_provider_effects(self):
        truth = self.contract["truth_boundary"]
        self.assertFalse(truth["provider_mutation_performed"])
        self.assertFalse(truth["external_effect_performed"])
        self.assertFalse(truth["credential_value_recorded"])


if __name__ == "__main__":
    unittest.main()
