"""Identity verification for SOVARA Gemini workflow receipts.

The expected challenge identity is derived from the admitted challenge spec and
collaboration request. Historical IDs are never embedded as verifier policy.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def verify_challenge_identity(
    receipt: Mapping[str, Any],
    challenge_spec: Mapping[str, Any],
    collaboration_request: Mapping[str, Any],
) -> bool:
    """Return true only when receipt, spec, and request bind the same identity."""

    expected_id = _clean(challenge_spec.get("challenge_id"))
    request_id = _clean(collaboration_request.get("request_id"))
    observed_id = _clean(receipt.get("challenge_id"))
    request_spec = _clean(collaboration_request.get("challenge_spec"))

    return bool(
        expected_id
        and request_id == expected_id
        and observed_id == expected_id
        and request_spec == "governance/sovara_creative_gemini_architecture_challenge_v1.json"
    )
