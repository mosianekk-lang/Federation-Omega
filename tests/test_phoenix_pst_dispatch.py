from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_v2_test", ROOT / "phoenix" / "build_exports_v2.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhoenixPstDispatchRemovalTests(unittest.TestCase):
    def test_v2_export_has_no_provider_dispatch_entrypoint(self) -> None:
        self.assertFalse(hasattr(MODULE, "maybe_dispatch_pst_remote_verifier"))
        self.assertFalse(hasattr(MODULE, "_gh_api"))

    def test_v2_export_has_no_pst_dispatch_contract(self) -> None:
        for name in ("PST_REQUEST_PATH", "PST_COMPLETION_PATH", "PST_WORKFLOW_PATH"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(MODULE, name))

    def test_v2_export_source_remains_side_effect_free(self) -> None:
        source = (ROOT / "phoenix" / "build_exports_v2.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("gh api", source)
        self.assertNotIn("maybe_dispatch_pst_remote_verifier", source)
        self.assertNotIn("PST_WORKFLOW_PATH", source)


if __name__ == "__main__":
    unittest.main()
