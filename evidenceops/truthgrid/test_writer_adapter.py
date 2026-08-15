from __future__ import annotations

import unittest

from evidenceops.truthgrid.guards import MutationIntent, TruthGridViolation
from evidenceops.truthgrid.writer_adapter import TruthGridWriterAdapter


class TruthGridWriterAdapterTests(unittest.TestCase):
    def test_guard_blocks_before_writer(self) -> None:
        calls: list[str] = []

        def writer(intent: MutationIntent) -> None:
            calls.append(intent.sheet)

        adapter = TruthGridWriterAdapter(
            writer=writer,
            readback=lambda _s, _k: {},
            schema_reader=lambda _s: ("Claim",),
        )
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

    def test_valid_write_binds_values_to_live_header_order_and_requires_matching_readback(self) -> None:
        state: dict[str, object] = {}
        observed_key_order: list[str] = []

        def writer(intent: MutationIntent) -> None:
            observed_key_order.extend(intent.values.keys())
            state.update(intent.values)

        adapter = TruthGridWriterAdapter(
            writer=writer,
            readback=lambda _sheet, _key: dict(state),
            schema_reader=lambda _sheet: ("Claim", "State"),
        )
        intent = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="UPDATE",
            target_key="CLAIM-001",
            row_identity_resolved_by_key=True,
            values={"State": "WORKING", "Claim": "bounded"},
            provider_readback_planned=True,
        )
        receipt = adapter.execute(intent)
        self.assertTrue(receipt.provider_readback_verified)
        self.assertTrue(receipt.schema_binding_verified)
        self.assertEqual(receipt.live_schema, ("Claim", "State"))
        self.assertEqual(observed_key_order, ["Claim", "State"])
        self.assertEqual(receipt.target_key, "CLAIM-001")
        self.assertEqual(receipt.readback["Claim"], "bounded")

    def test_unknown_field_fails_before_writer(self) -> None:
        calls: list[str] = []

        adapter = TruthGridWriterAdapter(
            writer=lambda intent: calls.append(intent.sheet),
            readback=lambda _sheet, _key: {},
            schema_reader=lambda _sheet: ("Claim", "State"),
        )
        intent = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="UPDATE",
            target_key="CLAIM-UNKNOWN",
            row_identity_resolved_by_key=True,
            values={"Claim": "x", "Legacy_State": "bad"},
        )
        with self.assertRaisesRegex(TruthGridViolation, "LIVE_SCHEMA_FIELD_MISMATCH:Legacy_State"):
            adapter.execute(intent)
        self.assertEqual(calls, [])

    def test_append_requires_full_live_schema_before_writer(self) -> None:
        calls: list[str] = []

        adapter = TruthGridWriterAdapter(
            writer=lambda intent: calls.append(intent.sheet),
            readback=lambda _sheet, _key: {},
            schema_reader=lambda _sheet: ("Claim", "State"),
        )
        intent = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="APPEND",
            target_key="CLAIM-APPEND",
            row_identity_resolved_by_key=True,
            values={"Claim": "x"},
        )
        with self.assertRaisesRegex(TruthGridViolation, "APPEND_REQUIRES_FULL_LIVE_SCHEMA:State"):
            adapter.execute(intent)
        self.assertEqual(calls, [])

    def test_duplicate_live_headers_fail_before_writer(self) -> None:
        calls: list[str] = []

        adapter = TruthGridWriterAdapter(
            writer=lambda intent: calls.append(intent.sheet),
            readback=lambda _sheet, _key: {},
            schema_reader=lambda _sheet: ("Claim", "Claim"),
        )
        intent = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="UPDATE",
            target_key="CLAIM-DUP",
            row_identity_resolved_by_key=True,
            values={"Claim": "x"},
        )
        with self.assertRaisesRegex(TruthGridViolation, "LIVE_SCHEMA_DUPLICATE_HEADER"):
            adapter.execute(intent)
        self.assertEqual(calls, [])

    def test_blank_live_header_fails_before_writer(self) -> None:
        calls: list[str] = []

        adapter = TruthGridWriterAdapter(
            writer=lambda intent: calls.append(intent.sheet),
            readback=lambda _sheet, _key: {},
            schema_reader=lambda _sheet: ("Claim", ""),
        )
        intent = MutationIntent(
            sheet="ASSERTION ATOMS",
            operation="UPDATE",
            target_key="CLAIM-BLANK",
            row_identity_resolved_by_key=True,
            values={"Claim": "x"},
        )
        with self.assertRaisesRegex(TruthGridViolation, "LIVE_SCHEMA_BLANK_HEADER"):
            adapter.execute(intent)
        self.assertEqual(calls, [])

    def test_readback_mismatch_fails_closed(self) -> None:
        def writer(_intent: MutationIntent) -> None:
            return None

        adapter = TruthGridWriterAdapter(
            writer=writer,
            readback=lambda _sheet, _key: {"Claim": "different"},
            schema_reader=lambda _sheet: ("Claim",),
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
