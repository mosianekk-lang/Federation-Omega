from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "phoenix" / "export_policy.json"
SOVARA_TEST = "tests/test_sovara_litellm_provider_airlock.py"


class SovaraRepositoryControlExportExclusionTests(unittest.TestCase):
    def test_temporary_isolated_v3_failure_map(self):
        """TEMPORARY DIAGNOSTIC: run peer v3 modules in isolated subprocesses."""
        failures = []
        current = Path(__file__).name
        for path in sorted((ROOT / "tests").glob("test_phoenix_provider_cutover_v3*.py")):
            if path.name == current:
                continue
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    path.name,
                    "-v",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0:
                failures.append(
                    {
                        "module": path.name,
                        "returncode": proc.returncode,
                        "stdout": proc.stdout,
                        "stderr": proc.stderr,
                    }
                )
        out = ROOT / "airlock-output"
        out.mkdir(exist_ok=True)
        (out / "proofos-shadow-calibration.json").write_text(
            json.dumps(
                {"temporary_isolated_v3_diagnostic": True, "failures": failures},
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_sovara_repository_control_test_is_excluded_from_core(self):
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        excluded = set(policy["core"]["excluded_test_globs"])
        self.assertIn(SOVARA_TEST, excluded)

    def test_sovara_test_requires_repository_workflow_surface(self):
        source = (ROOT / SOVARA_TEST).read_text(encoding="utf-8")
        self.assertIn(".github/workflows/sovara-litellm-v2-3-provider-admission.yml", source)
        self.assertIn("WORKFLOW = (ROOT / WORKFLOW_PATH).read_text", source)

    def test_export_policy_still_excludes_all_github_workflows(self):
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertIn(".github/", set(policy["core"]["excluded_prefixes"]))
        self.assertEqual(0, policy["invariants"]["core_workflow_count"])
        self.assertEqual(0, policy["invariants"]["core_nested_workflow_count"])


if __name__ == "__main__":
    unittest.main()
