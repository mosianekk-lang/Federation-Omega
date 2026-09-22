from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import formation_omega

from ao_harmonic_v3.formation_engine_compatibility import REQUIRED_PUBLIC_API
from ao_harmonic_v3.formation_engine_shadow import run_c5_formation_engine_shadow

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "ao_harmonic_forest_first_c5_formation_engine_contract_v1.json"


class ForestFirstC5FormationRepositoryShellTests(unittest.TestCase):
    def test_full_formation_regression_suite_is_green(self):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_formation_omega_*.py",
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("Ran ", process.stderr)
        self.assertIn("OK", process.stderr)

    def test_public_api_freeze_matches_current_formation_surface(self):
        required = set(REQUIRED_PUBLIC_API)
        self.assertTrue(required.issubset(set(formation_omega.__all__)))
        self.assertTrue(all(hasattr(formation_omega, name) for name in required))

    def test_contract_keeps_formation_in_mission_execution_without_authority_takeover(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        target = contract["target_identity"]
        self.assertEqual(target["canonical_identity"], "Formation")
        self.assertEqual(target["authority_layer"], "MISSION_EXECUTION")
        self.assertTrue(target["keep_as_engine"])
        self.assertFalse(target["sovereign_cognitive_authority"])
        self.assertFalse(contract["truth_boundary"]["runtime_changed"])
        self.assertFalse(contract["truth_boundary"]["provider_effect"])
        self.assertFalse(contract["truth_boundary"]["authority_expanded"])
        self.assertFalse(contract["truth_boundary"]["maturity_inherited"])

    def test_c5_shadow_is_green_from_repository_shell(self):
        report = run_c5_formation_engine_shadow()
        self.assertEqual(report["scenario_count"], 10)
        self.assertTrue(report["pass"])
        self.assertFalse(report["external_effect"])
        self.assertFalse(report["provider_runtime_proved"])
        self.assertFalse(report["physical_migration_executed"])
        self.assertFalse(report["formation_authority_expanded"])

    def test_c5_does_not_delete_or_rewire_formation_source(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["physical_action_before_p4"], "NONE")
        self.assertFalse(contract["source_actions"]["delete_formation_package"])
        self.assertFalse(contract["source_actions"]["rename_public_api"])
        self.assertFalse(contract["source_actions"]["move_provider_authority"])
        self.assertTrue(contract["source_actions"]["preserve_legacy_identity"])


if __name__ == "__main__":
    unittest.main()
