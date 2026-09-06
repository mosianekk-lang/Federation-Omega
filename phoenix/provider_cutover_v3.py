#!/usr/bin/env python3
"""Fail-closed module boundary for the Phoenix v3 provider engine.

The provider engine is preserved byte-for-byte in provider_cutover_v3_engine.py.
This wrapper keeps imports compatible while prohibiting direct ``--apply``.
Only Phoenix v3.1 may open the short-lived internal engine apply context, and
v3.1 itself remains gated by the canonical live-source guarded launcher.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_PATH = HERE / "provider_cutover_v3_engine.py"
INTERNAL_APPLY_ENV = "FEDOMEGA_PHOENIX_V3_ENGINE_APPLY"

if not ENGINE_PATH.is_file():
    raise RuntimeError("Phoenix v3 provider engine is missing")

SPEC = importlib.util.spec_from_file_location("phoenix_provider_cutover_v3_engine", ENGINE_PATH)
assert SPEC and SPEC.loader
ENGINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENGINE
SPEC.loader.exec_module(ENGINE)

# Preserve the historical import surface without exposing the engine's CLI main.
for _name, _value in vars(ENGINE).items():
    if _name.startswith("__") or _name == "main":
        continue
    globals()[_name] = _value


def internal_apply_context(argv: list[str] | None = None) -> bool:
    args = list(sys.argv if argv is None else argv)
    if "--apply" not in args:
        return True
    return os.getenv(INTERNAL_APPLY_ENV) == "1"


def main() -> int:
    if not internal_apply_context():
        raise ENGINE.CutoverError(
            "Direct Phoenix v3 base --apply is prohibited; provider effects must enter through provider_cutover_guarded.py -> provider_cutover_v3_1.py"
        )
    return ENGINE.main()


if __name__ == "__main__":
    raise SystemExit(main())
