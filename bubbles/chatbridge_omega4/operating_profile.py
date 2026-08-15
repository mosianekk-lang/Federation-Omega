from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class OperatingProfile:
    """Portable behavioural contract restored with a ChatBridge namespace.

    The profile is intentionally provider-neutral. It records how the restored workstream
    should operate, while the GovernanceCapsule continues to own authority, approval,
    confidentiality and external-effect boundaries.
    """

    profile_id: str
    version: str = "CBOP-1.0"
    execution_posture: str = "EXECUTE_VERIFY_READBACK"
    reconcile_not_rebuild: bool = True
    creator_mode: bool = True
    federation_route_scan: bool = True
    forest_first: bool = False
    failure_knowledge: bool = False
    harmonic_evolution: bool = False
    inplace_evolution: bool = False
    evidenceops_assurance: bool = False
    background_compute_fabric: bool = False
    live_bible_ref: str = ""
    master_bible_ref: str = ""
    master_sync_ref: str = ""
    active_systems: Tuple[str, ...] = field(default_factory=tuple)
    owner_interrupt_policy: str = "ONLY_CONSEQUENTIAL_OR_NONDELEGABLE"
    capture_policy: str = "SUBSTANTIVE_DELTA_TO_LOCAL_LIVE_BIBLE_WHEN_AVAILABLE"
    restore_policy: str = "DELTA_FIRST_RECONCILE_DONT_REBUILD_RESUME"
    anticipatory_policy: str = "NEXT_WHY_NOW_AND_UNLOCKS"
    packaging_policy: str = "HOT_MINIMUM_WARM_CANONICAL_POINTERS_COLD_HISTORY_POINTERS"
    notes: str = ""

    @classmethod
    def default(cls) -> "OperatingProfile":
        return cls(profile_id="CBOP-DEFAULT-EXECUTE-NOW-1")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["active_systems"] = list(self.active_systems)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OperatingProfile":
        data = dict(payload)
        if "active_systems" in data and not isinstance(data["active_systems"], tuple):
            data["active_systems"] = tuple(data["active_systems"])
        return cls(**data)
