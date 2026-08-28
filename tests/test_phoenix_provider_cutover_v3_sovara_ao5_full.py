from __future__ import annotations

import io
import unittest

from ops.sovara_ao5_full_v2.ao5_full_engine import canary, coverage_gate
from ops.sovara_ao5_full_v2.source_identity import CANONICAL_AUTHORITY, RAW_UPLOAD_SHA256


class SovaraAO5FullHostedBridgeTests(unittest.TestCase):
    """Bind full JARVIS AO5 zero-dilution proof to the admitted Federation Airlock."""

    def test_byte_exact_source_identity(self):
        self.assertEqual(CANONICAL_AUTHORITY, "RAW_UPLOAD_SHA256")
        self.assertEqual(
            RAW_UPLOAD_SHA256,
            "773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443",
        )

    def test_full_numbered_section_coverage(self):
        coverage = coverage_gate()
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["sections"], 55)
        self.assertEqual(coverage["roman_parts"], 54)
        self.assertTrue(coverage["part0"])

    def test_full_ao5_canary(self):
        result = canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 56)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)

    def test_full_ao5_regression_directory(self):
        suite = unittest.defaultTestLoader.discover(
            "ops/sovara_ao5_full_v2/tests",
            pattern="test_*.py",
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(
            stream=stream,
            verbosity=2,
            failfast=False,
        ).run(suite)
        self.assertTrue(
            result.wasSuccessful(),
            "FULL_AO5_REGRESSION_FAILED\n" + stream.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
