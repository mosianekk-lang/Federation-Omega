import ast, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]

class RoleMatrixTests(unittest.TestCase):
    def test_contract(self):
        p=json.loads((ROOT/"governance/fuse_gemini_role_matrix_request_v1.json").read_text())
        self.assertEqual(p["schema"],"FUSE_GEMINI_ROLE_MATRIX_REQUEST_V1")
        self.assertEqual(p["provider"],"GOOGLE_VERTEX_AI")
        self.assertEqual(p["transport"],"VERTEX_WIF_ADC")
        self.assertEqual(len(p["roles"]),8)
        self.assertEqual(len(set(p["roles"])),8)
        self.assertLessEqual(p["max_parallel_requests"],4)
        for k in ("case_data_allowed","provider_mutation_allowed","iam_mutation_allowed","secret_mutation_allowed","deployment_allowed","traffic_change_allowed","external_communication_allowed"):
            self.assertFalse(p[k])
    def test_runner_parses(self):
        ast.parse((ROOT/"scripts/run_gemini_role_matrix.py").read_text())
    def test_one_token_one_session_parallelism(self):
        s=(ROOT/"scripts/run_gemini_role_matrix.py").read_text()
        self.assertEqual(s.count('gcloud","auth","print-access-token'),1)
        self.assertIn("ThreadPoolExecutor",s)
        self.assertIn("max_parallel_requests",s)
    def test_receipt_proof_fields(self):
        s=(ROOT/"scripts/run_gemini_role_matrix.py").read_text()
        for k in ("provider_request_id","response_text_sha256","usage_metadata","latency_ms","receipt_sha256","semantic_verified"):
            self.assertIn(k,s)
    def test_no_hidden_cot_request(self):
        s=(ROOT/"scripts/run_gemini_role_matrix.py").read_text()
        self.assertIn("Do not reveal hidden chain-of-thought",s)
    def test_workflow_is_wif_only_no_secret(self):
        s=(ROOT/".github/workflows/fuse-gemini-role-matrix.yml").read_text()
        self.assertIn("id-token: write",s)
        self.assertIn("google-github-actions/auth@",s)
        self.assertNotIn("GEMINI_API_KEY",s)
        self.assertNotIn("secrets.",s)
    def test_push_scope_is_narrow(self):
        s=(ROOT/".github/workflows/fuse-gemini-role-matrix.yml").read_text()
        for p in (".github/workflows/fuse-gemini-role-matrix.yml","governance/fuse_gemini_role_matrix_request_v1.json","scripts/run_gemini_role_matrix.py"):
            self.assertIn(p,s)

if __name__=="__main__":
    unittest.main()
