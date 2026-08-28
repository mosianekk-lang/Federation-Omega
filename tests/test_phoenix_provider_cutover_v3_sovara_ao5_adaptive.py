from __future__ import annotations

import io
import unittest

from ops.sovara_ao5_full_v2.ao5_full_engine import canary, coverage_gate
from ops.sovara_ao5_full_v2.adaptive_optimizer import run_adaptive_canary, synthetic_benchmark
from ops.sovara_ao5_full_v2.source_identity import CANONICAL_AUTHORITY, RAW_UPLOAD_SHA256


class SovaraAO5AdaptiveHostedBridgeTests(unittest.TestCase):
    """Bind the full stacked AO5 package to a workflow already admitted on main.

    Federation Omega Airlock runs `test_phoenix_provider_cutover_v3*.py` on every
    pull request. This bridge makes that existing hosted court execute the full
    zero-dilution AO5 regression directory plus the adaptive challenger tests.

    The nested suite intentionally uses unittest's in-process loader rather than
    subprocess.run. Other provider-cutover regressions monkey-patch subprocess
    during the same discovery process, so subprocess would create a false
    coupling between otherwise unrelated tests.
    """

    def test_byte_exact_source_identity_is_unchanged(self):
        self.assertEqual(CANONICAL_AUTHORITY, "RAW_UPLOAD_SHA256")
        self.assertEqual(
            RAW_UPLOAD_SHA256,
            "773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443",
        )

    def test_full_ao5_coverage_remains_complete(self):
        coverage = coverage_gate()
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["sections"], 55)
        self.assertEqual(coverage["roman_parts"], 54)
        self.assertTrue(coverage["part0"])

    def test_full_ao5_canary_remains_green(self):
        result = canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 56)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)

    def test_adaptive_canary_is_green_and_effect_free(self):
        result = run_adaptive_canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 21)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)

    def test_full_package_regression_surface_including_optimizer(self):
        suite = unittest.defaultTestLoader.discover(
            "ops/sovara_ao5_full_v2/tests",
            pattern="test_*.py",
            top_level_dir=".",
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(
            stream=stream,
            verbosity=2,
            failfast=False,
        ).run(suite)
        self.assertTrue(
            result.wasSuccessful(),
            "FULL_AO5_STACKED_REGRESSION_FAILED\n" + stream.getvalue(),
        )

    def test_synthetic_benchmark_is_not_promoted_as_real_performance(self):
        benchmark = synthetic_benchmark()
        self.assertFalse(benchmark["provider_performance_claim"])
        self.assertFalse(benchmark["ten_x_claim"])
        self.assertEqual(
            benchmark["benchmark_class"],
            "SYNTHETIC_DETERMINISTIC_MATCHED_SCENARIO",
        )


if __name__ == "__main__":
    unittest.main()
