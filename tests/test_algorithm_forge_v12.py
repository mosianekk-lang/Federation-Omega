import math
import unittest

from federation.algorithm_forge_v12 import (
    AlgorithmBundle,
    AlgorithmEvaluation,
    AlgorithmRunMetricsV1,
    CompositePolicy,
    FrozenEvalCorpus,
    ProblemFingerprint,
    federation_learning_fields,
    metrics_from_prompt_run,
    pareto_frontier,
    select_shadow_candidate,
)


class DummyPromptMetrics:
    correctness = 1.0
    proof_completeness = 1.0
    recovery_success = 0.9
    achieved_parallelism = 3
    duplicate_tool_calls = 1
    retries = 2
    owner_interventions = 0


def fp():
    return ProblemFingerprint("SOURCE_TRUST", "SERVING_EVALUATOR_BOUND", "main@abc", failure_fingerprints=("B", "A", "A")).seal()


def bundle(name="AB12-C1", parent="AB12-BASE"):
    return AlgorithmBundle.build(
        name, parent,
        {"scheduler": "critical-path", "selection": "pareto"},
        parameters={"wave": 3, "beam": 2},
        compatible_receivers=("PROMPT_SCIENTIST", "FEDERATION_LEARNING"),
        rollback_ref="AB12-BASE",
    )


def evaluation(name, rate, *, cost=0.0, wall=10.0, owner=0, corpus="corpus", sample=10, floors=True):
    return AlgorithmEvaluation(
        name, corpus, sample, rate, wall, owner, cost, 1.0, 1.0, 1.0, floors, ("proof:1",)
    )


