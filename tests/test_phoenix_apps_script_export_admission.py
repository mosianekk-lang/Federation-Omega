from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_gs_admission",
    ROOT / "phoenix" / "build_exports.py",
)
assert SPEC and SPEC.loader
EXPORTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EXPORTS
SPEC.loader.exec_module(EXPORTS)


class PhoenixAppsScriptExportAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(
            (ROOT / "phoenix" / "export_policy.json").read_text(encoding="utf-8")
        )

    def test_policy_admits_apps_script_source_extension(self) -> None:
        self.assertEqual("1.0.21", self.policy["version"])
        self.assertIn(".gs", self.policy["core"]["include_extensions"])
        self.assertEqual(
            1,
            self.policy["core"]["include_extensions"].count(".gs"),
            "Apps Script source extension must be admitted exactly once",
        )

    def test_gs_admission_does_not_override_existing_core_exclusions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phoenix-gs-export-") as temporary:
            root = Path(temporary)
            files = {
                "apps_script/example/Code.gs": "function canary(){ return 'ok'; }\n",
                "runtime/unsafe.gs": "function runtimeState(){ return 'no'; }\n",
                "credentials/private.gs": "function credentialPath(){ return 'no'; }\n",
                ".github/workflows/unsafe.gs": "function workflowPath(){ return 'no'; }\n",
                "phoenix/control.gs": "function migrationControl(){ return 'no'; }\n",
                "apps_script/example/SecretMarker.gs": "const token = 'ghp_not_a_real_token';\n",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            safe = root / "apps_script/example/Code.gs"
            allowed, reason = EXPORTS.classify_core(safe, root, self.policy)
            self.assertTrue(allowed)
            self.assertEqual("APPROVED_SOURCE_FILE", reason)

            expected_classification = {
                "runtime/unsafe.gs": "EXCLUDED_PREFIX",
                "credentials/private.gs": "EXCLUDED_STATE_OR_AUTHORITY_SEGMENT",
                ".github/workflows/unsafe.gs": "GITHUB_WORKFLOW_NOT_CORE_SOURCE",
                "phoenix/control.gs": "MIGRATION_CONTROL_NOT_CORE_SOURCE",
            }
            for relative, expected_reason in expected_classification.items():
                allowed, reason = EXPORTS.classify_core(
                    root / relative, root, self.policy
                )
                self.assertFalse(allowed, relative)
                self.assertEqual(expected_reason, reason, relative)

            stage = root / "stage"
            stage.mkdir()
            included, excluded = EXPORTS.stage_core(root, stage, self.policy)
            included_by_path = {item.path: item for item in included}
            excluded_by_path = {item.path: item for item in excluded}

            self.assertIn("apps_script/example/Code.gs", included_by_path)
            self.assertTrue((stage / "apps_script/example/Code.gs").is_file())
            self.assertNotIn("apps_script/example/SecretMarker.gs", included_by_path)
            self.assertEqual(
                "SECRET_MARKER:ghp_",
                excluded_by_path["apps_script/example/SecretMarker.gs"].reason,
            )
            self.assertFalse(
                any(EXPORTS.is_github_workflow_path(item.path) for item in included)
            )
            self.assertFalse(
                any(
                    item.reason.startswith("SECRET_MARKER:")
                    for item in included
                )
            )


if __name__ == "__main__":
    unittest.main()
