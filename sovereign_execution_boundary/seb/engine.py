from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from .ledger import JsonlLedger
from .models import (ExecutionResult, FailureClass, MissionIR, MissionState,
                     ProviderRequest)
from .completion import CompletionTheorem
from .models import CompletionEvidence
from .objective import ObjectiveContract
from .policy import PolicyEngine
from .router import ProviderRouter


class SovereignEngine:
    def __init__(self, ledger: JsonlLedger, policy: PolicyEngine, router: ProviderRouter):
        self.ledger = ledger
        self.policy = policy
        self.router = router
        self.cancelled: set[str] = set()

    def cancel(self, mission_id: str) -> None:
        self.cancelled.add(mission_id)
        self.ledger.append(mission_id, "MISSION_CANCELLED", {})

    def execute(self, mission: MissionIR, prompt: str, schema: dict,
                verifier: Callable[[dict], bool], *, contract: ObjectiveContract | None = None,
                evidence_builder: Callable[[dict], CompletionEvidence] | None = None) -> ExecutionResult:
        try:
            mission.validate()
        except ValueError as exc:
            return ExecutionResult(mission.mission_id, MissionState.FAILED, None, None, 0, (),
                                   FailureClass.SEMANTIC_FAILURE, str(exc))
        if mission.mission_id in self.cancelled:
            return ExecutionResult(mission.mission_id, MissionState.CANCELLED, None, None, 0, (),
                                   message="mission cancelled")
        decision = self.policy.evaluate(mission)
        self.ledger.append(mission.mission_id, "POLICY_DECISION",
                           {"allowed": decision.allowed, "reason": decision.reason,
                            "decision_id": decision.decision_id})
        if not decision.allowed:
            return ExecutionResult(mission.mission_id, MissionState.FAILED, None, None, 0,
                                   (decision.decision_id,), FailureClass.MISSING_AUTHORITY,
                                   decision.reason)
        self.ledger.append(mission.mission_id, "MISSION_PROCESSING",
                           {"fingerprint": mission.fingerprint})
        req = ProviderRequest(mission.mission_id, str(uuid4()), prompt, schema, "mock-model",
                              mission.budget.max_tokens, mission.data_class)
        routed = self.router.route(req)
        for provider, kind, message in routed.failures:
            self.ledger.append(mission.mission_id, "ROUTE_FAILURE",
                               {"provider": provider, "class": kind.value, "message": message})
        if not routed.response:
            failure = routed.failures[-1][1] if routed.failures else FailureClass.PROVIDER_OUTAGE
            self.ledger.append(mission.mission_id, "MISSION_FAILED", {"class": failure.value})
            return ExecutionResult(mission.mission_id, MissionState.FAILED, None, None,
                                   routed.attempts, (), failure, "all eligible routes failed")
        response = routed.response
        if response.tokens > mission.budget.max_tokens:
            self.ledger.append(mission.mission_id, "MISSION_FAILED",
                               {"class": FailureClass.BUDGET_EXCEEDED.value})
            return ExecutionResult(mission.mission_id, MissionState.FAILED, None, response.provider,
                                   routed.attempts, (), FailureClass.BUDGET_EXCEEDED)
        if not verifier(response.content):
            self.router.quarantined.add(response.provider)
            self.ledger.append(mission.mission_id, "MISSION_QUARANTINED",
                               {"provider": response.provider, "class": FailureClass.SEMANTIC_FAILURE.value})
            return ExecutionResult(mission.mission_id, MissionState.QUARANTINED, response.content,
                                   response.provider, routed.attempts, (), FailureClass.SEMANTIC_FAILURE)
        if contract is not None:
            if evidence_builder is None:
                return ExecutionResult(mission.mission_id, MissionState.BLOCKED_INCOMPLETE,
                                       response.content, response.provider, routed.attempts, (),
                                       FailureClass.SEMANTIC_FAILURE,
                                       "completion evidence required for objective-bound mission")
            completion = CompletionTheorem().evaluate(contract, evidence_builder(response.content))
            self.ledger.append(mission.mission_id, "COMPLETION_DECISION",
                               {"complete": completion.complete, "defects": completion.defects,
                                "proof_hash": completion.proof_hash})
            if not completion.complete:
                return ExecutionResult(mission.mission_id, MissionState.BLOCKED_INCOMPLETE,
                                       response.content, response.provider, routed.attempts,
                                       (completion.proof_hash,), FailureClass.SEMANTIC_FAILURE,
                                       ";".join(completion.defects))
        proof_event = self.ledger.append(mission.mission_id, "MISSION_COMPLETED",
                                         {"provider": response.provider, "output": response.content})
        self.ledger.verify()
        return ExecutionResult(mission.mission_id, MissionState.COMPLETED, response.content,
                               response.provider, routed.attempts,
                               (decision.decision_id, proof_event.event_hash))
