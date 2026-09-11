import ast
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RoleMatrixTests(unittest.TestCase):
    def test_contract_is_bounded(self):
        payload = json.loads(
            (ROOT / "governance/fuse_gemini_role_matrix_request_v1.json").read_text()
        )
        self.assertEqual(payload["schema"], "FUSE_GEMINI_ROLE_MATRIX_REQUEST_V1")
        self.assertEqual(payload["provider"], "GOOGLE_VERTEX_AI")
        self.assertEqual(payload["transport"], "VERTEX_WIF_ADC")
        self.assertEqual(len(payload["roles"]), 8)
        self.assertEqual(len(set(payload["roles"])), 8)
        self.assertLessEqual(payload["max_parallel_requests"], 4)
        for key in (
            "case_data_allowed",
            "provider_mutation_allowed",
            "iam_mutation_allowed",
            "secret_mutation_allowed",
            "deployment_allowed",
            "traffic_change_allowed",
            "external_communication_allowed",
        ):
            self.assertFalse(payload[key])

    def test_runner_parses(self):
        ast.parse((ROOT / "scripts/run_gemini_role_matrix.py").read_text())

    def test_runner_one_access_token_and_parallel_pool(self):
        source = (ROOT / "scripts/run_gemini_role_matrix.py").read_text()
        self.assertEqual(source.count("print-access-token"), 1)
        self.assertIn("ThreadPoolExecutor", source)
        self.assertIn("max_parallel_requests", source)

    def test_runner_receipt_fields(self):
        source = (ROOT / "scripts/run_gemini_role_matrix.py").read_text()
        for key in (
            "provider_request_id",
            "input_sha256",
            "prompt_sha256",
            "response_text_sha256",
            "usage_metadata",
            "latency_ms",
            "receipt_sha256",
            "semantic_verified",
            "finish_reason",
        ):
            self.assertIn(key, source)

    def test_runner_bounds_thinking_for_compact_structured_output(self):
        source = (ROOT / "scripts/run_gemini_role_matrix.py").read_text()
        self.assertIn('"thinkingConfig": {"thinkingBudget": 0}', source)
        self.assertIn('"maxOutputTokens": 768', source)
        self.assertIn("thoughtsTokenCount", source)
        self.assertIn("Keep JSON compact", source)
        self.assertIn('finish_reason == "MAX_TOKENS"', source)

    def test_no_hidden_chain_of_thought_request(self):
        self.assertIn(
            "Do not reveal hidden chain-of-thought",
            (ROOT / "scripts/run_gemini_role_matrix.py").read_text(),
        )

    def test_workflow_reuses_existing_allowlisted_path(self):
        path = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"
        if not path.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        source = path.read_text(encoding="utf-8")
        self.assertIn("Run bounded portable reasoning role matrix", source)
        self.assertIn("scripts/run_gemini_role_matrix.py", source)

    def test_no_new_gemini_workflow(self):
        self.assertFalse((ROOT / ".github/workflows/fuse-gemini-role-matrix.yml").exists())


if __name__ == "__main__":
    unittest.main()
