"""Canonical Alpha→Omega commercial maturity API.

The authority-snapshot control plane is the supported live-authority entry point.
The v2 governed control plane remains exported for historical regression and
mock-provider conformance only. The legacy assurance class remains in its original
module for historical regression only.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

from authority_snapshot import (  # noqa: E402
    AuthorityDomainLease,
    CommercialAuthoritySnapshot,
    CommercialAuthoritySnapshotValidator,
    build_authority_snapshot,
)
from authority_snapshot_acceptance import (  # noqa: E402
    AuthoritySnapshotAcceptanceDecision,
    AuthoritySnapshotAcceptanceLedger,
)
from authority_snapshot_control_plane import (  # noqa: E402
    AuthoritySnapshotCommercialControlPlane,
)
from governed_commercial_assurance import (  # noqa: E402
    GovernedCommercialAssuranceControlPlane,
    LIVE_AUTHORITY_CLASS,
    MOCK_AUTHORITY_CLASS,
)

__all__ = [
    "AuthoritySnapshotCommercialControlPlane",
    "AuthoritySnapshotAcceptanceDecision",
    "AuthoritySnapshotAcceptanceLedger",
    "AuthorityDomainLease",
    "CommercialAuthoritySnapshot",
    "CommercialAuthoritySnapshotValidator",
    "build_authority_snapshot",
    "GovernedCommercialAssuranceControlPlane",
    "LIVE_AUTHORITY_CLASS",
    "MOCK_AUTHORITY_CLASS",
]
