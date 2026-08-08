from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

class DispatchDecision(str, Enum):
    ASSIGNED = "ASSIGNED"
    SUPPLY_EXPANSION_REQUIRED = "SUPPLY_EXPANSION_REQUIRED"
    HOLD_AUTHORITY = "HOLD_AUTHORITY"

@dataclass(frozen=True)
class CommissionerCandidate:
    commissioner_id: str
    display_name: str
    authority_verified: bool
    authority_fresh: bool
    services: tuple[str, ...]
    service_area: str
    available: bool
    conflict_clear: bool
    distance_km: float = 0.0
    capacity_score: int = 100

@dataclass(frozen=True)
class DispatchRequest:
    transaction_id: str
    service: str
    service_area: str
    citizen_location_ref: str

@dataclass(frozen=True)
class DispatchResult:
    decision: DispatchDecision
    commissioner_id: str | None
    reasons: tuple[str, ...]
    citizen_message: str
    platform_next_action: str

class CommissionerDispatchEngine:
    """Assign an authority-verified commissioner so the citizen never has to search manually."""

    @staticmethod
    def _eligible(candidate: CommissionerCandidate, request: DispatchRequest) -> bool:
        return bool(
            candidate.available
            and candidate.authority_verified
            and candidate.authority_fresh
            and candidate.conflict_clear
            and request.service in candidate.services
            and candidate.service_area.strip().lower() == request.service_area.strip().lower()
        )

    def dispatch(self, request: DispatchRequest, candidates: Iterable[CommissionerCandidate]) -> DispatchResult:
        pool = list(candidates)
        eligible = [c for c in pool if self._eligible(c, request)]
        if eligible:
            # Prefer closest available verified commissioner, then higher spare capacity.
            chosen = sorted(eligible, key=lambda c: (c.distance_km, -c.capacity_score, c.commissioner_id))[0]
            return DispatchResult(
                DispatchDecision.ASSIGNED,
                chosen.commissioner_id,
                ("AUTHORITY_VERIFIED", "CURRENT_CAPACITY_VERIFIED", "CONFLICT_CLEAR", "SERVICE_AREA_MATCH"),
                "Your commissioner has been assigned. EvidenceOps will handle the appointment and evidence trail.",
                "Create appointment, bind commissioner authority snapshot, notify parties and capture the transaction-specific legal event.",
            )

        if any(c.available and request.service in c.services for c in pool):
            return DispatchResult(
                DispatchDecision.HOLD_AUTHORITY,
                None,
                ("AVAILABLE_SUPPLY_EXISTS_BUT_AUTHORITY_OR_CONFLICT_GATE_NOT_CLOSED",),
                "EvidenceOps is validating the available commissioner before assignment.",
                "Verify authority/current office/conflict status; do not expose an unverified commissioner to the citizen.",
            )

        return DispatchResult(
            DispatchDecision.SUPPLY_EXPANSION_REQUIRED,
            None,
            ("NO_ELIGIBLE_COMMISSIONER_IN_SERVICE_AREA",),
            "EvidenceOps is sourcing a commissioner for your area; you do not need to find one yourself.",
            "Open automated supply-expansion task for the area, recruit/verify qualifying commissioners and assign the first eligible candidate.",
        )
