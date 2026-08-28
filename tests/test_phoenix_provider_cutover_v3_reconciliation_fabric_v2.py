from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReconciliationFabricV2PhoenixAdmissionTests(unittest.TestCase):
    def test_full_v2_adversarial_and_frontier_courts_are_independently_runnable(self):
        command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_formation_omega_reconciliation*.py",
            "-v",
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        self.assertEqual(0, result.returncode, output)
        self.assertIn("test_durable_replay_survives_restart_and_rejects_conflict", output)
        self.assertIn("test_cfbe_keeps_unverified_frontier_adapters_evidence_discounted", output)
        self.assertIn("OK", output)

    def test_core_compiles_without_optional_frontier_runtimes(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "formation_omega/reconciliation_fabric_v2.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        self.assertEqual(0, result.returncode, output)

    def test_external_frontier_tools_remain_optional_not_import_dependencies(self):
        source = (ROOT / "formation_omega" / "reconciliation_fabric_v2.py").read_text(encoding="utf-8")
        for forbidden_import in (
            "import temporalio",
            "import langgraph",
            "import opentelemetry",
            "import sigstore",
            "import opa",
            "import tla",
            "from temporalio",
            "from langgraph",
            "from opentelemetry",
            "from sigstore",
        ):
            self.assertNotIn(forbidden_import, source.lower())


if __name__ == "__main__":
    unittest.main()
