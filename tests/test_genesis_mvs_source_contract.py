from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "genesis" / "Build-Genesis.ps1"

class GenesisMvsSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BUILD.read_text(encoding="utf-8")

    def test_frozen_source_and_compilation_denominators(self):
        self.assertIn("if($files.Count -ne 29)", self.source)
        self.assertIn("if($cpp.Count -ne 20)", self.source)

    def test_native_security_and_reproducibility_flags(self):
        for marker in (
            "'/MT'",
            "'/guard:cf'",
            "'/DYNAMICBASE'",
            "'/HIGHENTROPYVA'",
            "'/NXCOMPAT'",
            "'/Brepro'",
        ):
            self.assertIn(marker, self.source)

    def test_self_court_recovery_and_duplicate_effect_courts_remain_required(self):
        self.assertIn("--self-court", self.source)
        self.assertGreaterEqual(self.source.count("--mvs-canary"), 2)
        self.assertIn("SELF_COURT_FAILED", self.source)
        self.assertIn("MVS_CANARY_FAILED", self.source)
        self.assertIn("MVS_DUPLICATE_COURT_FAILED", self.source)

    def test_reproducible_double_build_is_fail_closed(self):
        self.assertIn("R2_REPRODUCIBILITY_FAILED", self.source)
        self.assertIn("$a.sha256 -ne $b.sha256", self.source)
        self.assertIn("$a.bytes -ne $b.bytes", self.source)

    def test_admission_court_is_required(self):
        self.assertIn("RunAdmissionCourt", self.source)
        self.assertIn("ADMISSION_COURT_FAILED", self.source)
        self.assertIn("7_OF_7_REQUIRED", self.source)

    def test_receipt_preserves_hosted_only_truth_boundary(self):
        for marker in (
            "self_court='48_OF_48_REQUIRED'",
            "byte_identical=$true",
            "network_required=$false",
            "provider_runtime=$false",
            "dotnet_runtime=$false",
            "python_runtime=$false",
            "node_runtime=$false",
            "owner_pc_physical_proof=$false",
            "Hosted Windows MVS + admission proof only",
        ):
            self.assertIn(marker, self.source)

if __name__ == "__main__":
    unittest.main()
