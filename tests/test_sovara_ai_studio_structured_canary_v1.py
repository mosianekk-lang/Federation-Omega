from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"
REQUEST_PATH = ROOT / "governance/sovara_ai_studio_semantic_canary_request_v1.json"
POLICY_PATH = ROOT / "governance/github_airlock_policy.json"
REL = ".github/workflows/sovara-ai-studio-semantic-canary.yml"


class Court(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW_PATH.exists():
            raise unittest.SkipTest(
                "repository-only workflow contract is outside the Phoenix Core export"
            )
        cls.W = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.R = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        cls.P = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_governance_unchanged(self):
        self.assertIn(REL, self.P["active_workflow_allowlist"])
        self.assertIn(REL, self.P["oidc_workflow_allowlist"])
        self.assertNotIn(REL, self.P["provider_mutation_workflow_allowlist"])
        self.assertEqual(["main"], self.P["required_push_branches"][REL])

    def test_structured_contract(self):
        c = self.R["semantic_canary"]
        self.assertEqual("STRUCTURED_JSON_SCHEMA_NONCE", c["prompt_shape"])
        self.assertEqual("application/json", c["response_mime_type"])
        self.assertEqual(["status", "nonce"], c["response_schema"]["required"])
        self.assertTrue(self.R["negative_cache"]["unchanged_free_text_retry_forbidden"])

    def test_workflow_uses_schema(self):
        for token in (
            "responseMimeType':'application/json'",
            "responseSchema':response_schema",
            "parsed.get('status')=='VERIFIED'",
            "parsed.get('nonce')==nonce",
            "'acceptance_mode':'STRUCTURED_JSON_SCHEMA_V1'",
        ):
            self.assertIn(token, self.W)
        self.assertNotIn("exact=status==200 and text==expected", self.W)

    def test_zero_effect(self):
        for bad in (
            "gcloud services enable",
            "add-iam-policy-binding",
            "gcloud run deploy",
            "gcloud run services update-traffic",
            "gcloud secrets versions access",
            "git push",
            "git commit",
        ):
            self.assertNotIn(bad, self.W)
        for key in (
            "case_data_allowed",
            "provider_mutation_allowed",
            "iam_mutation_allowed",
            "secret_mutation_allowed",
            "deployment_allowed",
            "traffic_change_allowed",
            "external_communication_allowed",
        ):
            self.assertFalse(self.R[key], key)

    def test_actions_pinned(self):
        refs = re.findall(r"uses:\s*([^\s]+)", self.W)
        self.assertTrue(refs)
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}$", x) for x in refs), refs)

    def test_vertex_exact_target(self):
        self.assertEqual("gemini-2.5-flash", self.R["fallback_route"]["model"])
        self.assertEqual("global", self.R["fallback_route"]["location"])
        self.assertIn("publishers/google/models/{model}:generateContent", self.W)
        self.assertIn("aiplatform.endpoints.predict", self.W)


if __name__ == "__main__":
    unittest.main()
