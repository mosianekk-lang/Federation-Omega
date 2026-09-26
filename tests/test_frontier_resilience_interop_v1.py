import unittest

from federation.frontier_resilience_interop_v1 import (
    AsyncJobHandle,
    Decision,
    DeliveryProofTier,
    FailureDomainVector,
    MV3TransferSnapshot,
    ResumeSnapshot,
    StatefulTask,
    ToolCatalogueCacheEntry,
    adaptive_worker_slots,
    delivery_proof_transition,
    exact_resume_gate,
    failure_domain_placement,
    local_openai_compatibility_gate,
    module_summary,
    mv3_reconcile_transfer,
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
        self.assertTrue(summary["mv3_restart_fencing_bound"])
        self.assertTrue(summary["delivery_proof_tiers_bound"])

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

    def test_mv3_restart_recovers_same_transfer_and_never_allocates_new_identity(self):
        snap = MV3TransferSnapshot(
            mission_id="MISSION-FUSE-WORKSPACE-20260923-001",
            conversation_key="conv-1",
            transfer_id="CBT-conv-1-E7-deadbeef",
            client_epoch=7,
            handoff_state="OPENING",
            pending_atomic_action_id="restore-1",
            effect_identity="effect-1",
            effect_state="NO_EFFECT_PROVEN",
            successor_bound=False,
        )
        recovered = mv3_reconcile_transfer(
            snap,
            observed_client_epoch=7,
            successor_present=False,
            service_worker_restarted=True,
        )
        self.assertEqual(recovered.decision, Decision.REUSE)
        self.assertEqual(recovered.state, "RECOVER_OPENING_TRANSFER")
        self.assertTrue(recovered.same_transfer_required)
        self.assertTrue(recovered.same_client_epoch_required)
        self.assertFalse(recovered.create_new_transfer_allowed)
        self.assertTrue(recovered.successor_create_allowed)
        self.assertTrue(recovered.autosend_allowed)
        self.assertFalse(recovered.effect_replay_allowed)
        self.assertTrue(recovered.alarm_wakeup_required)

    def test_mv3_restart_reuses_existing_successor_at_most_once(self):
        snap = MV3TransferSnapshot(
            mission_id="mission",
            conversation_key="conv",
            transfer_id="transfer",
            client_epoch=4,
            handoff_state="IN_FLIGHT",
            effect_state="RESPONSE_ONLY",
            successor_bound=True,
        )
        recovered = mv3_reconcile_transfer(
            snap,
            observed_client_epoch=4,
            successor_present=True,
            service_worker_restarted=True,
        )
        self.assertEqual(recovered.state, "RECOVER_BOUND_SUCCESSOR")
        self.assertFalse(recovered.successor_create_allowed)
        self.assertFalse(recovered.create_new_transfer_allowed)
        self.assertTrue(recovered.autosend_allowed)

    def test_mv3_stale_persisted_transfer_is_rejected_after_newer_epoch_takeover(self):
        snap = MV3TransferSnapshot(
            mission_id="mission",
            conversation_key="conv",
            transfer_id="transfer-old",
            client_epoch=8,
            handoff_state="IN_FLIGHT",
            effect_state="NO_EFFECT_PROVEN",
        )
        rejected = mv3_reconcile_transfer(
            snap,
            observed_client_epoch=9,
            successor_present=False,
            service_worker_restarted=True,
        )
        self.assertEqual(rejected.decision, Decision.REJECT)
        self.assertEqual(rejected.state, "STALE_PERSISTED_TRANSFER_REJECTED")
        self.assertFalse(rejected.autosend_allowed)
        self.assertTrue(rejected.stale_writer_authority)

    def test_mv3_effect_unknown_holds_only_replay_lane_until_readback(self):
        snap = MV3TransferSnapshot(
            mission_id="mission",
            conversation_key="conv",
            transfer_id="transfer",
            client_epoch=3,
            handoff_state="IN_FLIGHT",
            pending_atomic_action_id="tool-42",
            effect_identity="effect-42",
            effect_state="EFFECT_UNKNOWN",
        )
        held = mv3_reconcile_transfer(
            snap,
            observed_client_epoch=3,
            successor_present=False,
            service_worker_restarted=True,
        )
        self.assertEqual(held.decision, Decision.HOLD)
        self.assertEqual(held.state, "POSSIBLE_EFFECT_PENDING_READBACK")
        self.assertFalse(held.autosend_allowed)
        self.assertFalse(held.effect_replay_allowed)

    def test_mv3_user_interruption_never_auto_resumes(self):
        snap = MV3TransferSnapshot(
            mission_id="mission",
            conversation_key="conv",
            transfer_id="transfer",
            client_epoch=2,
            handoff_state="CHECKPOINTED",
            user_interruption=True,
        )
        held = mv3_reconcile_transfer(
            snap,
            observed_client_epoch=2,
            successor_present=False,
            service_worker_restarted=False,
        )
        self.assertEqual(held.state, "USER_INTERRUPTION_NON_RESUME")
        self.assertFalse(held.autosend_allowed)
        self.assertFalse(held.successor_create_allowed)

    def test_delivery_tiers_acknowledged_means_d2_not_human_read(self):
        d1 = delivery_proof_transition(
            DeliveryProofTier.D0_RESULT_READY,
            "DELIVERY_JOURNALED",
        )
        self.assertEqual(d1.tier, DeliveryProofTier.D1_DELIVERY_JOURNALED)
        d2 = delivery_proof_transition(d1.tier, "ACKNOWLEDGED")
        self.assertEqual(d2.tier, DeliveryProofTier.D2_CURRENT_CLIENT_RENDER_VERIFIED)
        self.assertFalse(d2.human_read_inferred)
        inferred = delivery_proof_transition(d2.tier, "HUMAN_READ_INFERRED")
        self.assertEqual(inferred.decision, Decision.REJECT)
        self.assertEqual(inferred.tier, DeliveryProofTier.D2_CURRENT_CLIENT_RENDER_VERIFIED)

    def test_delivery_lost_final_stream_creates_debt_not_work_replay(self):
        debt = delivery_proof_transition(
            DeliveryProofTier.D1_DELIVERY_JOURNALED,
            "LOST_FINAL_STREAM",
        )
        self.assertEqual(debt.decision, Decision.REUSE)
        self.assertTrue(debt.resend_result_allowed)
        self.assertFalse(debt.rerun_work_allowed)
        self.assertEqual(debt.tier, DeliveryProofTier.D1_DELIVERY_JOURNALED)

    def test_delivery_d3_requires_explicit_owner_interaction(self):
        d3 = delivery_proof_transition(
            DeliveryProofTier.D2_CURRENT_CLIENT_RENDER_VERIFIED,
            "EXPLICIT_OWNER_INTERACTION",
        )
        self.assertEqual(d3.tier, DeliveryProofTier.D3_EXPLICIT_OWNER_INTERACTION_CONFIRMED)
        self.assertFalse(d3.human_read_inferred)

    def test_delivery_hash_or_transaction_mismatch_rejects_rebinding(self):
        receipt = delivery_proof_transition(
            DeliveryProofTier.D1_DELIVERY_JOURNALED,
            "CURRENT_CLIENT_RENDER_VERIFIED",
            artifact_hash_matches=False,
        )
        self.assertEqual(receipt.decision, Decision.REJECT)
        self.assertEqual(receipt.tier, DeliveryProofTier.D1_DELIVERY_JOURNALED)

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
