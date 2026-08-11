from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOCUSED_TEST = "test_ecertify_launch_now_canary_contract.py"
SCRIPT = ROOT / "evidenceops" / "ecertify_za" / "deployment" / "deploy_launch_now_cloud_run_canary.sh"
CONTRACT = ROOT / "evidenceops" / "ecertify_za" / "deployment" / "LAUNCH_NOW_CANARY_CONTRACT.json"


class ECertifyLaunchNowAdmissionTests(unittest.TestCase):
    """Make Bubbles/eCertify focused canary evidence visible in Airlock logs."""

    def test_focused_launch_now_canary_contract_suite_executes(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                FOCUSED_TEST,
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        evidence = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, evidence)
        self.assertIn(
            "test_track_a_does_not_require_identity_provider_or_cloudsql",
            evidence,
        )
        self.assertIn(
            "test_source_contract_never_self_certifies_public_launch",
            evidence,
        )
        self.assertIn("Ran 8 tests", evidence)
        self.assertIn("OK", evidence)

    def test_canary_source_and_contract_are_present(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(CONTRACT.is_file())
        self.assertTrue((ROOT / "tests" / FOCUSED_TEST).is_file())


if __name__ == "__main__":
    unittest.main()
