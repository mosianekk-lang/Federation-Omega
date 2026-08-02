"""Read a privacy-safe Formation mission summary from local JSON state."""

from __future__ import annotations

from pathlib import Path

from ..contracts import BlockerCode, CapabilityStatus
from ..errors import ContractError, PrivacyError
from ..privacy import reject_sensitive_tree, require_code, strict_json_loads
from .common import Observation, make_observation, read_local_text, safe_root

ALLOWED_MISSION_STATES = frozenset(
    {"OPEN", "PARTIAL_PROVEN", "READY", "AUTHORIZED", "PROVEN", "BLOCKED_WITH_ROUTE", "FAILED", "CANCELLED"}
)


def read_formation_state(
    root: str | Path,
    *,
    state_filename: str,
    node_id: str,
    owner_code: str,
    matter_code: str,
    observed_at: str,
) -> Observation:
    formation_root = safe_root(root)
    text = read_local_text(formation_root, state_filename)
    try:
        payload = strict_json_loads(text, field="formation_state")
    except PrivacyError as exc:
        raise ContractError("FORMATION_STATE_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise ContractError("FORMATION_STATE_OBJECT_REQUIRED")
    reject_sensitive_tree(payload)
    mission = payload.get("mission")
    if not isinstance(mission, dict):
        raise ContractError("FORMATION_MISSION_OBJECT_REQUIRED")
    allowed = {"id", "version", "state", "control_generation"}
    if set(mission) - allowed:
        raise ContractError("FORMATION_MISSION_FIELDS_NOT_MINIMIZED")
    mission_code = require_code(mission.get("id"), field="mission.id")
    mission_state = mission.get("state")
    if mission_state not in ALLOWED_MISSION_STATES:
        raise ContractError("UNKNOWN_FORMATION_MISSION_STATE")
    version = mission.get("version")
    generation = mission.get("control_generation")
    for name, value in (("version", version), ("control_generation", generation)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ContractError(f"INVALID_FORMATION_FIELD:{name}")
    blocker = BlockerCode.NONE if mission_state in {"READY", "AUTHORIZED", "PROVEN"} else BlockerCode.CAPABILITY_ABSENT
    status = CapabilityStatus.AVAILABLE if blocker is BlockerCode.NONE else CapabilityStatus.DEGRADED
    return make_observation(
        source_code="FORMATION_STATE",
        node_id=node_id,
        owner_code=owner_code,
        matter_code=matter_code,
        capability_code="FORMATION_STATE_READBACK",
        status=status,
        confidence_bp=9000,
        freshness_seconds=0,
        evidence_count=2,
        blocker_code=blocker,
        observed_at=observed_at,
        semantic_value={
            "mission_code": mission_code,
            "mission_version": version,
            "mission_state": mission_state,
            "control_generation": generation,
        },
    )
