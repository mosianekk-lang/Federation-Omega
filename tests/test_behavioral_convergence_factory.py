import unittest

from ao_harmonic_v3.behavioral_convergence_factory import (
    BehavioralCandidate,
    BehavioralConvergenceFactory,
    CandidateDisposition,
)
from ao_harmonic_v3.failure_win_v2 import FailureEventType


class BehavioralConvergenceFactoryTests(unittest.TestCase):
    def candidate(self, receiver_id="Receiver", event_id="E1", **overrides):
        values = dict(
            receiver_id=receiver_id,
            event_id=event_id,
            event_type=FailureEventType.FAILURE,
            semantic_surface="receiver native runtime behavior",
            recovery_semantic_surface="receiver native runtime behavior",
            objective="Recover the real receiver behavior with independent proof",
            failure_preserved=True,
            current=True,
            proof_fresh=True,
            material=True,
            authority_ready=True,
            rollback_available=True,
            independent_readback_available=True,
            closure_leverage=0.8,
            information_gain=0.8,
            success_probability=0.8,
            reversibility=0.9,
        )
        values.update(overrides)
        return BehavioralCandidate(**values)

    def test_last_run_failure_classes_are_filtered_before_execution(self):
        formation = self.candidate(
            "FORMATION-OMEGA",
            "FORMATION-PYTEST-EXPORT-FAILURE",
            semantic_surface="phoenix standalone core export",
            recovery_semantic_surface="phoenix standalone core export",
            evidence_refs=("github:airlock:failed-export",),
        )
        apps_script = self.candidate(
            "Google Apps Script",
            "APPS-SCRIPT-CLASPRC-MISSING",
            semantic_surface="apps script source authority",
            recovery_semantic_surface="apps script source authority",
            owner_authority_required=True,
            authority_ready=False,
        )
        jarvis = self.candidate(
            "JARVIS",
            "JARVIS-MONKEYPATCH-CONTAMINATION",
            test_harness_only=True,
        )
        bubbles = self.candidate(
            "Bubbles",
            "BUBBLES-DISABLED-LEGACY-WORKFLOW",
            admission_only=True,
        )

        plan = BehavioralConvergenceFactory().plan((formation, apps_script, jarvis, bubbles))
        by_event = {item.event_id: item.disposition for item in plan.assessments}

        self.assertEqual(by_event[formation.event_id], CandidateDisposition.EXECUTABLE_RECOVERY)
        self.assertEqual(by_event[apps_script.event_id], CandidateDisposition.HOLD_AUTHORITY)
        self.assertEqual(by_event[jarvis.event_id], CandidateDisposition.REJECT_TEST_HARNESS_ONLY)
        self.assertEqual(by_event[bubbles.event_id], CandidateDisposition.REJECT_ADMISSION_ONLY)
        self.assertEqual(plan.selected_event_ids, (formation.event_id,))

    def test_semantic_surface_mismatch_fails_closed(self):
        candidate = self.candidate(
            semantic_surface="formation amcf runtime",
            recovery_semantic_surface="bubbles cloud run operator",
        )
        assessment = BehavioralConvergenceFactory.classify(candidate)
        self.assertEqual(assessment.disposition, CandidateDisposition.REJECT_SURFACE_MISMATCH)

    def test_success_only_and_synthetic_evidence_cannot_enter_recovery_wave(self):
        success_only = self.candidate("Bubbles", "SUCCESS-ONLY", success_only=True)
        synthetic = self.candidate("TruthGrid", "SYNTHETIC", synthetic_only=True)
        plan = BehavioralConvergenceFactory().plan((success_only, synthetic))
        self.assertEqual(plan.selected_event_ids, ())
        self.assertEqual(plan.assessments[0].disposition, CandidateDisposition.REJECT_SUCCESS_ONLY)
        self.assertEqual(plan.assessments[1].disposition, CandidateDisposition.REJECT_SYNTHETIC_ONLY)

    def test_missing_rollback_or_readback_is_held_not_promoted(self):
        no_rollback = self.candidate("CASEFORGE", "NO-ROLLBACK", rollback_available=False)
        no_readback = self.candidate("TruthGrid", "NO-READBACK", independent_readback_available=False)
        plan = BehavioralConvergenceFactory().plan((no_rollback, no_readback))
        self.assertEqual(plan.selected_event_ids, ())
        self.assertEqual(plan.assessments[0].disposition, CandidateDisposition.HOLD_ROLLBACK)
        self.assertEqual(plan.assessments[1].disposition, CandidateDisposition.HOLD_READBACK)

    def test_owner_burden_reduces_rank_when_other_value_is_equal(self):
        low_burden = self.candidate("EvidenceOps", "LOW-BURDEN", owner_burden=0.0)
        high_burden = self.candidate("CASEFORGE", "HIGH-BURDEN", owner_burden=3.0)
        plan = BehavioralConvergenceFactory(max_parallel=2).plan((high_burden, low_burden))
        self.assertEqual(plan.selected_event_ids, ("LOW-BURDEN", "HIGH-BURDEN"))

    def test_parallel_wave_serializes_shared_receiver_state(self):
        first = self.candidate("TruthGrid", "TG-HIGH", closure_leverage=0.95)
        second = self.candidate("TruthGrid", "TG-LOW", closure_leverage=0.40)
        third = self.candidate("CFBE", "CFBE-HIGH", closure_leverage=0.90)
        plan = BehavioralConvergenceFactory(max_parallel=3).plan((second, third, first))
        self.assertEqual(plan.selected_event_ids, ("TG-HIGH", "CFBE-HIGH"))
        self.assertEqual(plan.selected_receiver_ids, ("TruthGrid", "CFBE"))


if __name__ == "__main__":
    unittest.main()
