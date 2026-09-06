from __future__ import annotations

import unittest

from federation.cfbe_chat_hyperperformance_v1 import EffectClass
from federation.execution_readback_closure_v1 import ClosureState, ExecutionClosureReceipt
from federation.mission_ir import MissionIR
from federation.mission_outcome_value_court_v1 import (
    MissionOutcomeState, MissionOutcomeValueCourt, OutcomeEvidence, RequiredAction, ValueObservation,
)


def mission(*, values=("latency","owner_interrupts")):
    return MissionIR(
        mission_id="m1", objective="finish mission", domain="FEDERATION",
        outcome_contract="all required work complete and verified", source_frontier="signed-main",
        privacy_class="P1_INTERNAL", rights_state="OWNER_AUTHORIZED", effect_class="BOUNDED_EFFECT",
        authority_requirements=("AUTH",), proof_requirements=("effect_receipts","outcome_readback"),
        value_metrics=values,
    )


def closure(action_id, state=ClosureState.EFFECT_VERIFIED):
    return ExecutionClosureReceipt(
        mission_id="m1", action_id=action_id, attempt_id=f"att-{action_id}", state=state,
        effect_class=EffectClass.INTERNAL_WRITE, write_ack_ref="ack", readback_ref="rb",
        rollback_ref="", reasons=(), receipt_digest=f"digest-{action_id}-{state.value}",
    )


def outcome(match=True, fresh=True):
    return OutcomeEvidence("out-1","m1","all required work complete and verified","provider:outcome",match,fresh)


def values(ok=True):
    return (
        ValueObservation("latency","metrics:latency","1200ms",ok),
        ValueObservation("owner_interrupts","metrics:interrupts","0",ok),
    )


class MissionOutcomeValueCourtTests(unittest.TestCase):
    def setUp(self): self.court=MissionOutcomeValueCourt(); self.m=mission()

    def decide(self, closures, **kw):
        return self.court.decide(
            mission=self.m,
            required_actions=(RequiredAction("a1"),RequiredAction("a2",require_behaviour=True)),
            closures=closures, outcome_evidence=kw.get("outcome_evidence",outcome()),
            proof_evidence=kw.get("proof_evidence",{"effect_receipts":"p1","outcome_readback":"p2"}),
            value_observations=kw.get("value_observations",values()),
        )

    def test_partial_actions_cannot_complete_mission(self):
        r=self.decide((closure("a1"),))
        self.assertEqual(MissionOutcomeState.HELD,r.state); self.assertIn("a2",r.missing_actions)

    def test_effect_only_cannot_satisfy_behaviour_required_action(self):
        r=self.decide((closure("a1"),closure("a2")))
        self.assertEqual(MissionOutcomeState.HELD,r.state)
        self.assertTrue(any("BEHAVIOUR_PROOF_REQUIRED" in x for x in r.reasons))

    def test_rollback_only_recovery_is_not_success(self):
        r=self.decide((closure("a1"),closure("a2",ClosureState.ROLLED_BACK_VERIFIED)))
        self.assertEqual(MissionOutcomeState.HELD,r.state)
        self.assertTrue(any("ROLLBACK_RECOVERY_IS_NOT_MISSION_SUCCESS" in x for x in r.reasons))

    def test_missing_required_proof_blocks(self):
        r=self.decide((closure("a1"),closure("a2",ClosureState.BEHAVIOUR_VERIFIED)),proof_evidence={"effect_receipts":"p1"})
        self.assertEqual(MissionOutcomeState.HELD,r.state); self.assertIn("outcome_readback",r.missing_proofs)

    def test_outcome_semantic_mismatch_blocks(self):
        r=self.decide((closure("a1"),closure("a2",ClosureState.BEHAVIOUR_VERIFIED)),outcome_evidence=outcome(False))
        self.assertEqual(MissionOutcomeState.HELD,r.state); self.assertIn("OUTCOME_CONTRACT_NOT_SATISFIED",r.reasons)

    def test_stale_outcome_evidence_blocks(self):
        r=self.decide((closure("a1"),closure("a2",ClosureState.BEHAVIOUR_VERIFIED)),outcome_evidence=outcome(True,False))
        self.assertEqual(MissionOutcomeState.HELD,r.state); self.assertIn("OUTCOME_EVIDENCE_NOT_FRESH",r.reasons)

    def test_missing_value_observation_blocks_value_claim(self):
        r=self.decide((closure("a1"),closure("a2",ClosureState.BEHAVIOUR_VERIFIED)),value_observations=(ValueObservation("latency","m","1200",True),))
        self.assertEqual(MissionOutcomeState.HELD,r.state); self.assertIn("owner_interrupts",r.missing_value_metrics)

    def test_failed_value_target_blocks(self):
        r=self.decide((closure("a1"),closure("a2",ClosureState.BEHAVIOUR_VERIFIED)),value_observations=values(False))
        self.assertEqual(MissionOutcomeState.HELD,r.state)
        self.assertTrue(any(x.startswith("VALUE_TARGET_NOT_MET") for x in r.reasons))

    def test_complete_verified_actions_outcome_proofs_and_values_promote_value_observed(self):
        r=self.decide((closure("a1"),closure("a2",ClosureState.BEHAVIOUR_VERIFIED)))
        self.assertEqual(MissionOutcomeState.VALUE_OBSERVED,r.state); self.assertTrue(r.complete); self.assertTrue(r.value_observed)

    def test_no_value_metrics_never_claims_value_observed(self):
        m=mission(values=())
        r=self.court.decide(
            mission=m, required_actions=(RequiredAction("a1",require_behaviour=True),),
            closures=(closure("a1",ClosureState.BEHAVIOUR_VERIFIED),), outcome_evidence=OutcomeEvidence("o","m1",m.outcome_contract,"r",True),
            proof_evidence={"effect_receipts":"p","outcome_readback":"p2"}, value_observations=(),
        )
        self.assertEqual(MissionOutcomeState.BEHAVIOUR_VERIFIED,r.state); self.assertFalse(r.value_observed)


if __name__=='__main__': unittest.main()
