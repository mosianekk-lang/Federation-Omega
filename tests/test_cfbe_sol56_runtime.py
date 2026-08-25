import json
import tempfile
import unittest
from pathlib import Path

from benchmarking.cfbe_omega.sol56_runtime import (
    BenchmarkCase,
    MAX_CONTEXT_TOKENS,
    MODEL_ID,
    RouteCandidate,
    RunObservation,
    evaluate_suite,
    load_observations,
    load_spec,
    nearest_rank,
    select_route,
    wilson_interval,
    write_report_atomic,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "benchmarking" / "cfbe_omega" / "sol56_benchmark_spec.json"
TEMPLATE_PATH = ROOT / "benchmarking" / "cfbe_omega" / "sol56_observations.template.jsonl"


class Sol56ContractTests(unittest.TestCase):
    def test_spec_is_complete_and_weighted(self):
        spec = load_spec(SPEC_PATH)
        self.assertEqual(len(spec["cases"]), 15)
        self.assertEqual(sum(case.weight for case in spec["cases"]), 100)
        self.assertEqual(max(case.context_tokens for case in spec["cases"]), 1_000_000)

    def test_context_over_model_limit_is_rejected(self):
        case = BenchmarkCase("X", "LONG_CONTEXT", 100, "TEST", 1, {}, MAX_CONTEXT_TOKENS + 1)
        with self.assertRaises(ValueError):
            case.validate()

    def test_provider_live_without_independent_readback_is_rejected(self):
        observation = RunObservation(
            run_id="R1", case_id="SOL56-OUTCOME-001", result_state="PASS",
            model=MODEL_ID, reasoning_effort="high", score_0_100=99,
            provider_live=True, independent_readback=False, output_hash="sha256:x",
        )
        with self.assertRaises(ValueError):
            observation.validate()

    def test_executed_run_requires_output_hash(self):
        observation = RunObservation(
            run_id="R1", case_id="SOL56-OUTCOME-001", result_state="PASS",
            model=MODEL_ID, reasoning_effort="high", score_0_100=99,
        )
        with self.assertRaises(ValueError):
            observation.validate()

    def test_template_fails_closed_without_fabricating_scores(self):
        report = evaluate_suite(load_spec(SPEC_PATH), load_observations(TEMPLATE_PATH))
        self.assertEqual(report["truth_state"], "PROVIDER_NOT_EXECUTED")
        self.assertIsNone(report["weighted_quality_0_100"])
        self.assertFalse(report["model_performance_claim_allowed"])
        self.assertEqual(report["scale_readiness"], "BLOCKED")

    def test_unknown_case_is_rejected(self):
        spec = load_spec(SPEC_PATH)
        observation = RunObservation("R", "UNKNOWN", "NOT_EXECUTED")
        with self.assertRaises(ValueError):
            evaluate_suite(spec, [observation])

    def test_nearest_rank_percentiles_are_deterministic(self):
        self.assertEqual(nearest_rank([1, 2, 3, 4, 5], 0.50), 3)
        self.assertEqual(nearest_rank([1, 2, 3, 4, 5], 0.95), 5)

    def test_wilson_interval_is_bounded(self):
        interval = wilson_interval(9, 10)
        self.assertIsNotNone(interval)
        assert interval is not None
        self.assertGreaterEqual(interval[0], 0)
        self.assertLessEqual(interval[1], 1)

    def test_atomic_report_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            write_report_atomic({"state": "PASS"}, path)
            self.assertEqual(json.loads(path.read_text()), {"state": "PASS"})
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])


class Sol56RouteTests(unittest.TestCase):
    def candidates(self):
        return [
            RouteCandidate("gpt-5.6-sol", 96, 30_000, 0.80, 0.01, True),
            RouteCandidate("gpt-5.6-terra", 88, 8_000, 0.20, 0.01, True),
            RouteCandidate("gpt-5.6-luna", 79, 2_000, 0.04, 0.01, True),
        ]

    def test_frontier_route_is_sol_only(self):
        self.assertEqual(select_route(self.candidates(), "FRONTIER").model, MODEL_ID)

    def test_bulk_route_can_choose_lighter_model(self):
        self.assertEqual(select_route(self.candidates(), "BULK").model, "gpt-5.6-luna")

    def test_unverified_candidate_is_never_selected(self):
        candidates = self.candidates() + [
            RouteCandidate("unverified-fast", 100, 1, 0, 0, False)
        ]
        self.assertNotEqual(select_route(candidates, "STANDARD").model, "unverified-fast")

    def test_quality_floor_fails_closed(self):
        with self.assertRaises(ValueError):
            select_route([RouteCandidate(MODEL_ID, 80, 1, 0, 0, True)], "FRONTIER")


if __name__ == "__main__":
    unittest.main()
