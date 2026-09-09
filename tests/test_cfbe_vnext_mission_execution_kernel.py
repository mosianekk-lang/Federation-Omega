from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from benchmarking.cfbe_omega.mission_execution_kernel_vnext import (
    ActionDecision,
    ActionProposal,
    AuthorityState,
    CFBEKernelError,
    ChangeRecord,
    EventConflict,
    EvidenceProof,
    FruitCriterion,
    IdempotencyConflict,
    MissionConstraints,
    MissionContract,
    MissionExecutionKernel,
    MissionState,
    OutwardState,
    Requirement,
    RequirementState,
    TerminalAction,
    TestRunEvidence,
    WaitRegistration,
    classify_changes,
    parse_coordination_record,
    validate_capability_skip,
    validate_failure_class,
)


NOW = datetime(2026, 9, 9, 1, 30, tzinfo=timezone.utc)


def contract(
    *,
    version: int = 1,
    requirements: tuple[Requirement, ...] | None = None,
    terminal_actions: tuple[TerminalAction, ...] = (),
    constraints: MissionConstraints | None = None,
) -> MissionContract:
    requirements = requirements or (
        Requirement("R1", "Build the deterministic mission execution kernel"),
        Requirement("R2", "Pass the independent false completion regression court"),
    )
    return MissionContract.create(
        mission_id="MISSION-CFBE-TEST",
        mission_version=version,
        owner_outcome="Deliver one locally verified deterministic kernel",
        terminal_fruit=(FruitCriterion("F1", "Independent terminal court reports complete"),),
        requirements=requirements,
        exclusions=("provider deployment", "optional evolution"),
        constraints=constraints or MissionConstraints(),
        terminal_actions=terminal_actions,
        critical_path=tuple(item.requirement_id for item in requirements),
    )


def proof(
    claim_id: str,
    *,
    proof_id: str,
    version: int = 1,
    independence: int = 1,
    dependencies: dict[str, str] | None = None,
    created_at: datetime = NOW,
) -> EvidenceProof:
    return EvidenceProof(
        proof_id=proof_id,
        claim_id=claim_id,
        mission_id="MISSION-CFBE-TEST",
        mission_version=version,
        artifact_hashes=("sha256:artifact",),
        dependency_hashes=dependencies or {"source": "sha256:source-v1"},
        environment_fingerprint="python-3.12",
        authority_fingerprint="A1-local",
        created_at=created_at.isoformat(),
        max_age_seconds=86400,
        invalidation_predicates=("dependency hash changed",),
        independence_level=independence,
    )


def action(**overrides) -> ActionProposal:
    values = dict(
        action_id="ACTION-1",
        mission_id="MISSION-CFBE-TEST",
        mission_version=1,
        requirement_ids=("R1",),
        authority_class="A1",
        expected_outcome_delta=1,
    )
    values.update(overrides)
    return ActionProposal(**values)


class KernelCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "kernel.sqlite3"
        self.kernel = MissionExecutionKernel(self.db)
        self.kernel.open_mission(contract())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def bind_and_prove(self, claim_id: str, proof_id: str) -> None:
        self.kernel.bind_proof(proof(claim_id, proof_id=proof_id))
        kind, item_id = claim_id.split(":", 1)
        if kind == "requirement":
            self.kernel.prove_requirement("MISSION-CFBE-TEST", 1, item_id, proof_id)
        else:
            self.kernel.prove_fruit("MISSION-CFBE-TEST", 1, item_id, proof_id)

    def test_contract_requires_finite_denominator(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "FINITE_MISSION_DENOMINATOR_REQUIRED"):
            MissionContract.create(
                mission_id="M1",
                mission_version=1,
                owner_outcome="Deliver a bounded tested result",
                terminal_fruit=(),
                requirements=(),
                critical_path=("R1",),
            )

    def test_optional_improvement_cannot_expand_denominator(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "OPTIONAL_REQUIREMENT"):
            contract(requirements=(Requirement("R1", "Add an optional improvement capability", optional=True),))

    def test_duplicate_requirement_is_rejected(self) -> None:
        duplicate = Requirement("R1", "Build the required deterministic component")
        with self.assertRaisesRegex(CFBEKernelError, "DUPLICATE_REQUIREMENT_ID"):
            contract(requirements=(duplicate, duplicate))

    def test_critical_path_cannot_reference_unfrozen_requirement(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "CRITICAL_PATH"):
            MissionContract.create(
                mission_id="M1",
                mission_version=1,
                owner_outcome="Deliver a bounded tested result",
                terminal_fruit=(FruitCriterion("F1", "Observed local result receipt exists"),),
                requirements=(Requirement("R1", "Build the required local result"),),
                critical_path=("R2",),
            )

    def test_same_mission_id_different_contract_conflicts(self) -> None:
        changed = contract(requirements=(Requirement("R1", "Build a materially different local component"),))
        with self.assertRaisesRegex(IdempotencyConflict, "DIFFERENT_CONTRACT"):
            self.kernel.open_mission(changed)

    def test_stale_action_is_cancelled(self) -> None:
        newer = contract(version=2)
        self.kernel.revise_mission(newer)
        receipt = self.kernel.decide_action(action())
        self.assertEqual(ActionDecision.CANCEL, receipt.decision)
        self.assertIn("STALE_MISSION_VERSION", receipt.reasons)

    def test_inactive_requirement_cancels_action(self) -> None:
        self.bind_and_prove("requirement:R1", "PROOF-R1")
        receipt = self.kernel.decide_action(action())
        self.assertEqual(ActionDecision.CANCEL, receipt.decision)

    def test_zero_value_action_is_denied(self) -> None:
        receipt = self.kernel.decide_action(action(expected_outcome_delta=0))
        self.assertEqual(ActionDecision.DENY, receipt.decision)
        self.assertIn("NO_CAUSAL_VALUE", receipt.reasons)

    def test_self_generated_obligation_recursion_is_denied(self) -> None:
        receipt = self.kernel.decide_action(
            action(expected_outcome_delta=0, creates_obligations=("write another receipt",))
        )
        self.assertEqual(ActionDecision.DENY, receipt.decision)
        self.assertIn("SELF_GENERATED_OBLIGATION_RECURSION", receipt.reasons)

    def test_cost_and_user_burden_fail_closed(self) -> None:
        receipt = self.kernel.decide_action(action(estimated_cost=1, estimated_user_burden=1))
        self.assertEqual(ActionDecision.DENY, receipt.decision)
        self.assertIn("MAXIMUM_COST_EXCEEDED", receipt.reasons)
        self.assertIn("MAXIMUM_USER_BURDEN_EXCEEDED", receipt.reasons)

    def test_nonfinite_and_negative_action_economics_fail_closed(self) -> None:
        for field, value in (
            ("estimated_cost", float("nan")),
            ("recurring_cost", -1),
            ("estimated_user_burden", float("inf")),
            ("expected_outcome_delta", float("-inf")),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(CFBEKernelError):
                    self.kernel.decide_action(action(**{field: value}))

    def test_string_boolean_constraints_are_rejected(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "BOOLEAN_TYPE"):
            contract(
                constraints=MissionConstraints(
                    zero_new_recurring_cost="false",  # type: ignore[arg-type]
                )
            )

    def test_authority_class_requires_approval(self) -> None:
        receipt = self.kernel.decide_action(action(authority_class="A3"))
        self.assertEqual(ActionDecision.APPROVAL_REQUIRED, receipt.decision)

    def test_provider_effect_defaults_to_unapproved(self) -> None:
        receipt = self.kernel.decide_action(
            action(effectful=True, resource_key="provider:x", idempotency_key="idem-1")
        )
        self.assertEqual(ActionDecision.APPROVAL_REQUIRED, receipt.decision)
        self.assertIn("EXTERNAL_EFFECT_NOT_AUTHORIZED", receipt.reasons)

    def test_single_use_permit(self) -> None:
        candidate = action()
        token = self.kernel.issue_permit(candidate, issued_at=NOW.isoformat())
        self.kernel.consume_permit(token, candidate, now=(NOW + timedelta(seconds=1)).isoformat())
        with self.assertRaisesRegex(CFBEKernelError, "PERMIT_ALREADY_CONSUMED"):
            self.kernel.consume_permit(token, candidate, now=(NOW + timedelta(seconds=2)).isoformat())

    def test_permit_binds_complete_action_fingerprint(self) -> None:
        candidate = action(resource_key="local:one", operation_key="inspect")
        token = self.kernel.issue_permit(candidate, issued_at=NOW.isoformat())
        changed = replace(candidate, resource_key="local:two")
        with self.assertRaisesRegex(CFBEKernelError, "PERMIT_ACTION_FINGERPRINT_MISMATCH"):
            self.kernel.consume_permit(token, changed, now=(NOW + timedelta(seconds=1)).isoformat())

    def test_expired_permit_is_denied(self) -> None:
        candidate = action()
        token = self.kernel.issue_permit(candidate, ttl_seconds=1, issued_at=NOW.isoformat())
        with self.assertRaisesRegex(CFBEKernelError, "PERMIT_EXPIRED"):
            self.kernel.consume_permit(token, candidate, now=(NOW + timedelta(seconds=1)).isoformat())

    def test_revision_cancels_stale_permit_and_descendants(self) -> None:
        candidate = action()
        token = self.kernel.issue_permit(candidate, issued_at=NOW.isoformat())
        self.kernel.revise_mission(contract(version=2))
        with self.assertRaisesRegex(CFBEKernelError, "ACTION_NO_LONGER_AUTHORIZED"):
            self.kernel.consume_permit(token, candidate, now=(NOW + timedelta(seconds=1)).isoformat())

    def test_removed_requirement_disappears_after_revision(self) -> None:
        newer = contract(
            version=2,
            requirements=(Requirement("R1", "Build the deterministic mission execution kernel"),),
        )
        projection = self.kernel.revise_mission(newer)
        self.assertNotIn("R2", projection.requirement_states)
        self.assertEqual(("R1",), projection.contract.critical_path)

    def test_denied_action_never_reaches_executor(self) -> None:
        calls: list[dict[str, object]] = []
        denied = action(
            effectful=True,
            resource_key="provider:x",
            idempotency_key="idem-denied",
        )
        with self.assertRaisesRegex(CFBEKernelError, "PERMIT_DENIED"):
            self.kernel.issue_permit(denied)
        self.assertEqual([], calls)

    def test_effect_executes_once_and_replay_returns_receipt(self) -> None:
        local_effects = MissionConstraints(external_effects_allowed=True)
        with tempfile.TemporaryDirectory() as root:
            kernel = MissionExecutionKernel(Path(root) / "effects.sqlite3")
            kernel.open_mission(contract(constraints=local_effects))
            candidate = action(effectful=True, resource_key="local:file", idempotency_key="idem-effect")
            calls: list[dict[str, object]] = []
            first_token = kernel.issue_permit(candidate)
            first = kernel.execute_once(candidate, first_token, {"value": 1}, lambda payload: calls.append(dict(payload)) or {"ok": True})
            second_token = kernel.issue_permit(replace(candidate, action_id="ACTION-2"))
            second = kernel.execute_once(replace(candidate, action_id="ACTION-2"), second_token, {"value": 1}, lambda payload: calls.append(dict(payload)) or {"ok": True})
            self.assertEqual([{"value": 1}], calls)
            self.assertEqual("EXECUTED_ONCE", first["execution_state"])
            self.assertEqual("IDEMPOTENT_REPLAY", second["execution_state"])
            with self.assertRaisesRegex(CFBEKernelError, "PERMIT_ALREADY_CONSUMED"):
                kernel.consume_permit(second_token, replace(candidate, action_id="ACTION-2"))

    def test_effect_payload_change_under_same_key_fails(self) -> None:
        local_effects = MissionConstraints(external_effects_allowed=True)
        with tempfile.TemporaryDirectory() as root:
            kernel = MissionExecutionKernel(Path(root) / "effects.sqlite3")
            kernel.open_mission(contract(constraints=local_effects))
            candidate = action(effectful=True, resource_key="local:file", idempotency_key="idem-effect")
            kernel.execute_once(candidate, kernel.issue_permit(candidate), {"value": 1}, lambda payload: {"ok": True})
            changed = replace(candidate, action_id="ACTION-2")
            with self.assertRaisesRegex(IdempotencyConflict, "PAYLOAD_CONFLICT"):
                kernel.execute_once(changed, kernel.issue_permit(changed), {"value": 2}, lambda payload: {"ok": True})

    def test_effect_identity_cannot_replay_across_resources(self) -> None:
        local_effects = MissionConstraints(external_effects_allowed=True)
        with tempfile.TemporaryDirectory() as root:
            kernel = MissionExecutionKernel(Path(root) / "effects.sqlite3")
            kernel.open_mission(contract(constraints=local_effects))
            first = action(
                effectful=True,
                resource_key="local:one",
                operation_key="write",
                idempotency_key="idem-resource-bound",
            )
            kernel.execute_once(first, kernel.issue_permit(first), {"value": 1}, lambda payload: {"target": "one"})
            second = replace(first, action_id="ACTION-2", resource_key="local:two")
            with self.assertRaisesRegex(IdempotencyConflict, "PAYLOAD_CONFLICT"):
                kernel.execute_once(second, kernel.issue_permit(second), {"value": 1}, lambda payload: {"target": "two"})

    def test_concurrent_action_identity_executes_effect_once(self) -> None:
        local_effects = MissionConstraints(external_effects_allowed=True)
        with tempfile.TemporaryDirectory() as root:
            kernel = MissionExecutionKernel(Path(root) / "effects.sqlite3")
            kernel.open_mission(contract(constraints=local_effects))
            first = action(effectful=True, resource_key="local:file", idempotency_key="idem-race")
            second = replace(first, action_id="ACTION-2")
            tokens = (kernel.issue_permit(first), kernel.issue_permit(second))
            barrier = threading.Barrier(2)
            executed: list[str] = []
            outcomes: list[str] = []

            def run(candidate: ActionProposal, token: str) -> None:
                barrier.wait()
                try:
                    receipt = kernel.execute_once(
                        candidate,
                        token,
                        {"value": 1},
                        lambda payload: executed.append(candidate.action_id) or {"ok": True},
                    )
                    outcomes.append(receipt["execution_state"])
                except CFBEKernelError as exc:
                    outcomes.append(str(exc))

            threads = (
                threading.Thread(target=run, args=(first, tokens[0])),
                threading.Thread(target=run, args=(second, tokens[1])),
            )
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(1, len(executed))
            self.assertIn("EXECUTED_ONCE", outcomes)
            self.assertEqual(2, len(outcomes))

    def test_restart_rehydrates_projection_and_continues_safely(self) -> None:
        before = self.kernel.set_requirement_state(
            "MISSION-CFBE-TEST", 1, "R1", RequirementState.READY
        )
        restarted = MissionExecutionKernel(self.db)
        restored = restarted.project("MISSION-CFBE-TEST")
        self.assertEqual(before.last_event_hash, restored.last_event_hash)
        self.assertEqual(RequirementState.READY, restored.requirement_states["R1"])
        candidate = action(action_id="ACTION-AFTER-RESTART")
        token = restarted.issue_permit(candidate)
        restarted.consume_permit(token, candidate)

    def test_event_compare_and_swap_rejects_stale_head(self) -> None:
        projection = self.kernel.project("MISSION-CFBE-TEST")
        self.kernel.set_requirement_state("MISSION-CFBE-TEST", 1, "R1", RequirementState.READY)
        with self.assertRaisesRegex(EventConflict, "COMPARE_AND_SWAP"):
            self.kernel.store.append(
                mission_id="MISSION-CFBE-TEST",
                mission_version=1,
                event_type="TEST",
                payload={"ok": True},
                idempotency_key="test-cas",
                expected_head=projection.last_event_hash,
            )

    def test_event_chain_tamper_is_detected(self) -> None:
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE events SET payload_json='{}' WHERE sequence=1")
        with self.assertRaisesRegex(EventConflict, "EVENT_CHAIN_INVALID"):
            self.kernel.store.verify("MISSION-CFBE-TEST")

    def test_dependency_change_invalidates_only_linked_proof(self) -> None:
        self.kernel.bind_proof(proof("requirement:R1", proof_id="PROOF-R1", dependencies={"source": "v1"}))
        self.kernel.prove_requirement("MISSION-CFBE-TEST", 1, "R1", "PROOF-R1")
        self.kernel.bind_proof(proof("requirement:R2", proof_id="PROOF-R2", dependencies={"policy": "p1"}))
        self.kernel.prove_requirement("MISSION-CFBE-TEST", 1, "R2", "PROOF-R2")
        invalidated = self.kernel.invalidate_dependencies("MISSION-CFBE-TEST", {"source": "v2"})
        projection = self.kernel.project("MISSION-CFBE-TEST")
        self.assertEqual(("PROOF-R1",), invalidated)
        self.assertEqual(RequirementState.OPEN, projection.requirement_states["R1"])
        self.assertEqual(RequirementState.PROVEN, projection.requirement_states["R2"])

    def test_unchanged_dependency_preserves_proof(self) -> None:
        self.kernel.bind_proof(proof("requirement:R1", proof_id="PROOF-R1", dependencies={"source": "v1"}))
        self.assertEqual((), self.kernel.invalidate_dependencies("MISSION-CFBE-TEST", {"source": "v1"}))

    def test_stale_version_proof_is_rejected(self) -> None:
        self.kernel.revise_mission(contract(version=2))
        with self.assertRaisesRegex(CFBEKernelError, "STALE_PROOF"):
            self.kernel.bind_proof(proof("requirement:R1", proof_id="PROOF-OLD", version=1))

    def test_false_completion_blocked_with_unresolved_requirements(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "FALSE_COMPLETION_BLOCKED"):
            self.kernel.terminalize("MISSION-CFBE-TEST", now=NOW.isoformat())

    def test_source_ready_cannot_substitute_for_terminal_authority(self) -> None:
        terminal = (TerminalAction("T1", "A3", AuthorityState.UNPROVEN),)
        with tempfile.TemporaryDirectory() as root:
            kernel = MissionExecutionKernel(Path(root) / "authority.sqlite3")
            kernel.open_mission(contract(terminal_actions=terminal))
            self.assertFalse(kernel.preflight_terminal_authority("MISSION-CFBE-TEST")["full_completion_promise_allowed"])
            report = kernel.terminality_report("MISSION-CFBE-TEST", now=NOW.isoformat())
            self.assertIn("AUTHORITY:T1", report.gaps)
            self.assertEqual(OutwardState.BLOCKED_EXTERNAL_AUTHORITY, report.state)

    def test_independent_proof_is_required_for_completion(self) -> None:
        self.kernel.bind_proof(proof("requirement:R1", proof_id="PROOF-R1", independence=0))
        self.kernel.prove_requirement("MISSION-CFBE-TEST", 1, "R1", "PROOF-R1")
        self.kernel.bind_proof(proof("requirement:R2", proof_id="PROOF-R2"))
        self.kernel.prove_requirement("MISSION-CFBE-TEST", 1, "R2", "PROOF-R2")
        self.kernel.bind_proof(proof("fruit:F1", proof_id="PROOF-F1"))
        self.kernel.prove_fruit("MISSION-CFBE-TEST", 1, "F1", "PROOF-F1")
        report = self.kernel.terminality_report("MISSION-CFBE-TEST", now=NOW.isoformat())
        self.assertIn("REQUIREMENT_PROOF:R1", report.gaps)

    def test_all_frozen_criteria_terminalize_then_stop_new_work(self) -> None:
        self.bind_and_prove("requirement:R1", "PROOF-R1")
        self.bind_and_prove("requirement:R2", "PROOF-R2")
        self.bind_and_prove("fruit:F1", "PROOF-F1")
        report = self.kernel.terminalize("MISSION-CFBE-TEST", now=NOW.isoformat())
        self.assertTrue(report.complete)
        self.assertEqual(MissionState.COMPLETE_VERIFIED, self.kernel.project("MISSION-CFBE-TEST").mission_state)
        decision = self.kernel.decide_action(action(action_id="ACTION-AFTER-COMPLETE"))
        self.assertEqual(ActionDecision.STOP, decision.decision)
        self.assertIn("OUTCOME_ERROR_ZERO", decision.reasons)

    def test_reconciler_selects_first_open_critical_requirement(self) -> None:
        self.assertEqual("R1", self.kernel.reconcile("MISSION-CFBE-TEST")["requirement_id"])
        self.bind_and_prove("requirement:R1", "PROOF-R1")
        self.assertEqual("R2", self.kernel.reconcile("MISSION-CFBE-TEST")["requirement_id"])

    def test_waiting_automatically_requires_all_durable_fields(self) -> None:
        state = self.kernel.register_wait(
            WaitRegistration(
                job_id="JOB-1",
                mission_id="MISSION-CFBE-TEST",
                mission_version=1,
                worker_identity="worker-1",
                checkpoint_ref="checkpoint:1",
                subscription_ref="webhook:provider-event",
                resume_action_id="ACTION-1",
                readback_endpoint="local://jobs/JOB-1",
            )
        )
        self.assertEqual(OutwardState.WAITING_AUTOMATICALLY, state)

    def test_user_message_is_not_an_automatic_subscription(self) -> None:
        state = self.kernel.register_wait(
            WaitRegistration(
                job_id="JOB-1",
                mission_id="MISSION-CFBE-TEST",
                mission_version=1,
                worker_identity="worker-1",
                checkpoint_ref="checkpoint:1",
                subscription_ref="USER_MESSAGE",
                resume_action_id="ACTION-1",
                readback_endpoint="local://jobs/JOB-1",
            )
        )
        self.assertNotEqual(OutwardState.WAITING_AUTOMATICALLY, state)

    def test_missing_wait_field_is_not_automatic(self) -> None:
        state = self.kernel.register_wait(
            WaitRegistration(
                job_id="JOB-1",
                mission_id="MISSION-CFBE-TEST",
                mission_version=1,
                worker_identity="",
                checkpoint_ref="checkpoint:1",
                subscription_ref="timer:1",
                resume_action_id="ACTION-1",
                readback_endpoint="local://jobs/JOB-1",
            )
        )
        self.assertEqual(OutwardState.FAILED_CHECKPOINTED, state)

    def test_cancel_mission_deactivates_waiting_and_stops_actions(self) -> None:
        self.kernel.register_wait(
            WaitRegistration("JOB-1", "MISSION-CFBE-TEST", 1, "worker", "checkpoint", "timer:1", "ACTION-1", "local://job")
        )
        projection = self.kernel.cancel_mission("MISSION-CFBE-TEST", "Owner superseded the mission")
        self.assertEqual(MissionState.CANCELLED, projection.mission_state)
        self.assertEqual(OutwardState.FAILED_CHECKPOINTED, self.kernel.waiting_state("MISSION-CFBE-TEST"))
        self.assertEqual(ActionDecision.STOP, self.kernel.decide_action(action()).decision)

    def test_zero_test_success_is_rejected(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "ZERO_TEST_SUCCESS"):
            TestRunEvidence("unittest", 0, 0, 0, 0).validate()

    def test_mismatched_test_counts_are_rejected(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "TEST_COUNT_MISMATCH"):
            TestRunEvidence("unittest", 3, 3, 2, 0).validate()

    def test_deletion_only_change_remains_visible(self) -> None:
        changes = classify_changes((ChangeRecord("obsolete.txt", "D"),))
        self.assertEqual("D", changes[0].status)

    def test_rename_requires_old_path(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "RENAME_OR_COPY"):
            classify_changes((ChangeRecord("new.txt", "R"),))

    def test_malformed_coordination_head_never_means_available(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "MALFORMED_COORDINATION_RECORD"):
            parse_coordination_record({"message": "noop"})

    def test_released_lease_requires_release_proof(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "RELEASE_PROOF_MISSING"):
            parse_coordination_record(
                {
                    "schema": "FEDERATION-COORDINATION-LEASE-1",
                    "lease_id": "F1",
                    "fencing_token": 1,
                    "state": "RELEASED",
                    "holder": "worker",
                    "expires_at": NOW.isoformat(),
                }
            )

    def test_reduced_export_skip_requires_manifest_registration(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "UNREGISTERED_CAPABILITY_SKIP"):
            validate_capability_skip("github-workflows", available=False, registered_unavailable=())
        self.assertEqual(
            "REGISTERED_UNAVAILABLE_SKIP",
            validate_capability_skip("github-workflows", available=False, registered_unavailable=("github-workflows",)),
        )

    def test_unsupported_failure_taxonomy_fails_before_execution(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "UNSUPPORTED_FAILURE_CLASS"):
            validate_failure_class("RELEASE_IDENTITY_MISMATCH", ("SUBSYSTEM_REGRESSION", "SOURCE_INTEGRITY_FAILURE"))


if __name__ == "__main__":
    unittest.main()
