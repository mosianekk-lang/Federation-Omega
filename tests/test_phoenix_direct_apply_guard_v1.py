from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_provider_cutover_v3_1_direct_guard_test",
    ROOT / "phoenix" / "provider_cutover_v3_1.py",
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class PhoenixDirectApplyGuardTests(unittest.TestCase):
    def test_dry_run_context_remains_callable_without_guard_env(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(MOD.GUARDED_APPLY_ENV, None)
            self.assertTrue(MOD.guarded_apply_context(["provider_cutover_v3_1.py"]))

    def test_direct_apply_is_blocked_without_guarded_launcher_context(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(MOD.GUARDED_APPLY_ENV, None)
            self.assertFalse(MOD.guarded_apply_context(["provider_cutover_v3_1.py", "--apply"]))

    def test_guarded_launcher_context_allows_apply_path_to_continue_to_existing_authority_engine(self) -> None:
        with patch.dict(os.environ, {MOD.GUARDED_APPLY_ENV: "1"}, clear=False):
            self.assertTrue(MOD.guarded_apply_context(["provider_cutover_v3_1.py", "--apply"]))

    def test_main_fails_before_base_apply_when_direct_apply_is_attempted(self) -> None:
        original_argv = sys.argv
        original_main = MOD.V3.main
        calls: list[str] = []
        try:
            sys.argv = ["provider_cutover_v3_1.py", "--apply"]
            MOD.V3.main = lambda: calls.append("base") or 0
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop(MOD.GUARDED_APPLY_ENV, None)
                with self.assertRaisesRegex(MOD.V3.CutoverError, "Direct Phoenix v3.1 --apply is prohibited"):
                    MOD.main()
        finally:
            sys.argv = original_argv
            MOD.V3.main = original_main
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
