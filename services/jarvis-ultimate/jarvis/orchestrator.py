from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .authority import AuthorityEnvelope
from .core import ACTION_SPECS, CapabilityFabric, CircuitBreaker, FormationKernel, LearningLedger, LedgerIntegrityError, PermitVerifier, semantic_fingerprint
from .execution import TwentyMinuteGovernor
from .graph import GovernedReasoningGraph, GraphInputError, SemanticVerificationError
from .math_engine import MathExpressionError, calculate
from .principles import catalogue, doctrine_summary
from .providers import OfflineReasoner, ProviderError, Reasoner, select_reasoner


class Jarvis:
    def __init__(self, state_dir: str | Path = "state", reasoner: Reasoner | None = None) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.reasoner = reasoner or select_reasoner()
        self.fabric = CapabilityFabric(self.reasoner.provider_mode)
        permit_verifier = PermitVerifier(
            os.getenv("JARVIS_FORMATION_ED25519_PUBLIC_KEY"),
            self.state_dir / "consumed_permits.txt",
        )
        self.formation = FormationKernel(permit_verifier)
        self.ledger = LearningLedger(
            self.state_dir / "learning.jsonl",
            os.getenv("JARVIS_LEDGER_HMAC_KEY"),
            os.getenv("JARVIS_LEDGER_ANCHOR_PATH"),
        )
        self.breaker = CircuitBreaker()
        self.graph = GovernedReasoningGraph()
        self.execution = TwentyMinuteGovernor()
        self.session_provider_proof: str | None = None
        self.session_provider_receipt: str | None = None

    def health(self) -> dict[str, Any]:
        ledger_valid = self.ledger.verify()
        return {
            "ok": ledger_valid,
            "service": "jarvis-ultimate",
            "version": "1.4.0",
            "reasoner": self.reasoner.name,
            "providerMode": self.reasoner.provider_mode,
            "providerSessionProof": self.session_provider_proof,
            "providerSessionReceipt": self.session_provider_receipt,
            "ledgerValid": ledger_valid,
            "ledgerCheckpointAuthenticated": self.ledger.authenticated_checkpoint_enabled,
            "ledgerExternalAnchorBound": self.ledger.external_anchor_enabled,
            "runtimeState": "ON_DEMAND_GOVERNED",
            "maturity": "IMPLEMENTED_TESTED_LOCAL",
            "executionPolicy": self.execution.policy.id,
            "lessonGate": self.execution.policy.lesson_gate_id,
            "directiveEnvelopeSeconds": self.execution.policy.max_directive_seconds,
            "emailSendRule": self.execution.policy.email_send_rule,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "capabilities": self.fabric.inventory(),
            "quarantined": sorted(self.breaker.quarantined),
            "actionSchemas": [ACTION_SPECS[key].public() for key in sorted(ACTION_SPECS)],
            "executionPolicy": self.execution.describe(),
        }

    def execution_policy(self) -> dict[str, Any]:
        return self.execution.describe()

    @staticmethod
    def formation_action_ids() -> list[str]:
        return list(ACTION_SPECS)

    def plan(
        self,
        objective: str,
        deliverable_form: str | None = None,
        expected_state_delta: str | None = None,
    ) -> dict[str, Any]:
        objective = objective.strip()
        if not objective:
            raise GraphInputError("OBJECTIVE_REQUIRED")
        mission = "JARVIS-" + uuid.uuid4().hex[:12]
        plan = self.execution.build_plan(
            mission,
            objective,
            deliverable_form=deliverable_form,
            expected_state_delta=expected_state_delta,
        )
        plan.update(
            {
                "taskState": "CREATED",
                "principles": [principle["id"] for principle in catalogue()],
                "workflowSteps": [
                    "observe current verified state",
                    "lock objective form and expected state delta",
                    "select verified routes and run advisory twin",
                    "fan out only independent streams",
                    "gate exact action schema and authority",
                    "execute one minimum effectful path when separately authorized",
                    "fan in tests adversarial review and semantic readback",
                    "capture unpromoted learning candidate",
                    "emit completion state and next best automated pathway",
                    "stop",
                ],
                "effectfulPathsAllowed": 1,
            }
        )
        return plan

    def review_cycle(
        self,
        elapsed_seconds: int,
        quality_evidence: Mapping[str, Mapping[str, Any] | bool],
        route_results: Sequence[Mapping[str, Any]],
        next_best_automated_pathway: str,
        retries: int = 0,
    ) -> dict[str, Any]:
        if not self.ledger.verify():
            raise LedgerIntegrityError("LEDGER_INTEGRITY_FAILED")
        review = self.execution.review_cycle(
            elapsed_seconds,
            quality_evidence,
            route_results,
            next_best_automated_pathway,
            retries,
        )
        outcome = "SUCCESS" if review["qualityPass"] and review["meaningfulStateDelta"] else "FAILURE"
        event = self.ledger.append(
            "omega-scientist-cycle-review",
            outcome,
            elapsed_seconds * 1000,
            semantic_fingerprint(review),
            semantic_fruit=review["completionState"] == "COMPLETE_VERIFIED",
        )
        review["learningHash"] = event["hash"]
        review["learningPromotion"] = "NOT_PROMOTED"
        return review

    def chat(self, message: str) -> dict[str, Any]:
        started = time.perf_counter()
        internal_math_request = message.strip().lower().startswith("/math ")
        route = "deterministic-math" if internal_math_request else self.reasoner.name
        if not self.ledger.verify():
            return {
                "answer": "State integrity failed; reasoning and learning writes are blocked.",
                "route": route,
                "elapsedMs": 0,
                "semanticFruit": False,
                "advisoryFruit": False,
                "effectFruit": False,
                "error": "LEDGER_INTEGRITY_FAILED",
                "learningHash": None,
                "learningPromotion": "NOT_PROMOTED",
                "quarantined": False,
                "workflowEvents": [],
            }
        if not self.breaker.allows(route):
            elapsed = int((time.perf_counter() - started) * 1000)
            evidence_hash = semantic_fingerprint({"route": route, "state": "QUARANTINED"})
            event = self.ledger.append(route, "QUARANTINED", elapsed, evidence_hash, semantic_fruit=False)
            return {
                "answer": "Provider route is quarantined pending two authenticated bounded recovery receipts from distinct registered verifiers.",
                "route": route,
                "elapsedMs": elapsed,
                "learningHash": event["hash"],
                "learningPromotion": "NOT_PROMOTED",
                "quarantined": True,
                "semanticFruit": False,
                "advisoryFruit": False,
                "effectFruit": False,
                "workflowEvents": [],
            }

        context = {
            "capabilities": self.fabric.inventory(),
            "principles": catalogue(),
            "doctrine": doctrine_summary(),
            "executionPolicy": self.execution.describe(),
        }
        try:
            graph_result = self.graph.run(message, context, self.reasoner)
            answer = graph_result.reasoning.text
            evidence_hash = graph_result.evidence_hash
            workflow_events = [event.public() for event in graph_result.events]
            success = True
            semantic_fruit = (
                internal_math_request
                and graph_result.reasoning.provider == "deterministic-math"
            ) or (
                type(self.reasoner) is OfflineReasoner
                and graph_result.reasoning.provider == "offline-deterministic"
            )
            advisory_fruit = True
            if not semantic_fruit:
                answer = (
                    "Untrusted external advisory; no effects were executed and no semantic or provider fruit is established. "
                    f"Proposal: {answer}"
                )
            error_code = None
            breaker_relevant = True
            outcome = "SUCCESS"
        except (GraphInputError, MathExpressionError) as exc:
            answer = f"Route failed closed: {str(exc)}"
            route = "input-validation"
            evidence_hash = semantic_fingerprint({"route": route, "error": str(exc)})
            workflow_events = []
            success = False
            semantic_fruit = False
            advisory_fruit = False
            error_code = str(exc)
            breaker_relevant = False
            outcome = "INPUT_REJECTED"
        except (ProviderError, SemanticVerificationError) as exc:
            answer = f"Route failed closed: {str(exc)}"
            evidence_hash = semantic_fingerprint({"route": route, "error": str(exc)})
            workflow_events = []
            success = False
            semantic_fruit = False
            advisory_fruit = False
            error_code = str(exc)
            breaker_relevant = True
            outcome = "FAILURE"

        elapsed = int((time.perf_counter() - started) * 1000)
        if breaker_relevant:
            self.breaker.record(route, success)
        event = self.ledger.append(
            route,
            outcome,
            elapsed,
            evidence_hash,
            semantic_fruit=semantic_fruit,
        )
        if success and self.reasoner.provider_mode != "offline" and route != "deterministic-math":
            self.session_provider_receipt = f"session-advisory-contract:{evidence_hash}"
        return {
            "answer": answer,
            "route": route,
            "providerMode": self.reasoner.provider_mode,
            "elapsedMs": elapsed,
            "semanticFruit": semantic_fruit,
            "advisoryFruit": advisory_fruit,
            "effectFruit": False,
            "error": error_code,
            "learningHash": event["hash"],
            "learningPromotion": "NOT_PROMOTED",
            "quarantined": route in self.breaker.quarantined,
            "workflowEvents": workflow_events,
        }

    def authorize(
        self,
        mission_id: str,
        mission_version: int,
        action_id: str,
        capability_id: str,
        resource: str | None = None,
        arguments: dict[str, Any] | None = None,
        permit: str | None = None,
    ) -> dict[str, Any]:
        decision = self.formation.decide(
            mission_id,
            mission_version,
            action_id,
            self.fabric.get(capability_id),
            resource=resource,
            arguments=arguments,
            authority_envelope=None,
            permit=permit,
            consume_permit=False,
        )
        return asdict(decision)

    def authorize_for_execution(
        self,
        mission_id: str,
        mission_version: int,
        action_id: str,
        capability_id: str,
        resource: str,
        arguments: dict[str, Any],
        authority_envelope: AuthorityEnvelope,
        permit: str | None,
    ) -> dict[str, Any]:
        """Executor-only transaction boundary; not exposed by the HTTP service."""
        decision = self.formation.decide(
            mission_id,
            mission_version,
            action_id,
            self.fabric.get(capability_id),
            resource=resource,
            arguments=arguments,
            authority_envelope=authority_envelope,
            permit=permit,
            consume_permit=True,
        )
        return asdict(decision)

    def math(self, expression: str) -> dict[str, Any]:
        result = calculate(expression)
        return {
            **asdict(result),
            "epistemicBoundary": "deterministic calculation; interpretation and model assumptions remain separate",
        }
