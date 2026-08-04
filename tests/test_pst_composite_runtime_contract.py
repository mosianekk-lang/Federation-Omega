from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
VERIFIER = ROOT / "ops" / "evidenceops_pst_v2_composite_verify.py"
BIBLE_BOUNDARY = ROOT / "phoenix" / "LOCAL_BIBLE_RECOVERY_EXTERNALIZATION.md"


class PstCompositeRuntimeContractTests(unittest.TestCase):
    def test_workflow_sets_writable_scratch_root_explicitly(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("PST_VERIFY_ROOT: /tmp/pst-composite-verify", text)
        self.assertIn("evidenceops_pst_v2_composite_verify.py", text)

    def test_marked_closure_run_isolates_and_cancels_stale_queue(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("startsWith(github.event.head_commit.message, '[PST-CLOSE]')", text)
        self.assertIn("'phoenix-emergency-execution-freeze'", text)
        self.assertIn("'phoenix-emergency-passive'", text)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'push'", text)
        self.assertIn("id: pst_closure", text)
        self.assertIn("if: steps.pst_closure.outputs.requested == 'true'", text)

    def test_local_bible_rebuild_is_externalized_from_source_workflow(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        boundary = BIBLE_BOUNDARY.read_text(encoding="utf-8")
        for forbidden in (
            "[BIBLE-REBUILD]",
            "id: bible_rebuild",
            "steps.bible_rebuild.outputs.requested",
            "id-token: write",
            "google-github-actions/auth@",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertIn("PRIVATE_OPS_PLANE_REQUIRED", boundary)
        self.assertIn("not executable from the legacy public source repository", boundary)

    def test_passive_runs_require_only_pst_completion_contract(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pst_ok=true", text)
        self.assertIn('requested="${{ steps.pst_closure.outputs.requested }}"', text)
        self.assertIn('if [[ "${requested}" != "true" ]]; then', text)
        self.assertIn(
            "Phoenix quarantine and exports verified; PST not requested",
            text,
        )
        self.assertNotIn("bible_ok", text)
        self.assertNotIn("bible_requested", text)

    def test_verifier_honours_explicit_root_override(self):
        previous = os.environ.get("PST_VERIFY_ROOT")
        os.environ["PST_VERIFY_ROOT"] = "/tmp/pst-runtime-contract-test"
        try:
            spec = importlib.util.spec_from_file_location(
                "pst_composite_runtime_contract_target", VERIFIER
            )
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            self.assertEqual(
                Path("/tmp/pst-runtime-contract-test"),
                module.ROOT,
            )
        finally:
            if previous is None:
                os.environ.pop("PST_VERIFY_ROOT", None)
            else:
                os.environ["PST_VERIFY_ROOT"] = previous


if __name__ == "__main__":
    unittest.main()
