from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REUSE = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_reuse_map_v1.json"


class KimDataverseLevel7PlusReuseMapTests(unittest.TestCase):
    def test_reuse_map_uses_existing_federation_power_and_adds_no_duplicate_control_plane(self) -> None:
        data = json.loads(REUSE.read_text(encoding="utf-8"))
        self.assertIn("SOL_6_2", data["reuse"])
        self.assertIn("BCO_PRIME", data["reuse"])
        self.assertIn("BUBBLES", data["reuse"])
        self.assertIn("SOVARA", data["reuse"])
        self.assertIn("PROOFOS", data["reuse"])
        self.assertEqual(0, data["new_duplicate_control_plane_count"])


if __name__ == "__main__":
    unittest.main()
