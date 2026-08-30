from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest


class FAEFoundryDiagnosticTests(unittest.TestCase):
    """Temporary no-effect diagnostic for PR #803; remove before admission."""

    def test_capture_current_main_compatibility_failures(self):
        if os.getenv("FAE_DIAGNOSTIC_CHILD") == "1":
            self.skipTest("nested diagnostic recursion disabled")

        env = dict(os.environ)
        env["FAE_DIAGNOSTIC_CHILD"] = "1"
        commands = {
            "phoenix_exports": [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_phoenix_exports.py",
                "-v",
            ],
            "phoenix_cutover_v3": [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_phoenix_provider_cutover_v3*.py",
                "-v",
            ],
        }

        def sanitize(value: str) -> str:
            value = re.sub(r"ghp_[A-Za-z0-9_\-]+", "[REDACTED_GITHUB_TOKEN]", value)
            value = re.sub(r"github_pat_[A-Za-z0-9_\-]+", "[REDACTED_GITHUB_PAT]", value)
            value = re.sub(r"sk-[A-Za-z0-9_\-]+", "[REDACTED_API_KEY]", value)
            value = re.sub(r"AIza[A-Za-z0-9_\-]+", "[REDACTED_GOOGLE_KEY]", value)
            return value[-12000:]

        results = {}
        for name, argv in commands.items():
            process = subprocess.run(
                argv,
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=420,
                check=False,
            )
            results[name] = {
                "returncode": process.returncode,
                "stdout_tail": sanitize(process.stdout),
                "stderr_tail": sanitize(process.stderr),
            }

        target = Path("airlock-output/proofos-shadow-calibration.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "schema": "FAE-PR803-TEMPORARY-DIAGNOSTIC-1",
                    "authority": "A0_NO_EFFECT",
                    "promotion_allowed": False,
                    "remove_before_admission": True,
                    "results": results,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()
