from pathlib import Path
import tempfile
import unittest

from federation.autonomic_completion_v5 import (
    AutonomicCompletionKernel,
    ExecutionContext,
    OutputClass,
    RuntimeMode,
    WorkPacket,
)
from federation.finality_guard_v1 import (
    FalseFinalityError,
    FinalityPresentationGuard,
    MissionPresentationState,
    TerminalAcceptance,
)
from federation.federation_learning_v1 import FederationLearningLedger
from federation.prompt_scientist_v2 import PromptGenome
from federation.run_store_v1 import RunStore


def genome():
    return PromptGenome(
        "V5.0.2-NFF",
        "V5.0.1",
        {
            "OWNER_AUTHORITY": "IMMUTABLE",
            "PROOF_FLOOR": "IMMUTABLE",
            "SECURITY_FLOOR": "IMMUTABLE",
            "PRIVACY_FLOOR": "IMMUTABLE",
            "TRUTH_BOUNDARIES": "IMMUTABLE",
            "PROVIDER_NATIVE_PROOF": "IMMUTABLE",
            "ROLLBACK_REQUIREMENTS": "IMMUTABLE",
            "OUTPUT_POLICY": "NO_FALSE_FINALITY",
            "RUNTIME_REENTRY": "PERSIST_OR_RESUME_CAPSULE",
            "LEARNING_CALLBACK": "EACH_MATERIAL_CYCLE",
        },
    )


class FinalityPresentationGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = FinalityPresentationGuard()

    def test_progress_is_forced_to_active_build(self):
        decision = self.guard.classify(
            output_class="PROGRESS_UPDATE",
            next_ready_packets=("V6", "V7"),
        )
        self.assertEqual(decision.state, MissionPresentationState.ACTIVE_BUILD)
        self.assertFalse(decision.terminal_reached)
        self.assertFalse(decision.completion_style_allowed)
        self.assertTrue(decision.mission_must_continue)
        self.assertEqual(decision.banner, "STATE: ACTIVE_BUILD")
        self.assertEqual(decision.terminal_line, "TERMINAL: NOT REACHED")

    def test_terminal_report_without_proof_fails_closed(self):
        with self.assertRaisesRegex(FalseFinalityError, "TERMINAL_REPORT_REQUIRES_PROOF_REF"):
            self.guard.classify(
                output_class="TERMINAL_REPORT",
                terminal_state="COMPLETE_VERIFIED",
            )

    def test_terminal_report_with_verified_proof_allows_completion_style(self):
        decision = self.guard.classify(
            output_class="TERMINAL_REPORT",
            terminal_state="COMPLETE_VERIFIED",
            terminal_proof_ref="proof:f130:verified",
        )
        self.assertEqual(decision.state, MissionPresentationState.TERMINAL_VERIFIED)
        self.assertTrue(decision.terminal_reached)
        self.assertTrue(decision.completion_style_allowed)
        self.assertFalse(decision.mission_must_continue)

    def test_success_state_cannot_hide_inside_progress_output(self):
        with self.assertRaisesRegex(
            FalseFinalityError,
            "SUCCESS_TERMINAL_STATE_CANNOT_BE_RENDERED_AS_NON_TERMINAL_OUTPUT",
        ):
            self.guard.classify(
                output_class="PROGRESS_UPDATE",
                terminal_state="COMPLETE_VERIFIED",
                terminal_proof_ref="proof:terminal",
            )

    def test_owner_decision_is_not_completion(self):
        decision = self.guard.classify(
            output_class="OWNER_DECISION",
            terminal_state="IRREDUCIBLE_OWNER_DECISION",
        )
        self.assertEqual(decision.state, MissionPresentationState.OWNER_DECISION_REQUIRED)
        self.assertFalse(decision.completion_style_allowed)
        self.assertTrue(decision.mission_must_continue)


