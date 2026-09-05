import unittest
from bubbles.chat_governor_omega3.performance_kernel import (
    DeltaCapsuleCompiler, ElasticSpecialistPlanner, FailureObservation, HookContext,
    HookDecision, HookEvent, HookResult, HostBindingContract, InformationGainStopRule,
    LifecycleHookBus, PendingWorkLedger, PreFinalEfficiencyGate, RemainingWork,
    SemanticReadCache, SemanticSpan, SkillDefinition, SkillPager, SpecialistCandidate,
    ToolSchemaCache, TraceToRegressionCompiler, UnnecessaryWorkMeter, WorkMetrics,
    performance_kernel_receipt,
)

NOW="2026-09-05T06:00:00+02:00"; LATER="2026-09-05T06:30:00+02:00"; EARLIER="2026-09-05T05:30:00+02:00"

class ChatGovPerformanceKernelTests(unittest.TestCase):
    def test_receipt_is_source_only(self):
        r=performance_kernel_receipt(); self.assertEqual(r.version,"3.5.0"); self.assertFalse(r.provider_effect_authorized); self.assertFalse(r.native_chatgpt_binding_claimed); self.assertGreaterEqual(len(r.capabilities),12)
    def test_effectful_hook_error_fails_closed(self):
        bus=LifecycleHookBus(); bus.register(HookEvent.PRE_TOOL,"boom",lambda _: (_ for _ in ()).throw(RuntimeError("x")))
        r=bus.emit(HookContext(HookEvent.PRE_TOOL,"M",effect_class="BOUNDED_EFFECT",material=True)); self.assertEqual(r.decision,"DENY"); self.assertIn("HOOK_ERROR_FAIL_CLOSED",r.reason)
    def test_read_hook_error_is_nonblocking(self):
        bus=LifecycleHookBus(); bus.register(HookEvent.PRE_TOOL,"boom",lambda _: (_ for _ in ()).throw(RuntimeError("x")))
        r=bus.emit(HookContext(HookEvent.PRE_TOOL,"M",effect_class="READ_ONLY",material=True)); self.assertEqual(r.decision,"ALLOW"); self.assertTrue(r.additional_context)
    def test_stop_hook_can_continue(self):
        bus=LifecycleHookBus(); bus.register(HookEvent.PRE_FINAL,"unfinished",lambda _: HookResult(HookDecision.BLOCK_CONTINUE,"gap"))
        r=bus.emit(HookContext(HookEvent.PRE_FINAL,"M")); self.assertEqual(r.decision,"BLOCK_CONTINUE"); self.assertEqual(r.reason,"gap")
    def test_schema_cache_reuses_only_fresh_same_version(self):
        c=ToolSchemaCache(); c.put(connector="GitHub",scope="fetch",schema={"a":1},source_version="v1",observed_at=NOW,fresh_until=LATER,proof_ref="p")
        self.assertIsNotNone(c.get(connector="GitHub",scope="fetch",source_version="v1",now=NOW)); self.assertIsNone(c.get(connector="GitHub",scope="fetch",source_version="v2",now=NOW)); self.assertEqual((c.hits,c.misses),(1,1))
    def test_schema_cache_expiry(self):
        c=ToolSchemaCache(); c.put(connector="G",scope="s",schema={},source_version="v",observed_at=EARLIER,fresh_until=NOW,proof_ref="p"); self.assertIsNone(c.get(connector="G",scope="s",source_version="v",now=NOW))
    def test_read_cache_refuses_effects(self):
        c=SemanticReadCache()
        with self.assertRaisesRegex(ValueError,"EFFECTFUL"): c.put(target="x",query={},source_anchor="a",result={},effect_class="BOUNDED_EFFECT",observed_at=NOW,fresh_until=LATER,proof_ref="p")
    def test_read_cache_hit(self):
        c=SemanticReadCache(); c.put(target="x",query={"q":1},source_anchor="a",result={"ok":1},effect_class="READ_ONLY",observed_at=NOW,fresh_until=LATER,proof_ref="p"); self.assertEqual(c.get(target="x",query={"q":1},source_anchor="a",now=NOW).value,{"ok":1})
    def test_specialists_parallel_only_when_isolated(self):
        p=ElasticSpecialistPlanner(max_active=2); cs=[SpecialistCandidate("A",.9,True,True),SpecialistCandidate("B",.8,True,True),SpecialistCandidate("C",1,True,True,True)]
        plan=p.plan(task_complexity=.9,candidates=cs); self.assertEqual(plan.mode,"PARALLEL_SPECIALISTS"); self.assertEqual(plan.selected,("A","B")); self.assertIn("C",plan.rejected)
    def test_simple_task_avoids_specialists(self):
        self.assertEqual(ElasticSpecialistPlanner().plan(task_complexity=.2,candidates=[SpecialistCandidate("A",1,True,True)]).mode,"DIRECT")
    def test_pending_write_reuse_and_conflict(self):
        p=PendingWorkLedger(); p.preserve(task_id="T",task_fingerprint="f",result_ref="r",result={"x":1}); self.assertIsNotNone(p.reusable(task_id="T",task_fingerprint="f")); self.assertIsNone(p.reusable(task_id="T",task_fingerprint="g"))
        with self.assertRaisesRegex(ValueError,"CONFLICT"): p.preserve(task_id="T",task_fingerprint="f2",result_ref="r",result={"x":2})
    def test_delta_capsule_is_incremental(self):
        d=DeltaCapsuleCompiler().compile({"a":1,"b":2},{"a":1,"b":3,"c":4}); self.assertEqual(d.changed,{"b":3,"c":4}); self.assertEqual(d.deleted,())
    def test_skill_pager_closes_dependencies(self):
        p=SkillPager([SkillDefinition("base",frozenset({"core"})),SkillDefinition("legal",frozenset({"legal"}),("base",)),SkillDefinition("image",frozenset({"image"}))],max_active=2)
        page=p.page(["legal"]); self.assertEqual(set(page.selected),{"base","legal"}); self.assertIn("image",page.omitted)
    def test_information_gain_required_always_runs(self):
        d=InformationGainStopRule().decide(required=True,decision_flip_probability=0,uncertainty_reduction=0,freshness_gain=0,acquisition_cost=99,acquisition_risk=99,owner_burden=99); self.assertTrue(d.continue_work)
    def test_information_gain_stops_low_value_optional(self):
        d=InformationGainStopRule(threshold=.2).decide(required=False,decision_flip_probability=.1,uncertainty_reduction=.1,freshness_gain=.1,acquisition_cost=1,acquisition_risk=1,owner_burden=1); self.assertFalse(d.continue_work)
    def test_unnecessary_work_two_x_target(self):
        b=WorkMetrics(duplicate_reads=4,schema_rediscovery=4,recomputed_successes=2,repeated_owner_prompts=2,tool_round_trips=8); c=WorkMetrics(duplicate_reads=1,schema_rediscovery=1,tool_round_trips=2)
        r=UnnecessaryWorkMeter.compare(baseline=b,candidate=c,baseline_quality=.9,candidate_quality=.9); self.assertTrue(r.two_x_target_met); self.assertGreaterEqual(r.reduction_fraction,.5)
    def test_trace_to_regression_redacts_secret_shapes(self):
        r=TraceToRegressionCompiler().compile(FailureObservation("tool","AUTH","x","r","token=abc",{"api_key":"abc","safe":"ok"})); self.assertEqual(r.sanitized_observation["message"],"[REDACTED]"); self.assertEqual(r.sanitized_observation["context"]["api_key"],"[REDACTED]"); self.assertFalse(r.auto_commit_authorized)
    def test_host_binding_truth_states(self):
        self.assertEqual(HostBindingContract(False,False,False,False,False).enforcement_state(),"SOURCE_ONLY_UNBOUND"); self.assertEqual(HostBindingContract(True,True,True,True,True).enforcement_state(),"HOST_BOUND")
    def test_prefinal_efficiency_blocks_avoidable_owner_followup(self):
        d=PreFinalEfficiencyGate().decide([RemainingWork("W",True,True,True,True)]); self.assertFalse(d.allow_final); self.assertTrue(d.continue_work); self.assertEqual(d.actionable_work_ids,("W",))
    def test_prefinal_efficiency_allows_precise_owner_decision(self):
        d=PreFinalEfficiencyGate().decide([RemainingWork("W",True,True,False,True,True)]); self.assertTrue(d.allow_final); self.assertTrue(d.owner_decision_required)
    def test_semantic_span_has_otel_shaped_keys(self):
        s=SemanticSpan.build(mission_id="M",operation_name="execute_tool",tool_name="GitHub.fetch",cache_hit=True,context_chars=100); self.assertEqual(s.attributes["gen_ai.operation.name"],"execute_tool"); self.assertTrue(s.attributes["cache.hit"])

if __name__ == "__main__": unittest.main()
