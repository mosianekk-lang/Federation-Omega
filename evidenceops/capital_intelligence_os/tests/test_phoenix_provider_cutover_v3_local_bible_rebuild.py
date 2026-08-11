from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
SCRIPT = ROOT / "ops" / "evidenceops_local_bible_event13_rebuild.py"
BOUNDARY = ROOT / "phoenix" / "LOCAL_BIBLE_RECOVERY_EXTERNALIZATION.md"
EXPECTED_PREVIOUS_HASH = "e58ba00136022251976051a041b3664fd51418aaabf2c840c8bf2c5d7903cf21"
EVENT_ID = "EVT-20260804-PST-REMOTE-CLOSURE-FEDERATION-LEARNING-AND-PACKAGE-REBUILD"


class LocalBibleRebuildBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.boundary = BOUNDARY.read_text(encoding="utf-8")

    def test_legacy_source_workflow_has_zero_oidc(self) -> None:
        forbidden = (
            "[BIBLE-REBUILD]",
            "id-token: write",
            "google-github-actions/auth@",
            "GOOGLE_ACCESS_TOKEN",
            "phoenix-export-output/local-bible-rebuild",
            "Authenticate private Local Bible recovery",
            "Rebuild private Local Bible Event 13",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.workflow)
        self.assertIn("PST not requested", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_airlock_oidc_allowlist_is_empty(self) -> None:
        self.assertEqual([], self.policy["oidc_workflow_allowlist"])
        self.assertNotIn("oidc_boundary", self.policy)
        self.assertEqual(
            "SEPARATE_PRIVATE_EXECUTION_PLANE",
            self.policy["automation_repository_role"],
        )

    def test_rebuild_is_packaged_capability_not_active_source_runtime(self) -> None:
        self.assertTrue(SCRIPT.exists())
        self.assertTrue(BOUNDARY.exists())
        self.assertIn("PRIVATE_OPS_PLANE_REQUIRED", self.boundary)
        self.assertIn("not executable from the legacy public source repository", self.boundary)
        self.assertIn("oidc_workflow_allowlist` is empty", self.boundary)
        self.assertIn("no provider rebuild or Library writeback is claimed", self.boundary)

    def test_rebuild_anchors_to_exact_predecessor_and_original_writer(self) -> None:
        self.assertIn(EXPECTED_PREVIOUS_HASH, self.script)
        self.assertIn(EVENT_ID, self.script)
        self.assertIn("capture_event.py", self.script)
        self.assertIn("subprocess.run([sys.executable, str(capture), \"append\"", self.script)
        self.assertIn("subprocess.run([sys.executable, str(capture), \"verify\"", self.script)
        self.assertIn("predecessor event hash drift", self.script)
        self.assertIn("Event 13 previous hash", self.script)
        self.assertIn("ZIP CRC failed", self.script)

    def test_rebuild_is_private_and_source_write_free(self) -> None:
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
            with self.subTest(value=value):
                self.assertNotIn(value, self.script)
        self.assertIn("https://www.googleapis.com/drive/v3/files/", self.script)
        self.assertIn('headers={"Authorization": f"Bearer {token}"}', self.script)
        self.assertIn("P2_PRIVATE_DRIVE_READ_ONLY_NO_PUBLIC_SOURCE_CONTENT", self.script)
        self.assertIn(
            "PROVIDER_PACKAGE_REBUILD_VERIFIED_PENDING_LIBRARY_WRITEBACK",
            self.script,
        )

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
