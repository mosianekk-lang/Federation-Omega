#!/usr/bin/env python3
"""Fail-closed compatibility boundary for Phoenix provider cutover v2.

The historical v2 engine is preserved byte-for-byte in
``provider_cutover_v2_engine.py`` for import compatibility and dry-run analysis.
Provider mutation through v2 is permanently retired: ``--apply`` must use the
current guarded v3 chain instead.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_PATH = HERE / "provider_cutover_v2_engine.py"
if not ENGINE_PATH.is_file():
    raise RuntimeError("Phoenix v2 provider engine is missing")

SPEC = importlib.util.spec_from_file_location("_phoenix_provider_cutover_v2_engine_guarded", ENGINE_PATH)
assert SPEC and SPEC.loader
ENGINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENGINE
SPEC.loader.exec_module(ENGINE)

if not hasattr(ENGINE, "CutoverError"):
    raise RuntimeError("Phoenix v2 provider engine identity check failed")

for _name in dir(ENGINE):
    if _name.startswith("__") or _name == "main":
        continue
    globals()[_name] = getattr(ENGINE, _name)


def apply_requested(argv: list[str] | None = None) -> bool:
    args = list(sys.argv if argv is None else argv)
    return "--apply" in args


def main() -> int:
    if apply_requested():
        raise ENGINE.CutoverError(
            "Phoenix v2 --apply is retired; provider effects must use provider_cutover_guarded.py -> provider_cutover_v3_1.py"
        )
    return ENGINE.main()


if __name__ == "__main__":
    raise SystemExit(main())
