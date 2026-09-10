from __future__ import annotations

import unittest

from federation.cfbe_prompt_compiler_v4 import CONSTITUTIONAL_INVARIANTS, CompilerError
from federation.cfbe_prompt_scientist_v1 import (
    Diagnosis,
    EvaluationDimensions,
    PromptCandidate,
    PromptEvaluation,
    PromptRunMetrics,
    PromptScientist,
    score_weight_total,
)


def dimensions(score: float) -> EvaluationDimensions:
    return EvaluationDimensions(
        completion=score,
        correctness=score,
        proof=score,
        execution_efficiency=score,
        parallel_utilization=score,
        owner_burden=score,
        recovery=score,
        context_efficiency=score,
        creative_freedom=score,
    )


class PromptScientistV1Tests(unittest.TestCase):
    def test_weights_total_100(self):
        self.assertEqual(score_weight_total(), 100)

    def test_diagnoses_observed_execution_failures(self):
        metrics = PromptRunMetrics(
            prompt_version="v2.1",
            mission_class="BUILD",
            task_complexity=5,
            packets_created=5,
            parallelizable_packets=4,
            achieved_parallelism=1,
            tool_calls=10,
            duplicate_tool_calls=3,
            owner_interventions=1,
            premature_stop=True,
            status_only_output=True,
            unsupported_claims=1,
            repeated_failure_fingerprints=1,
            learning_events_missing=1,
        )
        findings = set(PromptScientist.diagnose(metrics))
        self.assertTrue({
            Diagnosis.PREMATURE_STOP,
            Diagnosis.STATUS_THEATRE,
            Diagnosis.PROOF_FAILURE,
            Diagnosis.MISSED_PARALLELISM,
            Diagnosis.REPEATED_FAILURE,
            Diagnosis.TOOL_OVERUSE,
            Diagnosis.OWNER_BURDEN,
            Diagnosis.LEARNING_FAILURE,
        } <= findings)

    def test_challengers_preserve_constitutional_invariants(self):
        metrics = PromptRunMetrics(prompt_version="v2.1", mission_class="DEPLOY", task_complexity=4)
        challengers = PromptScientist.generate_challengers(metrics, (Diagnosis.PROOF_FAILURE,))
        self.assertEqual(len(challengers), 3)
        for candidate in challengers:
            self.assertEqual(candidate.protected_invariants, CONSTITUTIONAL_INVARIANTS)
            candidate.validate()

    def test_constitutional_invariant_deletion_fails_closed(self):
        reduced = frozenset(set(CONSTITUTIONAL_INVARIANTS) - {"PROOF_BEFORE_CLAIM"})
        candidate = PromptCandidate("bad", "BUILD", "v2.1", ("SHORTER",), reduced)
        with self.assertRaisesRegex(CompilerError, "CONSTITUTIONAL_INVARIANT_REGRESSION"):
            candidate.validate()

    def test_superior_green_challenger_promotes(self):
        incumbent = PromptEvaluation("P0", dimensions(0.70), ("baseline",))
        candidate = PromptCandidate("P2", "BUILD", "P0", ("PARALLELIZE",))
        challenger = PromptEvaluation("P2", dimensions(0.80), ("matched-mission",), regression_green=True)
        decision = PromptScientist.select_for_promotion(incumbent=incumbent, challengers=((candidate, challenger),))
        self.assertEqual(decision.state, "PROMPT_PROMOTED")
        self.assertEqual(decision.selected_candidate_id, "P2")
        self.assertGreaterEqual(decision.delta, 3.0)

    def test_critical_regression_vetoes_even_high_score(self):
        incumbent = PromptEvaluation("P0", dimensions(0.60), ("baseline",))
        candidate = PromptCandidate("P3", "BUILD", "P0", ("STRUCTURAL",))
        challenger = PromptEvaluation("P3", dimensions(0.99), ("eval",), critical_regression=True)
        decision = PromptScientist.select_for_promotion(incumbent=incumbent, challengers=((candidate, challenger),))
        self.assertEqual(decision.state, "PROMPT_RETAINED")
        self.assertEqual(decision.selected_candidate_id, "P0")


if __name__ == "__main__":
    unittest.main()
