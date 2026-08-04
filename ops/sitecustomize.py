"""Narrow runtime compatibility shim for the PST composite verifier.

GitHub-hosted runners do not permit the unprivileged job user to create a new
root under /mnt.  When—and only when—the PST composite verifier is the active
Python entrypoint, default its scratch root to /tmp.  An explicitly supplied
PST_VERIFY_ROOT always wins.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ENTRYPOINT = Path(sys.argv[0]).name if sys.argv else ""

if _ENTRYPOINT == "evidenceops_pst_v2_composite_verify.py":
    os.environ.setdefault("PST_VERIFY_ROOT", "/tmp/pst-composite-verify")
