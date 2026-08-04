"""Canonical Alpha→Omega commercial maturity API.

The journal-safe atomic authority-snapshot control plane is the supported
live-authority entry point. Live authority requires a provider-native snapshot,
monotonic durable acceptance, exact action-level binding, atomic
prepare/commit/rollback, a durable recovery bundle, and atomically published
transaction events that cannot expose a torn final record after process restart.
Earlier control planes remain exported for historical regression and
mock-provider conformance.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

from authority_action_journal import (  # noqa: E402
    JournalSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_action_crash_recovery import (  # noqa: E402
    CrashSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_action_atomicity import (  # noqa: E402
    AtomicAuthoritySnapshotCommercialControlPlane,
)
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
    "JournalSafeAtomicAuthoritySnapshotCommercialControlPlane",
    "CrashSafeAtomicAuthoritySnapshotCommercialControlPlane",
    "AtomicAuthoritySnapshotCommercialControlPlane",
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
