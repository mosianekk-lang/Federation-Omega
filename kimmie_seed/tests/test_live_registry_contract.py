from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "kimmie_seed" / "maturity_assessor.py"
REGISTRY_PATH = ROOT / "kimmie_seed" / "registry.json"

SPEC = importlib.util.spec_from_file_location("kimmie_maturity_assessor_live", MODULE_PATH)
assert SPEC and SPEC.loader
assessor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assessor)


class LiveRegistryContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.environment = {
            "nutrients": [
                {"type": nutrient, "state": "VERIFIED"}
                for nutrient in sorted(assessor.REQUIRED)
            ]
        }

    def test_live_registry_preserves_assessor_contract(self):
        gate = self.registry["promotion_gate"]
        self.assertEqual(gate["requirements"], gate["sapling_requirements"])

        connector = next(
            lane for lane in self.registry["child_lanes"]
            if lane["lane_id"] == "LANE-CONNECTOR-FOUNDRY"
        )
        self.assertTrue(assessor.child_is_useful_and_verified(connector))

        expected_sapling_gate = assessor.all_gate_requirements_verified(
            gate["sapling_requirements"], assessor.SAPLING_REQUIREMENTS
        )
        result = assessor.assess(
            {"seed_id": self.registry["seed_id"]},
            self.environment,
            self.registry,
            True,
            "PASSED",
            {"receipt_sha256": "contract-test"},
        )
        self.assertEqual(self.registry["current_verified_stage"], result["verified_stage"])
        self.assertEqual("PASS", result["status"])
        self.assertTrue(result["useful_child_capability_verified"])
        self.assertIn("LANE-CONNECTOR-FOUNDRY", result["verified_useful_child_lanes"])
        self.assertEqual(expected_sapling_gate, result["sapling_gate_verified"])

    def test_sapling_requires_every_named_gate(self):
        requirements = self.registry["promotion_gate"]["sapling_requirements"]
        self.assertEqual(assessor.SAPLING_REQUIREMENTS, set(requirements))
        if self.registry["current_verified_stage"] == "SAPLING":
            self.assertTrue(
                assessor.all_gate_requirements_verified(
                    requirements, assessor.SAPLING_REQUIREMENTS
                )
            )


if __name__ == "__main__":
    unittest.main()
