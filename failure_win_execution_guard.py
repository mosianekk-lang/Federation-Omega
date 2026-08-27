from __future__ import annotations

from typing import Any, Iterable, Mapping


_BEHAVIOR_PROVEN_STATES = {"BEHAVIOR_PROVEN", "V2_BEHAVIOR_PROVEN"}
_NO_ELIGIBLE_REASON = "NO_RECEIVER_HAS_ROLLOUT_AUTHORITY_WITH_CURRENT_BEHAVIORAL_PROOF"


def _eligible(receiver: Mapping[str, Any]) -> bool:
    return (
        str(receiver.get("state", "")) in _BEHAVIOR_PROVEN_STATES
        and bool(receiver.get("current", False))
        and bool(receiver.get("independent_readback", False))
        and bool(receiver.get("rollout_authority", False))
        and bool(str(receiver.get("behavioral_proof_ref", "")).strip())
    )


def evaluate_failure_win_execution(receivers: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Gate rollout authority independently from behavioral proof.

    Behavior proof never manufactures authority. Only receivers with current,
    independently read back behavioral proof *and* separately granted rollout
    authority are eligible. This function is pure and creates no provider effect.
    """

    rows = [dict(receiver) for receiver in receivers]
    eligible = [str(row.get("receiver_id", "")) for row in rows if _eligible(row)]
    eligible = [receiver_id for receiver_id in eligible if receiver_id]

    if not eligible:
        return {
            "decision": "HOLD_NO_EXECUTION",
            "eligible_receivers": [],
            "reasons": [_NO_ELIGIBLE_REASON],
            "behavior_proof_confers_authority": False,
            "external_effect": False,
        }

    return {
        "decision": "EXECUTION_ALLOWED_BOUNDED",
        "eligible_receivers": eligible,
        "reasons": ["CURRENT_BEHAVIORAL_PROOF_AND_SEPARATE_ROLLOUT_AUTHORITY_PRESENT"],
        "behavior_proof_confers_authority": False,
        "external_effect": False,
    }


__all__ = ["evaluate_failure_win_execution"]
