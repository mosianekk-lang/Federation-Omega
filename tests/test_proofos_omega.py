from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from proofos_omega import *

ROOT=Path(__file__).resolve().parents[1]; POLICY_PATH=ROOT/'governance/proofos_omega_policy_v1.json'; BASE='1'*40; HEAD='2'*40

def compile_for(paths):
    p=ProofPolicy.from_path(POLICY_PATH); i=ImpactCompiler(p).assess(paths); return p,i,ProofSelector(p).compile_manifest(base_sha=BASE,head_sha=HEAD,impact=i)

def selected(m): return {x.test_id for x in m.selected_tests}

class PolicyTests(unittest.TestCase):
    def test_policy_a1_no_effect(self):
        p=ProofPolicy.from_path(POLICY_PATH); self.assertEqual('FEDERATION-PROOFOS-OMEGA-V1',p.schema); self.assertEqual(0,p.sentinel_percent); self.assertIn(p.fallback_test_id,p.tests)
    def test_sovara_scoped_not_phoenix_export(self):
        _,i,m=compile_for(['ops/sovara_provider_execution_fabric.py']); s=selected(m); self.assertIn('SOVARA',i.impacted_subsystems); self.assertTrue({'sovara_provider_execution','sovara_provider_recovery'}<=s); self.assertNotIn('phoenix_exports',s); self.assertNotIn('full_federation_fallback',s)
    def test_runtime_bootstrap_selects_export(self):
        _,i,m=compile_for(['runtime_bootstrap/sitecustomize.py']); self.assertIn('RELEASE_EXPORT',i.direct_subsystems); self.assertIn('phoenix_exports',selected(m))
    def test_unknown_prod_falls_back_full(self):
        _,i,m=compile_for(['future_plane/new_runtime.py']); self.assertTrue(i.unmapped_production_paths); self.assertIn('full_federation_fallback',selected(m)); self.assertTrue(m.selector_state['fallback_full_suite_activated'])
    def test_unique_package_root_infers_realityguard_without_fallback(self):
        paths=['realityguard_v0.4.0/BUILD_CONTRACT.json','realityguard_v0.4.0/examples/gmail_attachment_failure_execution_guard.json','realityguard_v0.4.0/examples/gmail_attachment_repaired_execution_guard.json','realityguard_v0.4.0/pyproject.toml']; _,i,m=compile_for(paths); self.assertIn('REALITYGUARD',i.direct_subsystems); self.assertFalse(i.unmapped_production_paths); self.assertIn('deployment_safety_spine',selected(m)); self.assertNotIn('full_federation_fallback',selected(m)); self.assertFalse(m.selector_state['fallback_full_suite_activated'])
    def test_ambiguous_package_root_still_falls_back(self):
        _,i,m=compile_for(['governance/unmapped_policy.json']); self.assertEqual(('governance/unmapped_policy.json',),i.unmapped_production_paths); self.assertIn('full_federation_fallback',selected(m)); self.assertTrue(m.selector_state['fallback_full_suite_activated'])
    def test_package_root_inference_is_deterministic(self):
        paths=['realityguard_v0.4.0/pyproject.toml','realityguard_v0.4.0/BUILD_CONTRACT.json']; a=compile_for(paths)[1]; b=compile_for(list(reversed(paths)))[1]; self.assertEqual(a.to_dict(),b.to_dict())
    def test_docs_no_full(self):
        _,i,m=compile_for(['docs/x.md']); self.assertEqual(RiskTier.R0_DOCS,i.risk); self.assertNotIn('full_federation_fallback',selected(m))
    def test_airlock_r3_scoped(self):
        _,i,m=compile_for(['.github/workflows/github-airlock.yml']); s=selected(m); self.assertGreaterEqual(i.risk,RiskTier.R3_SECURITY_ABI); self.assertTrue({'airlock_kernel','stale_base_guard','proofos_self'}<=s); self.assertNotIn('phoenix_exports',s)
    def test_proofos_r4(self):
        _,i,m=compile_for(['proofos_omega/core.py']); self.assertEqual(RiskTier.R4_CORE,i.risk); self.assertTrue({'proofos_self','compileall_shared'}<=selected(m))
    def test_evidenceops_foundry_guard_preserved(self): self.assertIn('evidenceops_algorithm_foundry',selected(compile_for(['evidenceops/innovation_engine/algorithms.py'])[2]))
    def test_architron_semantic_guard_preserved(self):
        _,i,m=compile_for(['ops/architron_semantic_contract.py']); self.assertGreaterEqual(i.risk,RiskTier.R3_SECURITY_ABI); self.assertIn('ARCHITRON',i.impacted_subsystems); self.assertIn('architron_semantic_contract',selected(m)); self.assertNotIn('phoenix_exports',selected(m))
    def test_frontier_os_guard_preserved(self):
        _,i,m=compile_for(['frontier_convergence/os_core.py']); self.assertIn('FRONTIER_CONVERGENCE',i.impacted_subsystems); self.assertTrue({'frontier_os','frontier_core'}<=selected(m))
    def test_federation_core_fans_out(self):
        _,i,m=compile_for(['governance/federation_surface_awareness_v1.json']); self.assertTrue({'FEDERATION_CORE','SOVARA','JARVIS','CFBE'}<=set(i.impacted_subsystems)); self.assertTrue({'federation_autonomous_controller','sovara_provider_execution','cfbe_frontier_binding'}<=selected(m))
    def test_manifest_deterministic_verified(self):
        a=compile_for(['ops/sovara_provider_execution_fabric.py'])[2]; b=compile_for(['ops/sovara_provider_execution_fabric.py'])[2]; self.assertEqual(a.to_dict(),b.to_dict()); self.assertTrue(a.verify())
    def test_omission_proof_total(self):
        p,_,m=compile_for(['docs/x.md']); a=selected(m); o={x.test_id for x in m.omitted_tests}; self.assertFalse(a&o); self.assertEqual(set(p.tests),a|o); self.assertTrue(m.selector_state['omission_proof_complete'])
    def test_history_adds_never_removes(self):
        _,_,m=compile_for(['tools/github_airlock.py']); r={x.test_id:set(x.reasons) for x in m.selected_tests}; self.assertIn('P0_ALWAYS',r['airlock_kernel']); self.assertTrue(any(x.startswith('HISTORICAL_ASSOCIATION:') for x in r['airlock_kernel']))
    def test_prediction_is_add_only(self):
        m=compile_for(['docs/x.md'])[2]; self.assertTrue(m.selector_state['predictive_selector_may_only_add_tests']); self.assertTrue(m.selector_state['deterministic_selector_floor_may_not_be_removed_by_prediction'])
    def test_latest_guard_ids_registered(self):
        p=ProofPolicy.from_path(POLICY_PATH); self.assertTrue({'evidenceops_algorithm_foundry','architron_semantic_contract','sovara_provider_recovery','frontier_os'}<=set(p.tests))
    def test_malicious_target_rejected(self):
        r=json.loads(POLICY_PATH.read_text()); r['tests'][0]['target']='x.py; rm -rf /'; self.assertRaises(PolicyError,ProofPolicy,r)
    def test_shell_kind_rejected(self):
        r=json.loads(POLICY_PATH.read_text()); r['tests'][0]['kind']='shell'; self.assertRaises(PolicyError,ProofPolicy,r)
    def test_cycle_rejected(self):
        r=json.loads(POLICY_PATH.read_text()); r['subsystem_rules']=[{'subsystem':'A','patterns':['a/**'],'depends_on':['B']},{'subsystem':'B','patterns':['b/**'],'depends_on':['A']}]; self.assertRaises(PolicyError,ProofPolicy,r)
    def test_authority_expansion_rejected(self):
        r=json.loads(POLICY_PATH.read_text()); r['authority_ceiling']='A3_EXTERNAL_WRITE'; self.assertRaises(PolicyError,ProofPolicy,r)

