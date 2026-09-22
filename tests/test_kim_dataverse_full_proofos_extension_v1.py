from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "governance/proofos_omega_policy_extension_kim_dataverse_level7_plus_full_v1.json"


class KimDataverseFullProofOSExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(EXTENSION.read_text(encoding="utf-8"))

    def test_extension_uses_canonical_additive_schema(self) -> None:
        self.assertEqual("FEDERATION-PROOFOS-OMEGA-ADDITIVE-EXTENSION-V1", self.data["schema"])
        self.assertEqual("1.0.0", self.data["version"])
        self.assertNotIn("authority", self.data)
        self.assertNotIn("selector", self.data)

    def test_level7_programme_is_one_scoped_subsystem_and_one_blocking_court(self) -> None:
        self.assertEqual(1, len(self.data["subsystem_rules"]))
        self.assertEqual("KIM_DATAVERSE_LEVEL7_PLUS", self.data["subsystem_rules"][0]["subsystem"])
        self.assertEqual(1, len(self.data["tests"]))
        court = self.data["tests"][0]
        self.assertEqual("kim_dataverse_level7_plus_full_v1", court["id"])
        self.assertEqual("test_kim_dataverse_*.py", court["target"])
        self.assertEqual("SUBSYSTEM", court["block_scope"])

    def test_level7_programme_is_core_risk_without_authority_override(self) -> None:
        self.assertEqual("R4_CORE", self.data["risk_rules"][0]["risk"])
        self.assertIn("KIM_DATAVERSE_LEVEL7_PLUS_INSTITUTIONAL_AUTONOMY_CONSTITUTIONAL_CONTROL", self.data["risk_rules"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
