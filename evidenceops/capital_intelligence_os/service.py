from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Mapping, Any
from .autopilot import Autopilot
from .capital import GravityEngine, FinancingStressEngine
from .mna import DealLifecycle
from .models import ActionRequest, CapitalCandidate, Claim, Event

class CapitalIntelligenceService:
    """Provider-neutral application facade for the Genesis vertical slice."""
    def __init__(self) -> None:
        self.autopilot = Autopilot()
        self.gravity = GravityEngine()
        self.financing = FinancingStressEngine()
        self.deals: dict[str, DealLifecycle] = {}
    def ingest(self, event: Event, claims: Iterable[Claim] = (), actions: Iterable[ActionRequest] = ()) -> Mapping[str, Any]:
        return asdict(self.autopilot.process(event, claims, actions))
    def rank_capital(self, candidates: Iterable[CapitalCandidate]) -> list[Mapping[str, Any]]:
        return [asdict(item) for item in self.gravity.rank(candidates)]
    def deal(self, deal_id: str) -> DealLifecycle:
        if deal_id not in self.deals:
            self.deals[deal_id] = DealLifecycle(deal_id)
        return self.deals[deal_id]
    def health(self) -> Mapping[str, Any]:
        return {"service": "EvidenceOps Capital Intelligence OS", "release": "0.1.0-genesis", "authority_ceiling": "A1_INTERNAL", "live_trading": False, "external_financial_effects": False, "learning_chain_valid": self.autopilot.ledger.verify(), "deal_count": len(self.deals)}
