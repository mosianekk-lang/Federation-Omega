from __future__ import annotations

import unittest

from evidenceops.truthgrid.guards import MutationIntent, TruthGridViolation
from evidenceops.truthgrid.writer_adapter import TruthGridWriterAdapter


class TruthGridWriterAdapterTests(unittest.TestCase):
    def test_guard_blocks_before_writer(self) -> None:
        calls: list[str] = []

        def writer(intent: MutationIntent) -> None:
            calls.append(intent.sheet)

        adapter = TruthGridWriterAdapter(writer=writer, readback=lambda _s, _k: {})
        bad = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="UPDATE",
            target_key=None,
            row_identity_resolved_by_key=False,
            values={"Claim": "x"},
        )
        with self.assertRaisesRegex(TruthGridViolation, "KEY_BOUND_TARGET_REQUIRED"):
            adapter.execute(bad)
        self.assertEqual(calls, [])

    def test_valid_write_requires_matching_readback(self) -> None:
        state: dict[str, object] = {}

        def writer(intent: MutationIntent) -> None:
            state.update(intent.values)

        adapter = TruthGridWriterAdapter(
            writer=writer,
            readback=lambda _sheet, _key: dict(state),
        )
        intent = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="UPDATE",
            target_key="CLAIM-001",
            row_identity_resolved_by_key=True,
            values={"Claim": "bounded", "State": "WORKING"},
            provider_readback_planned=True,
        )
        receipt = adapter.execute(intent)
        self.assertTrue(receipt.provider_readback_verified)
        self.assertEqual(receipt.target_key, "CLAIM-001")
        self.assertEqual(receipt.readback["Claim"], "bounded")

    def test_readback_mismatch_fails_closed(self) -> None:
        def writer(_intent: MutationIntent) -> None:
            return None

        adapter = TruthGridWriterAdapter(
            writer=writer,
            readback=lambda _sheet, _key: {"Claim": "different"},
        )
        intent = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="UPDATE",
            target_key="CLAIM-002",
            row_identity_resolved_by_key=True,
            values={"Claim": "expected"},
            provider_readback_planned=True,
        )
        with self.assertRaisesRegex(TruthGridViolation, "PROVIDER_READBACK_MISMATCH:Claim"):
            adapter.execute(intent)


if __name__ == "__main__":
    unittest.main()
