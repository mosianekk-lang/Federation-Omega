from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from frontier_hardening_v2 import (
    AdaptiveRouterV2, AuthorityError, AuthorityLease, CausalEdgeV2, CausalGraphV2,
    ChampionChallenger, ConstraintError, DeterministicFaultInjector, EffectContract,
    FenceError, GatewayPolicy, GuardrailPipeline, GuardrailResult, HYPERLEVERAGE_100,
    HybridMemoryIndex, IdempotencyCollision, LearningPromotionGate, MaturityMatrix,
    MemoryItemV2, MissionGraphV2, MissionNodeV2, ProofBundleVerifier, ProofEnvelope,
    ProofError, RouteRecord, SLODefinition, SLOErrorBudget, SQLiteControlPlane,
    SupplyChainProvenance, TokenBucket, ToolboxManifest, TraceEnvelope,
    WorkloadIdentityPolicy, coverage_receipt, digest,
)


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dbpath = Path(self.tmp.name) / "control.sqlite3"; self.cp = SQLiteControlPlane(self.dbpath)
    def tearDown(self): self.cp.close(); self.tmp.cleanup()
    def test_event_chain_and_cas(self):
        self.cp.append_event("m1","MISSION_CREATED",{"x":1}); self.cp.append_event("m1","WORK_ADDED",{"x":2}); self.assertTrue(self.cp.verify_event_chain())
        self.assertEqual(self.cp.cas_put("mission","m1",{"state":"OPEN"},expected_version=0),1); self.assertEqual(self.cp.cas_put("mission","m1",{"state":"RUNNING"},expected_version=1),2)
        with self.assertRaises(FenceError): self.cp.cas_put("mission","m1",{"state":"BAD"},expected_version=1)
    def test_schema_version_gate(self):
        first=self.cp.register_schema("mission",1,{"fields":["id"]}); same=self.cp.register_schema("mission",1,{"fields":["id"]}); self.assertEqual(first["sha256"],same["sha256"])
        with self.assertRaises(ConstraintError): self.cp.register_schema("mission",1,{"fields":["id","state"]})
        self.assertEqual(self.cp.register_schema("mission",2,{"fields":["id","state"]})["version"],2)
    def test_lease_fencing_and_takeover(self):
        a=self.cp.acquire_lease("r1","worker-a",ttl_seconds=10,now_epoch=100)
        with self.assertRaises(FenceError): self.cp.acquire_lease("r1","worker-b",ttl_seconds=10,now_epoch=101)
        b=self.cp.acquire_lease("r1","worker-b",ttl_seconds=10,now_epoch=111); self.assertGreater(b["fencing_token"],a["fencing_token"])
        with self.assertRaises(FenceError): self.cp.assert_fence("r1","worker-a",epoch=a["epoch"],fencing_token=a["fencing_token"],now_epoch=112)
        self.cp.assert_fence("r1","worker-b",epoch=b["epoch"],fencing_token=b["fencing_token"],now_epoch=112)
    def test_lease_renewal_rejects_stale(self):
        a=self.cp.acquire_lease("r1","worker-a",ttl_seconds=10,now_epoch=100); renewed=self.cp.renew_lease("r1","worker-a",epoch=a["epoch"],fencing_token=a["fencing_token"],ttl_seconds=10,now_epoch=105); self.assertEqual(renewed["expires_at_epoch"],115)
        with self.assertRaises(FenceError): self.cp.renew_lease("r1","worker-a",epoch=a["epoch"],fencing_token=a["fencing_token"]-1,ttl_seconds=10,now_epoch=106)
    def test_idempotency_collision(self):
        first=self.cp.reserve_idempotency("idem-1",{"payload":1},"IDEMPOTENT"); second=self.cp.reserve_idempotency("idem-1",{"payload":1},"IDEMPOTENT"); self.assertEqual(first["request_sha256"],second["request_sha256"])
        with self.assertRaises(IdempotencyCollision): self.cp.reserve_idempotency("idem-1",{"payload":2},"IDEMPOTENT")
    def test_effect_outbox_and_interruption_semantics(self):
        c=EffectContract("e1","provider","send","target","AT_MOST_ONCE",True,True,"idem-e1",{"status":"ok"}); self.cp.prepare_effect(c,{"body":"x"}); self.cp.transition_effect("e1",expected_state="PREPARED",next_state="DISPATCHING"); self.cp.transition_effect("e1",expected_state="DISPATCHING",next_state="DISPATCHED",provider_ref="p1")
        self.assertEqual(self.cp.interrupted_effect_decision("e1")["action"],"PROBE_PROVIDER_BEFORE_RETRY"); self.cp.transition_effect("e1",expected_state="DISPATCHED",next_state="OBSERVED",result={"status":"ok"}); self.assertEqual(self.cp.transition_effect("e1",expected_state="OBSERVED",next_state="VERIFIED")["state"],"VERIFIED")
    def test_idempotent_interruption_can_retry_same_key(self):
        c=EffectContract("e1","provider","upsert","target","IDEMPOTENT",False,False,"idem-e1"); self.cp.prepare_effect(c,{"body":"x"}); self.cp.transition_effect("e1",expected_state="PREPARED",next_state="DISPATCHING"); self.assertEqual(self.cp.interrupted_effect_decision("e1")["action"],"SAFE_RETRY_WITH_SAME_IDEMPOTENCY_KEY")
    def test_authority_lease_one_use(self):
        lease=AuthorityLease("lease-1","merge","repo/main","actor","abc123",100,200,"nonce",1); self.cp.create_authority_lease(lease); use=self.cp.consume_authority_lease("lease-1",action="merge",target="repo/main",actor="actor",source_version="abc123",now_epoch=150); self.assertEqual(use["remaining"],0)
        with self.assertRaises(AuthorityError): self.cp.consume_authority_lease("lease-1",action="merge",target="repo/main",actor="actor",source_version="abc123",now_epoch=151)
    def test_budget_fail_closed(self):
        with self.assertRaises(ConstraintError): self.cp.consume_budget("unknown",1)
        self.cp.set_budget("mission",5); self.assertEqual(self.cp.consume_budget("mission",2)["remaining"],3)
        with self.assertRaises(ConstraintError): self.cp.consume_budget("mission",4)
    def test_value_ledger(self):
        self.cp.record_value(event_id="v1",mission_id="m1",accepted_outcome=True,owner_interventions=0,minutes_saved=10,cost=1.5); self.cp.record_value(event_id="v2",mission_id="m1",accepted_outcome=False,owner_interventions=1,minutes_saved=2,cost=.5); s=self.cp.value_summary("m1"); self.assertEqual(s["observations"],2); self.assertEqual(s["accepted_rate"],.5); self.assertEqual(s["owner_interventions"],1)


