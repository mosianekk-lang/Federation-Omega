from __future__ import annotations

from typing import Any

from .event_store import EventStore
from .models import SAFE_ID


class CanonicalQueryService:
    def __init__(self, store: EventStore):
        self.store = store

    def entity(self, entity_id: str) -> dict[str, Any]:
        if not SAFE_ID.fullmatch(entity_id):
            raise ValueError("invalid entity_id")
        projection = self.store.project(entity_id)
        proof_state = "SOURCE_LOCATED"
        if projection["event_count"] > 0:
            proof_state = "READBACK_VERIFIED"
        return {
            "query": "ENTITY_CURRENT_STATE",
            "proof_state": proof_state,
            **projection,
        }

    def mission(self, mission_id: str) -> dict[str, Any]:
        if not SAFE_ID.fullmatch(mission_id):
            raise ValueError("invalid mission_id")
        mission = self.store.get_mission(mission_id)
        return {
            "query": "MISSION_CONTRACT",
            "mission_id": mission_id,
            "proof_state": "READBACK_VERIFIED" if mission else "UNKNOWN",
            "mission": mission,
        }

    def route(self, objective: str) -> dict[str, Any]:
        text = objective.casefold()
        if any(word in text for word in ("legal", "evidence", "ccma", "hearing", "paia")):
            system = "EVIDENCEOPS"
            adapter = "evidenceops_legal"
        elif any(word in text for word in ("trade", "market", "strategy")):
            system = "OMEGA-MARKET"
            adapter = "trading_research"
        elif any(word in text for word in ("cloud", "github", "deploy", "software", "ict")):
            system = "FEDERATION-ICT"
            adapter = "generic"
        else:
            system = "FEDERATION-OMEGA"
            adapter = "generic"
        return {
            "query": "CANONICAL_ROUTE",
            "system": system,
            "adapter": adapter,
            "authority_ceiling": "A1",
            "external_effects": False,
            "confidence": 0.75,
        }
