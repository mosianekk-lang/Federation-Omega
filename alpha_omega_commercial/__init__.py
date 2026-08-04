"""Canonical Alpha→Omega commercial maturity API.

The governed control plane is the supported entry point. The legacy assurance class
remains in its original module for historical regression only.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

from governed_commercial_assurance import (  # noqa: E402
    GovernedCommercialAssuranceControlPlane,
    LIVE_AUTHORITY_CLASS,
    MOCK_AUTHORITY_CLASS,
)

__all__ = [
    "GovernedCommercialAssuranceControlPlane",
    "LIVE_AUTHORITY_CLASS",
    "MOCK_AUTHORITY_CLASS",
]
