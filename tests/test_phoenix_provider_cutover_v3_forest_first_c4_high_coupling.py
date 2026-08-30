from __future__ import annotations

from pathlib import Path
import unittest

from ao_harmonic_v3.high_coupling_policy_shadow import run_c4_high_coupling_policy_shadow

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "superior-logic-maturation-shadow.yml"
WRAPPER = ROOT / "tools" / "superior_logic_maturation_shadow.py"
CLI = ROOT / "evidenceops" / "caseforge" / "maturation_shadow_cli.py"


class ForestFirstC4RepositoryShellBindingTests(unittest.TestCase):
    def test_superior_logic_workflow_uses_caseforge_canonical_entrypoint(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        cli = CLI.read_text(encoding="utf-8")
        self.assertIn("python -m evidenceops.caseforge.maturation_shadow_cli", workflow)
        self.assertIn("evidenceops/caseforge/maturation_shadow_runtime.py", workflow)
        self.assertIn("evidenceops/caseforge/maturation_shadow_cli.py", workflow)
        self.assertIn("Compatibility entrypoint", wrapper)
        self.assertIn("from evidenceops.caseforge.maturation_shadow_cli import main", wrapper)
        self.assertIn("from .maturation_shadow_runtime import", cli)

    def test_workflow_remains_read_only_and_no_effect(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("assert receipt['external_effect'] is False", workflow)
        self.assertIn("assert receipt['self_sustaining'] is False", workflow)

    def test_c4_portable_shadow_is_green_from_repository_shell(self):
        report = run_c4_high_coupling_policy_shadow()
        self.assertEqual(report["scenario_count"], 10)
        self.assertTrue(report["pass"])
        self.assertFalse(report["external_effect"])
        self.assertFalse(report["physical_migration_executed"])
        self.assertFalse(report["provider_runtime_proved"])


if __name__ == "__main__":
    unittest.main()
