from __future__ import annotations

import unittest
from benchmarking.cfbe_omega import omega_harvest_max_v2 as m

D='a'*64

def ev(i, family=m.SourceFamily.OFFICIAL_DOC, group=None, neg=False):
    return m.SourceEvidence(f's{i}', family, f'https://e/{i}', ('%064x' % i)[-64:], '2026-09-04', .9, group or f'g{i}', 'Apache-2.0', True, neg)

class T(unittest.TestCase):
    def test_upgrade_deepens_20_without_overlap(self):
        r=m.upgrade_receipt(); self.assertEqual(42,r.total_deep_control_count); self.assertEqual(20,r.newly_deepened_gene_count)
    def test_source_plan_is_public_and_multi_family(self):
        p=m.default_source_universe('M','parser'); self.assertGreaterEqual(len(p.required_families),6); self.assertTrue(p.delta_first)
    def test_cursor_delta_first(self):
        e=ev(1); c=m.HarvestCursor(); self.assertTrue(c.changed(e)); c2=c.advance([e]); self.assertFalse(c2.changed(e))
    def test_slice_prioritizes_high_signal_not_size(self):
        a=m.RepositoryFileSignal('huge.gen',10_000_000)
        b=m.RepositoryFileSignal('core.py',5000,symbol_hits=2,change_count=3,failure_hits=1)
        self.assertEqual('core.py',m.plan_repository_slice([a,b],limit=1)[0].path)
    def test_python_structural_fingerprint_stable(self):
        s='''async def f(x):\n    try:\n        for i in x:\n            if i: await g(i)\n    except Exception: raise\n'''
        a=m.python_structural_fingerprint(s); b=m.python_structural_fingerprint(s)
        self.assertEqual(a.digest_sha256,b.digest_sha256); self.assertGreater(a.async_count,0)
    def test_structural_similarity(self):
        a=m.python_structural_fingerprint('def f(x):\n return g(x)')
        b=m.python_structural_fingerprint('def z(y):\n return g(y)')
        c=m.python_structural_fingerprint('x=1\nfor i in range(10): x+=i')
        self.assertGreater(m.structural_similarity(a,b),m.structural_similarity(a,c))
    def mech(self,id,prims=('a','b'),inv=('i',),out=('o',),dep=('d',)):
        return m.CapabilityMechanism(id,'fast parser',tuple(prims),tuple(inv),tuple(out),tuple(dep),('f',))
    def test_equivalence_and_superset(self):
        a=self.mech('a'); b=self.mech('b',('a','b','c'),('i','j'),('o','p'),('d',))
        self.assertGreater(m.capability_equivalence(a,b),.5); self.assertTrue(m.capability_superset(b,a).is_superset)
    def test_freshness_decay(self):
        self.assertGreater(m.frontier_freshness_score(m.FrontierFreshness(1,30)),m.frontier_freshness_score(m.FrontierFreshness(60,30)))
    def test_standardization_momentum(self):
        low=m.standardization_momentum(independent_implementations=1,vendors=1,standards_releases=1,months_observed=24)
        high=m.standardization_momentum(independent_implementations=8,vendors=6,standards_releases=4,months_observed=12)
        self.assertGreater(high,low)
    def test_negative_design_requires_proof(self):
        with self.assertRaises(ValueError): m.harvest_negative_design([m.NegativeFinding('x','f','c','bad','good',())])
        rules=m.harvest_negative_design([m.NegativeFinding('x','f','c','bad','good',('p',))]); self.assertIn('DO_NOT_REPEAT',rules[0])
    def test_architecture_diff(self):
        a=m.ArchitectureGraph(frozenset({'a','b'}),frozenset({('a','b','calls')}))
        b=m.ArchitectureGraph(frozenset({'a','b','c'}),frozenset({('a','b','calls'),('b','c','queues')}))
        r=m.architecture_diff(a,b); self.assertEqual(('c',),r.added_nodes)
    def test_hidden_cost_penalizes_manual_and_paid(self):
        self.assertGreater(m.hidden_cost_index(m.CostSurface(paid_services=1,manual_steps=2)),m.hidden_cost_index(m.CostSurface()))
    def test_license_triage(self):
        self.assertFalse(m.classify_license_admissibility(license_spdx='GPL-3.0-only',public_spec_available=True,proprietary_source=False).code_copy_allowed_by_this_court)
        self.assertTrue(m.classify_license_admissibility(license_spdx='Apache-2.0',public_spec_available=True,proprietary_source=False).clean_room_allowed)
        self.assertTrue(m.classify_license_admissibility(license_spdx='',public_spec_available=True,proprietary_source=False).requires_human_license_review)
    def test_triangulation_requires_independence(self):
        obs=[m.ClaimObservation('c','support',1,ev(1,m.SourceFamily.OFFICIAL_DOC,'vendor')),
             m.ClaimObservation('c','support',1,ev(2,m.SourceFamily.SOURCE_CODE,'repo'))]
        r=m.triangulate_claim(obs); self.assertTrue(r.sufficient_for_gene)
    def test_experiment_lock_is_deterministic(self):
        kw=dict(experiment_id='e',task_id='t',dataset_sha256=D,implementation_sha256=D,environment_sha256=D,
                hardware_class='cpu',cache_state='cold',authority_class='A1',cost_context='0',metrics=['latency'],failure_conditions=['quality'])
        self.assertEqual(m.preregister_experiment(**kw).fingerprint_sha256,m.preregister_experiment(**kw).fingerprint_sha256)
    def test_contamination_court(self):
        a=m.BenchmarkContext('t',D,'cpu','cold','A1','0','inc','v1'); b=m.BenchmarkContext('t',D,'gpu','cold','A1','0','chal','v1')
        r=m.benchmark_contamination_court(a,b); self.assertFalse(r.comparable); self.assertIn('HARDWARE_MISMATCH',r.contamination_flags)
    def test_bayes_and_sequential(self):
        self.assertGreater(m.bayesian_capability_belief(successes=8,failures=1).mean,.7)
        self.assertEqual('CANDIDATE_ACCEPT',m.sequential_evidence_court(successes=9,failures=0,min_observations=5).decision)
    def test_counterfactual(self):
        r=m.counterfactual_challenger(metric='quality',incumbent_values=[1,2],challenger_values=[2,4]); self.assertEqual(1.5,r.observed_delta)
    def test_calibration(self):
        r=m.confidence_calibration_court([.9,.8,.1,.2],[1,1,0,0]); self.assertTrue(r.sufficiently_calibrated)
    def test_ucb_allocates_untried_first(self):
        arms=[m.ChallengerArm('b',0,0,0),m.ChallengerArm('a',1,1,1)]; self.assertEqual('b',m.allocate_challenger(arms,total_trials=1))
    def test_pareto(self):
        a=m.FitnessVector('a',1,1,1,1,1,1); b=m.FitnessVector('b',.8,.8,2,2,2,.8)
        self.assertEqual(('a',),m.pareto_frontier([a,b]))
    def test_distribution_shift(self):
        self.assertEqual(0,m.distribution_shift({'a':1,'b':1},{'a':1,'b':1}))
        self.assertGreater(m.distribution_shift({'a':1,'b':0},{'a':0,'b':1}),.9)
    def test_eval_pin(self):
        r=m.pin_evaluation(dataset_sha256=D,evaluator_version='1',rubric_sha256=D,oracle_sha256=D,environment_sha256=D); self.assertEqual(64,len(r.fingerprint_sha256))
    def test_probe_batch_obeys_budget(self):
        p=[m.ProbeCandidate('a',1,1,1,2,0,0),m.ProbeCandidate('b',.8,1,1,1,0,0),m.ProbeCandidate('c',.2,1,1,1,0,0)]
        ids=m.select_probe_batch(p,max_cost=2,max_count=2); self.assertLessEqual(len(ids),2); self.assertNotIn('a',ids) if len(ids)==2 else None
    def test_completion_blocks_shallow_harvest(self):
        r=m.harvest_completion_court(m.HarvestCompletionInput('c',m.HarvestDepth.H4_PERFORMANCE,(),(),False,False,False,False)); self.assertEqual('HARVEST_OPEN',r.state); self.assertIn('H7_GENE_DEPTH_REQUIRED',r.blockers)
    def test_completion_gene_formed(self):
        stages=tuple(m.ArchaeologyStageReceipt(s,True,(f'p:{s}',)) for s in m.ARCHAEOLOGY_STAGES[:10])
        evidence=(ev(1,m.SourceFamily.OFFICIAL_DOC,'g1'),ev(2,m.SourceFamily.SOURCE_CODE,'g2'),ev(3,m.SourceFamily.TEST,'g3'),ev(4,m.SourceFamily.BENCHMARK,'g4'))
        r=m.harvest_completion_court(m.HarvestCompletionInput('c',m.HarvestDepth.H7_GENE,stages,evidence,True,True,True,True)); self.assertEqual('GENE_FORMED',r.state)
    def test_h9_requires_empirical(self):
        stages=tuple(m.ArchaeologyStageReceipt(s,True,(f'p:{s}',)) for s in m.ARCHAEOLOGY_STAGES)
        evidence=(ev(1,m.SourceFamily.OFFICIAL_DOC,'g1'),ev(2,m.SourceFamily.SOURCE_CODE,'g2'),ev(3,m.SourceFamily.TEST,'g3'),ev(4,m.SourceFamily.BENCHMARK,'g4'))
        r=m.harvest_completion_court(m.HarvestCompletionInput('c',m.HarvestDepth.H9_EMPIRICAL,stages,evidence,True,True,True,True,False,False)); self.assertIn('EMPIRICAL_ADVANTAGE_REQUIRED_FOR_H9',r.blockers)

    def test_evolution_history_mines_perf_regression_and_hotspots(self):
        changes=[
            m.EvolutionChange('c1','perf: batch parser for lower latency',('core.py','bench.py'),10,2,('pr:1',)),
            m.EvolutionChange('c2','revert regression in async scheduler',('core.py',),2,8,('pr:2',)),
            m.EvolutionChange('c3','security: taint test hardening',('security.py','test_security.py'),5,1,('pr:3',)),
        ]
        r=m.mine_evolution_history(changes)
        self.assertIn('c1',r.performance_changes); self.assertIn('c2',r.regression_or_revert_changes)
        self.assertEqual('core.py',r.hotspot_paths[0])

if __name__=='__main__': unittest.main()
