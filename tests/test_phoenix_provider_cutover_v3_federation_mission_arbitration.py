from datetime import datetime, timedelta, timezone
import unittest

from federation.orchestration.mission_arbitration import (
    CapabilityRoute,
    CapabilitySelector,
    ConcurrencyGuard,
    ConcurrencyState,
    ExecutionEnvelope,
    FailureMemoryRecord,
    FailureStatus,
    KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET,
    MissionLease,
    MissionSnapshot,
    NearMissEvent,
    PreWriteFence,
    ProofState,
    WorkstreamObservation,
)

BASE = "1" * 40
NEW = "2" * 40
HEAD = "3" * 40


def iso(dt):
    return dt.isoformat()


class FederationMissionArbitrationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 28, 1, 40, tzinfo=timezone.utc)
        self.lease = MissionLease.create(
            mission_id="MSN-LUNO-001",
            lane_id="LUNO-SOURCE",
            holder_id="CHAT-A",
            base_main_sha=BASE,
            lease_epoch=7,
            path_scope=(
                "federation/orchestration",
                "federation/capital_execution/venues/LUNO_OBSERVER_BINDING_CONTRACT.json",
            ),
            issued_at=iso(self.now - timedelta(minutes=2)),
            expires_at=iso(self.now + timedelta(minutes=20)),
        )

    def test_lease_is_fenced_and_cannot_expand_authority(self):
        self.assertTrue(self.lease.active_at(iso(self.now)))
        self.assertTrue(self.lease.fence_token.startswith("FMACF-FENCE-"))
        with self.assertRaises(ValueError):
            MissionLease.create(
                mission_id="MSN-X",
                lane_id="L",
                holder_id="H",
                base_main_sha=BASE,
                lease_epoch=1,
                path_scope=("federation",),
                issued_at=iso(self.now),
                expires_at=iso(self.now + timedelta(minutes=1)),
                authority_ceiling="A2",
            )

    def test_path_traversal_cannot_escape_mission_lease(self):
        with self.assertRaises(ValueError):
            MissionLease.create(
                mission_id="MSN-X",
                lane_id="L",
                holder_id="H",
                base_main_sha=BASE,
                lease_epoch=1,
                path_scope=("../governance",),
                issued_at=iso(self.now),
                expires_at=iso(self.now + timedelta(minutes=1)),
            )

    def test_fresh_main_and_nonoverlap_allows_prewrite(self):
        decision = ConcurrencyGuard().evaluate(
            lease=self.lease,
            current_main_sha=BASE,
            now=iso(self.now),
        )
        self.assertEqual(ConcurrencyState.CLEAR, decision.state)
        receipt = PreWriteFence().authorise(
            lease=self.lease,
            decision=decision,
            intended_paths=("federation/orchestration/mission_arbitration.py",),
        )
        self.assertTrue(receipt.allowed)
        self.assertEqual("PREWRITE_FENCE_VERIFIED", receipt.reason)

    def test_moving_main_is_a_hard_prewrite_fence_even_without_overlap(self):
        decision = ConcurrencyGuard().evaluate(
            lease=self.lease,
            current_main_sha=NEW,
            now=iso(self.now),
            main_changed_paths=("docs/unrelated.md",),
        )
        self.assertEqual(ConcurrencyState.MAIN_DRIFT_FAST_RECONVERGE, decision.state)
        self.assertFalse(decision.write_allowed)
        receipt = PreWriteFence().authorise(
            lease=self.lease,
            decision=decision,
            intended_paths=("federation/orchestration/mission_arbitration.py",),
        )
        self.assertFalse(receipt.allowed)

    def test_main_drift_with_path_overlap_requires_reconciliation(self):
        decision = ConcurrencyGuard().evaluate(
            lease=self.lease,
            current_main_sha=NEW,
            now=iso(self.now),
            main_changed_paths=("federation/orchestration/another.py",),
        )
        self.assertEqual(ConcurrencyState.MAIN_DRIFT_OVERLAP_HOLD, decision.state)
        self.assertIn("federation/orchestration", decision.overlapping_paths)

    def test_open_workstream_overlap_is_serialized(self):
        other = WorkstreamObservation.create(
            workstream_id="PR-OTHER",
            head_sha=HEAD,
            base_sha=BASE,
            paths=("federation/capital_execution/venues",),
        )
        decision = ConcurrencyGuard().evaluate(
            lease=self.lease,
            current_main_sha=BASE,
            now=iso(self.now),
            active_workstreams=(other,),
        )
        self.assertEqual(ConcurrencyState.ACTIVE_WORKSTREAM_OVERLAP_HOLD, decision.state)
        self.assertEqual(("PR-OTHER",), decision.overlapping_workstreams)

    def test_expired_lease_fails_closed(self):
        decision = ConcurrencyGuard().evaluate(
            lease=self.lease,
            current_main_sha=BASE,
            now=iso(self.now + timedelta(hours=1)),
        )
        self.assertEqual(ConcurrencyState.LEASE_EXPIRED, decision.state)
        self.assertFalse(decision.write_allowed)

    def test_known_open_wif_failure_blocks_unchanged_route(self):
        route = CapabilityRoute(
            route_id="GITHUB_TO_GOOGLE_WIF",
            capability_id="CAP-GCP-WIF",
            reality_state="C4",
            required_reality_state="C4",
            readiness="READY",
            proof_ref="source:workflow",
            reliability=0.95,
            freshness=0.95,
            proof_strength=0.95,
        )
        selection = CapabilitySelector().select(
            routes=(route,),
            memories=(KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET,),
        )
        self.assertEqual("", selection.selected_route_id)
        reasons = selection.decisions[0].reasons
        self.assertTrue(any(reason.startswith("KNOWN_OPEN_FAILURE") for reason in reasons))

    def test_closed_failure_requires_exact_recovery_proof_binding(self):
        memory = FailureMemoryRecord(
            fingerprint="TRANSIENT_ROUTE_FAILURE",
            route_id="ROUTE-A",
            status=FailureStatus.CLOSED,
            failure_proof_ref="failure:1",
            retry_condition="new provider receipt",
            recovery_proof_ref="provider:verified:2",
        )
        missing = CapabilityRoute(
            route_id="ROUTE-A",
            capability_id="CAP-A",
            reality_state="C4",
            required_reality_state="C4",
            readiness="READY",
            proof_ref="source:a",
        )
        bound = CapabilityRoute(
            route_id="ROUTE-A",
            capability_id="CAP-A",
            reality_state="C4",
            required_reality_state="C4",
            readiness="READY",
            proof_ref="source:a",
            retry_evidence_refs=("provider:verified:2",),
        )
        selector = CapabilitySelector()
        self.assertEqual("", selector.select(routes=(missing,), memories=(memory,)).selected_route_id)
        self.assertEqual("ROUTE-A", selector.select(routes=(bound,), memories=(memory,)).selected_route_id)

    def test_route_tournament_prefers_stronger_proof_reliability_after_hard_gates(self):
        weaker = CapabilityRoute(
            route_id="ROUTE-WEAK",
            capability_id="CAP-W",
            reality_state="C4",
            readiness="READY",
            proof_ref="proof:w",
            quality=0.8,
            reliability=0.55,
            freshness=0.7,
            proof_strength=0.55,
            latency=0.2,
            cost=0.2,
            owner_burden=0.2,
            risk=0.4,
        )
        stronger = CapabilityRoute(
            route_id="ROUTE-STRONG",
            capability_id="CAP-S",
            reality_state="C4",
            readiness="READY",
            proof_ref="proof:s",
            quality=0.8,
            reliability=0.95,
            freshness=0.95,
            proof_strength=0.95,
            latency=0.3,
            cost=0.3,
            owner_burden=0.1,
            risk=0.1,
        )
        selection = CapabilitySelector().select(routes=(weaker, stronger), memories=())
        self.assertEqual("ROUTE-STRONG", selection.selected_route_id)

    def test_capability_reality_and_authority_are_hard_gates_not_score_inputs(self):
        conceptual = CapabilityRoute(
            route_id="ROUTE-CONCEPT",
            capability_id="CAP-C",
            reality_state="C1",
            required_reality_state="C4",
            readiness="READY",
            proof_ref="design:c",
            quality=1.0,
            reliability=1.0,
            freshness=1.0,
            proof_strength=1.0,
        )
        effectful = CapabilityRoute(
            route_id="ROUTE-EFFECT",
            capability_id="CAP-E",
            reality_state="C5",
            required_reality_state="C4",
            readiness="READY",
            proof_ref="provider:e",
            authority_required="A2",
            external_effect=True,
            quality=1.0,
            reliability=1.0,
            freshness=1.0,
            proof_strength=1.0,
        )
        selection = CapabilitySelector().select(routes=(conceptual, effectful), memories=())
        self.assertEqual("", selection.selected_route_id)
        all_reasons = {reason for decision in selection.decisions for reason in decision.reasons}
        self.assertTrue(any(reason.startswith("REALITY_STATE_INSUFFICIENT") for reason in all_reasons))
        self.assertIn("AUTHORITY_CEILING_EXCEEDED", all_reasons)
        self.assertIn("EXTERNAL_EFFECT_NOT_AUTHORISED", all_reasons)

    def test_realityguard_completion_requires_full_readback_receipt_chain(self):
        envelope = ExecutionEnvelope(
            mission_id="MSN-X",
            operation_id="OP-12345678",
            authorization_ref="auth:1",
            execution_ref="exec:1",
            target_readback_ref="readback:1",
            expected_target_digest="abc",
            observed_target_digest="abc",
        )
        self.assertEqual(ProofState.READBACK_VERIFIED, envelope.proof_state)
        self.assertFalse(envelope.completion_claim_allowed)
        complete = ExecutionEnvelope(
            mission_id="MSN-X",
            operation_id="OP-12345678",
            authorization_ref="auth:1",
            execution_ref="exec:1",
            target_readback_ref="readback:1",
            receipt_ref="receipt:1",
            expected_target_digest="abc",
            observed_target_digest="abc",
        )
        self.assertEqual(ProofState.RECEIPT_VERIFIED, complete.proof_state)
        self.assertTrue(complete.completion_claim_allowed)

    def test_digest_mismatch_prevents_completion_claim(self):
        envelope = ExecutionEnvelope(
            mission_id="MSN-X",
            operation_id="OP-12345678",
            authorization_ref="auth:1",
            execution_ref="exec:1",
            target_readback_ref="readback:1",
            receipt_ref="receipt:1",
            expected_target_digest="abc",
            observed_target_digest="def",
        )
        self.assertEqual(ProofState.EXECUTED, envelope.proof_state)
        self.assertFalse(envelope.completion_claim_allowed)

    def test_near_miss_and_snapshot_are_deterministic(self):
        near = NearMissEvent.create(
            mission_id=self.lease.mission_id,
            event_type="KNOWN_DEAD_ROUTE_AVOIDED",
            prevented_action="google_oidc_exchange",
            signal="GOOGLE_WIF_INVALID_TARGET",
            control="ROUTE_AND_FAILURE_MEMORY",
            proof_refs=("run:33132793891",),
        )
        concurrency = ConcurrencyGuard().evaluate(
            lease=self.lease,
            current_main_sha=BASE,
            now=iso(self.now),
        )
        fallback = CapabilityRoute(
            route_id="LOCAL_SOURCE_REPAIR",
            capability_id="CAP-SOURCE",
            reality_state="C4",
            readiness="READY",
            proof_ref="repo:main",
        )
        selection = CapabilitySelector().select(
            routes=(fallback,),
            memories=(KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET,),
        )
        first = MissionSnapshot.create(
            lease=self.lease,
            concurrency=concurrency,
            selection=selection,
            memories=(KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET,),
            near_misses=(near,),
        )
        second = MissionSnapshot.create(
            lease=self.lease,
            concurrency=concurrency,
            selection=selection,
            memories=(KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET,),
            near_misses=(near,),
        )
        self.assertEqual(first.snapshot_digest, second.snapshot_digest)
        self.assertIn("GOOGLE_WIF_INVALID_TARGET", first.active_failure_fingerprints)

    def test_luno_contract_binds_mission_arbitration_and_known_failure_floor(self):
        import json
        from pathlib import Path

        contract = json.loads(
            Path("federation/capital_execution/venues/LUNO_OBSERVER_BINDING_CONTRACT.json").read_text(
                encoding="utf-8"
            )
        )
        arbitration = contract["mission_arbitration"]
        self.assertEqual(contract["version"], "1.3.0")
        self.assertEqual(
            arbitration["contract"],
            "governance/federation_mission_arbitration_fabric_v1.json",
        )
        self.assertTrue(arbitration["capability_discovery_before_route_selection"])
        self.assertTrue(arbitration["failure_memory_before_retry"])
        self.assertTrue(arbitration["current_main_prewrite_fence_required"])
        self.assertEqual(arbitration["known_failure_fingerprint"], "GOOGLE_WIF_INVALID_TARGET")
        self.assertEqual(arbitration["known_failed_route"], "GITHUB_TO_GOOGLE_WIF")
        self.assertFalse(contract["financial_effects"])
        self.assertFalse(contract["provider_write_operations"])
        self.assertIn(
            "MISSION_ARBITRATION_PRECEDES_PROVIDER_ROUTE_RETRY",
            contract["invariants"],
        )


if __name__ == "__main__":
    unittest.main()
