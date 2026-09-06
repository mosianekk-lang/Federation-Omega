from __future__ import annotations

import unittest

from federation.action_admission_gate_v1 import ActionAdmissionReceipt, ActionAdmissionState
from federation.cfbe_chat_hyperperformance_v1 import EffectClass
from federation.execution_readback_closure_v1 import (
    ClosureState,
    ExecutionAttempt,
    ExecutionReadbackClosure,
    IdempotencyLedger,
    RollbackReceipt,
    SemanticReadback,
)


def admission(effect=EffectClass.INTERNAL_WRITE, admitted=True):
    return ActionAdmissionReceipt(
        mission_id="m1", action_id="a1", unit_id="u1",
        state=ActionAdmissionState.ADMITTED if admitted else ActionAdmissionState.HELD,
        effect_class=effect, worker_id="w1", runtime_id="r1",
        authority_grant_id="g1", reasons=(), topology_receipt_digest="topo",
        receipt_digest="admit-digest",
    )


def attempt(effect=EffectClass.INTERNAL_WRITE, **kw):
    data=dict(
        attempt_id="attempt-1", action_admission_digest="admit-digest",
        mission_id="m1", action_id="a1", unit_id="u1", effect_class=effect,
        target_scope="repo:main", idempotency_key="idem-1",
        request_fingerprint="req-1", pre_state_fingerprint="pre-1",
        transport_ref="provider:transport" if effect is not EffectClass.READ_ONLY else "",
        write_ack_ref="provider:ack" if effect is not EffectClass.READ_ONLY else "",
    ); data.update(kw); return ExecutionAttempt(**data)


def readback(match=True, provider_native=True, behaviour=False, **kw):
    expected="post-1"; observed=expected if match else "wrong"
    data=dict(
        readback_id="rb-1", attempt_id="attempt-1", provider_ref="provider:readback",
        target_scope="repo:main", observed_state_fingerprint=observed,
        expected_state_fingerprint=expected, semantic_match=match, fresh=True,
        provider_native=provider_native, behaviour_ref="provider:behaviour" if behaviour else "",
    ); data.update(kw); return SemanticReadback(**data)


def rollback(**kw):
    data=dict(
        rollback_id="roll-1", attempt_id="attempt-1", rollback_ack_ref="provider:rollback-ack",
        readback_ref="provider:rollback-readback", restored_state_fingerprint="pre-1",
        expected_pre_state_fingerprint="pre-1", fresh=True, provider_native=True,
    ); data.update(kw); return RollbackReceipt(**data)


class ExecutionReadbackClosureTests(unittest.TestCase):
    def setUp(self): self.court=ExecutionReadbackClosure()

    def test_action_admitted_alone_is_not_effect_success(self):
        r=self.court.close(admission=admission(), attempt=attempt(write_ack_ref=""))
        self.assertEqual(ClosureState.ATTEMPT_STARTED,r.state); self.assertFalse(r.effect_verified)

    def test_write_ack_only_is_not_effect_verified(self):
        r=self.court.close(admission=admission(), attempt=attempt())
        self.assertEqual(ClosureState.WRITE_ACKNOWLEDGED,r.state)
        self.assertIn("WRITE_ACK_IS_NOT_EFFECT_PROOF",r.reasons)
        self.assertFalse(r.effect_verified)

    def test_provider_native_matching_readback_promotes_effect_verified(self):
        r=self.court.close(admission=admission(), attempt=attempt(), readback=readback())
        self.assertEqual(ClosureState.EFFECT_VERIFIED,r.state); self.assertTrue(r.effect_verified)

    def test_behavior_receipt_promotes_beyond_effect_verified(self):
        r=self.court.close(admission=admission(), attempt=attempt(), readback=readback(behaviour=True))
        self.assertEqual(ClosureState.BEHAVIOUR_VERIFIED,r.state); self.assertTrue(r.effect_verified)

    def test_non_provider_native_mutation_readback_fails(self):
        r=self.court.close(admission=admission(), attempt=attempt(), readback=readback(provider_native=False))
        self.assertEqual(ClosureState.READBACK_MISMATCH,r.state)
        self.assertIn("PROVIDER_NATIVE_READBACK_REQUIRED",r.reasons)

    def test_semantic_mismatch_requires_rollback_when_required(self):
        r=self.court.close(admission=admission(), attempt=attempt(), readback=readback(False), rollback_required=True)
        self.assertEqual(ClosureState.ROLLBACK_REQUIRED,r.state)
        self.assertFalse(r.effect_verified)

    def test_rollback_ack_only_is_not_rollback_verified(self):
        rb=rollback(readback_ref="",restored_state_fingerprint="",expected_pre_state_fingerprint="")
        r=self.court.close(admission=admission(), attempt=attempt(), readback=readback(False), rollback=rb, rollback_required=True)
        self.assertEqual(ClosureState.ROLLBACK_REQUIRED,r.state)
        self.assertIn("ROLLBACK_READBACK_REQUIRED",r.reasons)

    def test_matching_provider_native_rollback_readback_proves_restoration(self):
        r=self.court.close(admission=admission(), attempt=attempt(), readback=readback(False), rollback=rollback(), rollback_required=True)
        self.assertEqual(ClosureState.ROLLED_BACK_VERIFIED,r.state)
        self.assertFalse(r.effect_verified)

    def test_divergent_payload_reuse_of_idempotency_key_blocks(self):
        ledger=IdempotencyLedger({"idem-1":"old-request"})
        r=self.court.close(admission=admission(), attempt=attempt(), ledger=ledger, readback=readback())
        self.assertEqual(ClosureState.HELD,r.state)
        self.assertIn("IDEMPOTENCY_KEY_PAYLOAD_DIVERGENCE",r.reasons)

    def test_same_payload_idempotent_replay_can_be_verified(self):
        ledger=IdempotencyLedger({"idem-1":"req-1"})
        r=self.court.close(admission=admission(), attempt=attempt(), ledger=ledger, readback=readback())
        self.assertEqual(ClosureState.EFFECT_VERIFIED,r.state)

    def test_unadmitted_action_cannot_start(self):
        r=self.court.close(admission=admission(admitted=False), attempt=attempt())
        self.assertEqual(ClosureState.HELD,r.state)
        self.assertIn("ACTION_NOT_ADMITTED",r.reasons)

    def test_read_only_result_can_close_without_provider_native_mutation_semantics(self):
        a=admission(EffectClass.READ_ONLY); at=attempt(EffectClass.READ_ONLY)
        r=self.court.close(admission=a, attempt=at, readback=readback(provider_native=False))
        self.assertEqual(ClosureState.EFFECT_VERIFIED,r.state)

    def test_execution_error_is_terminal_or_rollback_required(self):
        at=attempt(execution_error_ref="provider:error")
        terminal=self.court.close(admission=admission(),attempt=at,rollback_required=False)
        recover=self.court.close(admission=admission(),attempt=at,rollback_required=True)
        self.assertEqual(ClosureState.TERMINAL_FAILED,terminal.state)
        self.assertEqual(ClosureState.ROLLBACK_REQUIRED,recover.state)

    def test_readback_must_bind_exact_attempt_and_target(self):
        rb=readback(attempt_id="other",target_scope="repo:other")
        r=self.court.close(admission=admission(),attempt=attempt(),readback=rb)
        self.assertEqual(ClosureState.READBACK_MISMATCH,r.state)
        self.assertIn("READBACK_ATTEMPT_MISMATCH",r.reasons)
        self.assertIn("READBACK_TARGET_MISMATCH",r.reasons)


if __name__=='__main__': unittest.main()
