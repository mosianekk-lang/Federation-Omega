from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


class TestFederationAutopilotSuitesProofOSBridge(unittest.TestCase):
    """Run the existing 93-case pytest court from ProofOS' unittest runner.

    This preserves the current ProofOS kind contract instead of weakening it or
    pretending that a pytest-parametrized module is unittest-discoverable.
    """

    def test_existing_pytest_court_executes_all_93_cases(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_federation_autopilot_suites_v1.py",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=170,
            check=False,
        )
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        self.assertEqual(completed.returncode, 0, msg=output[-8000:])
        self.assertIn("93 passed", output, msg=output[-8000:])


if __name__ == "__main__":
    unittest.main()
