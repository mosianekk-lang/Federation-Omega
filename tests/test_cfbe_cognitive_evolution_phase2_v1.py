import json
import os
import unittest
from unittest.mock import patch

from benchmarking.cfbe_omega import cognitive_evolution_phase2_v1 as m


class _Resp:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


def perfect_response(spec):
    decisions = [{"case_id": c.case_id, "decision": c.expected} for c in spec.cases]
    payload = {
        "responseId": f"resp-{spec.model}-{spec.arm}-{spec.harness}",
        "modelVersion": spec.model,
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
        "candidates": [{"content": {"parts": [{"text": json.dumps({"decisions": decisions})}]}}],
    }
    return json.dumps(payload).encode()


class ContractTests(unittest.TestCase):
    def test_case_sets_are_frozen_and_unique(self):
        sets = m.case_sets()
        self.assertEqual(set(sets), set(m.HARNESSES))
        for cases in sets.values():
            self.assertEqual(len(cases), 6)
            self.assertEqual(len({c.case_id for c in cases}), 6)

    def test_expected_labels_never_enter_request(self):
        cases = m.case_sets()["H1_CORE"]
        spec = m.TrialSpec(m.MODELS[0], "AOCEF", "H1_CORE", cases)
        payload, _ = m.build_request(spec)
        raw = json.dumps(payload)
        for case in cases:
            marker = f'"expected": "{case.expected}"'
            self.assertNotIn(marker, raw)

    def test_arms_are_materially_distinct(self):
        cases = m.case_sets()["H1_CORE"]
        a, _ = m.build_request(m.TrialSpec(m.MODELS[0], "INCUMBENT", "H1_CORE", cases))
        b, _ = m.build_request(m.TrialSpec(m.MODELS[0], "AOCEF", "H1_CORE", cases))
        self.assertNotEqual(a["systemInstruction"], b["systemInstruction"])

    def test_pinned_models_only(self):
        with self.assertRaisesRegex(ValueError, "MODEL_NOT_PINNED"):
            m.TrialSpec("untrusted-model", "AOCEF", "H1_CORE", m.case_sets()["H1_CORE"]).validate()

    def test_token_cap_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "OUTPUT_TOKEN_CAP"):
            m.TrialSpec(m.MODELS[0], "AOCEF", "H1_CORE", m.case_sets()["H1_CORE"], max_output_tokens=999).validate()

    def test_duplicate_output_case_fails(self):
        spec = m.TrialSpec(m.MODELS[0], "AOCEF", "H1_CORE", m.case_sets()["H1_CORE"])
        rows = [{"case_id": spec.cases[0].case_id, "decision": "REUSE"}] * len(spec.cases)
        with self.assertRaisesRegex(RuntimeError, "MISSING_DUPLICATE_OR_UNKNOWN"):
            m.validate_output(spec, {"decisions": rows})

    def test_perfect_scoring(self):
        spec = m.TrialSpec(m.MODELS[0], "AOCEF", "H1_CORE", m.case_sets()["H1_CORE"])
        decisions = {c.case_id: c.expected for c in spec.cases}
        self.assertEqual(m.score_decisions(spec, decisions), (6, 6, 2, 2))

    def test_execution_guard_required(self):
        spec = m.TrialSpec(m.MODELS[0], "AOCEF", "H1_CORE", m.case_sets()["H1_CORE"])
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "EXECUTION_GUARD"):
                m.execute_trial(spec=spec, access_token="token")

    def test_provider_receipt_does_not_record_token(self):
        spec = m.TrialSpec(m.MODELS[0], "AOCEF", "H1_CORE", m.case_sets()["H1_CORE"])
        body = perfect_response(spec)
        with patch.dict(os.environ, {"CFBE_COGEVO_PHASE2_EXECUTE": m.EXECUTION_GUARD}, clear=False):
            with patch.object(m, "urlopen", return_value=_Resp(body)):
                result = m.execute_trial(spec=spec, access_token="TOP-SECRET")
        serial = json.dumps(result.__dict__ if hasattr(result, "__dict__") else {
            "response_sha256": result.response_sha256,
            "output_sha256": result.output_sha256,
        })
        self.assertNotIn("TOP-SECRET", serial)
        self.assertEqual(result.accuracy, 1.0)


