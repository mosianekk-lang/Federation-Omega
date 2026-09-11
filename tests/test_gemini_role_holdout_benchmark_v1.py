import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COURT = ROOT / "scripts/run_gemini_role_holdout_benchmark.py"
BASE = ROOT / "scripts/run_gemini_role_matrix.py"

ROLES = (
    "ALPHA_OMEGA_REASONER",
    "CFBE_CRITIC",
    "CREATIVE_BRIEF_COMPILER",
    "DESIGNIR_VALIDATOR",
    "ROUTE_RANKER",
    "STORYBOARD_CONTINUITY_CRITIC",
    "PROVENANCE_ANALYST",
    "CHALLENGER_JUDGE",
)


class GeminiHoldoutPerformanceTests(unittest.TestCase):
    def test_extended_court_parses(self):
        ast.parse(COURT.read_text(encoding="utf-8"))

    def test_eight_task_specific_holdouts(self):
        s = COURT.read_text(encoding="utf-8")
        for role in ROLES:
            self.assertIn(f'"{role}"', s)
        self.assertIn("HOLDOUT_8_OF_8_VERIFIED", s)
        self.assertIn("task_semantic_verified", s)
        self.assertIn("unique_provider_request_ids", s)

    def test_holdout_has_protected_semantic_assertions(self):
        s = COURT.read_text(encoding="utf-8")
        for token in (
            "selected_route",
            "quality_floor_respected",
            "franchise_copy_allowed",
            "output_spec",
            "ineligible_selected",
            "continuity_break_detected",
            "consent_gap",
            "promotion",
        ):
            self.assertIn(token, s)

    def test_no_hidden_chain_of_thought_request(self):
        self.assertIn("Do not reveal hidden chain-of-thought", COURT.read_text(encoding="utf-8"))

    def test_extended_court_uses_one_access_token(self):
        s = COURT.read_text(encoding="utf-8")
        self.assertEqual(s.count('"gcloud", "auth", "print-access-token"'), 1)
        self.assertIn("single_access_token_for_both_cohorts", s)

    def test_matched_serial_parallel_court(self):
        s = COURT.read_text(encoding="utf-8")
        self.assertIn('_run_base_cohort(token, "SERIAL")', s)
        self.assertIn('_run_base_cohort(token, "PARALLEL")', s)
        self.assertIn("ThreadPoolExecutor", s)
        self.assertIn("PERFORMANCE_THRESHOLD = 2.0", s)
        self.assertIn("PERFORMANCE_2X_VERIFIED", s)
        self.assertIn("same_generation_contract", s)
        self.assertIn("unique_request_ids_across_cohorts", s)

    def test_zero_private_data_and_no_effect_receipts(self):
        s = COURT.read_text(encoding="utf-8")
        for token in (
            '"case_data_processed": False',
            '"provider_mutation_performed": False',
            '"iam_mutation_performed": False',
            '"secret_mutation_performed": False',
            '"deployment_performed": False',
            '"traffic_change_performed": False',
        ):
            self.assertIn(token, s)

    def test_base_runner_invokes_extended_court_only_in_admitted_workflow(self):
        s = BASE.read_text(encoding="utf-8")
        self.assertIn("run_gemini_role_holdout_benchmark.py", s)
        self.assertIn("GITHUB_WORKFLOW", s)
        self.assertIn("SOVARA AI Studio Direct Semantic Canary", s)
        self.assertLess(s.index("if verified != len(receipts)"), s.index("run_gemini_role_holdout_benchmark.py"))


if __name__ == "__main__":
    unittest.main()
