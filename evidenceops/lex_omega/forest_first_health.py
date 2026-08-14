from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class ForestFirstHealthState(str, Enum):
    """Human-readable operational state for Forest-First.

    The health state describes the currently evidenced control stack. It does
    not claim model-weight changes, legal accuracy, provider deployment or
    invisible activation in unrelated chats.
    """

    NOT_LOADED = "NOT_LOADED"
    SYSTEM_READY_SESSION_NOT_RESTORED = "SYSTEM_READY_SESSION_NOT_RESTORED"
    ACTIVE_VERIFIED = "ACTIVE_VERIFIED"
    DEGRADED = "DEGRADED"
    BLOCKED_HIGH_STAKES = "BLOCKED_HIGH_STAKES"


@dataclass(frozen=True)
class ForestFirstHealthInputs:
    canonical_doctrine_readback: bool = False
    runtime_source_readback: bool = False
    private_state_readback: bool = False
    session_restore_verified: bool = False
    risk_vs_proof_control_loaded: bool = False
    merits_genome_control_loaded: bool = False
    legal_route_card_control_loaded: bool = False
    position_change_control_loaded: bool = False
    teach_back_control_loaded: bool = False
    pleading_integrity_control_loaded: bool = False
    jfrie_binding_loaded: bool = False
    continuity_control_loaded: bool = False
    latest_regression_passed: bool = False


@dataclass(frozen=True)
class ForestFirstHealthReport:
    state: ForestFirstHealthState
    status_line: str
    missing_controls: Tuple[str, ...]
    blocking_controls: Tuple[str, ...]
    recommended_action: str
    safe_for_consequential_legal_release: bool
    truth_boundary: Tuple[str, ...] = (
        "Forest-First health does not prove the merits of a legal matter.",
        "Forest-First health does not prove current-law correctness without authority verification.",
        "Forest-First health does not prove provider deployment or invisible cross-chat activation.",
    )


_REQUIRED_CONTROLS = {
    "CANONICAL_DOCTRINE_READBACK": "canonical_doctrine_readback",
    "RUNTIME_SOURCE_READBACK": "runtime_source_readback",
    "PRIVATE_STATE_READBACK": "private_state_readback",
    "SESSION_RESTORE_VERIFIED": "session_restore_verified",
    "RISK_VS_PROOF_CONTROL": "risk_vs_proof_control_loaded",
    "MERITS_GENOME_CONTROL": "merits_genome_control_loaded",
    "LEGAL_ROUTE_CARD_CONTROL": "legal_route_card_control_loaded",
    "POSITION_CHANGE_CONTROL": "position_change_control_loaded",
    "TEACH_BACK_CONTROL": "teach_back_control_loaded",
    "PLEADING_INTEGRITY_CONTROL": "pleading_integrity_control_loaded",
    "JFRIE_BINDING": "jfrie_binding_loaded",
    "CONTINUITY_CONTROL": "continuity_control_loaded",
    "LATEST_REGRESSION_PASS": "latest_regression_passed",
}

_HIGH_STAKES_BLOCKERS = {
    "LEGAL_ROUTE_CARD_CONTROL",
    "TEACH_BACK_CONTROL",
    "JFRIE_BINDING",
    "RISK_VS_PROOF_CONTROL",
}


def evaluate_forest_first_health(
    inputs: ForestFirstHealthInputs,
    *,
    consequential_legal_work: bool = False,
) -> ForestFirstHealthReport:
    missing = tuple(
        name
        for name, field_name in _REQUIRED_CONTROLS.items()
        if not getattr(inputs, field_name)
    )
    blocking = tuple(name for name in missing if name in _HIGH_STAKES_BLOCKERS)

    base_system_ready = (
        inputs.canonical_doctrine_readback
        and inputs.runtime_source_readback
        and inputs.private_state_readback
        and inputs.latest_regression_passed
    )

    if not inputs.canonical_doctrine_readback and not inputs.runtime_source_readback:
        state = ForestFirstHealthState.NOT_LOADED
        action = (
            "Restore Forest-First from the canonical continuity capsule and verified runtime source before relying on it."
        )
    elif consequential_legal_work and blocking:
        state = ForestFirstHealthState.BLOCKED_HIGH_STAKES
        action = (
            "Do not treat consequential legal drafting as release-ready until the blocking controls are restored and read back."
        )
    elif base_system_ready and not inputs.session_restore_verified:
        state = ForestFirstHealthState.SYSTEM_READY_SESSION_NOT_RESTORED
        action = (
            "The system exists and is verified, but this session has not proved restoration. Run ChatBridge/Forest-First restore and re-check health."
        )
    elif not missing:
        state = ForestFirstHealthState.ACTIVE_VERIFIED
        action = "Continue under Forest-First controls and re-check after material capability, legal-route or continuity changes."
    else:
        state = ForestFirstHealthState.DEGRADED
        action = (
            "Continue only within the controls that are verified; restore missing controls before consequential release."
        )

    safe_release = state is ForestFirstHealthState.ACTIVE_VERIFIED and not blocking
    return ForestFirstHealthReport(
        state=state,
        status_line=f"FOREST-FIRST: {state.value}",
        missing_controls=missing,
        blocking_controls=blocking,
        recommended_action=action,
        safe_for_consequential_legal_release=safe_release,
    )


__all__ = [
    "ForestFirstHealthInputs",
    "ForestFirstHealthReport",
    "ForestFirstHealthState",
    "evaluate_forest_first_health",
]
