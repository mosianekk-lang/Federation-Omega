from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .core import CapabilityFabric, CircuitBreaker, FormationKernel, LearningLedger, PermitVerifier, semantic_fingerprint
from .graph import GovernedReasoningGraph, GraphInputError, SemanticVerificationError
from .math_engine import calculate
from .principles import catalogue, doctrine_summary
from .providers import ProviderError, Reasoner, select_reasoner


class Jarvis:
    def __init__(self, state_dir: str | Path = "state", reasoner: Reasoner | None = None) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.reasoner = reasoner or select_reasoner()
        self.fabric = CapabilityFabric(self.reasoner.provider_mode)
        permit_verifier = PermitVerifier(
            os.getenv("JARVIS_FORMATION_HMAC_KEY"),
            self.state_dir / "consumed_permits.txt",
        )
        self.formation = FormationKernel(permit_verifier)
        self.ledger = LearningLedger(self.state_dir / "learning.jsonl")
        self.breaker = CircuitBreaker()
        self.graph = GovernedReasoningGraph()
        self.session_provider_proof: str | None = None

    def health(self) -> dict[str, Any]:
        return {
            "ok": self.ledger.verify(),
            "service": "jarvis-ultimate",
            "version": "1.1.0",
            "reasoner": self.reasoner.name,
            "providerMode": self.reasoner.provider_mode,
            "providerSessionProof": self.session_provider_proof,
            "ledgerValid": self.ledger.verify(),
            "runtimeState": "ON_DEMAND_GOVERNED",
            "maturity": "IMPLEMENTED_TESTED_LOCAL",
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "capabilities": self.fabric.inventory(),
            "quarantined": sorted(self.breaker.quarantined),
            "actionSchemas": sorted(self.formation_action_ids()),
        }

    @staticmethod
    def formation_action_ids() -> list[str]:
        from .core import ACTION_SPECS

        return list(ACTION_SPECS)

    def plan(self, objective: str) -> dict[str, Any]:
        objective = objective.strip()
        if not objective:
            raise GraphInputError("OBJECTIVE_REQUIRED")
        mission = "JARVIS-" + uuid.uuid4().hex[:12]
        return {
            "missionId": mission,
            "objective": objective,
            "taskState": "CREATED",
            "principles": [principle["id"] for principle in catalogue()],
            "steps": [
                "observe",
                "define terminal fruit",
                "select verified route",
                "run advisory twin",
                "gate exact action schema",
                "execute one minimum effectful path",
                "semantic readback",
                "capture unpromoted learning candidate",
                "stop",
            ],
            "effectfulPathsAllowed": 1,
        }

    def chat(self, message: str) -> dict[str, Any]:
        started = time.perf_counter()
        route = self.reasoner.name
        if not self.breaker.allows(route):
            elapsed = int((time.perf_counter() - started) * 1000)
            evidence_hash = semantic_fingerprint({"route": route, "state": "QUARANTINED"})
            event = self.ledger.append(route, "QUARANTINED", elapsed, evidence_hash, semantic_fruit=False)
            return {
                "answer": "Provider route is quarantined pending two independent bounded recovery proofs.",
                "route": route,
                "elapsedMs": elapsed,
                "learningHash": event["hash"],
                "learningPromotion": "NOT_PROMOTED",
                "quarantined": True,
                "workflowEvents": [],
            }

        context = {
            "capabilities": self.fabric.inventory(),
            "principles": catalogue(),
            "doctrine": doctrine_summary(),
        }
        try:
            graph_result = self.graph.run(message, context, self.reasoner)
            answer = graph_result.reasoning.text
            evidence_hash = graph_result.evidence_hash
            workflow_events = [event.public() for event in graph_result.events]
            success = True
            error_code = None
        except (ProviderError, GraphInputError, SemanticVerificationError) as exc:
            answer = f"Route failed closed: {str(exc)}"
            evidence_hash = semantic_fingerprint({"route": route, "error": str(exc)})
            workflow_events = []
            success = False
            error_code = str(exc)

        elapsed = int((time.perf_counter() - started) * 1000)
        self.breaker.record(route, success)
        event = self.ledger.append(
            route,
            "SUCCESS" if success else "FAILURE",
            elapsed,
            evidence_hash,
            semantic_fruit=success,
        )
        if success and self.reasoner.provider_mode != "offline":
            self.session_provider_proof = f"session-semantic:{evidence_hash}"
            self.fabric.record_session_semantic_proof("gemini", self.session_provider_proof)
        return {
            "answer": answer,
            "route": route,
            "providerMode": self.reasoner.provider_mode,
            "elapsedMs": elapsed,
            "semanticFruit": success,
            "error": error_code,
            "learningHash": event["hash"],
            "learningPromotion": "NOT_PROMOTED",
            "quarantined": route in self.breaker.quarantined,
            "workflowEvents": workflow_events,
        }

    def authorize(
        self,
        mission_id: str,
        action_id: str,
        capability_id: str,
        permit: str | None = None,
    ) -> dict[str, Any]:
        decision = self.formation.decide(
            mission_id,
            action_id,
            self.fabric.get(capability_id),
            permit,
            consume_permit=False,
        )
        return asdict(decision)

    def authorize_for_execution(
        self,
        mission_id: str,
        action_id: str,
        capability_id: str,
        permit: str | None,
    ) -> dict[str, Any]:
        """Executor-only transaction boundary; not exposed by the HTTP service."""
        decision = self.formation.decide(
            mission_id,
            action_id,
            self.fabric.get(capability_id),
            permit,
            consume_permit=True,
        )
        return asdict(decision)

    def math(self, expression: str) -> dict[str, Any]:
        result = calculate(expression)
        return {
            **asdict(result),
            "epistemicBoundary": "deterministic calculation; interpretation and model assumptions remain separate",
        }
