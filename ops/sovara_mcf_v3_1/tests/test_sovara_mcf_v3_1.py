from __future__ import annotations
import unittest
from ops.sovara_mcf_v3_1.sovara_mcf_v3_1 import *

class MCF31SmokeTests(unittest.TestCase):
    def test_route_respects_privacy(self):
        m=MissionContract('M','EVIDENCEOPS','x',('quality',),(),10)
        a=CapabilityCandidate('A','LLM',.99,.99,.1,.1,1,1,0,.1,privacy_allowed=False)
        b=CapabilityCandidate('B','LLM',.8,.9,.1,.1,1,1,0,.1)
        self.assertEqual(ConstrainedRouteSelector().select(m,[a,b],RouteWeights()).selected_capability_id,'B')
    def test_verified_claim_needs_source(self):
        self.assertTrue(EvidenceVetoEngine.validate([EvidenceClaim('C','h',ClaimState.VERIFIED,())]))
    def test_capability_is_one_use(self):
        g=CapabilityGateway(b'x'*32)
        t=g.issue(mission_id='M',operation_id='O',actor_id='A',connector='drive',action='read',target='T',provider=None,purpose='evidence',max_spend=0,max_calls=1,ttl_seconds=10,rollback_required=False,now=100)
        g.reserve(t,now=101); g.consume(t,now=101)
        with self.assertRaises(ValueError): g.verify(t,now=101)
    def test_counterfactual_fork(self):
        r=InMemoryDurableMissionRuntime(); cp=r.checkpoint('M',{'x':1}); CausalTimeTravelEngine(r).fork_counterfactual(cp.checkpoint_id,'M2',{'provider':'B'})
        self.assertEqual(r.replay('M2')[1]['type'],'SUBSTITUTION')
    def test_hard_veto_blocks_tenx(self):
        self.assertEqual(SequentialEvidenceEngine().decision(SequentialEvidenceState(100,1,3,True,20)),'HOLD_HARD_VETO')
    def test_tenx_requires_full_gate(self):
        self.assertEqual(SequentialEvidenceEngine().decision(SequentialEvidenceState(100,0,3,True,10)),'TEN_X_CLAIM_ELIGIBLE')
    def test_v4_missing_data_holds(self):
        d=CFBEEvolutionGate().evaluate(EvolutionModule('V4',10,1,1,1,1,.1,('real.metric',)),set())
        self.assertEqual(d.decision,'HOLD')
    def test_otel_has_standard_model_keys(self):
        a=otel_mission_attributes(mission_id='M',mission_class='C',stage='S',route_id='R',route_role='CHAMPION',accepted=True,evidence_coverage=1,hard_veto_count=0,owner_interventions=0,owner_intervention_seconds=0,rollback_available=True,rollback_executed=False,model_requested='req',model_resolved='res')
        self.assertEqual(a['gen_ai.request.model'],'req')
        self.assertEqual(a['gen_ai.response.model'],'res')

if __name__=='__main__': unittest.main()
