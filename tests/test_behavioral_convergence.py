import unittest

from ao_harmonic_v3.behavioral_convergence import (
    BehavioralConvergenceEngine,
    BehavioralConvergenceState,
    BehavioralEvidenceKind,
    BehavioralOrigin,
    BehavioralProofReceipt,
    BehavioralReceiptConflict,
)
from ao_harmonic_v3.failure_win_v2 import RecoveryRoute
from ao_harmonic_v3.models import FederationEvent, PerformanceVector


class BehavioralConvergenceEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = BehavioralConvergenceEngine()
        self.incumbent = PerformanceVector(quality=5, reliability=5, proof=5, speed=1)
        candidate = PerformanceVector(
            quality=5,
            reliability=6,
            proof=6,
            speed=5,
            owner_time_recovered=2,
            recovery_gain=2,
        )
        self.route = RecoveryRoute(
            route_id="governed-pr-readmission",
            route_type="GOVERNED_REENTRY",
            performance=candidate,
            proof_strength=1.0,
            reversibility=1.0,
            strategic_value=1.0,
        )

    def event(self, *, event_id="AIRLOCK-33037638447", origin="REAL_PROVIDER"):
        return FederationEvent(
            event_id=event_id,
            event_type="FAILURE",
            source="Federation Omega",
            workstream="SOURCE_PROVENANCE",
            idempotency_key=event_id,
            timestamp="2026-08-27T03:52:35Z",
            proof_class="PROVIDER_READBACK",
            payload={
                "behavioral_origin": origin,
                "objective": "Keep current source admitted through governed provenance",
                "claim": "Current main should pass source provenance admission",
                "observed_fruit": "Airlock source provenance status UNADMITTED_HISTORY",
                "desired_outcome": "PR-governed admitted successor with exact readback",
                "failure_code": "SOURCE_PROVENANCE_UNADMITTED_DIRECT_MAIN",
                "provider": "github",
                "route_id": "direct-main-push",
                "material": True,
                "provider_dependent": True,
                "current": True,
                "independent_readback": True,
                "proof_refs": (
                    "github:airlock:33037638447",
                    "github:commit:ec7cbc9f1a5c0ae9fd6355852c9c4e2918620d43",
                    "source-provenance:4bc4068a8dc94f7998e33b6a947e92957f2292d2af7f6cae7de876c3ee08d2c1",
                ),
            },
        )

    def receipt(self, event_id, kind, observed_at, *, origin=BehavioralOrigin.REAL_PROVIDER):
        return BehavioralProofReceipt(
            event_id=event_id,
            receiver_id="Federation Omega",
            kind=kind,
            origin=origin,
            observed_at=observed_at,
            proof_refs=(f"proof:{event_id}",),
            independent_readback=True,
            current=True,
        )

    def test_current_direct_main_airlock_failure_opens_real_behavior_cycle(self):
        opened = self.engine.observe_federation_event(
            self.event(),
            incumbent=self.incumbent,
            routes=(self.route,),
            provider_dependent=True,
        )
        self.assertEqual(opened.state, BehavioralConvergenceState.BEHAVIOR_PROOF_OPEN)
        self.assertTrue(opened.empirical_failure_seen)
        self.assertFalse(opened.behavior_proven)
        self.assertEqual(opened.kernel_result["state"], "ROUTE_SELECTED")
        self.assertIn("FAILURE_FIRST_TEST", opened.kernel_result["proof_graph"]["missing_nodes"])

    def test_synthetic_event_is_preserved_but_cannot_advance_behavior(self):
        event = self.event(event_id="SYNTHETIC-1", origin="SYNTHETIC_TEST")
        result = self.engine.observe_federation_event(
            event,
            incumbent=self.incumbent,
            routes=(self.route,),
            provider_dependent=True,
        )
        self.assertEqual(result.state, BehavioralConvergenceState.INVOCATION_ONLY_NON_EMPIRICAL)
        self.assertFalse(result.empirical_failure_seen)
        self.assertFalse(result.behavior_proven)
        self.assertIn("WAIT_FOR_EMPIRICAL_FAILURE_OR_PRECURSOR", result.next_actions[0])

    def test_non_empirical_proof_receipt_does_not_close_gate(self):
        opened = self.engine.observe_federation_event(
            self.event(),
            incumbent=self.incumbent,
            routes=(self.route,),
            provider_dependent=True,
        )
        result = self.engine.record_proof(
            opened.fingerprint,
            self.receipt(
                "DOC-CAUSAL",
                BehavioralEvidenceKind.CAUSAL_MODEL,
                "2026-08-27T04:00:00Z",
                origin=BehavioralOrigin.DOCUMENTATION,
            ),
        )
        self.assertEqual(result.qualifying_receipts, 0)
        self.assertEqual(result.rejected_receipts, 1)
        self.assertIn("CAUSAL_MODEL_RECORDED", result.kernel_result["proof_graph"]["missing_nodes"])

    def test_full_real_proof_reaches_bounded_win_then_requires_derived_soak(self):
        opened = self.engine.observe_federation_event(
            self.event(),
            incumbent=self.incumbent,
            routes=(self.route,),
            provider_dependent=True,
        )
        kinds = (
            BehavioralEvidenceKind.CAUSAL_MODEL,
            BehavioralEvidenceKind.FALSIFICATION,
            BehavioralEvidenceKind.AUTHORITY_CURRENT,
            BehavioralEvidenceKind.COST_ALLOWED,
            BehavioralEvidenceKind.FAILURE_FIRST,
            BehavioralEvidenceKind.HEALTHY_PATH,
            BehavioralEvidenceKind.ROLLBACK,
            BehavioralEvidenceKind.FORWARD_CANARY,
            BehavioralEvidenceKind.SEMANTIC_READBACK,
            BehavioralEvidenceKind.POSITIVE_VALUE,
            BehavioralEvidenceKind.NO_REGRESSION,
            BehavioralEvidenceKind.OWNER_BURDEN_NOT_INCREASED,
            BehavioralEvidenceKind.PROVIDER_RECEIPT,
        )
        result = opened
        for index, kind in enumerate(kinds, start=1):
            result = self.engine.record_proof(
                opened.fingerprint,
                self.receipt(f"P-{index}", kind, "2026-08-27T04:00:00Z"),
            )
        self.assertEqual(result.state, BehavioralConvergenceState.BEHAVIOR_BOUNDED_WIN_SOAK_OPEN)
        self.assertFalse(result.behavior_proven)
        self.assertEqual(result.repeated_successes, 0)
        self.assertEqual(result.soak_seconds, 0.0)

        for event_id, timestamp in (
            ("SUCCESS-1", "2026-08-27T04:01:00Z"),
            ("SUCCESS-2", "2026-08-27T04:03:30Z"),
            ("SUCCESS-3", "2026-08-27T04:06:00Z"),
        ):
            result = self.engine.record_proof(
                opened.fingerprint,
                self.receipt(event_id, BehavioralEvidenceKind.SUCCESS, timestamp),
            )

        self.assertEqual(result.repeated_successes, 3)
        self.assertEqual(result.soak_seconds, 300.0)
        self.assertEqual(result.state, BehavioralConvergenceState.V2_BEHAVIOR_PROVEN)
        self.assertTrue(result.behavior_proven)
        self.assertEqual(result.kernel_result["state"], "OPERATIONAL_WIN_VERIFIED")

    def test_duplicate_event_is_idempotent_but_changed_payload_fails_closed(self):
        event = self.event()
        first = self.engine.observe_federation_event(event, incumbent=self.incumbent, routes=(self.route,))
        second = self.engine.observe_federation_event(event, incumbent=self.incumbent, routes=(self.route,))
        self.assertEqual(first.ledger_head, second.ledger_head)
        self.assertEqual(len(self.engine.ledger_snapshot()), 1)

        changed = FederationEvent(
            **{**event.__dict__, "payload": {**event.payload, "observed_fruit": "different fruit"}}
        )
        with self.assertRaises(BehavioralReceiptConflict):
            self.engine.observe_federation_event(changed, incumbent=self.incumbent, routes=(self.route,))

    def test_hash_chain_verifies_and_tamper_is_rejected(self):
        opened = self.engine.observe_federation_event(self.event(), incumbent=self.incumbent, routes=(self.route,))
        self.engine.record_proof(
            opened.fingerprint,
            self.receipt("P-CHAIN", BehavioralEvidenceKind.CAUSAL_MODEL, "2026-08-27T04:00:00Z"),
        )
        snapshot = list(self.engine.ledger_snapshot())
        count, head = BehavioralConvergenceEngine.verify_ledger_snapshot(snapshot)
        self.assertEqual(count, 2)
        self.assertEqual(head, self.engine.ledger_head)

        tampered = [dict(item) for item in snapshot]
        tampered[1]["payload_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            BehavioralConvergenceEngine.verify_ledger_snapshot(tampered)


if __name__ == "__main__":
    unittest.main()
