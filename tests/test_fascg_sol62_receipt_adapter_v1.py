import unittest
from benchmarking.cfbe_omega.fascg_sol62_receipt_adapter_v1 import (
    adapt_sol62_receipts, PROVIDER_EFFECT_AUTHORIZED, AUTHORITY_MINTING_AUTHORIZED,
    PRODUCTION_PROMOTION_AUTHORIZED, TEN_X_VERIFIED,
)


def reference_receipt():
    return {
        "programme":"SOL-6.2-TRANSACTIONAL-SELF-VERIFYING-RUNTIME",
        "version":"6.2",
        "status":"SOL_6_2_REFERENCE_RUNTIME_VERIFIED",
        "sha256":"a"*64,
        "gates":{
            "adversarial_unit_court":True,
            "state_transition_planning":True,
            "transactional_effect_preparation":True,
            "fenced_dispatch":True,
            "provider_readback":True,
            "proof_gated_commit":True,
            "observed_reality_closure":True,
            "verified_reality_execution_freeze":True,
            "event_chain_integrity":True,
            "restart_integrity":True,
            "restart_reality_closure":True,
        },
        "truth_boundary":{
            "source_runtime_implemented":True,
            "deterministic_reference_proof":True,
            "transactional_single_shared_filesystem":True,
            "provider_effect_proof_binding_enforced_in_reference_runtime":True,
            "multi_region_consensus":False,
            "provider_live_production_cutover":False,
            "provider_identity_inherited":False,
            "continuous_background_execution":False,
            "market_superiority_claim":False,
        }
    }


def hosted_receipt():
    return {"state":"HOSTED_SEPARATE_RUN_STATE_CONTINUITY_VERIFIED","receipt_sha256":"b"*64,"provider_effect_authorized":False}


class Sol62AdapterTests(unittest.TestCase):
    def refs(self): return ("github:sol-reference", "proofos:sol62-court")
    def test_truth_flags(self):
        self.assertFalse(PROVIDER_EFFECT_AUTHORIZED)
        self.assertFalse(AUTHORITY_MINTING_AUTHORIZED)
        self.assertFalse(PRODUCTION_PROMOTION_AUTHORIZED)
        self.assertFalse(TEN_X_VERIFIED)
    def test_reference_loads_as_control_evidence_only(self):
        e=adapt_sol62_receipts(reference_receipt(), proof_refs=self.refs())
        self.assertTrue(e.reference_verified); self.assertTrue(e.transactional_truth_spine_usable)
        self.assertFalse(e.hosted_continuity_verified); self.assertFalse(e.provider_bound)
        self.assertFalse(e.operational_verified); self.assertFalse(e.ten_x_verified)
    def test_hosted_continuity_can_be_consumed_without_provider_inheritance(self):
        e=adapt_sol62_receipts(reference_receipt(), proof_refs=self.refs(), hosted_continuity_receipt=hosted_receipt())
        self.assertTrue(e.hosted_continuity_verified); self.assertFalse(e.provider_bound)
        self.assertEqual(e.fascg_promotion_ceiling,"HOSTED_SHADOW")
    def test_requires_two_proof_refs(self):
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_PROOF"):
            adapt_sol62_receipts(reference_receipt(), proof_refs=("one",))
    def test_rejects_failed_reference_gate(self):
        r=reference_receipt(); r["gates"]["fenced_dispatch"]=False
        with self.assertRaisesRegex(ValueError,"GATES_INCOMPLETE"):
            adapt_sol62_receipts(r, proof_refs=self.refs())
    def test_rejects_provider_maturity_overclaim(self):
        r=reference_receipt(); r["truth_boundary"]["provider_live_production_cutover"]=True
        with self.assertRaisesRegex(ValueError,"MATURITY_OVERCLAIM"):
            adapt_sol62_receipts(r, proof_refs=self.refs())
    def test_rejects_unverified_hosted_continuity(self):
        h=hosted_receipt(); h["state"]="FAILED"
        with self.assertRaisesRegex(ValueError,"HOSTED_CONTINUITY_NOT_VERIFIED"):
            adapt_sol62_receipts(reference_receipt(), proof_refs=self.refs(), hosted_continuity_receipt=h)
    def test_rejects_hosted_effect_inheritance(self):
        h=hosted_receipt(); h["provider_effect_authorized"]=True
        with self.assertRaisesRegex(ValueError,"EFFECT_INHERITANCE"):
            adapt_sol62_receipts(reference_receipt(), proof_refs=self.refs(), hosted_continuity_receipt=h)

if __name__ == '__main__': unittest.main()
