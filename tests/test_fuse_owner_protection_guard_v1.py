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
        self.assertIn("UNCHANGED_FAILURE_ROUTE_RETRY:ADOBE-MCP", receipt.violations)

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
        self.assertIn("BUILD_EPOCH_MUTATED_DURING_ADMISSION:ADOBE-E1", receipt.violations)

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
        self.assertIn("OWNER_RESCUE_PREVENTION_BINDING_MISSING", receipt.violations)

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
        self.assertIn(
            "STALE_MISSION_POINTER:STRATEGIC-SECONDARY-BRAIN->MISSION-ADOBE-OMEGA",
            receipt.violations,
        )

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
        self.assertIn("PREMATURE_COMPLETION_CLAIM", receipt.violations)

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
        self.assertTrue(receipt.completion_verified)
        self.assertTrue(receipt.final_response_allowed)

    def test_genuine_owner_decision_surfaces_only_after_machine_work_exhausted(self) -> None:
        owner_only = self.guard.evaluate(
            self.snapshot(genuine_owner_decisions=("AUTHORIZE-IRREVERSIBLE-PUBLISH",))
        )
        self.assertEqual(GuardDecision.OWNER_DECISION_REQUIRED, owner_only.decision)
        self.assertTrue(owner_only.final_response_allowed)

        machine_first = self.guard.evaluate(
            self.snapshot(
                lanes=(MissionLane("SAFE-READ", LaneState.READY),),
                genuine_owner_decisions=("AUTHORIZE-IRREVERSIBLE-PUBLISH",),
            )
        )
        self.assertEqual(GuardDecision.CONTINUE_AUTOMATICALLY, machine_first.decision)
        self.assertFalse(machine_first.final_response_allowed)

    def test_irreducible_block_requires_exhaustion_evidence(self) -> None:
        held = MissionLane(
            "PROVIDER-ONLY",
            LaneState.PROVIDER_HELD,
            recovery_exhausted=True,
        )
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
        self.assertTrue(proven.final_response_allowed)

    def test_receipt_is_deterministic(self) -> None:
        snapshot = self.snapshot(lanes=(MissionLane("A", LaneState.READY),))
        first = self.guard.evaluate(snapshot)
        second = self.guard.evaluate(snapshot)
        self.assertEqual(first.receipt_digest, second.receipt_digest)

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
        self.assertEqual(GuardDecision.CONTINUE_AUTOMATICALLY, receipt.decision)


if __name__ == "__main__":
    unittest.main()
