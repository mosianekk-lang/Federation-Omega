from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import unittest

import federation.orchestration.mission_arbitration as arbitration_module
from federation.orchestration import (
    CapabilityRoute,
    CapabilitySelector,
    ConcurrencyGuard,
    ConcurrencyState,
    ExecutionEnvelope,
    FailureMemoryRecord,
    FailureStatus,
    MissionLease,
    MissionSnapshot,
    NearMissEvent,
    PreWriteFence,
    ProofState,
)

BASE = "1" * 40
NEXT = "2" * 40


def iso(value: datetime) -> str:
    return value.isoformat()


class MissionArbitrationGeneHarvestTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 30, 0, 20, tzinfo=timezone.utc)
        self.lease = MissionLease.create(
            mission_id="CFBE-HARVEST-1",
            lane_id="ARBITRATION",
            holder_id="FEDERATION",
            base_main_sha=BASE,
            lease_epoch=3,
            path_scope=("federation/orchestration",),
            issued_at=iso(self.now - timedelta(minutes=1)),
            expires_at=iso(self.now + timedelta(minutes=20)),
        )

    def route(self, route_id: str, **kwargs) -> CapabilityRoute:
        values = {
            "route_id": route_id,
            "capability_id": f"CAP-{route_id}",
            "reality_state": "C4",
            "required_reality_state": "C3",
            "readiness": "READY",
            "authority_required": "A1_INTERNAL",
            "proof_ref": f"proof:{route_id}",
        }
        values.update(kwargs)
        return CapabilityRoute(**values)

    def test_admitted_lean_api_remains_compatible(self):
        decision = ConcurrencyGuard().evaluate(
            lease=self.lease, current_main_sha=BASE, now=iso(self.now)
        )
        self.assertEqual("CLEAR", decision.state)
        receipt = PreWriteFence().authorise(
            lease=self.lease,
            decision=decision,
            current_main_sha=BASE,
            intended_paths=("federation/orchestration/mission_arbitration.py",),
        )
        self.assertTrue(receipt.allowed)
        self.assertEqual(
            "R",
            CapabilitySelector().select(routes=(self.route("R"),), memories=()).selected_route_id,
        )

    def test_cfbe_multidimensional_tournament_prefers_stronger_proof_route(self):
        weak = self.route(
            "WEAK",
            reliability=0.40,
            freshness=0.40,
            proof_strength=0.40,
            risk=0.80,
        )
        strong = self.route(
            "STRONG",
            reliability=0.95,
            freshness=0.95,
            proof_strength=0.95,
            risk=0.10,
            owner_burden=0.10,
        )
        result = CapabilitySelector().select(routes=(weak, strong), memories=())
        self.assertEqual("STRONG", result.selected_route_id)
        self.assertGreater(result.selected_score, weak.score)

    def test_reality_and_authority_remain_hard_gates(self):
        conceptual = self.route("CONCEPT", reality_state="C1", quality=1.0)
        effectful = self.route(
            "EFFECT",
            reality_state="C5",
            authority_required="A2",
            external_effect=True,
            quality=1.0,
        )
        result = CapabilitySelector().select(routes=(conceptual, effectful), memories=())
        self.assertEqual("", result.selected_route_id)
        reasons = {reason for item in result.decisions for reason in item.reasons}
        self.assertTrue(any(reason.startswith("REALITY_STATE_INSUFFICIENT") for reason in reasons))
        self.assertIn("AUTHORITY_CEILING_EXCEEDED", reasons)
        self.assertIn("EXTERNAL_EFFECT_NOT_AUTHORISED", reasons)

    def test_dynamic_current_failure_blocks_unchanged_retry(self):
        memory = FailureMemoryRecord(
            fingerprint="CURRENT_PROVIDER_FAILURE_001",
            route_id="R",
            status="OPEN",
            failure_proof_ref="run:current",
            retry_condition="require newer provider receipt",
        )
        result = CapabilitySelector().select(routes=(self.route("R"),), memories=(memory,))
        self.assertEqual("", result.selected_route_id)
        self.assertIn("R", result.blocked_routes)

    def test_closed_failure_requires_exact_recovery_proof_binding(self):
        memory = FailureMemoryRecord(
            fingerprint="RECOVERED_ROUTE_001",
            route_id="R",
            status=FailureStatus.CLOSED,
            failure_proof_ref="run:old",
            retry_condition="new provider receipt",
            recovery_proof_ref="provider:verified:2",
        )
        blocked = self.route("R")
        admitted = self.route("R", retry_evidence_refs=("provider:verified:2",))
        selector = CapabilitySelector()
        self.assertEqual("", selector.select(routes=(blocked,), memories=(memory,)).selected_route_id)
        self.assertEqual("R", selector.select(routes=(admitted,), memories=(memory,)).selected_route_id)

    def test_near_miss_and_failure_aware_snapshot_are_deterministic(self):
        near = NearMissEvent.create(
            mission_id=self.lease.mission_id,
            event_type="DEAD_ROUTE_AVOIDED",
            prevented_action="unchanged_retry",
            signal="CURRENT_PROVIDER_FAILURE_001",
            control="DYNAMIC_FAILURE_MEMORY",
            proof_refs=("run:current",),
        )
        memory = FailureMemoryRecord(
            fingerprint="CURRENT_PROVIDER_FAILURE_001",
            route_id="FAILED",
            status="OPEN",
            failure_proof_ref="run:current",
            retry_condition="new proof",
        )
        concurrency = ConcurrencyGuard().evaluate(
            lease=self.lease, current_main_sha=BASE, now=iso(self.now)
        )
        selection = CapabilitySelector().select(routes=(self.route("SAFE"),), memories=(memory,))
        first = MissionSnapshot.create(
            lease=self.lease,
            current_main_sha=BASE,
            concurrency=concurrency,
            selection=selection,
            memories=(memory,),
            near_misses=(near,),
        )
        second = MissionSnapshot.create(
            lease=self.lease,
            current_main_sha=BASE,
            concurrency=concurrency,
            selection=selection,
            memories=(memory,),
            near_misses=(near,),
        )
        self.assertEqual(first.snapshot_sha256, second.snapshot_sha256)
        self.assertIn(memory.fingerprint, first.active_failure_fingerprints)
        self.assertIn(near.event_id, first.near_miss_ids)

    def test_completion_claim_still_requires_full_proof_chain(self):
        partial = ExecutionEnvelope(
            mission_id="M",
            operation_id="O",
            authorization_ref="auth",
            execution_ref="exec",
            target_readback_ref="readback",
            expected_target_digest="x",
            observed_target_digest="x",
        )
        self.assertEqual(ProofState.READBACK_VERIFIED, partial.proof_state)
        self.assertFalse(partial.completion_claim_allowed)

    def test_contract_and_source_forbid_static_provider_failure_truth(self):
        source = inspect.getsource(arbitration_module)
        forbidden = "KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET"
        self.assertNotIn(forbidden, source)
        contract = json.loads(
            Path("federation/orchestration/mission_arbitration_contract_v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("STATIC_PROVIDER_FAILURE_ASSUMPTIONS_ARE_FORBIDDEN", contract["invariants"])
        self.assertFalse(contract["truth_boundary"]["historical_failure_is_current_without_fresh_proof"])

    def test_moving_main_still_revokes_old_write_fence(self):
        decision = ConcurrencyGuard().evaluate(
            lease=self.lease,
            current_main_sha=NEXT,
            now=iso(self.now),
            main_changed_paths=("docs/unrelated.md",),
        )
        self.assertEqual(ConcurrencyState.MAIN_DRIFT_FAST_RECONVERGE, decision.state)
        self.assertFalse(decision.write_allowed)


if __name__ == "__main__":
    unittest.main()