class ProofAndAuthorityTests(unittest.TestCase):
    def proof(self, **changes):
        base=dict(proof_id="p1",subject="mission:m1",target="repo/main",operation="merge",issuer="github",observed_at="1970-01-01T00:02:30Z",max_age_seconds=100,source_version="abc",evidence_sha256=digest({"ok":True}),semantic_state="VERIFIED",provider_correlation_id="run-1",signature_ref="sig-1",evidence_class="PROVIDER_NATIVE",scope="repo"); base.update(changes); return ProofEnvelope(**base)
    def test_proof_bindings_and_freshness(self):
        p=self.proof(); check=p.validate(now_epoch=200,expected_subject="mission:m1",expected_target="repo/main",expected_operation="merge",expected_source_version="abc",accepted_evidence_classes={"PROVIDER_NATIVE"},require_provider_correlation=True,require_signature_ref=True); self.assertTrue(check["valid"]); stale=p.validate(now_epoch=300); self.assertFalse(stale["valid"]); self.assertIn("PROOF_STALE",stale["reasons"])
    def test_proof_bundle_rejects_wrong_semantics(self):
        result=ProofBundleVerifier([self.proof(semantic_state="UNVERIFIED")]).verify_requirements([{"proof_id":"p1","subject":"mission:m1"}],now_epoch=200); self.assertFalse(result["valid"]); self.assertIn("p1",result["invalid"])
    def test_control_plane_rejects_unverified_proof(self):
        with tempfile.TemporaryDirectory() as td:
            cp=SQLiteControlPlane(Path(td)/"db.sqlite3")
            try:
                with self.assertRaises(ProofError): cp.register_proof(self.proof(semantic_state="CLAIMED"))
            finally: cp.close()
    def test_workload_identity(self):
        policy=WorkloadIdentityPolicy(allowed_issuers={"https://token.actions.githubusercontent.com"},audience="sol-runtime",subject_prefix="repo:mosianekk-lang/Federation-Omega:",max_ttl_seconds=600); good={"iss":"https://token.actions.githubusercontent.com","aud":"sol-runtime","sub":"repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main","iat":100,"exp":200,"credential_type":"oidc"}; self.assertTrue(policy.validate(good,now_epoch=150)["valid"]); self.assertFalse(policy.validate(dict(good,credential_type="static_key"),now_epoch=150)["valid"])
    def test_gateway_enforcement(self):
        policy=GatewayPolicy("gateway-1","runtime-1"); self.assertTrue(policy.admit({"runtime_id":"runtime-1","via_gateway":"gateway-1","authenticated_principal":"spiffe://sol/worker","policy_version":"1"})["admitted"]); self.assertFalse(policy.admit({"runtime_id":"runtime-1","via_gateway":None,"authenticated_principal":"x","policy_version":"1"})["admitted"])


