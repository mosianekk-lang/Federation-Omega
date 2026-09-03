import unittest

from federation.kioas_audit_to_repair import (
    AuditFinding,
    RepairClass,
    RepairRoute,
    TransactionState,
    VerificationResult,
    compile_audit,
    compile_finding,
    compile_execution_packet,
    compile_resume_packet,
    compile_candidate_artifact_identity,
    decide_canonical_pointer_promotion,
    mark_applied,
    terminality_court,
    transaction_from_mapping,
    transaction_to_mapping,
    validate_transaction_receipt,
    resume_disposition,
    verify_transaction,
)


class ArcTests(unittest.TestCase):
    def route(self, route_id="r1", **overrides):
        data = dict(
            route_id=route_id,
            route_kind="REUSE",
            summary="reuse existing repair primitive",
            callable_now=True,
            reversible=True,
            zero_or_included_cost=True,
            within_a1_authority=True,
            independent_readback_available=True,
            rollback_available=True,
        )
        data.update(overrides)
        return RepairRoute(**data)

    def finding(self, finding_id="F-1", **overrides):
        data = dict(
            finding_id=finding_id,
            objective="restore desired state",
            observed_state="broken",
            desired_state="healthy",
        )
        data.update(overrides)
        return AuditFinding(**data)

    def compile(self, finding=None, routes=None, **kwargs):
        return compile_finding(
            finding or self.finding(),
            routes or [self.route()],
            source_epoch=kwargs.pop("source_epoch", "a" * 40),
            authority_state=kwargs.pop("authority_state", "A1_INTERNAL"),
            failure_semantics=kwargs.pop("failure_semantics", "SEMANTIC_FAILURE"),
            cfbe_prepass_ref=kwargs.pop("cfbe_prepass_ref", "CFBE:PREPASS:TEST"),
            **kwargs,
        )


    def test_material_finding_requires_cfbe_prepass(self):
        with self.assertRaisesRegex(ValueError, "CFBE_PREPASS_REF_REQUIRED"):
            compile_finding(
                self.finding(),
                [self.route()],
                source_epoch="a" * 40,
                authority_state="A1_INTERNAL",
                failure_semantics="X",
            )

    def test_benchmark_refs_bind_reconciliation_incident_and_progressive_promotion(self):
        tx = self.compile()
        for required in ("P-017", "P-023", "P-024", "P-025", "PAT-CFBE-VIRT100-001"):
            self.assertIn(required, tx.benchmark_refs)

    def test_auto_repair_now_for_safe_callable_reversible_route(self):
        tx = self.compile()
        self.assertEqual(tx.repair_class, RepairClass.AUTO_REPAIR_NOW)
        self.assertEqual(tx.state, TransactionState.READY)
        self.assertFalse(tx.external_effect_authorized)
        self.assertFalse(tx.self_certification_allowed)

    def test_shared_state_route_requires_fenced_repair(self):
        tx = self.compile(routes=[self.route(requires_shared_state_fence=True)])
        self.assertEqual(tx.repair_class, RepairClass.AUTO_REPAIR_FENCED)
        self.assertIn("FDOF_FENCE_ACQUIRED_WITH_CURRENT_SOURCE", tx.required_preconditions)

    def test_canary_route_is_not_direct_repair(self):
        tx = self.compile(routes=[self.route(requires_canary=True)])
        self.assertEqual(tx.repair_class, RepairClass.AUTO_REPAIR_CANARY)
        self.assertIn("FAILURE_FIRST_CANARY_REQUIRED", tx.required_preconditions)

    def test_missing_callable_executor_becomes_waiting_capability_not_report_only(self):
        tx = self.compile(routes=[self.route(callable_now=False)])
        self.assertEqual(tx.repair_class, RepairClass.WAITING_EXACT_CAPABILITY)
        self.assertEqual(tx.state, TransactionState.WAITING)
        self.assertTrue(tx.resume_trigger)

    def test_provider_or_owner_gate_blocks_only_exact_effect(self):
        tx = self.compile(finding=self.finding(authority_gap=1.0, exact_provider_or_owner_trigger=True))
        self.assertEqual(tx.repair_class, RepairClass.OWNER_OR_PROVIDER_TRIGGER_REQUIRED)
        self.assertEqual(tx.state, TransactionState.HELD_EXACT_GATE)

    def test_repeated_unchanged_failure_circuit_breaks(self):
        first = self.compile()
        second = self.compile(prior_failure_fingerprints=[first.failure_fingerprint])
        self.assertEqual(second.repair_class, RepairClass.QUARANTINE_AND_REROUTE)
        self.assertTrue(second.repeated_unchanged_failure)

    def test_reuse_beats_build_when_other_fitness_is_equal(self):
        reuse = self.route("reuse", route_kind="REUSE")
        build = self.route("build", route_kind="BUILD")
        tx = self.compile(routes=[build, reuse])
        self.assertEqual(tx.selected_route_id, "reuse")

    def test_route_without_readback_or_rollback_is_ineligible(self):
        unsafe = self.route("unsafe", independent_readback_available=False, rollback_available=False)
        tx = self.compile(routes=[unsafe])
        self.assertEqual(tx.repair_class, RepairClass.WAITING_EXACT_CAPABILITY)
        self.assertIsNone(tx.selected_route_id)

    def test_independent_verification_required_for_repaired_verified(self):
        tx = self.compile()
        applied = mark_applied(tx, executor_id="EXECUTOR", execution_ref="exec:1")
        fail = VerificationResult("VERIFIER", "proof:fail", True, False, True, True, True, True, True)
        held = verify_transaction(applied, fail)
        self.assertEqual(held.state, TransactionState.APPLIED_UNVERIFIED)
        ok = VerificationResult("VERIFIER", "proof:ok", True, True, True, True, True, True, True)
        repaired = verify_transaction(applied, ok)
        self.assertEqual(repaired.state, TransactionState.REPAIRED_VERIFIED)


    def test_cannot_verify_before_execution(self):
        tx = self.compile()
        ok = VerificationResult("VERIFIER", "proof:ok", True, True, True, True, True, True, True)
        with self.assertRaisesRegex(ValueError, "TRANSACTION_NOT_APPLIED_UNVERIFIED"):
            verify_transaction(tx, ok)

    def test_executor_cannot_self_certify(self):
        tx = mark_applied(self.compile(), executor_id="SAME", execution_ref="exec:1")
        ok = VerificationResult("SAME", "proof:ok", True, True, True, True, True, True, True)
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_VERIFIER_REQUIRED"):
            verify_transaction(tx, ok)

    def test_callable_fallback_beats_theoretically_stronger_unavailable_route(self):
        unavailable = self.route("future", route_kind="REUSE", callable_now=False, proof_strength=10)
        available = self.route("now", route_kind="EXTEND", callable_now=True, proof_strength=1)
        tx = self.compile(routes=[unavailable, available])
        self.assertEqual(tx.selected_route_id, "now")
        self.assertNotEqual(tx.repair_class, RepairClass.WAITING_EXACT_CAPABILITY)

    def test_audit_cannot_close_with_executable_repair(self):
        tx = self.compile()
        court = terminality_court([tx])
        self.assertEqual(court.state, "AUDIT_OPEN_EXECUTABLE_REPAIRS")

    def test_audit_can_terminally_hold_exact_nonbypassable_gate(self):
        tx = self.compile(finding=self.finding(exact_provider_or_owner_trigger=True))
        court = terminality_court([tx])
        self.assertEqual(court.state, "AUDIT_TERMINAL_WITH_RESUMABLE_EXACT_GATES")

    def test_historical_gnen_packaging_failure_compiles_as_fenced_source_repair(self):
        finding = self.finding(
            finding_id="FLT-GNEN-003",
            observed_state="workflow-free export retains GNEN tests but omits .gs source",
            desired_state="export-aware source test skips only when .gs subtree is intentionally absent",
            severity=1.5,
            dependency_unlock=2.0,
            owner_burden_reduction=1.5,
        )
        route = self.route(
            route_id="PATCH_EXISTING_TEST_PACKAGING",
            route_kind="EXTEND",
            summary="amend only existing GNEN export-aware test packaging",
            requires_shared_state_fence=True,
            proof_strength=1.5,
        )
        tx = self.compile(finding=finding, routes=[route], failure_semantics="WORKFLOW_FREE_EXPORT_TEST_PACKAGING")
        self.assertEqual(tx.repair_class, RepairClass.AUTO_REPAIR_FENCED)
        self.assertEqual(tx.selected_route_id, "PATCH_EXISTING_TEST_PACKAGING")

    def test_gas_liveness_gap_compiles_waiting_exact_executor(self):
        finding = self.finding(
            finding_id="FLT-CHAT-002",
            observed_state="GNS3 definitions migrated but unattended heartbeat not proven",
            desired_state="single gasSchedulerRunV3 trigger and later unattended heartbeat",
        )
        route = self.route(
            route_id="GAS_SAME_PROJECT_RECOVERY",
            route_kind="REUSE",
            callable_now=False,
            summary="invoke existing gasSchedulerInstallV3 and run-now functions",
        )
        tx = self.compile(finding=finding, routes=[route])
        self.assertEqual(tx.repair_class, RepairClass.WAITING_EXACT_CAPABILITY)

    def test_github_ruleset_gap_compiles_provider_trigger_required(self):
        finding = self.finding(
            finding_id="FLT-CHAT-003",
            observed_state="main unprotected and repository rulesets empty",
            desired_state="provider-enforced zero-bypass main admission",
            exact_provider_or_owner_trigger=True,
            consequential_external_effect=True,
        )
        tx = self.compile(finding=finding, routes=[self.route()])
        self.assertEqual(tx.repair_class, RepairClass.OWNER_OR_PROVIDER_TRIGGER_REQUIRED)

    def test_compile_audit_prioritizes_high_unlock_finding(self):
        high = self.finding("HIGH", severity=2, dependency_unlock=3)
        low = self.finding("LOW", severity=1, dependency_unlock=1)
        txs = compile_audit(
            [low, high],
            {"HIGH": [self.route("rh")], "LOW": [self.route("rl")]},
            source_epoch="b" * 40,
            authority_state="A1_INTERNAL",
            failure_semantics_by_finding={"HIGH": "X", "LOW": "Y"},
            cfbe_prepass_ref="CFBE:PREPASS:TEST",
        )
        self.assertEqual(txs[0].finding_id, "HIGH")

    def test_checkpoint_roundtrip_preserves_transaction_and_receipt(self):
        tx = self.compile()
        payload = transaction_to_mapping(tx)
        restored = transaction_from_mapping(payload)
        self.assertEqual(restored, tx)
        self.assertTrue(validate_transaction_receipt(restored))

    def test_tampered_checkpoint_fails_closed(self):
        tx = self.compile()
        payload = transaction_to_mapping(tx)
        payload["priority_score"] = payload["priority_score"] + 1
        with self.assertRaisesRegex(ValueError, "TRANSACTION_RECEIPT_INVALID"):
            transaction_from_mapping(payload)

    def test_crash_after_apply_requires_readback_before_reexecution(self):
        tx = mark_applied(self.compile(), executor_id="EXEC", execution_ref="exec:crash")
        decision = resume_disposition(
            tx, current_source_epoch=tx.source_epoch, current_authority_state=tx.authority_state
        )
        self.assertEqual(decision, "READBACK_BEFORE_ANY_REEXECUTION")

    def test_source_drift_requires_jit_recompile_not_rebuild(self):
        tx = self.compile(source_epoch="a" * 40)
        decision = resume_disposition(
            tx, current_source_epoch="b" * 40, current_authority_state=tx.authority_state
        )
        self.assertEqual(decision, "RECOMPILE_JIT_SOURCE_DRIFT")

    def test_authority_drift_requires_recompile(self):
        tx = self.compile(authority_state="A1_INTERNAL")
        decision = resume_disposition(
            tx, current_source_epoch=tx.source_epoch, current_authority_state="A0_READ_ONLY"
        )
        self.assertEqual(decision, "RECOMPILE_AUTHORITY_DRIFT")

    def test_waiting_checkpoint_resumes_only_on_trigger_recheck(self):
        tx = self.compile(routes=[self.route(callable_now=False)])
        decision = resume_disposition(
            tx, current_source_epoch=tx.source_epoch, current_authority_state=tx.authority_state
        )
        self.assertEqual(decision, "RECHECK_RESUME_TRIGGER")

    def test_changed_route_changes_failure_fingerprint(self):
        first = self.compile(routes=[self.route("r1")])
        second = self.compile(routes=[self.route("r2")])
        self.assertNotEqual(first.failure_fingerprint, second.failure_fingerprint)

    def test_waiting_capability_does_not_false_circuit_break(self):
        first = self.compile(routes=[self.route(callable_now=False)])
        second = self.compile(
            routes=[self.route(callable_now=False)],
            prior_failure_fingerprints=[first.failure_fingerprint],
        )
        self.assertEqual(second.repair_class, RepairClass.WAITING_EXACT_CAPABILITY)
        self.assertTrue(second.repeated_unchanged_failure)

    def test_unsafe_unexecuted_route_does_not_false_circuit_break(self):
        first = self.compile(routes=[self.route(zero_or_included_cost=False)])
        second = self.compile(
            routes=[self.route(zero_or_included_cost=False)],
            prior_failure_fingerprints=[first.failure_fingerprint],
        )
        self.assertEqual(second.repair_class, RepairClass.OWNER_OR_PROVIDER_TRIGGER_REQUIRED)

    def test_execution_packet_is_no_effect_and_mesh_bound(self):
        tx = self.compile()
        packet = compile_execution_packet(tx)
        self.assertEqual(packet.executor_contract, "FEDERATION_EXECUTION_MESH")
        self.assertFalse(packet.external_effect_authorized)
        self.assertFalse(packet.provider_effect_authorized)
        self.assertFalse(packet.self_certification_allowed)
        self.assertEqual(packet.idempotency_key, tx.transaction_id)

    def test_execution_packet_rejects_waiting_transaction(self):
        tx = self.compile(routes=[self.route(callable_now=False)])
        with self.assertRaisesRegex(ValueError, "TRANSACTION_NOT_READY_FOR_EXECUTION_PACKET"):
            compile_execution_packet(tx)

    def test_resume_packet_is_gas_gns3_only(self):
        tx = self.compile(routes=[self.route(callable_now=False)])
        packet = compile_resume_packet(tx)
        self.assertEqual(packet.scheduler_surface, "GOOGLE_APPS_SCRIPT_GNS3")
        self.assertFalse(packet.chatgpt_scheduler_allowed)
        self.assertTrue(packet.affected_controller_only)
        self.assertFalse(packet.external_effect_authorized)

    def test_resume_packet_rejects_ready_transaction(self):
        tx = self.compile()
        with self.assertRaisesRegex(ValueError, "TRANSACTION_NOT_RESUMABLE_WAIT_STATE"):
            compile_resume_packet(tx)


    def test_content_addressed_candidate_identity_is_deterministic_and_immutable_named(self):
        payload = b"arc-candidate-bytes"
        first = compile_candidate_artifact_identity(
            logical_name="KIOAS_ARC",
            version="1.0.0",
            payload=payload,
            source_epoch="f" * 40,
        )
        second = compile_candidate_artifact_identity(
            logical_name="KIOAS_ARC",
            version="1.0.0",
            payload=payload,
            source_epoch="f" * 40,
        )
        self.assertEqual(first, second)
        self.assertIn(first.sha256[:16], first.immutable_file_name)
        self.assertEqual(first.write_mode, "CREATE_IMMUTABLE_CANDIDATE")
        self.assertEqual(first.canonical_pointer_mutation, "COMPARE_AND_SET_ONLY")
        self.assertFalse(first.delete_superseded)

    def test_changed_candidate_bytes_create_distinct_immutable_name(self):
        a = compile_candidate_artifact_identity(
            logical_name="KIOAS_ARC", version="1.0.0", payload=b"a", source_epoch="f" * 40
        )
        b = compile_candidate_artifact_identity(
            logical_name="KIOAS_ARC", version="1.0.0", payload=b"b", source_epoch="f" * 40
        )
        self.assertNotEqual(a.sha256, b.sha256)
        self.assertNotEqual(a.immutable_file_name, b.immutable_file_name)

    def test_pointer_promotion_allows_only_compare_and_set_match(self):
        old = "1" * 64
        new = "2" * 64
        decision = decide_canonical_pointer_promotion(
            observed_sha256=old,
            expected_observed_sha256=old,
            candidate_sha256=new,
        )
        self.assertEqual(decision.state, "PROMOTE_POINTER_ONLY")
        self.assertTrue(decision.mutation_allowed)
        self.assertTrue(decision.requires_fresh_readback)
        self.assertFalse(decision.delete_superseded)

    def test_pointer_promotion_holds_on_concurrent_drift(self):
        decision = decide_canonical_pointer_promotion(
            observed_sha256="3" * 64,
            expected_observed_sha256="1" * 64,
            candidate_sha256="2" * 64,
        )
        self.assertEqual(decision.state, "HOLD_CONCURRENT_DRIFT")
        self.assertFalse(decision.mutation_allowed)

    def test_pointer_promotion_noops_when_candidate_already_current(self):
        digest = "4" * 64
        decision = decide_canonical_pointer_promotion(
            observed_sha256=digest,
            expected_observed_sha256=digest,
            candidate_sha256=digest,
        )
        self.assertEqual(decision.state, "ALREADY_CURRENT")
        self.assertFalse(decision.mutation_allowed)


if __name__ == "__main__":
    unittest.main()
