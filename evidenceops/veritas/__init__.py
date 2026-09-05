"""Veritas-Ω bounded A0 execution adapter.

This package exposes the canonical VER-TRU-001 service through the common
EvidenceOps six-contract interface without granting provider, legal, filing,
or mutation authority.
"""

from .adapter import (
    AuthorityDecision,
    ExecutionProof,
    VeritasAdapter,
    VeritasRequest,
)

__all__ = [
    "AuthorityDecision",
    "ExecutionProof",
    "VeritasAdapter",
    "VeritasRequest",
]
