from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SparksProviderPacketAdmissionTests(unittest.TestCase):
    def test_sparks_packet_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(
            str(ROOT / "tests"), pattern="test_bubbles_sparks_provider_packet.py"
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(8, result.testsRun, evidence)
        self.assertIn("test_without_authorised_surface_execution_fails_closed", evidence)
        self.assertIn("test_ecertify_receipt_fails_if_public_or_document_bytes_cross_boundary", evidence)

    def test_packet_and_validator_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "sparks_provider_execution_packet.json").is_file())
        self.assertTrue((ROOT / "bubbles" / "sparks_provider_packet.py").is_file())


if __name__ == "__main__":
    unittest.main()
