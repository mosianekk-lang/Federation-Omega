import unittest
from benchmarking.cfbe_omega.fascg_phase2_bridge_v1 import (
    Phase2Disposition, adapt_phase2_receipt,
    PROVIDER_EFFECT_AUTHORIZED, MODEL_INFERENCE_AUTHORIZED,
    PRODUCTION_SELF_MUTATION_AUTHORIZED, TEN_X_VERIFIED,
)


def receipt(state="PH2_EMPIRICAL_ADVANTAGE_CANDIDATE", delta=0.10, protected=True, transfer=0.90, critical=1.0, trials=8, expected=8):
    return {
        "schema":"CFBE_AO_COGNITIVE_EVOLUTION_PHASE2_RECEIPT_V1",
        "state":state,
        "trial_count":trials,
        "expected_trial_count":expected,
        "independent_model_count":2,
        "independent_harness_count":2,
        "accuracy_delta":delta,
        "aocef_critical_fault_catch_rate":critical,
        "transfer_scores":{"alternate_model":transfer,"alternate_harness":transfer,"adjacent_task":transfer},
        "protected_gate_passed":protected,
        "provider_mutation_performed":False,
        "model_output_self_certification_allowed":False,
        "ten_x_proven":False,
        "receipt_sha256":"a"*64,
    }

class Phase2BridgeTests(unittest.TestCase):
    def refs(self): return ("github-actions:run-1", "vertex:receipt-artifact-1")
    def test_truth_flags(self):
        self.assertFalse(PROVIDER_EFFECT_AUTHORIZED); self.assertFalse(MODEL_INFERENCE_AUTHORIZED)
        self.assertFalse(PRODUCTION_SELF_MUTATION_AUTHORIZED); self.assertFalse(TEN_X_VERIFIED)
    def test_advantage_promotes_only_to_shadow(self):
        e=adapt_phase2_receipt(receipt(), provider_proof_refs=self.refs())
        self.assertEqual(e.disposition, Phase2Disposition.PROMOTE_SHADOW_CANDIDATE)
        self.assertEqual(e.promotion_ceiling,"HOSTED_SHADOW"); self.assertFalse(e.provider_bound); self.assertFalse(e.ten_x_verified)
    def test_no_advantage_retained_not_promoted(self):
        e=adapt_phase2_receipt(receipt(state="PH2_NO_EMPIRICAL_ADVANTAGE",delta=0.0), provider_proof_refs=self.refs())
        self.assertEqual(e.disposition, Phase2Disposition.RETAIN_NO_ADVANTAGE)
    def test_protected_regression_rejected(self):
        e=adapt_phase2_receipt(receipt(state="PH2_PROTECTED_GATE_FAILED", protected=False, transfer=.7, critical=.5), provider_proof_refs=self.refs())
        self.assertEqual(e.disposition, Phase2Disposition.REJECT_PROTECTED_GATE)
    def test_incomplete_holds(self):
        e=adapt_phase2_receipt(receipt(state="PH2_INCOMPLETE_REPLICATION",trials=7), provider_proof_refs=self.refs())
        self.assertEqual(e.disposition, Phase2Disposition.HOLD_INCOMPLETE)
    def test_requires_independent_proof_refs(self):
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_PROOF"):
            adapt_phase2_receipt(receipt(), provider_proof_refs=("only-one",))
    def test_ten_x_inheritance_forbidden(self):
        r=receipt(); r["ten_x_proven"]=True
        with self.assertRaisesRegex(ValueError,"TEN_X_INHERITANCE"):
            adapt_phase2_receipt(r, provider_proof_refs=self.refs())

if __name__ == '__main__': unittest.main()
