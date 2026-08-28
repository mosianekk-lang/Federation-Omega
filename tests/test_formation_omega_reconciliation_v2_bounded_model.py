from __future__ import annotations

import unittest

from formation_omega.reconciliation_v2_bounded_model import (
    AdmissionModelState,
    exhaustive_check,
    invariants,
)


class ReconciliationV2BoundedModelTests(unittest.TestCase):
    def test_all_reachable_bounded_states_preserve_constitutional_invariants(self):
        result = exhaustive_check()
        self.assertGreater(result.reachable_state_count, 20)
        self.assertGreater(result.transition_count, result.reachable_state_count)
        self.assertTrue(result.safe, "\n".join(result.violations))
        self.assertEqual((), result.violations)

    def test_oracle_detects_stale_permit_merge(self):
        bad = AdmissionModelState(
            main="MAIN_B",
            head="HEAD_A",
            checked_head="HEAD_A",
            permit_main="MAIN_A",
            permit_head="HEAD_A",
            merged=True,
        )
        self.assertIn("NO_STALE_PERMIT_MERGE", invariants(bad))

    def test_oracle_detects_semantic_conflict_merge(self):
        bad = AdmissionModelState(semantic_conflict=True, merged=True)
        self.assertIn("NO_MERGE_ON_SEMANTIC_CONFLICT", invariants(bad))

    def test_oracle_detects_a1_external_effect_merge(self):
        bad = AdmissionModelState(external_effect=True, merged=True)
        self.assertIn("NO_A1_EXTERNAL_EFFECT_AT_MERGE", invariants(bad))

    def test_oracle_detects_closure_without_rollback(self):
        bad = AdmissionModelState(merged=True, closed=True, rollback_available=False)
        self.assertIn("ROLLBACK_REQUIRED_FOR_MERGE", invariants(bad))
        self.assertIn("CLOSURE_REQUIRES_ROLLBACK", invariants(bad))


if __name__ == "__main__":
    unittest.main()
