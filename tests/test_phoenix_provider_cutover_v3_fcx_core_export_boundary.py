from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_POLICY = ROOT / "phoenix" / "export_policy.json"
FCX_TEST = ROOT / "tests" / "test_sovara_creative_fcx_copilot_agent_profiles.py"


class FCXCoreExportBoundaryTests(unittest.TestCase):
    def test_source_repository_airlock_test_is_excluded_from_core(self) -> None:
        policy = json.loads(EXPORT_POLICY.read_text(encoding="utf-8"))
        self.assertIn(
            "tests/test_github_airlock.py",
            policy["core"]["excluded_test_globs"],
        )

    def test_fcx_agent_assertions_use_explicit_core_manifest_boundary(self) -> None:
        source = FCX_TEST.read_text(encoding="utf-8")
        self.assertIn('CORE_MANIFEST = ROOT / "PHOENIX_CORE_MANIFEST.json"', source)
        self.assertIn("require_repository_agent_surface", source)
        self.assertIn("if CORE_MANIFEST.is_file():", source)
        self.assertIn('.github/agents is missing outside a Phoenix Core export', source)

    def test_export_policy_keeps_github_surface_excluded(self) -> None:
        policy = json.loads(EXPORT_POLICY.read_text(encoding="utf-8"))
        self.assertIn(".github/", policy["core"]["excluded_prefixes"])
        self.assertEqual(0, policy["invariants"]["core_workflow_count"])
        self.assertEqual(0, policy["invariants"]["core_nested_workflow_count"])


if __name__ == "__main__":
    unittest.main()