class ReceiptTests(unittest.TestCase):
    def result(self, model, arm, harness, accuracy=1.0, critical=1.0):
        cases = m.case_sets()[harness]
        total = len(cases)
        crit_total = sum(c.critical_fault for c in cases)
        return m.TrialResult(
            model=model, arm=arm, harness=harness,
            provider_request_id=f"r-{model}-{arm}-{harness}", model_returned=model,
            decisions={c.case_id: c.expected for c in cases},
            correct=round(accuracy * total), total=total,
            critical_faults_caught=round(critical * crit_total), critical_faults_total=crit_total,
            prompt_tokens=10, candidate_tokens=5, total_tokens=15,
            wall_time_seconds=0.5, response_sha256="a"*64, output_sha256="b"*64,
        )

    def test_no_tenx_even_with_perfect_results(self):
        rows = [self.result(model, arm, harness) for model in m.MODELS for arm in m.ARMS for harness in m.HARNESSES]
        receipt = m.compile_receipt(rows)
        self.assertFalse(receipt["ten_x_proven"])
        self.assertEqual(receipt["cey_state"], "UNSCORED_OWNER_VALUE_AND_COMPARABLE_COST_NOT_YET_VERIFIED")

    def test_advantage_candidate_requires_positive_delta_and_protected_gate(self):
        rows = []
        for model in m.MODELS:
            for harness in m.HARNESSES:
                rows.append(self.result(model, "INCUMBENT", harness, accuracy=0.5, critical=0.5))
                rows.append(self.result(model, "AOCEF", harness, accuracy=1.0, critical=1.0))
        receipt = m.compile_receipt(rows)
        self.assertEqual(receipt["state"], "PH2_EMPIRICAL_ADVANTAGE_CANDIDATE")
        self.assertGreater(receipt["accuracy_delta"], 0)
        self.assertTrue(receipt["protected_gate_passed"])

    def test_equal_performance_is_not_advantage(self):
        rows = [self.result(model, arm, harness) for model in m.MODELS for arm in m.ARMS for harness in m.HARNESSES]
        receipt = m.compile_receipt(rows)
        self.assertEqual(receipt["state"], "PH2_NO_EMPIRICAL_ADVANTAGE")

    def test_incomplete_replication_fails_closed(self):
        rows = [self.result(m.MODELS[0], "AOCEF", "H1_CORE")]
        receipt = m.compile_receipt(rows)
        self.assertEqual(receipt["state"], "PH2_INCOMPLETE_REPLICATION")
        self.assertFalse(receipt["ten_x_proven"])

    def test_transfer_floor_fails_closed(self):
        rows = []
        for model in m.MODELS:
            for harness in m.HARNESSES:
                rows.append(self.result(model, "INCUMBENT", harness, accuracy=0.5, critical=0.5))
                acc = 0.5 if (model == m.MODELS[1] and harness == "H2_ADJACENT") else 1.0
                rows.append(self.result(model, "AOCEF", harness, accuracy=acc, critical=1.0))
        receipt = m.compile_receipt(rows)
        self.assertEqual(receipt["state"], "PH2_PROTECTED_GATE_FAILED")

    def test_zero_owner_actions_and_no_mutations(self):
        rows = [self.result(model, arm, harness) for model in m.MODELS for arm in m.ARMS for harness in m.HARNESSES]
        receipt = m.compile_receipt(rows)
        self.assertEqual(receipt["owner_actions"], 0)
        for key in (
            "provider_mutation_performed", "iam_mutation_performed", "oauth_mutation_performed",
            "secret_mutation_performed", "deployment_performed", "traffic_change_performed",
            "model_training_performed", "production_self_mutation_performed",
        ):
            self.assertFalse(receipt[key])


if __name__ == "__main__":
    unittest.main()
