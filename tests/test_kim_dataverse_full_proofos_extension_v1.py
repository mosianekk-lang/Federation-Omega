from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "governance/proofos_omega_policy_extension_kim_dataverse_level7_plus_full_v1.json"


class KimDataverseFullProofOSExtensionTests(unittest.TestCase):
    def test_extension_is_internal_only_and_caps_source_at_level6_candidate(self) -> None:
        data = json.loads(EXTENSION.read_text(encoding="utf-8"))
        self.assertEqual("A1_INTERNAL_REVERSIBLE", data["authority"]["max_authority"])
        self.assertTrue(all(value is False for key, value in data["authority"].items() if key != "max_authority"))
        self.assertEqual("LEVEL6_SOURCE_CANDIDATE", data["source_promotion_ceiling"])
        self.assertIn("PERSISTENT_NO_CHAT_CONTINUITY", data["explicit_empirical_holds"])
        self.assertIn("PROSPECTIVE_OWNER_VALUE", data["explicit_empirical_holds"])


if __name__ == "__main__":
    unittest.main()
