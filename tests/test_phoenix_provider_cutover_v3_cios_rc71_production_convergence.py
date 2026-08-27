from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CIOSRC71ProductionConvergenceAdmissionTests(unittest.TestCase):
    def test_complete_internal_cios_court_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(
            str(ROOT / "evidenceops" / "capital_intelligence_os" / "tests"),
            pattern="test_*.py",
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertGreaterEqual(result.testsRun, 230, evidence)

    def test_cumulative_release_verifier_remains_proof_safe(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "evidenceops.capital_intelligence_os.verify_release"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertFalse(payload["production_claim"])
        self.assertEqual("PROVIDER_BINDING_READY", payload["maturity"])

    def test_modisa_contract_is_v33_and_does_not_claim_deployment(self) -> None:
        contract = json.loads(
            (ROOT / "evidenceops" / "capital_intelligence_os" / "BUILD_CONTRACT.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("3.3", contract["contract_version"])
        self.assertTrue(contract["states"]["tested"])
        self.assertFalse(contract["states"]["deployed"])
        self.assertFalse(contract["states"]["proven"])
        self.assertTrue(contract["proof"]["unresolved_defects"])


if __name__ == "__main__":
    unittest.main()
