#!/usr/bin/env python3
from __future__ import annotations

"""Compatibility entrypoint for the Superior Logic maturation shadow runtime.

The canonical provider invocation is:
    python -m evidenceops.caseforge.maturation_shadow_cli

This wrapper preserves direct-script usability by explicitly placing the repository
root on sys.path before delegating to the package-native CLI. This prevents the
provider-only import failure captured in run 33126859126.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidenceops.caseforge.maturation_shadow_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
