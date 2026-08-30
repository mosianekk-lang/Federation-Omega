from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_v2_test", ROOT / "phoenix" / "build_exports_v2.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
SOURCE = (ROOT / "phoenix" / "build_exports_v2.py").read_text(encoding="utf-8")


class PhoenixPstDispatchTests(unittest.TestCase):
    """Guard the post-#180 Phoenix purity decision.

    PST workflow dispatch was a temporary one-time closure hook and was deliberately
    removed from export generation when Phoenix adopted pure v3.1 exports. These
    regressions now protect that removal instead of requiring the retired effect path.
    """

    def test_export_builder_has_no_pst_dispatch_function(self) -> None:
        self.assertFalse(hasattr(MODULE, "maybe_dispatch_pst_remote_verifier"))
        self.assertNotIn("maybe_dispatch_pst_remote_verifier", SOURCE)

    def test_export_builder_has_no_pst_request_or_completion_authority(self) -> None:
        for retired_symbol in (
            "PST_REQUEST_PATH",
            "PST_COMPLETION_PATH",
            "PST_WORKFLOW_PATH",
            "PST_WORKFLOW_FILE",
        ):
            with self.subTest(retired_symbol=retired_symbol):
                self.assertFalse(hasattr(MODULE, retired_symbol))
                self.assertNotIn(retired_symbol, SOURCE)

    def test_export_builder_has_no_github_provider_dispatch_client(self) -> None:
        self.assertFalse(hasattr(MODULE, "_gh_api"))
        self.assertNotIn('subprocess.run(', SOURCE)
        self.assertNotIn('"gh", "api"', SOURCE)
        self.assertNotIn("workflow_dispatch", SOURCE)

    def test_main_remains_export_only(self) -> None:
        self.assertIn("receipt = BASE.build(root, output, policy)", SOURCE)
        self.assertNotIn('receipt["pst_remote_verifier_dispatch"]', SOURCE)
        self.assertNotIn("actions/workflows", SOURCE)


if __name__ == "__main__":
    unittest.main()
