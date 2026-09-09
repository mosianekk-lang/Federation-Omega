import unittest
from benchmarking.cfbe_omega.fascg_operational_witness_adapter_v1 import (
    PROVIDER_EFFECT_AUTHORIZED, STABLE_PROMOTION_AUTHORIZED, TEN_X_VERIFIED,
    adapt_operational_witness,
)
from benchmarking.cfbe_omega.fascg_production_runtime_v1 import ProductionStage

SHA='a'*40

def receipt(external=True):
    return {
        'source_head_sha':SHA,
        'status':'WITNESS_EXECUTION_HOST_AND_EXTERNAL_READBACK_VERIFIED' if external else 'WITNESS_EXECUTION_AND_HOST_READBACK_VERIFIED_EXTERNAL_READBACK_HELD',
        'execution_witness':{'kind':'EXECUTION','verified':True},
        'host_readback_witness':{'kind':'READBACK','provider':'github','verified':True,'independent':True},
        'readback_witness':({'kind':'READBACK','provider':'federation-provider-surfaces','verified':True,'independent':True} if external else None),
        'verified_surface_count':2 if external else 0,
        'provider_effect_authorized':False,
        'stable_promotion_authorized':False,
        'full_autopilot_runtime_proven':False,
    }

class OperationalWitnessAdapterTests(unittest.TestCase):
    def refs(self): return ('github-actions:witness-run','bubbles:provider-readback-artifact')
    def test_truth_flags(self):
        self.assertFalse(PROVIDER_EFFECT_AUTHORIZED); self.assertFalse(STABLE_PROMOTION_AUTHORIZED); self.assertFalse(TEN_X_VERIFIED)
    def test_external_readback_maps_only_to_provider_bound(self):
        e=adapt_operational_witness(receipt(True),expected_source_sha=SHA,proof_refs=self.refs())
        self.assertEqual(e.selected_stage,ProductionStage.PROVIDER_BOUND); self.assertTrue(e.external_provider_readback_verified)
        self.assertFalse(e.operational_verified); self.assertFalse(e.ten_x_verified)
    def test_external_readback_held_stays_hosted_shadow(self):
        e=adapt_operational_witness(receipt(False),expected_source_sha=SHA,proof_refs=self.refs())
        self.assertEqual(e.selected_stage,ProductionStage.HOSTED_SHADOW); self.assertFalse(e.external_provider_readback_verified)
    def test_source_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_SHA_MISMATCH'):
            adapt_operational_witness(receipt(),expected_source_sha='b'*40,proof_refs=self.refs())
    def test_requires_independent_proof_refs(self):
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_PROOF'):
            adapt_operational_witness(receipt(),expected_source_sha=SHA,proof_refs=('one',))
    def test_upstream_stable_promotion_cannot_be_inherited(self):
        r=receipt(); r['stable_promotion_authorized']=True
        with self.assertRaisesRegex(ValueError,'STABLE_PROMOTION_INHERITANCE'):
            adapt_operational_witness(r,expected_source_sha=SHA,proof_refs=self.refs())
    def test_unverified_host_readback_rejected(self):
        r=receipt(); r['host_readback_witness']['verified']=False
        with self.assertRaisesRegex(ValueError,'HOST_READBACK'):
            adapt_operational_witness(r,expected_source_sha=SHA,proof_refs=self.refs())
    def test_single_witness_never_operational(self):
        e=adapt_operational_witness(receipt(),expected_source_sha=SHA,proof_refs=self.refs(),owner_value_score=1.0)
        self.assertFalse(e.operational_verified); self.assertFalse(e.sustained_value_verified)

if __name__=='__main__': unittest.main()
