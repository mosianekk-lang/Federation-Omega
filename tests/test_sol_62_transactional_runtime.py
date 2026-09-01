from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOL = ROOT / "sol_61_runtime"
if str(SOL) not in sys.path:
    sys.path.insert(0, str(SOL))

from test_sol_62_strict_runtime import *  # noqa: F401,F403,E402
