from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V2 = load("phoenix_v2_entrypoint_guard_test", ROOT / "phoenix" / "provider_cutover_v2.py")


class PhoenixV2EntrypointGuardTests(unittest.TestCase):
    def test_direct_v2_apply_is_retired_before_engine_main(self) -> None:
        original_argv = sys.argv
        original_main = V2.ENGINE.main
        calls: list[str] = []
        try:
            sys.argv = ["provider_cutover_v2.py", "--apply"]
            V2.ENGINE.main = lambda: calls.append("engine") or 0
            with self.assertRaisesRegex(V2.CutoverError, "Phoenix v2 --apply is retired"):
                V2.main()
        finally:
            sys.argv = original_argv
            V2.ENGINE.main = original_main
        self.assertEqual([], calls)

    def test_v2_dry_run_path_remains_available(self) -> None:
        self.assertFalse(V2.apply_requested(["provider_cutover_v2.py"]))
        self.assertTrue(V2.apply_requested(["provider_cutover_v2.py", "--apply"]))

    def test_historical_v2_public_surface_is_preserved(self) -> None:
        for name in ("CutoverError", "GitHubAPI", "safe_extract", "verify_repository"):
            self.assertTrue(hasattr(V2, name), name)

    def test_export_builder_carries_wrapper_and_engine(self) -> None:
        source = (ROOT / "phoenix" / "build_exports_v2.py").read_text(encoding="utf-8")
        self.assertIn('"provider_cutover.py"', source)
        self.assertIn('"provider_cutover_v2_engine.py"', source)
        self.assertIn("V2_PROVIDER_EFFECT_RETIRED_COMPATIBILITY_BOUNDARY", source)
        self.assertIn("V2_PRESERVED_DRY_RUN_ENGINE", source)

    def test_preserved_engine_identity_matches_original_v2_blob(self) -> None:
        engine = ROOT / "phoenix" / "provider_cutover_v2_engine.py"
        self.assertTrue(engine.is_file())
        data = engine.read_bytes()
        text = data.decode("utf-8")
        self.assertIn("Provider-authorised Federation Omega Phoenix cutover v2", text)
        self.assertIn('API_VERSION = "2026-03-10"', text)
        header = f"blob {len(data)}\0".encode("ascii")
        self.assertEqual(hashlib.sha1(header + data).hexdigest(), "41a8e089c48f3772636b59521c47734a4ca98362")


if __name__ == "__main__":
    unittest.main()
