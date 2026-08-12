from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "ipep" / "audio_evidence_v4"


class IPEPReadOnlyServiceAdmissionTests(unittest.TestCase):
    def test_focused_service_suite_executes_with_real_loopback_canary(self) -> None:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_readonly_service.py",
                "-v",
            ],
            cwd=PACKAGE_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate(timeout=30)
        evidence = stdout + stderr
        self.assertEqual(0, process.returncode, evidence)
        self.assertIn("test_unauthorized_requests_fail_closed", evidence)
        self.assertIn("test_health_and_readiness_are_semantic", evidence)
        self.assertIn("test_search_returns_stable_provenance_citation", evidence)
        self.assertIn("test_non_loopback_binding_is_rejected", evidence)
        self.assertIn("Ran 7 tests", evidence)
        self.assertIn("OK", evidence)

    def test_service_source_and_cli_contract_are_present(self) -> None:
        self.assertTrue((PACKAGE_ROOT / "evidenceops_audio_v4" / "service.py").is_file())
        pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "4.1.0"', pyproject)
        self.assertIn('evidenceops-audio-v4-serve = "evidenceops_audio_v4.service:main"', pyproject)


if __name__ == "__main__":
    unittest.main()
