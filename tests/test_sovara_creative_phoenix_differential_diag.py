from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(pattern: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )


class PhoenixDifferentialDiagnosticTests(unittest.TestCase):
    def test_exact_phoenix_failures_are_visible(self) -> None:
        failures: list[str] = []
        for pattern in ("test_phoenix_exports.py", "test_phoenix_provider_cutover_v3*.py"):
            proc = run(pattern)
            if proc.returncode != 0:
                failures.append(
                    f"PATTERN={pattern}\nSTDOUT:\n{proc.stdout[-12000:]}\nSTDERR:\n{proc.stderr[-20000:]}"
                )
        if failures:
            self.fail("\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
