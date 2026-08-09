"""TruthGrid fail-closed enforcement primitives.

This package contains deterministic guards used by EvidenceOps writers before any
TruthGrid mutation or release-state promotion.  Source/configuration existence is
not runtime proof; callers must preserve independent provider readback receipts.
"""

from .guards import (
    Mission,
    MissionLockDecision,
    MutationIntent,
    TruthGridGuard,
    TruthGridViolation,
)

__all__ = [
    "Mission",
    "MissionLockDecision",
    "MutationIntent",
    "TruthGridGuard",
    "TruthGridViolation",
]