class AutonomicKernelNoFalseFinalityTests(unittest.TestCase):
    def kernel(self, td, **kwargs):
        return AutonomicCompletionKernel(
            RunStore(Path(td) / "run.db"),
            FederationLearningLedger(Path(td) / "learn.jsonl"),
            **kwargs,
        )

    def context(self, mission_id="NFF-M1", target="COMPLETE_VERIFIED"):
        return ExecutionContext(
            mission_id,
            "BUILD",
            target,
            RuntimeMode.CURRENT_RUN,
            genome(),
            (WorkPacket("BUILD"),),
        )

    def test_packet_exhaustion_is_not_terminal_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            kernel = self.kernel(td)
            result = kernel.run_cycle(
                self.context(),
                cycle=1,
                packet_executor=lambda p: (True, "proof:build"),
            )
            self.assertEqual(result.terminal_state, "")
            self.assertEqual(result.telemetry.output_class, OutputClass.PROGRESS_UPDATE.value)
            self.assertEqual(result.presentation_state, MissionPresentationState.ACTIVE_BUILD.value)
            self.assertFalse(result.completion_style_allowed)
            self.assertTrue(result.mission_must_continue)
            self.assertTrue(result.recompile_required)
            self.assertEqual(result.maturity_gaps, ("TERMINAL_ACCEPTANCE_COURT_REQUIRED",))
            self.assertEqual(result.terminal_proof_ref, "")

    def test_nonterminal_packet_exhaustion_at_platform_boundary_emits_resume_not_finality(self):
        with tempfile.TemporaryDirectory() as td:
            kernel = self.kernel(td)
            ctx = ExecutionContext(
                "NFF-RESUME",
                "BUILD",
                "COMPLETE_VERIFIED",
                RuntimeMode.NO_PERSISTENT_RUNNER,
                genome(),
                (WorkPacket("BUILD"),),
            )
            result = kernel.run_cycle(
                ctx,
                cycle=1,
                packet_executor=lambda p: (True, "proof:build"),
                force_platform_boundary=True,
            )
            self.assertEqual(result.terminal_state, "")
            self.assertEqual(result.telemetry.output_class, OutputClass.RESUME_CAPSULE.value)
            self.assertIsNotNone(result.resume_capsule)
            self.assertEqual(
                result.presentation_state,
                MissionPresentationState.ACTIVE_RESUME_REQUIRED.value,
            )
            self.assertFalse(result.completion_style_allowed)
            self.assertTrue(result.mission_must_continue)

    def test_explicit_terminal_court_can_release_terminal_report(self):
        with tempfile.TemporaryDirectory() as td:
            def terminal_court(ctx):
                return TerminalAcceptance(
                    verified=True,
                    state=ctx.target_state,
                    proof_ref="proof:f130:terminal",
                )

            kernel = self.kernel(td, terminal_acceptance_provider=terminal_court)
            result = kernel.run_cycle(
                self.context(),
                cycle=1,
                packet_executor=lambda p: (True, "proof:build"),
            )
            self.assertEqual(result.terminal_state, "COMPLETE_VERIFIED")
            self.assertEqual(result.telemetry.output_class, OutputClass.TERMINAL_REPORT.value)
            self.assertEqual(result.terminal_proof_ref, "proof:f130:terminal")
            self.assertEqual(result.presentation_state, MissionPresentationState.TERMINAL_VERIFIED.value)
            self.assertTrue(result.completion_style_allowed)
            self.assertFalse(result.mission_must_continue)

    def test_terminal_court_without_proof_cannot_release_finality(self):
        with tempfile.TemporaryDirectory() as td:
            def bad_court(ctx):
                return TerminalAcceptance(
                    verified=True,
                    state=ctx.target_state,
                    proof_ref="",
                )

            kernel = self.kernel(td, terminal_acceptance_provider=bad_court)
            with self.assertRaisesRegex(FalseFinalityError, "TERMINAL_ACCEPTANCE_PROOF_REQUIRED"):
                kernel.run_cycle(
                    self.context(),
                    cycle=1,
                    packet_executor=lambda p: (True, "proof:build"),
                )

    def test_unverified_terminal_court_keeps_mission_active(self):
        with tempfile.TemporaryDirectory() as td:
            def open_court(ctx):
                return TerminalAcceptance(
                    verified=False,
                    state=ctx.target_state,
                    gaps=("V6_PROVIDER_READBACK", "V7_F130_SNAPSHOT"),
                )

            kernel = self.kernel(td, terminal_acceptance_provider=open_court)
            result = kernel.run_cycle(
                self.context(),
                cycle=1,
                packet_executor=lambda p: (True, "proof:build"),
            )
            self.assertEqual(result.terminal_state, "")
            self.assertEqual(result.maturity_gaps, ("V6_PROVIDER_READBACK", "V7_F130_SNAPSHOT"))
            self.assertEqual(result.presentation_state, MissionPresentationState.ACTIVE_BUILD.value)
            self.assertFalse(result.completion_style_allowed)
            self.assertTrue(result.mission_must_continue)

    def test_commercial_terminal_court_emits_proof_ref_before_terminal_style(self):
        with tempfile.TemporaryDirectory() as td:
            kernel = self.kernel(td)
            ctx = ExecutionContext(
                "NFF-COMMERCIAL",
                "BUILD",
                "COMMERCIAL_READY_VERIFIED",
                RuntimeMode.CURRENT_RUN,
                genome(),
                (WorkPacket("BUILD"),),
                current_maturity="LOCAL_TESTED",
                commercial_evidence={"FUNCTIONALITY": True},
                commercial_applicable_gates=("FUNCTIONALITY",),
            )
            result = kernel.run_cycle(
                ctx,
                cycle=1,
                packet_executor=lambda p: (True, "proof:build"),
            )
            self.assertEqual(result.terminal_state, "COMMERCIAL_READY_VERIFIED")
            self.assertTrue(result.terminal_proof_ref.startswith("commercial-maturity-court:sha256:"))
            self.assertEqual(result.presentation_state, MissionPresentationState.TERMINAL_VERIFIED.value)
            self.assertTrue(result.completion_style_allowed)


if __name__ == "__main__":
    unittest.main()
