from __future__ import annotations

import unittest

from ops.sovara_ao5_full_v2.ao4_heritage import (
    AO4_RAW_SHA256,
    AO5_CANONICAL_RAW_SHA256,
    heritage_canary,
    load_map,
    reconstruct_ao4_bytes,
    receipt,
)


class AO4HeritageIntegrationTests(unittest.TestCase):
    def test_exact_ao4_source_identity(self):
        raw = reconstruct_ao4_bytes()
        import hashlib
        self.assertEqual(hashlib.sha256(raw).hexdigest(), AO4_RAW_SHA256)

    def test_all_ao4_parts_map_into_current_ao5(self):
        data = load_map()
        self.assertEqual(len(data["sections"]), 53)
        self.assertEqual(len({x["ao4_part"] for x in data["sections"]}), 53)
        self.assertEqual(data["ao5"]["canonical_raw_sha256"], AO5_CANONICAL_RAW_SHA256)

    def test_legacy_aliases_are_lossless_and_bounded(self):
        data = load_map()
        self.assertEqual(len(data["legacy_stream_aliases"]), 25)
        self.assertEqual(len(data["legacy_path_aliases"]), 13)
        self.assertEqual(data["authority"]["ao4_role"], "HERITAGE_SOURCE_AND_LEGACY_COMPATIBILITY")
        self.assertEqual(data["authority"]["ao5_role"], "CURRENT_EXECUTABLE_FORENSIC_DECISION_INTELLIGENCE_AUTHORITY")

    def test_heritage_execution_canary(self):
        result = heritage_canary()
        self.assertTrue(result.complete)
        self.assertFalse(result.authority_expanded)
        self.assertEqual(result.external_effects, 0)

    def test_receipt_truth_boundary(self):
        out = receipt()
        self.assertTrue(out["complete"])
        self.assertEqual(out["integration_state"], "HERITAGE_INTEGRATED_CURRENT_AO5_NOT_DOWNGRADED")
        self.assertIn("no provider deployment", out["truth_boundary"].lower())


if __name__ == "__main__":
    unittest.main()
