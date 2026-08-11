from __future__ import annotations

import fnmatch
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "cloudops_runtime_freshness_verifier_v1.json"
IMPLEMENTATION = (
    ROOT / "federation_consolidation" / "cloudops_runtime_freshness_verifier.py"
)
POLICY = ROOT / "phoenix" / "export_policy.json"
THIS_TEST = (
    "tests/test_phoenix_provider_cutover_v3_"
    "cloudops_runtime_freshness_contract.py"
)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_contract_binds_implementation(self):
        self.assertEqual(
            "FEDOMEGA-CLOUDOPS-RUNTIME-FRESHNESS-CONTRACT-1",
            self.contract["schema"],
        )
        self.assertTrue(IMPLEMENTATION.is_file())
        self.assertEqual(
            str(IMPLEMENTATION.relative_to(ROOT)),
            self.contract["implementation"],
        )

    def test_freshness_and_truth_boundaries(self):
        fresh = self.contract["freshness_contract"]
        truth = self.contract["truth_boundary"]
        self.assertFalse(fresh["stored_done_label_proves_current_runtime"])
        self.assertFalse(fresh["undated_rows_prove_current_state"])
        self.assertFalse(truth["historical_success_proves_current_liveness"])
        self.assertTrue(truth["fresh_provider_readback_required_for_promotion"])
        self.assertFalse(truth["provider_mutation_performed"])
        self.assertFalse(truth["credential_value_recorded"])

    def test_contract_test_is_excluded_from_standalone_core(self):
        patterns = self.policy["core"]["excluded_test_globs"]
        self.assertTrue(
            any(fnmatch.fnmatchcase(THIS_TEST, pattern) for pattern in patterns)
        )
        export = self.contract["export_classification"]
        self.assertEqual(
            "PORTABLE_DETERMINISTIC_CORE_CAPABILITY", export["class"]
        )
        self.assertTrue(export["implementation_expected_in_core_archive"])
        self.assertTrue(export["behaviour_tests_expected_in_core_archive"])
        self.assertTrue(export["contract_test_runs_in_phoenix_v3_suite"])


if __name__ == "__main__":
    unittest.main()
