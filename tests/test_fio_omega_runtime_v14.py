import hashlib
import unittest

from federation.fio_omega_runtime import *


def H(x): return 'sha256:'+hashlib.sha256(x.encode()).hexdigest()


class FIONativeRuntimeTests(unittest.TestCase):
    def binding(self): return MissionBinding('M1','OWNER',H('hmc'),H('mir'),H('obj'))
    def manifests(self):
        return (
            ProcessorManifest('astra','OPENAI','Astra','snap-a',('REASON','CREATIVE_GENERATE','REFERENCE_CONTROL','VIDEO_GENERATE','TIMELINE')),
            ProcessorManifest('gemini','GOOGLE','Gemini','snap-g',('REASON','CREATIVE_GENERATE','REFERENCE_CONTROL','THREE_D_GENERATE','VIDEO_GENERATE','TIMELINE','PRESENTATION_BUILD','TEXT_LAYOUT')),
            ProcessorManifest('claude','ANTHROPIC','Claude','snap-c',('REASON','UI_LAYOUT','TEXT_LAYOUT','WEB_BUILD','DOCUMENT_BUILD')),
            ProcessorManifest('local','SOVEREIGN_LOCAL','Local','snap-l',('REASON','CREATIVE_GENERATE','REFERENCE_CONTROL','THREE_D_GENERATE','UI_LAYOUT','TEXT_LAYOUT','WEB_BUILD','DOCUMENT_BUILD','PRESENTATION_BUILD'),True),
        )
    def attest(self, down=()):
        return tuple(ProcessorAttestation(m.processor_id,m.processor_id not in down,True,True,True,.92,100,10,(f'proof:{m.processor_id}',),'now') for m in self.manifests())
    def portfolio(self): return ProcessorPortfolio(self.manifests())
    def state(self): return CreativeStateRef('M1','graph','v7','vt:graph',H('taste'),'RIGHTS_OK','PRIVATE',(H('ref'),))
    def envelope(self): return FreedomEnvelope('E1','M1',(Medium.IMAGE,Medium.THREE_D,Medium.VIDEO,Medium.UI,Medium.WEB,Medium.PRESENTATION,Medium.DOCUMENT),.7,.8,.85,.8,2,False,12)
    def root(self):
        s=self.state(); e=self.envelope()
        return DesignIR('ROOT','M1',s.state_digest,e.envelope_digest,Medium.IMAGE,'root',('concept:1',),{'palette':'black-gold'},{'character':'hero'},{},{},('CREATIVE_GENERATE','REFERENCE_CONTROL'))
    def stages(self):
        return (
            StageSpec('image',Medium.IMAGE,'hero frame'),
            StageSpec('3d',Medium.THREE_D,'3d',('image',)),
            StageSpec('video',Medium.VIDEO,'motion',('3d',)),
            StageSpec('ui',Medium.UI,'ui',('image',)),
            StageSpec('web',Medium.WEB,'web',('ui',)),
            StageSpec('deck',Medium.PRESENTATION,'deck',('image',)),
            StageSpec('doc',Medium.DOCUMENT,'doc',('deck',)),
        )

    def test_binding_drift_fails_closed(self):
        rt=SovereignIntelligenceRuntime(self.binding(),self.portfolio())
        with self.assertRaisesRegex(ValueError,'HMC_FINGERPRINT_DRIFT'): rt.assert_binding(H('wrong'),H('mir'))
    def test_external_effect_delegated(self):
        t=IntelligenceTask('t','M1','effect',('REASON',),external_effect=True)
        self.assertEqual('DELEGATE_TO_SOVARA_MODISA_FDOF',self.portfolio().route(t,self.attest()).state)
    def test_flagship_outage_retains_route(self):
        t=IntelligenceTask('t','M1','reason',('REASON',),Risk.HIGH,.8,2)
        p=self.portfolio().route(t,self.attest(('astra',)))
        self.assertEqual('INTELLIGENCE_ROUTE_CANDIDATE',p.state); self.assertNotEqual('OPENAI',p.selected_provider)
    def test_sensitive_prefers_local_only(self):
        t=IntelligenceTask('t','M1','private',('REASON',),Risk.HIGH,.8,1,True)
        p=self.portfolio().route(t,self.attest()); self.assertEqual('SOVEREIGN_LOCAL',p.selected_provider)
    def test_attestation_requires_proof(self):
        with self.assertRaisesRegex(ValueError,'PROCESSOR_ATTESTATION_PROOF_REQUIRED'): ProcessorAttestation('x',True,True,True,True,.9).validate()
    def test_gene_cannot_expand_authority(self):
        with self.assertRaisesRegex(ValueError,'AUTHORITY_EXPANSION'): CapabilityGene('g','m',('src',),True,'FIO',('t',),True,True).validate()
    def test_logical_universe_can_exceed_render_budget(self):
        u=CreativeUniverse(self.root()); branches=[u.branch(str(i)) for i in range(10000)]; self.assertEqual(10000,len(branches)); self.assertEqual(12,self.envelope().materialization_budget)
    def test_golden_path_preserves_state(self):
        path,ds=GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='GCP',stages=self.stages())
        self.assertTrue(all(d.design.creative_state_digest==path.state_digest for d in ds))
    def test_golden_path_preserves_taste(self):
        path,ds=GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='GCP',stages=self.stages())
        self.assertTrue(all(d.design.identity_controls['taste_fingerprint']==path.taste_fingerprint for d in ds))
    def test_golden_path_dependency_order_enforced(self):
        bad=(StageSpec('a',Medium.IMAGE,'a',('b',)),StageSpec('b',Medium.VIDEO,'b'))
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_NOT_PRIOR'): GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='x',stages=bad)
    def test_materialization_budget_does_not_bound_logic(self):
        path,_=GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='GCP',stages=self.stages())
        p=MaterializationBudget().allocate(path,12); self.assertFalse(p.logical_branch_space_bounded); self.assertEqual(12,p.total_variants)
    def test_continuity_detects_taste_drift(self):
        path,ds=GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='GCP',stages=self.stages())
        d=ds[0]; o=ContinuityObservation(d.stage.stage_id,d.design.design_digest,path.state_digest,path.envelope_digest,path.graph_version,H('wrong'),path.references,.95,.95,.95,.95,('proof',))
        self.assertIn('TASTE_DRIFT',ContinuityCourt().evaluate(path,d,o,self.envelope()).reasons)
    def test_continuity_accepts_preserved_stage(self):
        path,ds=GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='GCP',stages=self.stages())
        d=ds[0]; o=ContinuityObservation(d.stage.stage_id,d.design.design_digest,path.state_digest,path.envelope_digest,path.graph_version,path.taste_fingerprint,path.references,.95,.95,.95,.95,('proof',))
        self.assertTrue(ContinuityCourt().evaluate(path,d,o,self.envelope()).promotable)
    def test_quality_requires_independent_judge(self):
        o=CreativeOutput('image','OPENAI',H('art'),.95,.95,.95,.95,.95,.95,('proof',),'OPENAI',('judge',))
        self.assertIn('SELF_JUDGING_PROVIDER_NOT_SUFFICIENT',CreativeQualityCourt().evaluate(o,self.envelope()).reasons)
    def test_quality_accepts_independent_judge(self):
        o=CreativeOutput('image','OPENAI',H('art'),.95,.95,.95,.95,.95,.95,('proof',),'GOOGLE',('judge',))
        self.assertTrue(CreativeQualityCourt().evaluate(o,self.envelope()).promotable)
    def test_stage_failover_preserves_state(self):
        t=IntelligenceTask('v','M1','video',('VIDEO_GENERATE','TIMELINE'),Risk.HIGH,.8,2)
        route=self.portfolio().route(t,self.attest()); rec=StageFailover().recover('video',route,failed_processor_id=route.selected_processor_id)
        self.assertEqual('STAGE_FAILOVER_READY',rec.state); self.assertTrue(rec.preserve_design_ir and rec.preserve_graph_version and rec.preserve_taste)
    def test_completion_requires_all_stages(self):
        path,_=GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='GCP',stages=self.stages())
        q={s.stage_id:CourtDecision('PASS',s.stage_id,True,('ok',)) for s in path.stages}; c=dict(q)
        self.assertTrue(GoldenPathCompletionCourt().evaluate(path,q,c).complete)
    def test_completion_holds_missing_proof(self):
        path,_=GoldenPathCompiler().compile(self.state(),self.envelope(),self.root(),path_id='GCP',stages=self.stages())
        q={s.stage_id:CourtDecision('PASS',s.stage_id,True,('ok',)) for s in path.stages[:-1]}; c={s.stage_id:CourtDecision('PASS',s.stage_id,True,('ok',)) for s in path.stages}
        self.assertFalse(GoldenPathCompletionCourt().evaluate(path,q,c).complete)
    def test_runtime_cannot_self_complete_without_port(self):
        rt=SovereignIntelligenceRuntime(self.binding(),self.portfolio())
        self.assertEqual('COMPLETION_PORT_REQUIRED',rt.before_final({},'candidate')['state'])

if __name__=='__main__': unittest.main()
