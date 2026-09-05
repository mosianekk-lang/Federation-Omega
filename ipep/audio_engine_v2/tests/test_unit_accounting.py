import unittest

from evidenceops_audio.unit_accounting import (
    UnitAccountingError,
    UnitReceipt,
    reconcile_unit_accounting,
)


CHUNK_SHA = "a" * 64
RAW_SHA = "b" * 64


def receipt(unit_id, segments, *, state="PROCESSED", exit_code=0):
    return UnitReceipt(
        unit_id=unit_id,
        source_chunk_sha256=CHUNK_SHA,
        unit_start_seconds=0.0,
        unit_end_seconds=60.0,
        provider="local_whisper_cpp",
        provider_exit_code=exit_code,
        raw_response_sha256=RAW_SHA,
        segment_count=segments,
        state=state,
    )


class UnitAccountingTests(unittest.TestCase):
    def test_zero_segment_unit_is_explicitly_accounted(self):
        result = reconcile_unit_accounting(
            ["unit-001-01", "unit-001-02", "unit-001-03"],
            [
                receipt("unit-001-01", 2),
                receipt("unit-001-02", 0),
                receipt("unit-001-03", 1),
            ],
        )
        self.assertEqual(result["state"], "ACCOUNTING_VERIFIED")
        self.assertEqual(result["processed_unit_count"], 3)
        self.assertEqual(result["emitted_segment_unit_count"], 2)
        self.assertEqual(result["zero_segment_unit_count"], 1)
        self.assertEqual(result["failed_unit_count"], 0)
        self.assertEqual(result["zero_segment_unit_ids"], ["unit-001-02"])

    def test_failed_unit_is_separate_from_zero_segment_unit(self):
        result = reconcile_unit_accounting(
            ["unit-001-01", "unit-001-02"],
            [receipt("unit-001-01", 0), receipt("unit-001-02", 0, state="FAILED", exit_code=1)],
        )
        self.assertEqual(result["state"], "ACCOUNTING_VERIFIED_WITH_FAILURES")
        self.assertEqual(result["zero_segment_unit_ids"], ["unit-001-01"])
        self.assertEqual(result["failed_unit_ids"], ["unit-001-02"])

    def test_missing_receipt_fails_closed(self):
        with self.assertRaisesRegex(UnitAccountingError, "missing=unit-001-02"):
            reconcile_unit_accounting(
                ["unit-001-01", "unit-001-02"],
                [receipt("unit-001-01", 1)],
            )

    def test_unexpected_receipt_fails_closed(self):
        with self.assertRaisesRegex(UnitAccountingError, "unexpected=unit-001-03"):
            reconcile_unit_accounting(
                ["unit-001-01"],
                [receipt("unit-001-01", 1), receipt("unit-001-03", 1)],
            )

    def test_duplicate_receipt_fails_closed(self):
        with self.assertRaisesRegex(UnitAccountingError, "duplicate provider receipts"):
            reconcile_unit_accounting(
                ["unit-001-01"],
                [receipt("unit-001-01", 1), receipt("unit-001-01", 1)],
            )

    def test_raw_provider_receipt_hash_is_mandatory(self):
        invalid = receipt("unit-001-01", 0)
        invalid = UnitReceipt(**{**invalid.__dict__, "raw_response_sha256": ""})
        with self.assertRaisesRegex(UnitAccountingError, "invalid raw_response_sha256"):
            reconcile_unit_accounting(["unit-001-01"], [invalid])


if __name__ == "__main__":
    unittest.main()
