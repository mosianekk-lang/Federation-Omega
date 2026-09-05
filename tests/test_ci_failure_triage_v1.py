from __future__ import annotations

import unittest

from federation.ci_failure_triage_v1 import CIFailureTriage


class CIFailureTriageV1Tests(unittest.TestCase):
    def test_candidate_contract_drift_and_baseline_dependency_are_separated(self) -> None:
        log = r"""
======================================================================
ERROR: test_opa_allow (tests.test_fuse_opa_policy_adapter_v1.OPATests.test_opa_allow)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/work/Federation-Omega/federation/opa_policy_adapter_v1.py", line 90, in decide
    mission.validate()
ValueError: MISSION_IR_PROOF_REQUIREMENTS_REQUIRED
======================================================================
ERROR: test_fastdoc_v2 (tests.test_fastdoc_v2.FastDocTests.test_fastdoc_v2)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/work/Federation-Omega/tests/test_fastdoc_v2.py", line 8, in test_fastdoc_v2
    import pymupdf
ModuleNotFoundError: No module named 'pymupdf'
"""
        receipt = CIFailureTriage().triage(
            log,
            candidate_paths=("federation/opa_policy_adapter_v1.py",),
            base_sha="base",
            head_sha="head",
            run_id="1",
            job_id="2",
        )
        self.assertTrue(receipt.admission_blocked)
        self.assertEqual(len(receipt.candidate_failures), 1)
        self.assertEqual(receipt.candidate_failures[0].failure_kind, "CANONICAL_CONTRACT_DRIFT")
        self.assertEqual(len(receipt.baseline_failures), 1)
        self.assertEqual(receipt.baseline_failures[0].failure_kind, "ENVIRONMENT_DEPENDENCY")
        self.assertIn("REPAIR_CANDIDATE_REGRESSIONS", receipt.repair_order)
        self.assertIn("REPAIR_TEST_ENVIRONMENT_OR_PACKAGING", receipt.repair_order)
        self.assertIn("RERUN_EXACT_HEAD_FULL_COURT", receipt.repair_order)

    def test_effect_state_conflation_is_classified_as_candidate_regression(self) -> None:
        log = r"""
======================================================================
FAIL: test_real_sol62_adapter_executes_verified_transition (tests.test_fuse_serving_kernel_v1.KernelTests.test_real_sol62_adapter_executes_verified_transition)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/work/Federation-Omega/tests/test_fuse_serving_kernel_v1.py", line 240, in test_real_sol62_adapter_executes_verified_transition
    self.assertEqual(receipt.state, "COMPLETE")
AssertionError: 'HOLD_UAS' != 'COMPLETE'
"""
        receipt = CIFailureTriage().triage(
            log,
            candidate_paths=("tests/test_fuse_serving_kernel_v1.py",),
        )
        self.assertEqual(receipt.failure_count, 1)
        self.assertEqual(receipt.candidate_failures[0].failure_kind, "PROOF_STATE_CONFLATION")

    def test_missing_file_is_packaging_failure_and_still_blocks_admission(self) -> None:
        log = r"""
======================================================================
ERROR: test_extracted_core (tests.test_shadow_canary.ShadowTests.test_extracted_core)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/work/Federation-Omega/tests/test_shadow_canary.py", line 22, in test_extracted_core
    open(".github/workflows/example.yml")
FileNotFoundError: [Errno 2] No such file or directory: '.github/workflows/example.yml'
"""
        receipt = CIFailureTriage().triage(log)
        self.assertTrue(receipt.admission_blocked)
        self.assertEqual(receipt.baseline_failures[0].failure_kind, "PACKAGING_OR_FIXTURE_CONTRACT")

    def test_green_log_yields_nonblocking_receipt(self) -> None:
        receipt = CIFailureTriage().triage("Ran 42 tests in 1.0s\nOK")
        self.assertFalse(receipt.admission_blocked)
        self.assertEqual(receipt.failure_count, 0)
        self.assertEqual(receipt.repair_order, ())


if __name__ == "__main__":
    unittest.main()
