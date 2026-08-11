from __future__ import annotations

from typing import Iterable
from .algorithms import AttentionCompressionEngine, EpistemicShockIndex, FragilityCascade
from .authority import AuthorityGuard
from .learning import LearningLedger
from .models import ActionRequest, Alert, AutopilotResult, Claim, Event
from .proofgraph import ProofGraph

class Autopilot:
    """Bounded event-driven control loop for safe internal A0/A1 automation."""
    def __init__(self, graph: ProofGraph | None = None, authority: AuthorityGuard | None = None, ledger: LearningLedger | None = None) -> None:
        self.graph = graph or ProofGraph()
        self.authority = authority or AuthorityGuard()
        self.ledger = ledger or LearningLedger()
        self.attention = AttentionCompressionEngine()
        self.shock = EpistemicShockIndex()
        self.fragility = FragilityCascade()

    def process(self, event: Event, claims: Iterable[Claim] = (), requested_actions: Iterable[ActionRequest] = ()) -> AutopilotResult:
        event.validate()
        claim_ids: list[str] = []
        contradiction_ids: list[str] = []
        alerts: list[Alert] = []
        for claim in claims:
            shock = self.shock.score(self.graph, claim)
            contradictions = self.graph.add_claim(claim)
            claim_ids.append(claim.claim_id)
            contradiction_ids.extend(c.contradiction_id for c in contradictions)
            if contradictions or shock >= 0.45:
                alert = self.attention.make_alert(claim.subject_id, f"Material evidence state changed for {claim.predicate}", materiality=max(event.materiality, shock), uncertainty=1.0 - claim.confidence, irreversibility=0.30, deadline_pressure=0.20, auto_resolvability=0.25 if contradictions else 0.55)
                if alert:
                    alert.reason_codes.extend(["CONTRADICTION" if contradictions else "EPISTEMIC_SHOCK"])
                    alerts.append(alert)
        impacted = self.graph.impact_of(event.subject_id)
        if event.materiality >= 0.55 and impacted:
            alert = self.attention.make_alert(event.subject_id, f"Material change propagates to {len(impacted)} dependent object(s)", materiality=event.materiality, uncertainty=0.35, irreversibility=0.25, deadline_pressure=0.25, auto_resolvability=0.45)
            if alert:
                alert.reason_codes.append("IMPACT_PROPAGATION")
                alerts.append(alert)
        action_decisions = [self.authority.evaluate(action) for action in requested_actions]
        learning = self.ledger.append("SUCCESS", "AUTOPILOT_EVENT", {"event_type": event.event_type, "domain": event.domain.value, "claim_count": len(claim_ids), "contradiction_count": len(contradiction_ids), "impacted_count": len(impacted), "alert_count": len(alerts), "action_dispositions": [d.disposition.value for d in action_decisions]})
        return AutopilotResult(event.event_id, claim_ids, contradiction_ids, impacted, alerts, action_decisions, learning.event_hash)