class GuardrailTests(unittest.TestCase):
    def test_all_four_guardrail_boundaries(self):
        pipe=GuardrailPipeline(); allow=lambda value: GuardrailResult("allow","ALLOW"); reject_secret=lambda value: GuardrailResult("secret","REJECT" if "secret" in value else "ALLOW","secret forbidden"); pipe.input_guards.append(allow); pipe.pre_tool_guards.append(reject_secret); pipe.post_tool_guards.append(allow); pipe.output_guards.append(allow); self.assertEqual(pipe.check_input({"text":"ok"})["decision"],"ALLOW"); self.assertEqual(pipe.check_pre_tool({"secret":"x"})["decision"],"REJECT"); self.assertEqual(pipe.check_post_tool({"result":"ok"})["decision"],"ALLOW"); self.assertEqual(pipe.check_output({"text":"ok"})["decision"],"ALLOW")


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.router=AdaptiveRouterV2(cooldown_seconds=50); self.r1=RouteRecord("p","build","m1","r1","e1",1,100,.99,10,2); self.r2=RouteRecord("p","build","m2","r1","e2",.5,150,.97,10,2); self.router.register(self.r1); self.router.register(self.r2)
    def test_composite_route_identity_prevents_overwrite(self): self.assertEqual(len(self.router.routes),2)
    def test_breaker_cooldown_and_half_open(self):
        for _ in range(4): self.router.record_outcome(self.r1.key,success=False,latency_ms=100,now_epoch=100)
        self.assertEqual(self.router.routes[self.r1.key].breaker_state,"OPEN"); self.assertEqual(self.router.routes[self.r1.key].open_until_epoch,150); selected=self.router.select(capability="build",now_epoch=120,max_unit_cost=2,max_latency_ms=500,min_success_rate=.5); self.assertNotEqual(selected["selected"],self.r1.key); self.assertIn(self.r1.key,self.router.half_open_due(151))
    def test_token_bucket(self):
        b=TokenBucket(2,1,initial_tokens=1); self.assertTrue(b.allow(1,100)); self.assertFalse(b.allow(1,100)); self.assertTrue(b.allow(1,101))


class MissionTests(unittest.TestCase):
    def test_cycle_detection(self):
        g=MissionGraphV2("m"); g.add(MissionNodeV2("a",("b",))); g.add(MissionNodeV2("b",("a",)))
        with self.assertRaises(ConstraintError): g.validate_dag()
    def test_superseded_failed_path_can_close(self):
        g=MissionGraphV2("m",mission_constraints=("budget_ok",)); g.add(MissionNodeV2("a",status="FAILED")); g.supersede_failed("a",MissionNodeV2("a-repair",status="VERIFIED")); self.assertEqual(g.evaluate_closure(satisfied_constraints={"budget_ok"})["state"],"PROOF_CLOSED")
    def test_node_verification_enforces_constraints_and_proofs(self):
        proof=ProofEnvelope.from_evidence(proof_id="p",subject="node:a",target="repo",operation="test",issuer="ci",source_version="abc",evidence={"pass":True},observed_at="1970-01-01T00:02:30Z",max_age_seconds=100); g=MissionGraphV2("m"); g.add(MissionNodeV2("a",required_proofs=({"proof_id":"p","subject":"node:a","target":"repo","operation":"test","source_version":"abc"},),constraints=("budget_ok",))); result=g.verify_node("a",proof_bundle=ProofBundleVerifier([proof]),now_epoch=200,satisfied_constraints={"budget_ok"}); self.assertEqual(result["status"],"VERIFIED")
    def test_ready_respects_conflict_domains_and_dependencies(self):
        g=MissionGraphV2("m"); g.add(MissionNodeV2("a",priority=100,conflict_domains=("repo",))); g.add(MissionNodeV2("b",priority=90,conflict_domains=("repo",))); g.add(MissionNodeV2("c",priority=80,conflict_domains=("drive",))); self.assertEqual(g.ready(capacity=3),["a","c"]); g.nodes["a"].status="VERIFIED"; g.add(MissionNodeV2("d",dependencies=("a",),priority=95)); self.assertIn("d",g.ready(capacity=3))


