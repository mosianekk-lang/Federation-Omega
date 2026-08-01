from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "maturity_assessor.py"
SPEC = importlib.util.spec_from_file_location("kimmie_maturity_assessor", MODULE_PATH)
assert SPEC and SPEC.loader
assessor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assessor)


class KimmieMaturityAssessorTests(unittest.TestCase):
    def setUp(self):
        self.genome = {"seed_id": "KIMMIE-IPEP-001"}
        self.environment = {
            "nutrients": [
                {"type": nutrient, "state": "VERIFIED"}
                for nutrient in sorted(assessor.REQUIRED)
            ]
        }

    def test_current_spout_schema_is_not_downgraded(self):
        registry = {
            "current_verified_stage": "SPROUT",
            "promotion_gate": {
                "sapling_requirements": {
                    "repeated_successful_maturity_cycles": "PARTIAL",
                    "reusable_capability_multiple_corpora_or_environments": "VERIFIED",
                    "persistent_monitoring": "PARTIAL",
                    "maintenance_evidence": "PARTIAL",
                    "recovery_evidence": "NOT_VERIFIED",
                }
            },
            "child_lanes": [
                {
                    "lane_id": "LANE-CONNECTOR-FOUNDRY",
                    "verified_stage": "SPROUT",
                    "operational_state": "PROVIDER_TEST_PASSED",
                    "authorised_environment": {
                        "github_repository": "VERIFIED_READ_WRITE",
                        "google_drive_connector": "VERIFIED_READ_WRITE",
                    },
                    "required_nutrients": {
                        "proof_receipt": "VERIFIED_PRESENT",
                        "maintenance_owner": "mosianekk-lang",
                    },
                    "proof_gates": {
                        "provider_specific_execution": "PASSED_GOOGLE_DRIVE",
                        "independent_provider_readback": "PASSED",
                        "provider_ci": "PASSED",
                    },
                }
            ],
        }
        result = assessor.assess(
            self.genome, self.environment, registry, True, "PASSED",
            {"receipt_sha256": "abc"},
        )
        self.assertEqual("SPROUT", result["verified_stage"])
        self.assertEqual("PASS", result["status"])
        self.assertTrue(result["useful_child_capability_verified"])
        self.assertIn("LANE-CONNECTOR-FOUNDRY", result["verified_useful_child_lanes"])
        self.assertFalse(result["sapling_gate_verified"])

    def test_design_only_child_cannot_promote_root(self):
        registry = {
            "current_verified_stage": "ROOTED",
            "promotion_gate": {"sapling_requirements": {}},
            "child_lanes": [
                {
                    "lane_id": "DESIGN-ONLY",
                    "verified_stage": "SPROUT",
                    "operational_state": "DESIGNED",
                    "authorised_environment": {"github": "VERIFIED"},
                    "required_nutrients": {
                        "proof_receipt": "ABSENT",
                        "maintenance_owner": "mosianekk-lang",
                    },
                    "proof_gates": {"design": "PASSED"},
                }
            ],
        }
        result = assessor.assess(
            self.genome, self.environment, registry, True, "PASSED",
            {"receipt_sha256": "abc"},
        )
        self.assertEqual("ROOTED", result["verified_stage"])
        self.assertFalse(result["useful_child_capability_verified"])

    def test_partial_sapling_gate_cannot_promote(self):
        requirements = {
            "repeated_successful_maturity_cycles": "VERIFIED",
            "reusable_capability_multiple_corpora_or_environments": "VERIFIED",
            "persistent_monitoring": "VERIFIED",
            "maintenance_evidence": "VERIFIED",
            "recovery_evidence": "PARTIAL",
        }
        self.assertFalse(
            assessor.all_gate_requirements_verified(requirements, assessor.SAPLING_REQUIREMENTS)
        )


if __name__ == "__main__":
    unittest.main()
