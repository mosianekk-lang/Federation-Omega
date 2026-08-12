from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ECertifySentinelSecurityAdmissionTests(unittest.TestCase):
    def test_sentinel_security_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_ecertify_sentinel_security.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(8, result.testsRun, evidence)
        self.assertIn("test_receipt_tamper_is_rejected", evidence)
        self.assertIn("test_source_contract_never_authorises_public_launch", evidence)

    def test_threat_model_and_gate_source_are_present(self) -> None:
        self.assertTrue((ROOT / "evidenceops" / "ecertify_za" / "LAUNCH_NOW_THREAT_MODEL.json").is_file())
        self.assertTrue((ROOT / "evidenceops" / "ecertify_za" / "security_controls.py").is_file())


if __name__ == "__main__":
    unittest.main()