class MemoryCausalTests(unittest.TestCase):
    def test_memory_supersession_contradiction_and_hybrid_retrieval(self):
        index=HybridMemoryIndex(); index.add(MemoryItemV2("old","provider status","provider route unavailable",True,.9,100,50,"s1")); index.add(MemoryItemV2("new","provider status","provider route available verified",True,.95,190,90,"s2",supersedes=("old",))); index.add(MemoryItemV2("other","provider status","provider route down",False,.4,195,80,"s3",contradicts=("new",))); result=index.retrieve("provider route available",now_epoch=200); ids=[x["memory_id"] for x in result["selected"]]; self.assertNotIn("old",ids); self.assertEqual(ids[0],"new"); self.assertTrue(result["contradictions"])
    def test_causal_path_strength(self):
        g=CausalGraphV2(); g.add(CausalEdgeV2("db_lock","queue",.8,.9)); g.add(CausalEdgeV2("queue","latency",.7,.8)); self.assertAlmostEqual(g.influence("db_lock","latency"),.8*.9*.7*.8); ranked=g.rank_interventions(symptom="latency",interventions=[{"id":"root","target":"db_lock","expected_effect":.8,"reversibility":1,"cost":.1,"risk":.1},{"id":"symptom","target":"latency","expected_effect":.2,"reversibility":1,"cost":.1,"risk":.1}]); self.assertEqual(ranked[0]["id"],"root")


class ObservabilitySupplyChainTests(unittest.TestCase):
    def test_otel_attributes_redact_secrets(self):
        span=TraceEnvelope("t","s",None,"tool","provider_call",1,2.0,"OK",{"mission.id":"m1","authorization_token":"secret","provider":"x"}); attrs=span.otel_attributes(); self.assertIn("mission.id",attrs); self.assertNotIn("authorization_token",attrs)
    def test_error_budget_freezes_on_fast_burn(self):
        budget=SLOErrorBudget(SLODefinition("slo",.99,window=100)); state=None
        for _ in range(10): state=budget.record(False)
        self.assertEqual(state["action"],"FREEZE_PROMOTION")
    def test_supply_chain_expectation_verification(self):
        artifact="a"*64; prov=SupplyChainProvenance(artifact,"https://github.com/o/r","abc","github-actions","python",(("dep://one","b"*64),),"run-1","sig://1","rekor://1"); result=prov.verify(expected_artifact_sha256=artifact,expected_source_uri="https://github.com/o/r",expected_source_revision="abc",allowed_builders={"github-actions"},require_signature=True,require_transparency_log=True); self.assertTrue(result["valid"])
    def test_toolbox_fingerprint(self):
        manifest=ToolboxManifest("1"); manifest.register("search",schema={"q":"str"},implementation_sha256="c"*64); fp=manifest.fingerprint(); self.assertTrue(manifest.verify(fp))
    def test_fault_injection(self):
        f=DeterministicFaultInjector({"after_dispatch":"CRASH"})
        with self.assertRaisesRegex(RuntimeError,"CRASH"): f.invoke("after_dispatch")


class LearningAndCoverageTests(unittest.TestCase):
    def test_champion_challenger_requires_samples_and_no_regression(self):
        champion={"success_rate":.9,"proof_quality":.8,"latency_ms":500,"cost":2,"owner_interventions":2}; challenger={"success_rate":.99,"proof_quality":.95,"latency_ms":300,"cost":1,"owner_interventions":0}; self.assertFalse(ChampionChallenger.evaluate(champion,challenger,challenger_samples=10)["promote"]); self.assertTrue(ChampionChallenger.evaluate(champion,challenger,challenger_samples=30)["promote"])
    def test_learning_gate(self):
        gate=LearningPromotionGate(); self.assertTrue(gate.evaluate(distinct_events=3,independent_sources=2,contradiction_count=0,regression_count=0,measured_gain=.05)["promote"]); self.assertFalse(gate.evaluate(distinct_events=3,independent_sources=1,contradiction_count=0,regression_count=0,measured_gain=.05)["promote"])
    def test_maturity_no_cross_scope_inheritance(self):
        self.assertTrue(MaturityMatrix.can_promote("SOURCE_IMPLEMENTED","DETERMINISTIC_TESTED",same_scope=True,proof_chain_complete=True)); self.assertFalse(MaturityMatrix.can_promote("SOURCE_IMPLEMENTED","DETERMINISTIC_TESTED",same_scope=False,proof_chain_complete=True))
    def test_hyperleverage_100_coverage(self):
        self.assertEqual(len(HYPERLEVERAGE_100),100); self.assertEqual(len({g["id"] for g in HYPERLEVERAGE_100}),100); self.assertEqual(len({g["title"] for g in HYPERLEVERAGE_100}),100); receipt=coverage_receipt(); self.assertEqual(receipt["status"],"SOURCE_IMPLEMENTATION_COMPLETE"); self.assertTrue(all(receipt["gates"].values()))


if __name__ == "__main__": unittest.main()
