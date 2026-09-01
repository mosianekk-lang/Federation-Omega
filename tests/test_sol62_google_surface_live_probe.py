from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sol62-google-surface-probe.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"


class Sol62GoogleSurfaceLiveProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW.exists():
            raise unittest.SkipTest(
                "workflow-free export excludes repository workflow controls"
            )
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_probe_is_admitted_but_has_no_cloud_mutation_authority(self) -> None:
        workflow = ".github/workflows/sol62-google-surface-probe.yml"
        self.assertIn(workflow, self.policy["active_workflow_allowlist"])
        self.assertEqual(["push", "workflow_dispatch"], self.policy["allowed_events"][workflow])
        self.assertEqual(["main"], self.policy["required_push_branches"][workflow])
        self.assertIn(workflow, self.policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(workflow, self.policy["oidc_workflow_allowlist"])
        self.assertNotIn(workflow, self.policy["provider_mutation_workflow_allowlist"])
        self.assertNotIn("id-token: write", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_apps_script_probe_is_exact_read_only_provider_readback(self) -> None:
        self.assertIn("bubbles/apps_script_deployment_probe.py", self.text)
        self.assertIn("--receipt /tmp/sol62-google/SURFACE_RECEIPT.json", self.text)
        self.assertIn("provider_mutation_performed\":false", self.text)
        self.assertIn("credential_values_recorded\":false", self.text)

    def test_ai_studio_canary_never_logs_or_persists_key(self) -> None:
        self.assertIn("HAS_GEMINI_API_KEY", self.text)
        self.assertIn("secrets.GEMINI_API_KEY", self.text)
        self.assertIn("set +x", self.text)
        self.assertIn("x-goog-api-key", self.text)
        self.assertIn("CREDENTIAL_MISSING", self.text)
        self.assertIn("SEMANTIC_MISMATCH", self.text)
        self.assertIn("VERIFIED_SCOPED", self.text)
        self.assertNotIn("echo $GEMINI_API_KEY", self.text)
        self.assertNotIn("print(key)", self.text)


if __name__ == "__main__":
    unittest.main()
