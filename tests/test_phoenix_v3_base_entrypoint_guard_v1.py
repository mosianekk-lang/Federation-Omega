from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = load("phoenix_v3_base_guard_test", ROOT / "phoenix" / "provider_cutover_v3.py")
V31 = load("phoenix_v31_base_guard_test", ROOT / "phoenix" / "provider_cutover_v3_1.py")


class PhoenixV3BaseEntrypointGuardTests(unittest.TestCase):
    def test_direct_base_apply_is_blocked_before_engine_main(self) -> None:
        original_argv = sys.argv
        original_main = BASE.ENGINE.main
        calls: list[str] = []
        try:
            sys.argv = ["provider_cutover_v3.py", "--apply"]
            BASE.ENGINE.main = lambda: calls.append("engine") or 0
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop(BASE.INTERNAL_APPLY_ENV, None)
                with self.assertRaisesRegex(BASE.ENGINE.CutoverError, "Direct Phoenix v3 base --apply is prohibited"):
                    BASE.main()
        finally:
            sys.argv = original_argv
            BASE.ENGINE.main = original_main
        self.assertEqual([], calls)

    def test_base_dry_run_path_remains_available_without_internal_context(self) -> None:
        self.assertTrue(BASE.internal_apply_context(["provider_cutover_v3.py"]))
        self.assertFalse(BASE.internal_apply_context(["provider_cutover_v3.py", "--apply"]))

    def test_guarded_v31_opens_internal_engine_context_only_during_apply(self) -> None:
        original_argv = sys.argv
        original_main = V31.V3.main
        internal_env = getattr(V31.V3, "INTERNAL_APPLY_ENV", V31.DEFAULT_INTERNAL_APPLY_ENV)
        observed: list[str | None] = []
        try:
            sys.argv = ["provider_cutover_v3_1.py", "--apply"]
            V31.V3.main = lambda: observed.append(os.getenv(internal_env)) or 0
            with patch.dict(os.environ, {V31.GUARDED_APPLY_ENV: "1"}, clear=False):
                os.environ.pop(internal_env, None)
                self.assertEqual(0, V31.main())
                self.assertIsNone(os.getenv(internal_env))
        finally:
            sys.argv = original_argv
            V31.V3.main = original_main
        self.assertEqual(["1"], observed)

    def test_preserved_engine_bytes_match_export_template(self) -> None:
        source = ROOT / "phoenix" / "provider_cutover_v3_engine.py"
        exported = ROOT / "phoenix" / "ops-template" / "provider_cutover_v3_engine.py"
        self.assertTrue(source.is_file())
        self.assertTrue(exported.is_file())
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(digest(source), digest(exported))

    def test_v31_exact_lease_patch_reaches_preserved_engine(self) -> None:
        self.assertIs(V31.V3.git_push, V31.git_push_exact_lease)
        self.assertTrue(hasattr(V31.V3, "ENGINE"))
        self.assertIs(V31.V3.ENGINE.git_push, V31.git_push_exact_lease)


if __name__ == "__main__":
    unittest.main()
