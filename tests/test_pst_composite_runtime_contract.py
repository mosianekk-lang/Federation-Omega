from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
VERIFIER = ROOT / "ops" / "evidenceops_pst_v2_composite_verify.py"


class PstCompositeRuntimeContractTests(unittest.TestCase):
    def test_workflow_sets_writable_scratch_root_explicitly(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("PST_VERIFY_ROOT: /tmp/pst-composite-verify", text)
        self.assertIn("evidenceops_pst_v2_composite_verify.py", text)

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
