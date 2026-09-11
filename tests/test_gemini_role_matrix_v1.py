import ast, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]

class RoleMatrixTests(unittest.TestCase):
    def test_contract_is_bounded(self):
        p=json.loads((ROOT/'governance/fuse_gemini_role_matrix_request_v1.json').read_text())
        self.assertEqual(p['schema'],'FUSE_GEMINI_ROLE_MATRIX_REQUEST_V1')
        self.assertEqual(p['provider'],'GOOGLE_VERTEX_AI')
        self.assertEqual(p['transport'],'VERTEX_WIF_ADC')
        self.assertEqual(len(p['roles']),8); self.assertEqual(len(set(p['roles'])),8)
        self.assertLessEqual(p['max_parallel_requests'],4)
        for k in ('case_data_allowed','provider_mutation_allowed','iam_mutation_allowed','secret_mutation_allowed','deployment_allowed','traffic_change_allowed','external_communication_allowed'): self.assertFalse(p[k])
    def test_runner_parses(self): ast.parse((ROOT/'scripts/run_gemini_role_matrix.py').read_text())
    def test_runner_one_access_token_and_parallel_pool(self):
        s=(ROOT/'scripts/run_gemini_role_matrix.py').read_text(); self.assertEqual(s.count("gcloud','auth','print-access-token"),1); self.assertIn('ThreadPoolExecutor',s); self.assertIn('max_parallel_requests',s)
    def test_runner_receipt_fields(self):
        s=(ROOT/'scripts/run_gemini_role_matrix.py').read_text()
        for k in ('provider_request_id','input_sha256','prompt_sha256','response_text_sha256','usage_metadata','latency_ms','receipt_sha256','semantic_verified'): self.assertIn(k,s)
    def test_no_hidden_chain_of_thought_request(self): self.assertIn('Do not reveal hidden chain-of-thought',(ROOT/'scripts/run_gemini_role_matrix.py').read_text())
    def test_workflow_reuses_existing_allowlisted_path(self):
        s=(ROOT/'.github/workflows/sovara-ai-studio-semantic-canary.yml').read_text(); self.assertIn('Run bounded portable reasoning role matrix',s); self.assertIn('scripts/run_gemini_role_matrix.py',s)
    def test_no_new_gemini_workflow(self): self.assertFalse((ROOT/'.github/workflows/fuse-gemini-role-matrix.yml').exists())

if __name__=='__main__': unittest.main()
