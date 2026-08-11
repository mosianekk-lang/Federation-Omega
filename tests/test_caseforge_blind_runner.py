from __future__ import annotations

import unittest

from evidenceops.caseforge.blind_runner import (
    BlindIsolationError,
    CONTROL_MARKER,
    HiddenControlScorer,
    IsolatedBlindRunner,
    ModelBinding,
    assert_blind_payload,
)


def scores(value: float = 0.9) -> dict[str, float]:
    return {
        "legal_route": value,
        "evidence_integrity": value,
        "authority_quality": value,
        "fact_chronology": value,
        "contradiction_reasoning": value,
        "adversarial_resilience": value,
        "remedy_procedure": value,
        "uncertainty_calibration": value,
        "traceability": value,
    }


BLIND = {
    "case_id": "CF-TEST-001",
    "research_question": "Which explanation is best supported?",
    "observations": [
        {"id": "O1", "statement": "service is unavailable", "state": "USER_SUPPLIED"}
    ],
}

CONTROL = {
    "case_id": "CF-TEST-001",
    "answer_key": {"required": ["separate verified facts from hypotheses"]},
    "scoring_requirements": {"evidence_integrity": ["preserve uncertainty"]},
    "fatal_tests": ["FABRICATED_AUTHORITY"],
}


class EchoAgent:
    def __init__(self) -> None:
        self.seen_payload = None
        self.seen_context = None

    def analyze(self, blind_payload, context):
        self.seen_payload = blind_payload
        self.seen_context = context
        return {
            "case_id": context.case_id,
            "blind_sha": context.blind_input_sha256,
            "analysis": "insufficient primary evidence; retain competing hypotheses",
        }


class MutatingAgent:
    def analyze(self, blind_payload, context):
        blind_payload["injected"] = True
        return {"analysis": "mutation attempted"}


class BlindRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = IsolatedBlindRunner()
        self.binding = ModelBinding(
            provider="deterministic-test-double",
            model="echo-agent",
            version="1.0",
            configuration={"temperature": 0, "mode": "test"},
        )

    def test_answer_key_and_nested_control_leakage_are_rejected(self) -> None:
        with self.assertRaisesRegex(BlindIsolationError, "leakage"):
            assert_blind_payload({"case_id": "C", "nested": {"answer_key": "secret"}})
        with self.assertRaisesRegex(BlindIsolationError, "leakage"):
            assert_blind_payload({"case_id": "C", "nested": {"answerKey": "secret"}})
        with self.assertRaisesRegex(BlindIsolationError, "leakage"):
            assert_blind_payload({"case_id": "C", "text": f"x {CONTROL_MARKER} y"})

    def test_tested_agent_receives_only_blind_payload_and_control_free_context(self) -> None:
        agent = EchoAgent()
        receipt = self.runner.run(
            run_id="RUN-1",
            blind_payload=BLIND,
            agent=agent,
            model_binding=self.binding,
        )
        self.assertEqual(set(BLIND), set(agent.seen_payload))
        self.assertNotIn("answer_key", agent.seen_payload)
        context_keys = set(vars(agent.seen_context))
        self.assertFalse(any("control" in key or "answer" in key for key in context_keys))
        self.assertTrue(receipt.input_unchanged)
        self.assertFalse(receipt.external_effect)
        self.assertEqual("A1_INTERNAL", receipt.authority_ceiling)

    def test_two_isolated_runs_reproduce_input_and_output_hashes(self) -> None:
        first = self.runner.run(
            run_id="RUN-A",
            blind_payload=BLIND,
            agent=EchoAgent(),
            model_binding=self.binding,
        )
        second = self.runner.run(
            run_id="RUN-B",
            blind_payload=BLIND,
            agent=EchoAgent(),
            model_binding=self.binding,
        )
        self.assertEqual(first.blind_input_sha256, second.blind_input_sha256)
        self.assertEqual(first.tested_output_sha256, second.tested_output_sha256)
        self.assertEqual(first.configuration_sha256, second.configuration_sha256)
        self.assertNotEqual(first.run_id, second.run_id)

    def test_model_identity_version_and_configuration_are_receipt_bound(self) -> None:
        receipt = self.runner.run(
            run_id="RUN-MODEL",
            blind_payload=BLIND,
            agent=EchoAgent(),
            model_binding=self.binding,
        )
        self.assertEqual("deterministic-test-double", receipt.provider)
        self.assertEqual("echo-agent", receipt.model)
        self.assertEqual("1.0", receipt.version)
        self.assertEqual(64, len(receipt.configuration_sha256))
        self.assertEqual("DETERMINISTIC_TEST_ONLY", receipt.execution_state)

    def test_provider_verified_state_requires_provider_native_readback_reference(self) -> None:
        binding = ModelBinding(
            provider="provider-x",
            model="model-y",
            version="2026-08",
            configuration={},
            execution_state="PROVIDER_VERIFIED",
        )
        with self.assertRaisesRegex(BlindIsolationError, "provider readback"):
            self.runner.run(
                run_id="RUN-PROVIDER",
                blind_payload=BLIND,
                agent=EchoAgent(),
                model_binding=binding,
            )

    def test_tested_agent_cannot_mutate_blind_input(self) -> None:
        with self.assertRaisesRegex(BlindIsolationError, "mutated"):
            self.runner.run(
                run_id="RUN-MUTATION",
                blind_payload=BLIND,
                agent=MutatingAgent(),
                model_binding=self.binding,
            )
        self.assertNotIn("injected", BLIND)

    def test_hidden_scorer_evaluates_without_modifying_tested_output(self) -> None:
        run = self.runner.run(
            run_id="RUN-SCORE",
            blind_payload=BLIND,
            agent=EchoAgent(),
            model_binding=self.binding,
        )
        original_output = dict(run.tested_output)
        scorer = HiddenControlScorer(
            scorer_id="caseforge-control-scorer",
            scorer_version="1.0",
            control_pack=CONTROL,
        )
        scored = scorer.score(blind_run=run, competency_scores=scores())
        self.assertEqual("PASS", scored.decision)
        self.assertTrue(scored.output_unchanged_by_scorer)
        self.assertEqual(original_output, run.tested_output)
        self.assertEqual(64, len(scored.control_sha256))
        self.assertFalse(scored.external_effect)

    def test_fatal_integrity_event_overrides_perfect_numeric_score(self) -> None:
        run = self.runner.run(
            run_id="RUN-FATAL",
            blind_payload=BLIND,
            agent=EchoAgent(),
            model_binding=self.binding,
        )
        scorer = HiddenControlScorer(
            scorer_id="caseforge-control-scorer",
            scorer_version="1.0",
            control_pack=CONTROL,
        )
        scored = scorer.score(
            blind_run=run,
            competency_scores=scores(1.0),
            fatal_events=["FABRICATED_AUTHORITY"],
        )
        self.assertEqual(1.0, scored.score)
        self.assertEqual("FAIL_FATAL", scored.decision)
        self.assertEqual(("FABRICATED_AUTHORITY",), scored.fatal_failures)

    def test_blind_and_control_case_identity_must_match(self) -> None:
        run = self.runner.run(
            run_id="RUN-MISMATCH",
            blind_payload=BLIND,
            agent=EchoAgent(),
            model_binding=self.binding,
        )
        scorer = HiddenControlScorer(
            scorer_id="scorer",
            scorer_version="1.0",
            control_pack={"case_id": "OTHER", "answer_key": {}},
        )
        with self.assertRaisesRegex(BlindIsolationError, "case mismatch"):
            scorer.score(blind_run=run, competency_scores=scores())


if __name__ == "__main__":
    unittest.main()
