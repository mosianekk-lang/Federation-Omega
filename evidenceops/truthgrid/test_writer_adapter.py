from __future__ import annotations

import unittest

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
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

    def test_failure_win_v2_truthgrid_receiver_canary_preserves_readback_gate(self) -> None:
        state: dict[str, object] = {}

        def writer(intent: MutationIntent) -> None:
            state.update(intent.values)

        native = TruthGridWriterAdapter(
            writer=writer,
            readback=lambda _sheet, _key: dict(state),
            schema_reader=lambda _sheet: ("Claim", "State"),
        ).execute(
            MutationIntent(
                sheet="ASSERTION ATOMS",
                operation="UPDATE",
                target_key="FWV2-TRUTHGRID-CANARY",
                row_identity_resolved_by_key=True,
                values={"Claim": "synthetic bounded claim", "State": "WORKING"},
                provider_readback_planned=True,
            )
        )
        self.assertTrue(native.provider_readback_verified)
        self.assertTrue(native.schema_binding_verified)

        incumbent = PerformanceVector(quality=8, reliability=8, proof=9, speed=2, owner_burden=1)
        candidate = PerformanceVector(
            quality=8, reliability=8, proof=9, speed=5,
            owner_time_recovered=2, recovery_gain=2, owner_burden=0,
        )
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-TRUTHGRID-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="TruthGrid",
                    objective="preempt a synthetic evidence-projection drift risk",
                    claim="a schema-bound assertion projection may become stale",
                    observed_fruit="synthetic local readback only; no provider mutation",
                    desired_outcome="prewarm a current schema/readback route",
                    failure_code="SYNTHETIC_TRUTHGRID_SCHEMA_DRIFT",
                    material=False,
                    precursor_signals=("schema-drift-fixture", "readback-mismatch-fixture"),
                ),
                incumbent=incumbent,
                routes=(RecoveryRoute(
                    route_id="truthgrid-current-schema-readback-fixture",
                    route_type="REROUTE",
                    performance=candidate,
                    proof_strength=1.0,
                    reversibility=1.0,
                    strategic_value=1.0,
                    expected_value=2.0,
                ),),
            )
        )
        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertTrue(result.vector_gate_passed)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)


if __name__ == "__main__":
    unittest.main()
