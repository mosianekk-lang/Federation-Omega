from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class JarvisAdmissionTests(unittest.TestCase):
    """Bind the focused JARVIS v2 receiver canary to the existing Airlock wildcard.

    The focused canary itself executes the native public-safe JarvisAO5Engine
    before invoking Failure-Win v2. Historical JARVIS regressions remain source
    evidence but are not silently converted into a new mandatory release gate.
    No workflow, permission, credential, or external authority is added.
    """

    def test_jarvis_failure_win_receiver_canary_executes(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_jarvis_failure_win_v2.py",
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "JARVIS Failure-Win v2 receiver canary failed.\n"
                f"stdout:\n{proc.stdout[-6000:]}\n"
                f"stderr:\n{proc.stderr[-6000:]}"
            )

    def test_native_and_failure_win_canaries_are_present(self) -> None:
        required = (
            ROOT / "ao_harmonic_v3" / "jarvis_ao5.py",
            ROOT / "verification" / "jarvis_ao5_public_safe_canary.py",
            ROOT / "tests" / "test_jarvis_failure_win_v2.py",
        )
        self.assertTrue(all(path.is_file() for path in required))


if __name__ == "__main__":
    unittest.main()
