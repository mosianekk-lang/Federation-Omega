from __future__ import annotations

import json
import unittest
from pathlib import Path

from evidenceops.capability_heartbeat import static_verify
from evidenceops.capability_heartbeat import validate_build_contract

ROOT = Path(__file__).resolve().parents[1]


class ValidatorTests(unittest.TestCase):
    def test_current_build_contract_structure(self):
        value = json.loads((ROOT / "BUILD_CONTRACT.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_build_contract.validate(value), [])

    def test_false_live_state_is_rejected(self):
        value = json.loads((ROOT / "BUILD_CONTRACT.json").read_text(encoding="utf-8"))
        value["states"]["deployed"] = True
        self.assertIn("live maturity states must remain false", validate_build_contract.validate(value))

    def test_require_proof_accepts_finalized_local_evidence(self):
        value = json.loads((ROOT / "BUILD_CONTRACT.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_build_contract.validate(value, require_proof=True), [])

    def test_static_production_boundary(self):
        self.assertEqual(static_verify.verify_python(), [])

    def test_independent_block_controls_are_statically_present(self):
        self.assertEqual(static_verify.verify_integrity_controls(), [])

    def test_compatibility_command_is_exact_and_required(self):
        value = json.loads((ROOT / "BUILD_CONTRACT.json").read_text(encoding="utf-8"))
        value["testing"]["compatibility_command"] = "python3 -m unittest"
        self.assertIn(
            "testing.compatibility_command must equal the exact 55-test command",
            validate_build_contract.validate(value),
        )

    def test_third_review_control_manifest_is_required(self):
        value = json.loads((ROOT / "BUILD_CONTRACT.json").read_text(encoding="utf-8"))
        value["proof"]["adversarial_controls"].remove("HB-IMMUTABILITY-003")
        self.assertIn(
            "proof.adversarial_controls must cover every independent BLOCK finding",
            validate_build_contract.validate(value),
        )


if __name__ == "__main__":
    unittest.main()
