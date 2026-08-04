"""Canonical Alpha→Omega commercial maturity API.

The provider-dispatch-outbox control plane is the newest service-platform
candidate. It preserves the V10 crash-safe exact-request boundary and adds a
hash-bound provider command outbox with a stable provider idempotency key,
restart-safe mock-provider receipt admission and a fail-closed live-provider
proof boundary. Earlier control planes remain exported for historical
regression and reference-provider conformance.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

from provider_dispatch_outbox import (  # noqa: E402
    ConformantMockProviderAdapter,
    ProviderDispatchOutboxCommercialControlPlane,
)
from authority_action_idempotency import (  # noqa: E402
    IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
)
from authority_action_coordination import (  # noqa: E402
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane,
)
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
    "ProviderDispatchOutboxCommercialControlPlane",
    "ConformantMockProviderAdapter",
    "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane",
    "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane",
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
