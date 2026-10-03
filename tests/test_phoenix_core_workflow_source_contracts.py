"""Mandatory repository workflow assertions, also collected by their original courts."""
from __future__ import annotations

from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_WORKFLOW = ROOT / ".github/workflows/fuse-localllm-desktop-windows-build-v1.yml"
SOVARA_WORKFLOW = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"


class DesktopWorkflowSourceContracts(unittest.TestCase):
    def test_windows_workflow_packaging_regression_guard(self):
        wf = DESKTOP_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if($line -notmatch '^[0-9a-f]{64}  .+$'){ throw \"MALFORMED_SHA256SUMS_LINE:$line\" }", wf)
        self.assertEqual(wf.count("uses: actions/upload-artifact@"), 1)
        self.assertEqual(wf.count("Compress-Archive -Path"), 1)
        self.assertEqual(wf.count("schema='FUSE-LOCALLLM-DESKTOP-WINDOWS-BUILD-PROOF-V1'"), 1)


class GeminiWorkflowSourceContracts(unittest.TestCase):
    def test_windows_package_recursively_attests_overlay(self):
        workflow = DESKTOP_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Get-ChildItem $releaseRoot -Recurse -File", workflow)
        self.assertIn("provider-fabric/FUSE-LocalLLM-ProviderFabric.ps1", workflow)
        self.assertIn("provider-fabric/gemini_roles.json", workflow)
        self.assertIn("provider_fabric_sha256", workflow)
        self.assertIn("gemini_roles_sha256", workflow)
        self.assertIn("checksum_manifest_sha256", workflow)


class SovaraWorkflowSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = SOVARA_WORKFLOW.read_text(encoding="utf-8")

    def test_reuses_approved_keyless_gateway(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("google-github-actions/auth@", self.workflow)
        self.assertIn("Run V2 Gemini 3.8 Interactions semantic canary", self.workflow)
        self.assertIn("python3 scripts/run_google_interactions_v2_canary.py", self.workflow)
        self.assertIn('branches: ["main"]', self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)

    def test_v2_semantic_canary_runs_before_legacy_performance_court(self) -> None:
        v2_index = self.workflow.index("Run V2 Gemini 3.8 Interactions semantic canary")
        legacy_index = self.workflow.index("Run bounded portable reasoning role matrix")
        self.assertLess(v2_index, legacy_index)

    def test_interactions_receipt_upload_is_immutable_artifact(self) -> None:
        self.assertIn("Upload immutable redacted V2 Interactions receipt", self.workflow)
        self.assertIn("INTERACTIONS_V2_SEMANTIC_RECEIPT.json", self.workflow)
        self.assertIn("retention-days: 90", self.workflow)

    def test_provider_job_requires_explicit_owner_dispatch(self) -> None:
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("issues:", self.workflow)
        self.assertIn("    types: [opened]", self.workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.workflow)
        self.assertIn("github.event_name == 'issues'", self.workflow)
        self.assertIn("github.event.issue.title == '[FO-DISPATCH] FUSE_AISTUDIO_INTERACTIONS_CANARY_V1'", self.workflow)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.workflow)
        self.assertIn("issues: read", self.workflow)



class PortableProfileFailureContracts(unittest.TestCase):
    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("profile_negative_contract", ROOT / "tests/phoenix_core_test_profile.py")
        self.profile = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.profile)
        self.temporary = tempfile.TemporaryDirectory(prefix="phoenix-profile-negative-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def _valid_archive(self):
        included = []
        for relative in self.profile.PORTABLE_LOADERS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, path)
            data = path.read_bytes()
            included.append({"path": relative, "classification": "CORE_INCLUDED", "reason": "APPROVED_SOURCE_FILE",
                             "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        excluded = []
        for relative in [self.profile.SOURCE_COURT, *self.profile.WORKFLOW_PATHS]:
            data = (ROOT / relative).read_bytes()
            excluded.append({"path": relative, "classification": "CORE_EXCLUDED",
                             "reason": "MIGRATION_CONTROL_TEST_NOT_CORE_SOURCE" if relative == self.profile.SOURCE_COURT else "GITHUB_WORKFLOW_NOT_CORE_SOURCE",
                             "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        payload = {"schema": "FEDOMEGA-PHOENIX-EXPORT-MANIFEST-1", "target": "Federation-Omega-Core",
                   "repository_role": "CANONICAL_SOURCE_ONLY", "test_profile": self.profile.PROFILE,
                   "invariants": {name: 0 for name in ("workflow_count", "runtime_state_count", "migration_control_test_count", "secret_marker_count")},
                   "files": included, "excluded": excluded}
        self._write_manifest(payload)
        self.assertEqual(self.profile.collection_profile(self.root), "PORTABLE_CORE")
        return payload

    def _write_manifest(self, payload):
        (self.root / "PHOENIX_CORE_MANIFEST.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_forged_or_incomplete_marker_cannot_drop_source_courts(self):
        payload = self._valid_archive()
        incomplete = json.loads(json.dumps(payload))
        incomplete["excluded"].pop()
        for invalid in ({}, {**payload, "test_profile": {}}, incomplete):
            with self.subTest(keys=sorted(invalid)):
                self._write_manifest(invalid)
                with self.assertRaisesRegex(AssertionError, "PHOENIX_TEST_PROFILE_INVALID"):
                    self.profile.collection_profile(self.root)

    def test_changed_included_loader_hash_is_rejected(self):
        payload = self._valid_archive()
        payload["files"][0]["sha256"] = "0" * 64
        self._write_manifest(payload)
        with self.assertRaisesRegex(AssertionError, "included_hash:"):
            self.profile.collection_profile(self.root)

    def test_source_workflow_missing_cannot_be_treated_as_portable(self):
        for relative in [self.profile.SOURCE_COURT, *self.profile.WORKFLOW_PATHS]:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("source fixture", encoding="utf-8")
        self.assertEqual(self.profile.collection_profile(self.root), "SOURCE")
        (self.root / self.profile.WORKFLOW_PATHS[0]).unlink()
        with self.assertRaisesRegex(AssertionError, "SOURCE_DEPENDENCY_MISSING:"):
            self.profile.collection_profile(self.root)


if __name__ == "__main__":
    unittest.main()
