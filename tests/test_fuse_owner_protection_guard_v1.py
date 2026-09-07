from __future__ import annotations

import unittest

from federation.fuse_owner_protection_guard_v1 import (
    BuildEpochState,
    GuardDecision,
    LaneState,
    MissionLane,
    OwnerProtectionGuard,
    OwnerProtectionSnapshot,
)


class OwnerProtectionGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = OwnerProtectionGuard()

    @staticmethod
    def snapshot(**overrides) -> OwnerProtectionSnapshot:
        base = dict(
            mission_id="MISSION-ADOBE-OMEGA",
            current_mission_id="MISSION-ADOBE-OMEGA",
            objective="Build Adobe Omega to verified operational completion",
        )
        base.update(overrides)
        return OwnerProtectionSnapshot(**base)

    def test_blocked_repository_lane_does_not_freeze_independent_runtime_lane(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(
                    MissionLane("SOURCE-MERGE", LaneState.BLOCKED, blocker_id="FDOF-LEASE"),
                    MissionLane("EMAIL-PDF-RUNTIME", LaneState.READY),
                ),
                global_halt_asserted=True,
            )
        )
        self.assertEqual(GuardDecision.CONTINUE_AUTOMATICALLY, receipt.decision)
        self.assertEqual(("EMAIL-PDF-RUNTIME",), receipt.executable_lanes)
        self.assertTrue(any(x.startswith("BLOCKER_SCOPE_LEAK") for x in receipt.violations))

    def test_timer_deferral_is_rejected_when_immediate_work_exists(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(MissionLane("LOCAL-RUNTIME", LaneState.READY),),
                scheduled_deferral_proposed=True,
            )
        )
        self.assertEqual(GuardDecision.CONTINUE_AUTOMATICALLY, receipt.decision)
        self.assertTrue(any(x.startswith("IMMEDIATE_WORK_DEFERRED_TO_SCHEDULE") for x in receipt.violations))

    def test_user_requested_schedule_is_not_itself_a_violation(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(MissionLane("LOCAL-RUNTIME", LaneState.READY),),
                scheduled_deferral_proposed=True,
                user_requested_schedule=True,
            )
        )
        self.assertFalse(any(x.startswith("IMMEDIATE_WORK_DEFERRED_TO_SCHEDULE") for x in receipt.violations))

    def test_unchanged_failed_route_requires_changed_route(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(
                    MissionLane(
                        "ADOBE-MCP",
                        LaneState.FAILED,
                        retry_requested=True,
                        failure_fingerprint="HTTP403:MCP",
                        prior_failure_fingerprint="HTTP403:MCP",
                    ),
                )
            )
        )
        self.assertEqual(GuardDecision.CHANGED_ROUTE_REQUIRED, receipt.decision)

    def test_changed_failure_predicate_allows_new_attempt_path(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(
                    MissionLane(
                        "ADOBE-MCP",
                        LaneState.FAILED,
                        retry_requested=True,
                        failure_fingerprint="HTTP403:MCP",
                        prior_failure_fingerprint="HTTP403:MCP",
                        failure_predicate_changed=True,
                    ),
                )
            )
        )
        self.assertNotEqual(GuardDecision.CHANGED_ROUTE_REQUIRED, receipt.decision)

    def test_build_epoch_head_churn_is_blocked_during_admission(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                build_epoch=BuildEpochState(
                    epoch_id="ADOBE-E1",
                    admission_in_progress=True,
                    frozen_candidate_head="abc",
                    observed_candidate_head="def",
                )
            )
        )
        self.assertEqual(GuardDecision.HOLD_BUILD_EPOCH, receipt.decision)

    def test_scope_expansion_is_queued_while_admission_is_running(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                build_epoch=BuildEpochState(
                    epoch_id="ADOBE-E1",
                    admission_in_progress=True,
                    frozen_candidate_head="abc",
                    observed_candidate_head="abc",
                    scope_change_proposed=True,
                )
            )
        )
        self.assertEqual(GuardDecision.HOLD_BUILD_EPOCH, receipt.decision)

    def test_machine_resolvable_work_cannot_be_offloaded_to_owner(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(machine_resolvable_owner_tasks=("rerun-ci", "inspect-log"))
        )
        self.assertEqual(GuardDecision.CONTINUE_AUTOMATICALLY, receipt.decision)
        self.assertIn(
            "MACHINE_RESOLVABLE_WORK_OFFLOADED_TO_OWNER:inspect-log,rerun-ci",
            receipt.violations,
        )

    def test_owner_rescue_requires_prevention_binding(self) -> None:
        receipt = self.guard.evaluate(self.snapshot(owner_rescue_incident=True))
        self.assertEqual(GuardDecision.PREVENTION_BINDING_REQUIRED, receipt.decision)
        repaired = self.guard.evaluate(
            self.snapshot(
                owner_rescue_incident=True,
                prevention_evidence_ref="test:owner-protection-regression",
            )
        )
        self.assertNotEqual(GuardDecision.PREVENTION_BINDING_REQUIRED, repaired.decision)

    def test_stale_mission_pointer_is_reconciled_before_work_continues(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(current_mission_id="STRATEGIC-SECONDARY-BRAIN")
        )
        self.assertEqual(GuardDecision.RECONCILE_MISSION_POINTER, receipt.decision)

    def test_premature_completion_claim_is_denied(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(MissionLane("EMAIL-PDF", LaneState.READY),),
                required_outcomes=("EMAIL-PDF-VERIFIED",),
                completion_claim_requested=True,
                objective_satisfied=False,
            )
        )
        self.assertFalse(receipt.completion_verified)
        self.assertFalse(receipt.final_response_allowed)

    def test_verified_completion_requires_all_required_lanes_and_outcomes(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(
                    MissionLane("PDF", LaneState.DONE, proof_refs=("proof:pdf",)),
                    MissionLane("RASTER", LaneState.DONE, proof_refs=("proof:raster",)),
                ),
                required_outcomes=("PDF-VERIFIED", "RASTER-VERIFIED"),
                proven_outcomes=("PDF-VERIFIED", "RASTER-VERIFIED"),
                objective_satisfied=True,
                completion_claim_requested=True,
            )
        )
        self.assertEqual(GuardDecision.ALLOW_VERIFIED_COMPLETE, receipt.decision)
        self.assertTrue(receipt.final_response_allowed)

    def test_genuine_owner_decision_surfaces_only_after_machine_work_exhausted(self) -> None:
        owner_only = self.guard.evaluate(
            self.snapshot(genuine_owner_decisions=("AUTHORIZE-IRREVERSIBLE-PUBLISH",))
        )
        self.assertEqual(GuardDecision.OWNER_DECISION_REQUIRED, owner_only.decision)
        machine_first = self.guard.evaluate(
            self.snapshot(
                lanes=(MissionLane("SAFE-READ", LaneState.READY),),
                genuine_owner_decisions=("AUTHORIZE-IRREVERSIBLE-PUBLISH",),
            )
        )
        self.assertEqual(GuardDecision.CONTINUE_AUTOMATICALLY, machine_first.decision)

    def test_irreducible_block_requires_exhaustion_evidence(self) -> None:
        held = MissionLane("PROVIDER-ONLY", LaneState.PROVIDER_HELD, recovery_exhausted=True)
        not_proven = self.guard.evaluate(
            self.snapshot(lanes=(held,), irreducible_blocker="Provider has no route")
        )
        self.assertEqual(GuardDecision.CONTINUE_RECOVERY, not_proven.decision)
        proven = self.guard.evaluate(
            self.snapshot(
                lanes=(held,),
                irreducible_blocker="Provider has no route",
                exhaustion_evidence_ref="proof:route-exhaustion",
            )
        )
        self.assertEqual(GuardDecision.BLOCKED_IRREDUCIBLY, proven.decision)

    def test_receipt_is_deterministic(self) -> None:
        snapshot = self.snapshot(lanes=(MissionLane("A", LaneState.READY),))
        self.assertEqual(
            self.guard.evaluate(snapshot).receipt_digest,
            self.guard.evaluate(snapshot).receipt_digest,
        )

    def test_duplicate_lane_ids_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate lane_id"):
            self.guard.evaluate(
                self.snapshot(
                    lanes=(
                        MissionLane("A", LaneState.READY),
                        MissionLane("A", LaneState.BLOCKED),
                    )
                )
            )

    def test_dependency_lane_waits_without_freezing_other_independent_work(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(
                    MissionLane("SOURCE", LaneState.BLOCKED),
                    MissionLane("POST-MERGE", LaneState.READY, dependencies=("SOURCE",)),
                    MissionLane("LOCAL-CANARY", LaneState.READY),
                )
            )
        )
        self.assertEqual(("LOCAL-CANARY",), receipt.executable_lanes)

    def test_platform_fault_explanation_is_intercepted_when_safe_route_exists(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(MissionLane("ALT-RUNTIME", LaneState.READY),),
                final_response_requested=True,
                proposed_owner_message="The provider is unavailable, so you need to retry later.",
                platform_fault_signals=("PROVIDER_TIMEOUT",),
            )
        )
        self.assertEqual(GuardDecision.INTERCEPT_ASSISTANT_OUTPUT, receipt.decision)
        self.assertFalse(receipt.final_response_allowed)
        self.assertTrue(receipt.auto_continue_required)
        self.assertIn("PLATFORM_FAULT_OFFLOADED_TO_OWNER:PROVIDER_TIMEOUT", receipt.violations)
        self.assertIn("PRE_FINAL_RESPONSE_MACHINE_DEBT_REMAINS", receipt.violations)

    def test_passive_queue_no_ack_is_intercepted_when_provider_route_untried(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                final_response_requested=True,
                assistant_excuse_signals=("NO_ACK_WAIT",),
                platform_fault_signals=("PASSIVE_QUEUE",),
                known_safe_route_substitutions=("OWNER_OAUTH_APPS_SCRIPT", "PRIVATE_CLOUD_RUN"),
                attempted_route_substitutions=("OWNER_OAUTH_APPS_SCRIPT",),
            )
        )
        self.assertEqual(GuardDecision.INTERCEPT_ASSISTANT_OUTPUT, receipt.decision)
        self.assertIn(
            "KNOWN_SUBSTITUTE_ROUTE_NOT_ATTEMPTED:PRIVATE_CLOUD_RUN",
            receipt.violations,
        )

    def test_machine_resolvable_you_need_to_prompt_is_intercepted(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                owner_prompt_proposed=True,
                proposed_owner_message="You need to click retry and monitor the provider.",
                machine_resolvable_owner_tasks=("retry-provider",),
            )
        )
        self.assertEqual(GuardDecision.INTERCEPT_ASSISTANT_OUTPUT, receipt.decision)
        self.assertTrue(any(v.startswith("ASSISTANT_EXCUSE_SURFACE_ATTEMPT") for v in receipt.violations))

    def test_explicit_status_only_request_may_surface_without_stopping_mission(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(MissionLane("SAFE-REPAIR", LaneState.READY),),
                final_response_requested=True,
                status_only_requested=True,
                proposed_owner_message="Current status: provider route repair is running.",
            )
        )
        self.assertEqual(GuardDecision.ALLOW_STATUS_ONLY, receipt.decision)
        self.assertTrue(receipt.final_response_allowed)
        self.assertTrue(receipt.auto_continue_required)

    def test_proven_irreducible_platform_boundary_can_surface(self) -> None:
        held = MissionLane("PROVIDER", LaneState.PROVIDER_HELD, recovery_exhausted=True)
        receipt = self.guard.evaluate(
            self.snapshot(
                lanes=(held,),
                final_response_requested=True,
                proposed_owner_message="Provider boundary remains after exhausted recovery.",
                platform_fault_signals=("PROVIDER_AUTHORITY_ABSENT",),
                machine_routes_exhausted=True,
                irreducible_blocker="No authorised callable provider identity",
                exhaustion_evidence_ref="proof:all-safe-routes-exhausted",
                prevention_evidence_ref="reg:owner-excuse-001",
            )
        )
        self.assertEqual(GuardDecision.BLOCKED_IRREDUCIBLY, receipt.decision)
        self.assertTrue(receipt.final_response_allowed)

    def test_genuine_owner_only_decision_not_suppressed_after_machine_work_exhausted(self) -> None:
        receipt = self.guard.evaluate(
            self.snapshot(
                final_response_requested=True,
                genuine_owner_decisions=("AUTHORIZE-IAM-EXPANSION",),
                machine_routes_exhausted=True,
            )
        )
        self.assertEqual(GuardDecision.OWNER_DECISION_REQUIRED, receipt.decision)
        self.assertTrue(receipt.final_response_allowed)


if __name__ == "__main__":
    unittest.main()
