from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
SCRIPT = ROOT / "ops" / "evidenceops_local_bible_event13_rebuild.py"
AUTH_SHA = "7c6bc770dae815cd3e89ee6cdf493a5fab2cc093"
EXPECTED_PREVIOUS_HASH = "e58ba00136022251976051a041b3664fd51418aaabf2c840c8bf2c5d7903cf21"
EVENT_ID = "EVT-20260804-PST-REMOTE-CLOSURE-FEDERATION-LEARNING-AND-PACKAGE-REBUILD"


class LocalBibleRebuildBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_workflow_uses_marked_read_only_wif_route(self) -> None:
        self.assertIn("[BIBLE-REBUILD]", self.workflow)
        self.assertIn("id-token: write", self.workflow)
        self.assertIn(f"google-github-actions/auth@{AUTH_SHA}", self.workflow)
        self.assertIn("token_format: access_token", self.workflow)
        self.assertIn(
            "access_token_scopes: https://www.googleapis.com/auth/drive.readonly",
            self.workflow,
        )
        self.assertIn(
            "service_account: superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            self.workflow,
        )
        self.assertIn("create_credentials_file: false", self.workflow)
        self.assertIn("export_environment_variables: false", self.workflow)

    def test_workflow_has_no_source_write_or_runtime_commit_path(self) -> None:
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("git commit", self.workflow)
        self.assertNotIn("git push", self.workflow)
        self.assertNotIn("actions/checkout@v", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("phoenix-export-output/local-bible-rebuild/*", self.workflow)
        self.assertIn(
            "PROVIDER_PACKAGE_REBUILD_VERIFIED_PENDING_LIBRARY_WRITEBACK",
            self.workflow,
        )

    def test_airlock_oidc_exception_is_exact_and_read_only(self) -> None:
        expected = [".github/workflows/phoenix-emergency-freeze.yml"]
        self.assertEqual(expected, self.policy["oidc_workflow_allowlist"])
        boundary = self.policy["oidc_boundary"]
        self.assertEqual(expected[0], boundary["workflow"])
        self.assertEqual("[BIBLE-REBUILD]", boundary["trigger_marker"])
        self.assertEqual(
            "https://www.googleapis.com/auth/drive.readonly", boundary["scope"]
        )
        self.assertFalse(boundary["repository_write_authority"])
        self.assertFalse(boundary["public_link_allowed"])
        self.assertTrue(boundary["provider_readback_required"])

    def test_rebuild_anchors_to_exact_predecessor_and_original_writer(self) -> None:
        self.assertIn(EXPECTED_PREVIOUS_HASH, self.script)
        self.assertIn(EVENT_ID, self.script)
        self.assertIn("capture_event.py", self.script)
        self.assertIn("subprocess.run([sys.executable, str(capture), \"append\"", self.script)
        self.assertIn("subprocess.run([sys.executable, str(capture), \"verify\"", self.script)
        self.assertIn("predecessor event hash drift", self.script)
        self.assertIn("Event 13 previous hash", self.script)
        self.assertIn("ZIP CRC failed", self.script)

    def test_rebuild_is_private_and_artifact_only(self) -> None:
        forbidden = (
            "drive.google.com/uc",
            "export=download",
            "permissions.create",
            "anyoneWithLink",
            "git commit",
            "git push",
            "contents: write",
        )
        for value in forbidden:
            self.assertNotIn(value, self.script)
        self.assertIn("https://www.googleapis.com/drive/v3/files/", self.script)
        self.assertIn('headers={"Authorization": f"Bearer {token}"}', self.script)
        self.assertIn("P2_PRIVATE_DRIVE_READ_ONLY_NO_PUBLIC_SOURCE_CONTENT", self.script)
        self.assertIn("pending Library writeback", self.script)

    def test_failure_success_constraint_learning_ids_are_bound(self) -> None:
        required = (
            "INC-FO-LBRF-20260804-001",
            "REM-FO-LBRF-20260804-001",
            "FORM-FO-LBRF-20260804-001",
            "ALG-LBRF-001",
            "LS-LBRF-001",
            "AR-LBRF-001",
            "CT-LBRF-001",
            "RP-LBRF-001",
            "LOCAL_BINARY_FAILURE_X2",
        )
        for value in required:
            self.assertIn(value, self.script)

    def test_typed_set_preserves_template_field_shapes(self) -> None:
        spec = importlib.util.spec_from_file_location("lbrf", SCRIPT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = {"sources_inspected": "legacy", "verified_proof": []}
        module.typed_set(payload, "sources_inspected", ["one", "two"])
        module.typed_set(payload, "verified_proof", "proof")
        self.assertEqual("one; two", payload["sources_inspected"])
        self.assertEqual(["proof"], payload["verified_proof"])


if __name__ == "__main__":
    unittest.main()
