from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "realityguard.cli", *args], cwd=ROOT, text=True, capture_output=True, env={"PYTHONPATH": str(ROOT / "src")})

    def test_health_smoke(self):
        proc = self.run_cli("health")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["status"], "ok")

    def test_taxonomy_has_30_rules(self):
        proc = self.run_cli("taxonomy")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(json.loads(proc.stdout)["failures"]), 30)

    def test_false_claim_exit_is_three(self):
        proc = self.run_cli("scan", "--input", "examples/false_ownership.json")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(json.loads(proc.stdout)["verdict"], "BLOCK_FALSE_REALITY")

    def test_invalid_input_exit_is_two(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text("not json")
            proc = self.run_cli("scan", "--input", str(path))
        self.assertEqual(proc.returncode, 2)

    def test_audit_log_redacts_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            source = json.loads((ROOT / "examples/false_ownership.json").read_text())
            source["context"]["api_key"] = "sk-abcdefghijklmnop"
            input_path = Path(temp) / "input.json"
            log_path = Path(temp) / "audit.jsonl"
            input_path.write_text(json.dumps(source))
            self.run_cli("scan", "--input", str(input_path), "--audit-log", str(log_path))
            logged = log_path.read_text()
        self.assertNotIn("sk-abcdefghijklmnop", logged)
        self.assertIn("[REDACTED]", logged)


if __name__ == "__main__":
    unittest.main()
