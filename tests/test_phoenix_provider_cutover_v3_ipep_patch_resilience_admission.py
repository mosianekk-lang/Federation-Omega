from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "ipep" / "audio_evidence_v4"


class IPEPPatchResilienceAdmissionTests(unittest.TestCase):
    def test_patch_fault_suite_executes(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_resilience.py", "-v"],
            cwd=PACKAGE,
            text=True,
            capture_output=True,
        )
        evidence = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, evidence)
        self.assertIn("Ran 4 tests", evidence)
        self.assertIn("OK", evidence)
        self.assertIn("test_tampered_custody_chain_is_detected", evidence)
        self.assertIn("test_missing_index_fails_closed_without_rebuilding_silently", evidence)

    def test_resilience_probe_source_is_present(self) -> None:
        self.assertTrue((PACKAGE / "evidenceops_audio_v4" / "resilience.py").is_file())


if __name__ == "__main__":
    unittest.main()
