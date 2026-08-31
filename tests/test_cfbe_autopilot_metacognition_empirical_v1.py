from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.autopilot_metacognition_empirical_court_v1 import (
    EvidenceMode,
    MetaCognitionPair,
    ResumeObservation,
    evaluate_empirical_court,
    frontier_bridge,
    measurement_contract,
)


HEAD = "a" * 40


def pair(index: int, *, mode: EvidenceMode = EvidenceMode.HOSTED_SHADOW, **changes: object) -> MetaCognitionPair:
    payload: dict[str, object] = {
        "pair_id": f"pair-{index}",
        "source_head_sha": HEAD,
        "task_signature": f"task-{index}",
        "evidence_mode": mode,
        "baseline_quality": 0.70,
        "candidate_quality": 0.78,
        "baseline_elapsed_ms": 100.0,
        "candidate_elapsed_ms": 120.0,
        "baseline_owner_interventions": 2,
        "candidate_owner_interventions": 1,
        "candidate_reflection_used": True,
        "candidate_confidence": 0.90,
        "candidate_outcome_correct": index % 10 != 0,
        "independent_readback": True,
        "proof_refs": (f"baseline:{index}", f"candidate:{index}"),
    }
    payload.update(changes)
    return MetaCognitionPair(**payload)


def resume(index: int, *, mode: EvidenceMode = EvidenceMode.HOSTED_SHADOW, **changes: object) -> ResumeObservation:
    payload: dict[str, object] = {
        "observation_id": f"resume-{index}",
        "source_head_sha": HEAD,
        "evidence_mode": mode,
        "process_before": f"process-{index}-before",
        "process_after": f"process-{index}-after",
        "checkpoint_id": f"checkpoint-{index}",
        "resumed": True,
        "duplicate_effect_count": 0,
        "state_drift": False,
        "independent_readback": True,
        "proof_refs": (f"checkpoint:{index}", f"readback:{index}"),
    }
    payload.update(changes)
    return ResumeObservation(**payload)


def court(mode: EvidenceMode):
    return evaluate_empirical_court(
        source_head_sha=HEAD,
        paired_cases=[pair(i, mode=mode) for i in range(30)],
        resume_cases=[resume(i, mode=mode) for i in range(10)],
    )


