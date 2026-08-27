from __future__ import annotations

import unittest

from ao_harmonic_v3.failure_win_sheet_boundary import (
    EVENT_SHEET,
    MANIFEST_SHEET,
    FailureWinSheetRole,
    FailureWinSheetWrite,
    ProjectionWriteViolation,
    assert_failure_win_sheet_write_allowed,
)


class FailureWinProjectionBoundaryAirlockTests(unittest.TestCase):
    def test_event_ledger_remains_writable_and_manifest_spill_fails_closed(self):
        assert_failure_win_sheet_write_allowed(
            FailureWinSheetWrite(EVENT_SHEET, 0, 26, FailureWinSheetRole.EVENT_WRITER)
        )
        with self.assertRaisesRegex(
            ProjectionWriteViolation,
            "DERIVED_MANIFEST_SPILL_WRITE_PROHIBITED",
        ):
            assert_failure_win_sheet_write_allowed(
                FailureWinSheetWrite(MANIFEST_SHEET, 4, 12, FailureWinSheetRole.EVENT_WRITER)
            )


if __name__ == "__main__":
    unittest.main()
