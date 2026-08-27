from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class JarvisAdmissionTests(unittest.TestCase):
    """Bind JARVIS regressions to the existing provider-cutover-v3 Airlock wildcard.

    No workflow, permission, credential, or external authority is added. The
    existing Airlock step already executes test_phoenix_provider_cutover_v3*.py.
    """

    def test_jarvis_focused_suite_executes(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_jarvis*.py",
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "JARVIS focused regression suite failed.\n"
                f"stdout:\n{proc.stdout[-6000:]}\n"
                f"stderr:\n{proc.stderr[-6000:]}"
            )

    def test_native_and_failure_win_canaries_are_present(self) -> None:
        required = (
            ROOT / "ao_harmonic_v3" / "jarvis_ao5.py",
            ROOT / "verification" / "jarvis_ao5_public_safe_canary.py",
            ROOT / "tests" / "test_jarvis_ao5.py",
            ROOT / "tests" / "test_jarvis_failure_win_v2.py",
        )
        self.assertTrue(all(path.is_file() for path in required))


if __name__ == "__main__":
    unittest.main()