class AutoPilotMetaCognitionEmpiricalCourtV1Tests(unittest.TestCase):
    def test_measurement_contract_has_exact_five_empirical_axes_without_private_reasoning(self) -> None:
        contract = measurement_contract()
        self.assertEqual(5, len(contract.required_proof_axes))
        self.assertEqual(
            {
                "paired_reflection_vs_no_reflection",
                "confidence_vs_resolved_outcome",
                "cross_process_checkpoint_resume",
                "owner_intervention_delta",
                "independent_readback",
            },
            set(contract.required_proof_axes),
        )
        self.assertIn("private_chain_of_thought_is_not_required_or_recorded", contract.truth_boundary)

    def test_synthetic_shadow_can_only_reach_structural_qualification(self) -> None:
        receipt = court(EvidenceMode.SYNTHETIC_SHADOW)
        self.assertEqual("STRUCTURAL_ONLY_SYNTHETIC_SHADOW", receipt.decision)
        self.assertTrue(receipt.structure_qualified)
        self.assertFalse(receipt.hosted_shadow_qualified)
        self.assertFalse(receipt.observed_empirical_candidate)
        self.assertFalse(receipt.provider_runtime_candidate)
        self.assertFalse(receipt.full_autopilot_runtime_proven)

    def test_hosted_shadow_qualifies_without_observed_or_provider_inheritance(self) -> None:
        receipt = court(EvidenceMode.HOSTED_SHADOW)
        self.assertEqual("HOSTED_SHADOW_METACOG_QUALIFIED", receipt.decision)
        self.assertTrue(receipt.structure_qualified)
        self.assertTrue(receipt.hosted_shadow_qualified)
        self.assertFalse(receipt.observed_empirical_candidate)
        self.assertFalse(receipt.provider_runtime_candidate)

    def test_observed_operational_cohort_reaches_empirical_candidate_only(self) -> None:
        receipt = court(EvidenceMode.OBSERVED_OPERATIONAL)
        self.assertEqual("OBSERVED_METACOG_EMPIRICAL_CANDIDATE", receipt.decision)
        self.assertTrue(receipt.observed_empirical_candidate)
        self.assertFalse(receipt.provider_runtime_candidate)
        self.assertFalse(receipt.full_autopilot_runtime_proven)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_authorized)

    def test_provider_native_resume_reaches_runtime_candidate_not_full_autopilot(self) -> None:
        receipt = court(EvidenceMode.PROVIDER_NATIVE)
        self.assertEqual("PROVIDER_RUNTIME_METACOG_CANDIDATE", receipt.decision)
        self.assertTrue(receipt.provider_runtime_candidate)
        self.assertFalse(receipt.full_autopilot_runtime_proven)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_authorized)

    def test_pairwise_quality_regression_is_blocking_even_if_aggregate_gain_survives(self) -> None:
        pairs = [pair(i) for i in range(30)]
        pairs[0] = pair(0, candidate_quality=0.40)
        receipt = evaluate_empirical_court(
            source_head_sha=HEAD,
            paired_cases=pairs,
            resume_cases=[resume(i) for i in range(10)],
        )
        self.assertEqual("HOLD_EMPIRICAL_GATES_OPEN", receipt.decision)
        self.assertIn("PAIRWISE_DECISION_QUALITY_REGRESSION", receipt.blockers)

    def test_bad_confidence_calibration_is_blocking(self) -> None:
        pairs = [pair(i, candidate_confidence=0.95, candidate_outcome_correct=False) for i in range(30)]
        receipt = evaluate_empirical_court(
            source_head_sha=HEAD,
            paired_cases=pairs,
            resume_cases=[resume(i) for i in range(10)],
        )
        self.assertIn("CONFIDENCE_BRIER_SCORE_ABOVE_CEILING", receipt.blockers)
        self.assertIn("CONFIDENCE_CALIBRATION_ERROR_ABOVE_CEILING", receipt.blockers)
        self.assertFalse(receipt.observed_empirical_candidate)

    def test_resume_must_be_cross_process_without_duplicate_effect_or_state_drift(self) -> None:
        resumes = [resume(i) for i in range(10)]
        resumes[0] = resume(0, process_after="process-0-before", duplicate_effect_count=1, state_drift=True)
        receipt = evaluate_empirical_court(
            source_head_sha=HEAD,
            paired_cases=[pair(i) for i in range(30)],
            resume_cases=resumes,
        )
        self.assertIn("CROSS_PROCESS_RESUME_INCOMPLETE", receipt.blockers)
        self.assertIn("DUPLICATE_EFFECT_ON_RESUME", receipt.blockers)
        self.assertIn("STATE_DRIFT_ON_RESUME", receipt.blockers)

    def test_independent_readback_is_required_across_pair_and_resume_evidence(self) -> None:
        pairs = [pair(i) for i in range(30)]
        pairs[0] = pair(0, independent_readback=False)
        receipt = evaluate_empirical_court(
            source_head_sha=HEAD,
            paired_cases=pairs,
            resume_cases=[resume(i) for i in range(10)],
        )
        self.assertIn("INDEPENDENT_READBACK_INCOMPLETE", receipt.blockers)
        self.assertFalse(receipt.structure_qualified)

    def test_minimum_pair_and_resume_samples_are_blocking(self) -> None:
        receipt = evaluate_empirical_court(
            source_head_sha=HEAD,
            paired_cases=[pair(i) for i in range(29)],
            resume_cases=[resume(i) for i in range(9)],
        )
        self.assertIn("MINIMUM_PAIRED_METACOG_CASES_REQUIRED", receipt.blockers)
        self.assertIn("MINIMUM_CROSS_PROCESS_RESUME_CASES_REQUIRED", receipt.blockers)

    def test_duplicate_ids_fail_closed(self) -> None:
        pairs = [pair(i) for i in range(30)]
        pairs[-1] = pair(0)
        with self.assertRaisesRegex(ValueError, "METACOG_PAIR_IDS_MUST_BE_UNIQUE"):
            evaluate_empirical_court(
                source_head_sha=HEAD,
                paired_cases=pairs,
                resume_cases=[resume(i) for i in range(10)],
            )

    def test_source_head_mismatch_fails_closed(self) -> None:
        pairs = [pair(i) for i in range(30)]
        pairs[0] = pair(0, source_head_sha="b" * 40)
        with self.assertRaisesRegex(ValueError, "METACOG_PAIR_SOURCE_HEAD_MISMATCH"):
            evaluate_empirical_court(
                source_head_sha=HEAD,
                paired_cases=pairs,
                resume_cases=[resume(i) for i in range(10)],
            )

    def test_receipt_digest_is_deterministic(self) -> None:
        first = court(EvidenceMode.HOSTED_SHADOW)
        second = court(EvidenceMode.HOSTED_SHADOW)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_frontier_bridge_preserves_owner_value_and_effect_authority_boundaries(self) -> None:
        receipt = court(EvidenceMode.PROVIDER_NATIVE)
        bridge = frontier_bridge(receipt)
        self.assertTrue(bridge["durable_runtime"]["provider_runtime_candidate"])
        self.assertFalse(bridge["durable_runtime"]["full_autopilot_runtime_proven"])
        self.assertFalse(bridge["owner_value"]["owner_value_proven"])
        self.assertFalse(bridge["provider_effect_authorized"])
        self.assertFalse(bridge["stable_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
