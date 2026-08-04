from __future__ import annotations

from copy import deepcopy
from typing import Any

from authority_snapshot import digest
from provider_reconciliation_challenge import (
    ChallengeBoundMockProviderAdapter,
    ChallengeBoundProviderDispatchCommercialControlPlane as _ChallengeBoundProviderDispatchCommercialControlPlane,
    MAX_CHALLENGE_TTL_SECONDS,
    MIN_CHALLENGE_TTL_SECONDS,
    RECONCILIATION_CHALLENGE_CLASS,
)

_CHALLENGE_VERIFIED_STATE = (
    "MOCK_PROVIDER_CHALLENGE_RECONCILIATION_CONFORMANCE_VERIFIED_"
    "LIVE_PROVIDER_PROOF_REQUIRED"
)
_FENCING_VERIFIED_STATE = (
    "MOCK_PROVIDER_FENCING_CONFORMANCE_VERIFIED_"
    "LIVE_PROVIDER_PROOF_REQUIRED"
)


class ChallengeBoundProviderDispatchCommercialControlPlane(
    _ChallengeBoundProviderDispatchCommercialControlPlane
):
    """Restart-safe V15 projection preserving the challenge-specific state label.

    The inherited V13 verifier knows the receipt semantics but predates the V15
    state label. For that one label, verify the original record hash first, then
    validate an exact deep copy through the inherited fencing state. The stored
    record and its hash are never rewritten or weakened.
    """

    @staticmethod
    def _verify_dispatch_record(record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise RuntimeError("provider dispatch record invalid")
        if record.get("state") != _CHALLENGE_VERIFIED_STATE:
            return _ChallengeBoundProviderDispatchCommercialControlPlane._verify_dispatch_record(
                record
            )

        original_payload = dict(record)
        original_hash = original_payload.pop("record_sha256", None)
        if original_hash != digest(original_payload):
            raise RuntimeError("provider dispatch record hash invalid")

        normalized = deepcopy(record)
        normalized.pop("record_sha256", None)
        normalized["state"] = _FENCING_VERIFIED_STATE
        normalized["record_sha256"] = digest(normalized)
        _ChallengeBoundProviderDispatchCommercialControlPlane._verify_dispatch_record(
            normalized
        )
        return dict(record)


__all__ = [
    "ChallengeBoundProviderDispatchCommercialControlPlane",
    "ChallengeBoundMockProviderAdapter",
    "RECONCILIATION_CHALLENGE_CLASS",
    "MIN_CHALLENGE_TTL_SECONDS",
    "MAX_CHALLENGE_TTL_SECONDS",
]
