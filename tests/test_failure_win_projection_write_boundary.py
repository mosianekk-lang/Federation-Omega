from __future__ import annotations

import unittest

from ao_harmonic_v3.failure_win_sheet_boundary import (
    ALIAS_SHEET,
    EVENT_SHEET,
    MANIFEST_SHEET,
    FailureWinSheetRole,
    FailureWinSheetWrite,
    ProjectionWriteViolation,
    assert_failure_win_sheet_write_allowed,
)


class FailureWinProjectionWriteBoundaryTests(unittest.TestCase):
    def test_event_writer_can_write_event_ledger(self):
        assert_failure_win_sheet_write_allowed(
            FailureWinSheetWrite(EVENT_SHEET, 0, 26, FailureWinSheetRole.EVENT_WRITER)
        )

    def test_exact_observed_spill_block_range_fails_closed(self):
        with self.assertRaisesRegex(
            ProjectionWriteViolation,
            "DERIVED_MANIFEST_SPILL_WRITE_PROHIBITED",
        ):
            assert_failure_win_sheet_write_allowed(
                FailureWinSheetWrite(MANIFEST_SHEET, 4, 12, FailureWinSheetRole.EVENT_WRITER)
            )

    def test_compiler_cannot_overwrite_formula_owned_spill(self):
        with self.assertRaisesRegex(
            ProjectionWriteViolation,
            "DERIVED_MANIFEST_SPILL_WRITE_PROHIBITED",
        ):
            assert_failure_win_sheet_write_allowed(
                FailureWinSheetWrite(MANIFEST_SHEET, 4, 13, FailureWinSheetRole.MANIFEST_COMPILER)
            )

    def test_registry_manager_is_bounded_to_manifest_a_through_d(self):
        assert_failure_win_sheet_write_allowed(
            FailureWinSheetWrite(
                MANIFEST_SHEET, 0, 4, FailureWinSheetRole.RECEIVER_REGISTRY_MANAGER
            )
        )
        with self.assertRaises(ProjectionWriteViolation):
            assert_failure_win_sheet_write_allowed(
                FailureWinSheetWrite(
                    MANIFEST_SHEET, 0, 5, FailureWinSheetRole.RECEIVER_REGISTRY_MANAGER
                )
            )

    def test_manifest_compiler_is_bounded_to_snapshot_metadata_o_through_p(self):
        assert_failure_win_sheet_write_allowed(
            FailureWinSheetWrite(MANIFEST_SHEET, 14, 16, FailureWinSheetRole.MANIFEST_COMPILER)
        )
        with self.assertRaises(ProjectionWriteViolation):
            assert_failure_win_sheet_write_allowed(
                FailureWinSheetWrite(MANIFEST_SHEET, 13, 16, FailureWinSheetRole.MANIFEST_COMPILER)
            )

    def test_alias_manager_cannot_write_other_failure_win_sheets(self):
        assert_failure_win_sheet_write_allowed(
            FailureWinSheetWrite(ALIAS_SHEET, 0, 8, FailureWinSheetRole.RECEIVER_ALIAS_MANAGER)
        )
        with self.assertRaises(ProjectionWriteViolation):
            assert_failure_win_sheet_write_allowed(
                FailureWinSheetWrite(EVENT_SHEET, 0, 8, FailureWinSheetRole.RECEIVER_ALIAS_MANAGER)
            )

    def test_unknown_failure_win_sheet_fails_closed(self):
        with self.assertRaisesRegex(ProjectionWriteViolation, "UNKNOWN_FAILURE_WIN_SHEET"):
            assert_failure_win_sheet_write_allowed(
                FailureWinSheetWrite("Failure-Win Imaginary Projection", 0, 1, FailureWinSheetRole.EVENT_WRITER)
            )


if __name__ == "__main__":
    unittest.main()
