from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from .core import CapabilityFabric, CircuitBreaker, FormationKernel, LearningLedger, semantic_fingerprint
from .execution import TwentyMinuteGovernor
from .principles import catalogue
from .providers import select_reasoner


class Jarvis:
    def __init__(self, state_dir: str | Path = "state") -> None:
        self.fabric = CapabilityFabric()
        self.formation = FormationKernel()
        self.reasoner = select_reasoner()
        self.ledger = LearningLedger(Path(state_dir) / "learning.jsonl")
        self.breaker = CircuitBreaker()
        self.execution = TwentyMinuteGovernor()

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "jarvis-ultimate",
            "version": "1.0.0",
            "reasoner": self.reasoner.name,
            "ledgerValid": self.ledger.verify(),
            "runtimeState": "ON_DEMAND_GOVERNED",
            "executionPolicy": self.execution.policy.id,
            "directiveEnvelopeSeconds": self.execution.policy.max_directive_seconds,
        }

    def capabilities(self) -> dict[str, Any]:
        return {"capabilities": self.fabric.inventory(), "quarantined": sorted(self.breaker.quarantined)}

    def execution_policy(self) -> dict[str, Any]:
        return self.execution.describe()

    def plan(self, objective: str) -> dict[str, Any]:
        mission = "JARVIS-" + uuid.uuid4().hex[:12]
        plan = self.execution.build_plan(mission, objective)
        plan["principles"] = [p["id"] for p in catalogue()]
        plan["effectfulPathsAllowed"] = 1
        return plan

    def review_cycle(self, elapsed_seconds: int, quality_gates: Mapping[str, bool], retries: int = 0) -> dict[str, Any]:
        review = self.execution.review_cycle(elapsed_seconds, quality_gates, retries)
        event = self.ledger.append(
            "omega-scientist-cycle-review",
            "SUCCESS" if review["cyclePass"] else "FAILURE",
            elapsed_seconds * 1000,
            semantic_fingerprint(review),
        )
        review["learningHash"] = event["hash"]
        return review

    def chat(self, message: str) -> dict[str, Any]:
        started = time.perf_counter()
        context = {
            "capabilities": self.fabric.inventory(),
            "principles": catalogue(),
            "executionPolicy": self.execution.describe(),
        }
        route = self.reasoner.name
        try:
            answer = self.reasoner.respond(message, context)
            success = bool(answer)
        except Exception as exc:
            answer = f"Provider route failed closed: {type(exc).__name__}"
            success = False
        elapsed = int((time.perf_counter() - started) * 1000)
        self.breaker.record(route, success)
        event = self.ledger.append(route, "SUCCESS" if success else "FAILURE", elapsed, semantic_fingerprint({"message": message, "answer": answer}))
        return {"answer": answer, "route": route, "elapsedMs": elapsed, "learningHash": event["hash"], "quarantined": route in self.breaker.quarantined}

    def authorize(self, mission_id: str, action: str, capability_id: str, permit: str | None = None) -> dict[str, Any]:
        decision = self.formation.decide(mission_id, action, self.fabric.get(capability_id), permit)
        return decision.__dict__