class AlgorithmForgeV12Tests(unittest.TestCase):
    def test_problem_fingerprint_is_stable_and_dedupes_failures(self):
        a = fp()
        b = ProblemFingerprint("SOURCE_TRUST", "SERVING_EVALUATOR_BOUND", "main@abc", failure_fingerprints=("A", "B")).seal()
        self.assertEqual(a, b)
        self.assertTrue(a.verify())

    def test_problem_fingerprint_rejects_blank_required_field(self):
        with self.assertRaises(ValueError):
            ProblemFingerprint("", "P", "main").seal()

    def test_bundle_hash_is_mapping_order_invariant(self):
        a = AlgorithmBundle.build("AB", "P", {"a": 1, "b": 2}, parameters={"x": 3, "y": 4})
        b = AlgorithmBundle.build("AB", "P", {"b": 2, "a": 1}, parameters={"y": 4, "x": 3})
        self.assertEqual(a.content_sha256, b.content_sha256)
        self.assertTrue(a.verify())

    def test_bundle_protected_invariants_cannot_regress(self):
        with self.assertRaises(ValueError):
            AlgorithmBundle.build("AB", "P", {"a": 1}, protected_invariants=frozenset({"OWNER_AUTHORITY"}))

    def test_bundle_nested_policy_is_immutable_by_construction(self):
        raw = {"wave": 3}
        b = AlgorithmBundle.build("AB", "P", {"scheduler": "cp"}, parameters=raw)
        raw["wave"] = 99
        self.assertEqual(dict(b.parameters)["wave"], "3")

    def test_composite_policy_requires_all_hard_floors(self):
        p = fp()
        with self.assertRaises(ValueError):
            CompositePolicy("CP", p.fingerprint_id, ("AB",), hard_floors=("OWNER_AUTHORITY",)).seal()

    def test_composite_policy_rejects_duplicate_bundle_ids(self):
        p = fp()
        with self.assertRaises(ValueError):
            CompositePolicy("CP", p.fingerprint_id, ("AB", "AB")).seal()

    def test_metrics_reject_nan_and_negative_counters(self):
        p = fp()
        with self.assertRaises(ValueError):
            AlgorithmRunMetricsV1(p.fingerprint_id, "AB", 1, 1.0, math.nan).validate()
        with self.assertRaises(ValueError):
            AlgorithmRunMetricsV1(p.fingerprint_id, "AB", -1, 1.0, 1.0).validate()

    def test_metrics_require_positive_owner_hour_denominator(self):
        p = fp()
        with self.assertRaises(ValueError):
            AlgorithmRunMetricsV1(p.fingerprint_id, "AB", 1, 0.0, 1.0).validate()

    def test_primary_metric_is_terminal_predicates_per_owner_hour(self):
        p = fp()
        m = AlgorithmRunMetricsV1(p.fingerprint_id, "AB", 4, 0.5, 5.0).validate()
        self.assertEqual(m.terminal_predicates_per_owner_hour, 8.0)

    def test_hard_floor_requires_correctness_and_proof(self):
        p = fp()
        m = AlgorithmRunMetricsV1(p.fingerprint_id, "AB", 1, 1.0, 1.0, correctness=0.99)
        self.assertFalse(m.hard_floors_green)

    def test_frozen_corpus_requires_three_disjoint_sets(self):
        with self.assertRaises(ValueError):
            FrozenEvalCorpus(("v",), ("a",), ("v",)).freeze()
        frozen = FrozenEvalCorpus(("v",), ("a",), ("h",)).freeze()
        self.assertTrue(frozen.verify())

    def test_pareto_frontier_removes_dominated_candidate(self):
        a = evaluation("A", 2.0, wall=5.0)
        b = evaluation("B", 1.0, wall=10.0)
        self.assertEqual(tuple(e.bundle_id for e in pareto_frontier((a, b))), ("A",))

    def test_shadow_selection_requires_matched_corpus_and_samples(self):
        inc = evaluation("INC", 1.0)
        unmatched = evaluation("C", 2.0, corpus="other")
        decision = select_shadow_candidate(inc, (unmatched,))
        self.assertEqual(decision.state, "RETAIN_INCUMBENT")

    def test_shadow_selection_hard_vetoes_floor_regression(self):
        inc = evaluation("INC", 1.0)
        bad = evaluation("C", 2.0, floors=False)
        self.assertEqual(select_shadow_candidate(inc, (bad,)).state, "RETAIN_INCUMBENT")

    def test_shadow_selection_never_self_promotes(self):
        inc = evaluation("INC", 1.0)
        good = evaluation("C", 1.2)
        decision = select_shadow_candidate(inc, (good,), minimum_primary_gain=0.05)
        self.assertEqual(decision.state, "CANDIDATE_FOR_SHADOW")
        self.assertEqual(decision.selected_bundle_id, "C")

    def test_shadow_selection_rejects_negative_minimum_gain(self):
        with self.assertRaises(ValueError):
            select_shadow_candidate(evaluation("INC", 1.0), (evaluation("C", 2.0),), minimum_primary_gain=-0.1)

    def test_prompt_metrics_adapter_preserves_current_root_without_mutation(self):
        p = fp()
        m = metrics_from_prompt_run(
            DummyPromptMetrics(),
            problem_fingerprint_id=p.fingerprint_id,
            algorithm_bundle_id="AB",
            terminal_predicates_closed=2,
            owner_hours=0.5,
            wall_clock_seconds=4.0,
            evidence_refs=("receipt:1",),
            rollback_ref="AB-OLD",
        )
        self.assertEqual(m.achieved_concurrency, 3)
        self.assertEqual(m.terminal_predicates_per_owner_hour, 4.0)

    def test_federation_learning_fields_are_privacy_minimised_and_identity_bound(self):
        p = fp()
        b = bundle()
        policy = CompositePolicy("CP12-1", p.fingerprint_id, (b.bundle_id,)).seal()
        m = AlgorithmRunMetricsV1(p.fingerprint_id, b.bundle_id, 1, 1.0, 2.0, evidence_refs=("r:1",), rollback_ref="AB12-BASE")
        out = federation_learning_fields(p, b, policy, m)
        self.assertFalse(out["private_chain_of_thought_stored"])
        self.assertEqual(out["algorithm_bundle_sha256"], b.content_sha256)

    def test_federation_learning_fields_reject_identity_mismatch(self):
        p = fp()
        b = bundle()
        policy = CompositePolicy("CP12-1", p.fingerprint_id, (b.bundle_id,)).seal()
        bad = AlgorithmRunMetricsV1(p.fingerprint_id, "OTHER", 1, 1.0, 2.0, evidence_refs=("r",), rollback_ref="old")
        with self.assertRaises(ValueError):
            federation_learning_fields(p, b, policy, bad)


if __name__ == "__main__":
    unittest.main()
