from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LASE_SRC = ROOT / "systems" / "lex-autonomous-strategy" / "src"
NESTED_TEST = ROOT / "systems" / "lex-autonomous-strategy" / "tests" / "test_hardening_v2.py"

sys.path.insert(0, str(LASE_SRC))

spec = importlib.util.spec_from_file_location("_lex_hardening_v2_nested_tests", NESTED_TEST)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load nested LEX hardening tests: {NESTED_TEST}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

LexHardeningV2Tests = module.LexHardeningV2Tests
