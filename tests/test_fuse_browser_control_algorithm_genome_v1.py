from __future__ import annotations

import unittest

from federation.browser_control_algorithm_genome_v1 import (
    ALGORITHMS,
    algorithm_summary,
    select_algorithms,
    validate_algorithms,
)


class FuseBrowserControlAlgorithmGenomeTests(unittest.TestCase):
    def test_exactly_50_monotonic_unique_algorithms(self):
        validate_algorithms()
        ids = [row.algorithm_id for row in ALGORITHMS]
        self.assertEqual(len(ids), 50)
        self.assertEqual(ids[0], "FBCP-001")
        self.assertEqual(ids[-1], "FBCP-050")
        self.assertEqual(len(ids), len(set(ids)))

    def test_browser_control_genome_cannot_create_authority_or_truth_root(self):
        summary = algorithm_summary()
        self.assertFalse(summary["authority_expansion"])
        self.assertFalse(summary["new_controller"])
        self.assertFalse(summary["new_truth_root"])
        self.assertIn("ALGORITHM_REGISTERED_NE_SOURCE_IMPLEMENTED", summary["truth_boundary"])

    def test_new_tab_query_selects_direct_tab_control(self):
        selected = select_algorithms(
            "open ChatGPT new chat in another tab and keep current tab alive",
            limit=10,
        )
        ids = {row.algorithm_id for row in selected}
        self.assertIn("FBCP-018", ids)
        self.assertTrue({"FBCP-006", "FBCP-026"} & ids)

    def test_ui_drift_query_selects_semantic_resilience(self):
        selected = select_algorithms(
            "ChatGPT UI changed and semantic control locator is stale",
            limit=12,
        )
        ids = {row.algorithm_id for row in selected}
        self.assertTrue({"FBCP-009", "FBCP-031", "FBCP-032", "FBCP-048"} & ids)

    def test_sensitive_click_query_selects_authority_and_readback(self):
        selected = select_algorithms(
            "sensitive website click needs authority lease semantic readback and replay guard",
            limit=12,
        )
        ids = {row.algorithm_id for row in selected}
        self.assertIn("FBCP-025", ids)
        self.assertTrue({"FBCP-027", "FBCP-047"} & ids)

    def test_no_match_uses_category_diverse_fallback(self):
        selected = select_algorithms("ZXQJ_UNSEEN_BROWSER_RESIDUAL", limit=12)
        self.assertEqual(len(selected), 12)
        self.assertEqual(len({row.category for row in selected}), 12)


if __name__ == "__main__":
    unittest.main()
