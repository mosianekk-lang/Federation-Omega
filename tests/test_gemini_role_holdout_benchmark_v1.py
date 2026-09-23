import ast
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_gemini_role_holdout_benchmark as holdout
COURT = ROOT / "scripts/run_gemini_role_holdout_benchmark.py"
BASE = ROOT / "scripts/run_gemini_role_matrix.py"
WORKFLOW = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"

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


    def test_holdout_case_corpus_is_frozen(self):
        self.assertEqual(
            "4adb1bf9dc1efb7965262bad1518c4247e1f10bef40783546de915a63fc7bd0a",
            holdout.FROZEN_HOLDOUT_CASES_SHA256,
        )
        self.assertEqual(
            holdout.FROZEN_HOLDOUT_CASES_SHA256,
            holdout.sha(holdout.stable(holdout.HOLDOUT_CASES)),
        )

    def test_typed_role_contracts_cover_every_holdout(self):
        self.assertEqual(set(ROLES), set(holdout.ROLE_OUTPUT_CONTRACTS))
        for role in ROLES:
            schema = holdout.ROLE_OUTPUT_CONTRACTS[role]["schema"]
            self.assertEqual("OBJECT", schema["type"])
            self.assertEqual(set(holdout.HOLDOUT_CASES[role]["required"]), set(schema["required"]))
            self.assertIn("guidance", holdout.ROLE_OUTPUT_CONTRACTS[role])

    def test_failed_role_oracles_remain_strict(self):
        self.assertTrue(holdout.semantic_holdout_pass(
            "CFBE_CRITIC",
            {"verdict": "REJECT", "quality_floor_respected": True, "reason": "frozen gate"},
        ))
        self.assertFalse(holdout.semantic_holdout_pass(
            "CFBE_CRITIC",
            {"verdict": "REJECT", "quality_floor_respected": False, "reason": "wrong field semantics"},
        ))
        self.assertTrue(holdout.semantic_holdout_pass(
            "PROVENANCE_ANALYST",
            {"provenance_state": "HOLD", "consent_gap": True, "release_allowed": False},
        ))
        self.assertFalse(holdout.semantic_holdout_pass(
            "PROVENANCE_ANALYST",
            {"provenance_state": "HOLD", "consent_gap": "missing", "release_allowed": False},
        ))
        self.assertTrue(holdout.semantic_holdout_pass(
            "CHALLENGER_JUDGE",
            {"winner": "A", "promotion": False, "regressions": ["safety", "latency"]},
        ))
        self.assertFalse(holdout.semantic_holdout_pass(
            "CHALLENGER_JUDGE",
            {"winner": "B", "promotion": True, "regressions": []},
        ))

    def test_failed_role_field_semantics_are_explicit(self):
        s = COURT.read_text(encoding="utf-8")
        for token in (
            "If the candidate violates the floor and you reject or hold it",
            "consent_gap is a boolean",
            "quality and safety are higher-is-better; latency is lower-is-better",
            '"responseSchema": output_contract["schema"]',
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

    def test_workflow_reexecutes_when_holdout_harness_changes(self):
        if not WORKFLOW.exists():
            self.skipTest("Phoenix Core export intentionally excludes repository workflow controls")
        s = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('scripts/run_gemini_role_holdout_benchmark.py', s)

    def test_base_runner_invokes_extended_court_only_in_admitted_workflow(self):
        s = BASE.read_text(encoding="utf-8")
        self.assertIn("run_gemini_role_holdout_benchmark.py", s)
        self.assertIn("GITHUB_WORKFLOW", s)
        self.assertIn("SOVARA AI Studio Direct Semantic Canary", s)
        self.assertLess(s.index("if verified != len(receipts)"), s.index("run_gemini_role_holdout_benchmark.py"))


if __name__ == "__main__":
    unittest.main()