class CacheRunnerTests(unittest.TestCase):
    def small(self,optional=False):
        return ProofPolicy({'schema':'FEDERATION-PROOFOS-OMEGA-V1','version':'1.0.0','authority_ceiling':'A1_INTERNAL','external_effect_default':False,'selector':{'fallback_full_suite_test_id':'full','sentinel_percent':0,'production_extensions':['.py'],'nonproduction_prefixes':['tests','docs']},'risk_rules':[],'subsystem_rules':[{'subsystem':'APP','patterns':['app/**'],'depends_on':[]}],'historical_associations':[],'tests':[{'id':'focused','kind':'unittest_glob','target':'test_focus.py','patterns':['app/**'],'subsystems':['APP'],'always':True,'optional_if_missing':optional,'failure_class':'SUBSYSTEM_REGRESSION','block_scope':'SUBSYSTEM','timeout_seconds':30},{'id':'full','kind':'unittest_glob','target':'test_*.py','patterns':[],'subsystems':[],'min_risk':'R5_RELEASE','sentinel_eligible':False,'failure_class':'GENERAL_REGRESSION','block_scope':'GLOBAL','timeout_seconds':30}]})
    def setup(self,root,with_test=True):
        (root/'app').mkdir(); (root/'tests').mkdir(); (root/'app/x.py').write_text('VALUE=1\n');
        if with_test: (root/'tests/test_focus.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
    def test_proof_key_content_sensitive(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.setup(r); p=self.small(); m=ProofSelector(p).compile_manifest(base_sha=BASE,head_sha=HEAD,impact=ImpactCompiler(p).assess(['app/x.py'])); a=proof_key_for_test(repo_root=r,manifest=m,policy=p,spec=p.tests['focused'],runtime_identity={'python':'x'}); (r/'app/x.py').write_text('VALUE=2\n'); b=proof_key_for_test(repo_root=r,manifest=m,policy=p,spec=p.tests['focused'],runtime_identity={'python':'x'}); self.assertNotEqual(a,b)
    def test_cache_pass_only(self):
        with tempfile.TemporaryDirectory() as td:
            c=ProofCache(Path(td)/'c'); good=TestExecutionResult('x','PASS',0,1,'a'*64,'b'*64,'c'*64,'SUBSYSTEM_REGRESSION','SUBSYSTEM'); c.store(good); self.assertIsNotNone(c.load('a'*64)); bad=TestExecutionResult('y','FAIL',1,1,'d'*64,'e'*64,'f'*64,'SUBSYSTEM_REGRESSION','SUBSYSTEM'); c.store(bad); self.assertIsNone(c.load('d'*64))
    def test_runner_only_selected(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.setup(r); (r/'tests/test_unrelated.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail()\n'); p=self.small(); m=ProofSelector(p).compile_manifest(base_sha=BASE,head_sha=HEAD,impact=ImpactCompiler(p).assess(['app/x.py'])); self.assertEqual({'focused'},selected(m)); rep=ProofRunner(policy=p,repo_root=r).run(m); self.assertEqual('PASS',rep.status)
    def test_missing_required_fails_optional_skips(self):
        for optional,status in [(False,'FAIL'),(True,'PASS')]:
            with tempfile.TemporaryDirectory() as td:
                r=Path(td); self.setup(r,False); p=self.small(optional); m=ProofSelector(p).compile_manifest(base_sha=BASE,head_sha=HEAD,impact=ImpactCompiler(p).assess(['app/x.py'])); self.assertEqual(status,ProofRunner(policy=p,repo_root=r).run(m).status)

class CFBETests(unittest.TestCase):
    SPEC=ROOT/'benchmarking/cfbe_omega/proofos_admission_spec_v1.json'
    def metrics(self): return {'p95_admission_latency_seconds':100,'ci_compute_minutes_per_pr':50,'unrelated_test_execution_ratio':1,'false_block_rate':.2,'security_escape_rate':0,'regression_escape_rate':.02,'selector_false_negative_rate':.001,'critical_invariant_coverage':1,'omission_attribution_coverage':.2,'proof_cache_hit_ratio':0,'owner_intervention_rate':.5,'mean_time_to_root_cause_seconds':1000}
    def challenger(self):
        x=self.metrics(); x.update({'p95_admission_latency_seconds':18,'ci_compute_minutes_per_pr':8,'unrelated_test_execution_ratio':.08,'false_block_rate':.015,'regression_escape_rate':.01,'selector_false_negative_rate':.0005,'omission_attribution_coverage':1,'proof_cache_hit_ratio':.85,'owner_intervention_rate':.04,'mean_time_to_root_cause_seconds':250}); return x
    def test_source_only_held(self):
        c=CFBEAdmissionComparator.from_path(self.SPEC); r=c.compare(incumbent=BenchmarkObservation('REPEATED_OPERATIONAL_SCOPED',self.metrics(),('i',)),challenger=BenchmarkObservation('SOURCE_DESIGN_ONLY',self.challenger())); self.assertEqual('HELD_NO_OPERATIONAL_EVIDENCE',r.status); self.assertTrue(r.hard_gates_pass)
    def test_provider_live_can_be_ten_x_candidate(self):
        c=CFBEAdmissionComparator.from_path(self.SPEC); r=c.compare(incumbent=BenchmarkObservation('REPEATED_OPERATIONAL_SCOPED',self.metrics(),('i',)),challenger=BenchmarkObservation('PROVIDER_LIVE_INDEPENDENT_READBACK',self.challenger(),('provider','independent'))); self.assertEqual('TEN_X_FRONTIER_CANDIDATE',r.status)
    def test_safety_regression_rejects_speed(self):
        c=CFBEAdmissionComparator.from_path(self.SPEC); x=self.challenger(); x['security_escape_rate']=.01; r=c.compare(incumbent=BenchmarkObservation('REPEATED_OPERATIONAL_SCOPED',self.metrics()),challenger=BenchmarkObservation('PROVIDER_LIVE_INDEPENDENT_READBACK',x,('p',))); self.assertEqual('REJECTED_SAFETY_OR_REGRESSION_GATE',r.status)

class IntegrationTests(unittest.TestCase):
    def test_thin_airlock_when_repository_surface_present(self):
        f=ROOT/'.github/workflows/github-airlock.yml'
        if not f.exists(): self.skipTest('workflow-free export')
        s=f.read_text(); self.assertIn('name: Run Airlock regression tests',s); self.assertIn('name: Compile Evidence-Directed ProofOS manifest',s); self.assertIn('name: Execute manifest-selected proof court',s); self.assertNotIn('name: Run provider cutover v3 regression tests',s); self.assertNotIn('contents: write',s); self.assertIn('persist-credentials: false',s)

if __name__=='__main__': unittest.main()