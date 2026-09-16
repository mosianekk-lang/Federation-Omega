from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarking/cfbe_omega/KIM_DATAVERSE_LEVEL7_PLUS_IMPLEMENTATION_MANIFEST_V1_20260901.json"


class KimDataverseLevel7PlusManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_registers_all_core_institutional_components(self) -> None:
        components = set(self.manifest["components"])
        required = {
            "kim_dataverse_level7_plus_v1",
            "kim_dataverse_autonomic_control_fabric_v1",
            "kim_dataverse_institutional_twin_v1",
            "kim_dataverse_constitutional_evolution_v1",
            "kim_dataverse_persistent_carrier_contract_v1",
            "kim_dataverse_causal_value_learning_v1",
            "kim_dataverse_institutional_qualification_v1",
            "kim_dataverse_level8_frontier_v1",
            "kim_dataverse_institutional_bridge_v1",
        }
        self.assertEqual(required, components)

    def test_level7_operational_maturity_remains_empirically_held(self) -> None:
        self.assertEqual("SOURCE_AND_CONTROL_PLANE_CANDIDATE_ONLY", self.manifest["maturity_claim"])
        self.assertIn("LEVEL7_OPERATIONAL_MATURITY_NOT_SELF_DECLARED", self.manifest["empirical_holds"])

    def test_manifest_grants_no_consequential_authority(self) -> None:
        self.assertTrue(all(value is False for value in self.manifest["authority"].values()))

    def test_architecture_preserves_one_authority_and_no_duplicate_control_planes(self) -> None:
        invariants = "\n".join(self.manifest["architecture_invariants"])
        self.assertIn("one SOL authority constitution", invariants)
        self.assertIn("no duplicate scheduler", invariants)
        self.assertIn("no duplicate memory root", invariants)
        self.assertIn("no duplicate provider executor", invariants)


if __name__ == "__main__":
    unittest.main()
