from __future__ import annotations
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
W=(ROOT/".github/workflows/sovara-ai-studio-semantic-canary.yml").read_text()
R=json.loads((ROOT/"governance/sovara_ai_studio_semantic_canary_request_v1.json").read_text())
P=json.loads((ROOT/"governance/github_airlock_policy.json").read_text())
REL=".github/workflows/sovara-ai-studio-semantic-canary.yml"

class Court(unittest.TestCase):
    def test_governance_unchanged(self):
        self.assertIn(REL,P["active_workflow_allowlist"])
        self.assertIn(REL,P["oidc_workflow_allowlist"])
        self.assertNotIn(REL,P["provider_mutation_workflow_allowlist"])
        self.assertEqual(["main"],P["required_push_branches"][REL])
    def test_structured_contract(self):
        c=R["semantic_canary"]
        self.assertEqual("STRUCTURED_JSON_SCHEMA_NONCE",c["prompt_shape"])
        self.assertEqual("application/json",c["response_mime_type"])
        self.assertEqual(["status","nonce"],c["response_schema"]["required"])
        self.assertTrue(R["negative_cache"]["unchanged_free_text_retry_forbidden"])
    def test_workflow_uses_schema(self):
        for token in ("responseMimeType':'application/json'","responseSchema':response_schema","parsed.get('status')=='VERIFIED'","parsed.get('nonce')==nonce","'acceptance_mode':'STRUCTURED_JSON_SCHEMA_V1'"):
            self.assertIn(token,W)
        self.assertNotIn("exact=status==200 and text==expected",W)
    def test_zero_effect(self):
        for bad in ("gcloud services enable","add-iam-policy-binding","gcloud run deploy","gcloud run services update-traffic","gcloud secrets versions access","git push","git commit"):
            self.assertNotIn(bad,W)
        for k in ("case_data_allowed","provider_mutation_allowed","iam_mutation_allowed","secret_mutation_allowed","deployment_allowed","traffic_change_allowed","external_communication_allowed"):
            self.assertFalse(R[k],k)
    def test_actions_pinned(self):
        refs=re.findall(r"uses:\s*([^\s]+)",W)
        self.assertTrue(refs)
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}$",x) for x in refs),refs)
    def test_vertex_exact_target(self):
        self.assertEqual("gemini-2.5-flash",R["fallback_route"]["model"])
        self.assertEqual("global",R["fallback_route"]["location"])
        self.assertIn("publishers/google/models/{model}:generateContent",W)
        self.assertIn("aiplatform.endpoints.predict",W)

if __name__=="__main__":
    unittest.main()
