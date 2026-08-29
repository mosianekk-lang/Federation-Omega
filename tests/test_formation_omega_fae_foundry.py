import json
import unittest
from formation_omega.fully_automated_elevation_foundry import AuthorityEnvelope, BuildStage, CandidateRoute, IdeaCandidate, SovereignFoundryCompiler, ValidationError


def candidate(**changes):
    base=dict(idea_id="NF-CH-TEST-001",title="Bible idea to production",mission="Compile one source-backed idea into a proof-bound system plan.",user_value="Reduce idea-to-operational-value latency without false completion.",source_refs=("drive:master-bible#chapter","drive:registry#row"),exact_gap="No canonical machine-readable project genome compiler.",current_baseline="Ideas are represented in documents and distributed ledgers.",protected_capabilities=("proof-before-claim","reuse-first"),reuse_candidates=("Formation-Ω","CFBE","SOVARA"),candidate_routes=(CandidateRoute("R1","EXTEND","Extend existing Formation/CFBE contracts.",( "Formation-Ω",),0.2,0.95,0.95,0,0.1),CandidateRoute("R2","NEW_BUILD","Build standalone orchestrator.",(),0.8,0.5,0.6,5000,0.6)),falsification_tests=("A competing existing compiler already satisfies all required fields.",),authority=AuthorityEnvelope(permitted=("READ","DRAFT","VALIDATE","SIMULATE")))
    base.update(changes); return IdeaCandidate(**base)


class FoundryCompilerTests(unittest.TestCase):
    def test_compile_is_deterministic(self):
        a=SovereignFoundryCompiler.compile(candidate()); b=SovereignFoundryCompiler.compile(candidate()); self.assertEqual(a.genome_sha256,b.genome_sha256); self.assertEqual(a.selected_route.route_id,"R1")
    def test_reuse_first_tie_break(self):
        self.assertEqual(SovereignFoundryCompiler.select_route((CandidateRoute("new","NEW_BUILD","new"),CandidateRoute("reuse","REUSE","reuse"))).route_id,"reuse")
    def test_source_evidence_required(self):
        with self.assertRaisesRegex(ValidationError,"SOURCE_EVIDENCE_REQUIRED"): SovereignFoundryCompiler.compile(candidate(source_refs=()))
    def test_competing_route_required(self):
        with self.assertRaisesRegex(ValidationError,"COMPETING_ROUTE_REQUIRED"): SovereignFoundryCompiler.compile(candidate(candidate_routes=()))
    def test_falsification_required(self):
        with self.assertRaisesRegex(ValidationError,"FALSIFICATION_TEST_REQUIRED"): SovereignFoundryCompiler.compile(candidate(falsification_tests=()))
    def test_authority_contradiction_fails_closed(self):
        with self.assertRaisesRegex(ValidationError,"AUTHORITY_CONTRADICTION"): AuthorityEnvelope(permitted=("PAY",),prohibited=("PAY",))
    def test_no_silent_production_promotion(self):
        g=SovereignFoundryCompiler.compile(candidate()); states=SovereignFoundryCompiler.evaluate_progress(g,{BuildStage.IDEA_CAPTURED.value:("idea",),BuildStage.SOURCE_VERIFIED.value:("source",),BuildStage.GAP_DEFINED.value:("gap",),BuildStage.PROJECT_GENOME_COMPILED.value:("genome",),BuildStage.FORMATION_SELECTED.value:("formation",)}); self.assertEqual(SovereignFoundryCompiler.current_frontier(states),BuildStage.FORMATION_SELECTED); self.assertEqual(next(s for s in states if s.stage==BuildStage.DEPLOYED).state,"HELD")
    def test_owner_gate_blocks_deployment_even_with_evidence(self):
        g=SovereignFoundryCompiler.compile(candidate()); ev={s.value:(f"proof:{s.value}",) for s in BuildStage}; states=SovereignFoundryCompiler.evaluate_progress(g,ev,distinct_successes=3,soak_seconds=300,owner_release=False); d=next(s for s in states if s.stage==BuildStage.DEPLOYED); self.assertIn("OWNER_RELEASE_REQUIRED",d.blockers)
    def test_repeated_success_and_soak_are_distinct(self):
        g=SovereignFoundryCompiler.compile(candidate()); ev={s.value:(f"proof:{s.value}",) for s in BuildStage}; states=SovereignFoundryCompiler.evaluate_progress(g,ev,distinct_successes=2,soak_seconds=299,owner_release=True); self.assertEqual(next(s for s in states if s.stage==BuildStage.REPEATED_SUCCESS).state,"HELD"); self.assertEqual(next(s for s in states if s.stage==BuildStage.SOAKED).state,"HELD")
    def test_json_contract_has_maturity_and_authority(self):
        encoded=json.dumps(SovereignFoundryCompiler.compile(candidate()).as_dict(),sort_keys=True); self.assertIn("FAE-PROJECT-GENOME-1",encoded); self.assertIn("SEMANTIC_READBACK_VERIFIED",encoded); self.assertIn("FULLY_ESTABLISHED_SYSTEM_OR_SERVICE",encoded)

if __name__ == "__main__": unittest.main()
