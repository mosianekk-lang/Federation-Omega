import unittest

from federation.frontier_resilience_interop_v1 import (
    AsyncJobHandle,
    Decision,
    FailureDomainVector,
    ResumeSnapshot,
    StatefulTask,
    ToolCatalogueCacheEntry,
    adaptive_worker_slots,
    exact_resume_gate,
    failure_domain_placement,
    local_openai_compatibility_gate,
    module_summary,
    oauth_binding_gate,
    offscreen_context_plan,
    reconcile_async_job,
    task_delivery_plan,
    tool_catalogue_cache_decision,
    workflow_version_gate,
)


class FrontierResilienceInteropTests(unittest.TestCase):
    def test_module_is_internal_no_effect_and_covers_054_063(self):
        summary = module_summary()
        self.assertEqual(summary["capability_ids"], tuple(f"AGF-{i:03d}" for i in range(54, 64)))
        self.assertEqual(summary["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(summary["external_effect_default"])
        self.assertFalse(summary["provider_effect_authorized"])

    def test_async_job_reuses_handle_and_never_replays_effect(self):
        prior = AsyncJobHandle("job-1", "provider-a", "IN_PROGRESS", "idem-1", effect_id="eff-1")
        observed = AsyncJobHandle(
            "job-1", "provider-a", "COMPLETED", "idem-1",
            effect_id="eff-1", result_id="r1", result_sha256="a" * 64,
        )
        receipt = reconcile_async_job(prior, observed)
        self.assertEqual(receipt.decision, Decision.READY)
        self.assertEqual(receipt.state, "RESULT_READY")
        self.assertFalse(receipt.effect_replay_allowed)

    def test_async_terminal_result_identity_cannot_change(self):
        prior = AsyncJobHandle("job-1", "provider-a", "COMPLETED", "idem-1", result_id="r1", result_sha256="a" * 64)
        observed = AsyncJobHandle("job-1", "provider-a", "COMPLETED", "idem-1", result_id="r2", result_sha256="b" * 64)
        self.assertEqual(reconcile_async_job(prior, observed).decision, Decision.REJECT)

    def test_exact_resume_rejects_concurrent_or_ambiguous_history(self):
        snap = ResumeSnapshot("run", "session", "s" * 64, "p" * 64, "t" * 64, "owner")
        self.assertEqual(exact_resume_gate(snap, observed_session_tail_sha256="t" * 64, owner_token="owner").decision, Decision.READY)
        self.assertEqual(exact_resume_gate(snap, observed_session_tail_sha256="x" * 64, owner_token="owner").decision, Decision.HOLD)
        self.assertEqual(exact_resume_gate(snap, observed_session_tail_sha256="t" * 64, owner_token="owner", concurrent_resume=True).decision, Decision.REJECT)

    def test_tool_cache_is_ttl_scope_and_epoch_bound(self):
        entry = ToolCatalogueCacheEntry("tools/list", "a" * 64, 1000, 5000, "session", "cap-1", "auth-1")
        self.assertTrue(tool_catalogue_cache_decision(entry, now_ms=2000, required_scope="session", capability_epoch="cap-1", auth_epoch="auth-1").reusable)
        self.assertFalse(tool_catalogue_cache_decision(entry, now_ms=7000, required_scope="session", capability_epoch="cap-1", auth_epoch="auth-1").reusable)
        self.assertFalse(tool_catalogue_cache_decision(entry, now_ms=2000, required_scope="session", capability_epoch="cap-2", auth_epoch="auth-1").reusable)

    def test_stateful_task_resubscribe_preserves_identity(self):
        task = StatefulTask("task-1", "ctx-1", "WORKING", ("art-1",), "sub-1")
        receipt = task_delivery_plan(task, requested_task_id="task-1", requested_context_id="ctx-1")
        self.assertEqual(receipt.decision, Decision.REUSE)
        self.assertTrue(receipt.resubscribe_allowed)
        self.assertTrue(receipt.push_allowed)
        self.assertEqual(receipt.artifact_ids, ("art-1",))

    def test_offscreen_helper_is_singleflight_and_never_writer_authority(self):
        self.assertEqual(offscreen_context_plan(existing_context_count=0, creation_inflight=False, dom_helper_required=True).decision, Decision.CREATE)
        self.assertEqual(offscreen_context_plan(existing_context_count=1, creation_inflight=False, dom_helper_required=True).decision, Decision.REUSE)
        self.assertEqual(offscreen_context_plan(existing_context_count=2, creation_inflight=False, dom_helper_required=True).decision, Decision.REJECT)
        self.assertFalse(offscreen_context_plan(existing_context_count=1, creation_inflight=False, dom_helper_required=True).writer_authority_granted)

    def test_workflow_replay_requires_compatible_history(self):
        ready = workflow_version_gate(history_version="v1", code_version="v2", compatible_versions={"v1"}, history_complete=True)
        held = workflow_version_gate(history_version="v0", code_version="v2", compatible_versions={"v1"}, history_complete=True)
        self.assertEqual(ready.decision, Decision.READY)
        self.assertFalse(ready.replay_effects_allowed)
        self.assertEqual(held.decision, Decision.HOLD)

    def test_worker_slots_expand_only_with_resource_headroom(self):
        plan = adaptive_worker_slots(backlog=20, current_slots=4, min_slots=1, max_slots=12, cpu_fraction=0.4, memory_fraction=0.5)
        held = adaptive_worker_slots(backlog=20, current_slots=4, min_slots=1, max_slots=12, cpu_fraction=0.95, memory_fraction=0.5)
        self.assertGreater(plan.desired_slots, 4)
        self.assertLessEqual(held.desired_slots, 4)

    def test_local_runtime_requires_responses_tools_mcp_and_state(self):
        ready = local_openai_compatibility_gate(
            model_listing=True, responses=True, tools=True, mcp=True, stateful_chat=True, local_only=True
        )
        held = local_openai_compatibility_gate(
            model_listing=True, responses=True, tools=True, mcp=False, stateful_chat=True, local_only=True
        )
        self.assertEqual(ready.decision, Decision.READY)
        self.assertFalse(ready.provider_effect_authorized)
        self.assertEqual(held.decision, Decision.HOLD)
        self.assertIn("mcp", held.missing_features)

    def test_failure_domain_unknown_or_shared_does_not_fake_redundancy(self):
        dims = ("provider", "account", "region", "state")
        a = FailureDomainVector("a", {"provider": "x", "account": "a", "region": "r1", "state": "s1"})
        b = FailureDomainVector("b", {"provider": "y", "account": "b", "region": "r2", "state": "s2"})
        c = FailureDomainVector("c", {"provider": "y", "account": "b", "region": "r2", "state": "s1"})
        d = FailureDomainVector("d", {"provider": "y", "account": "b"})
        self.assertEqual(failure_domain_placement(a, b, required_dimensions=dims).min_cut_cardinality, 2)
        self.assertEqual(failure_domain_placement(a, c, required_dimensions=dims).decision, Decision.HOLD)
        self.assertEqual(failure_domain_placement(a, d, required_dimensions=dims).decision, Decision.HOLD)

    def test_oauth_gate_rejects_mixup_and_wrong_loopback_class(self):
        ok = oauth_binding_gate(
            expected_issuer="https://auth.example", observed_issuer="https://auth.example",
            application_type="native", redirect_uri="http://127.0.0.1:8111/cb",
        )
        mixup = oauth_binding_gate(
            expected_issuer="https://auth.example", observed_issuer="https://evil.example",
            application_type="native", redirect_uri="http://127.0.0.1:8111/cb",
        )
        wrong_class = oauth_binding_gate(
            expected_issuer="https://auth.example", observed_issuer="https://auth.example",
            application_type="web", redirect_uri="http://localhost:8111/cb",
        )
        self.assertEqual(ok.decision, Decision.READY)
        self.assertEqual(mixup.decision, Decision.REJECT)
        self.assertEqual(wrong_class.decision, Decision.REJECT)


if __name__ == "__main__":
    unittest.main()
