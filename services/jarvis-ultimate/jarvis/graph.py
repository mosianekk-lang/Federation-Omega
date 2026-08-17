from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .core import semantic_fingerprint
from .providers import Reasoner, ReasoningResult


class GraphInputError(ValueError):
    pass


class SemanticVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class NodeInfo:
    node_id: str
    sequence: int


@dataclass(frozen=True)
class WorkflowEvent:
    node_info: NodeInfo
    output: dict[str, Any]

    def public(self) -> dict[str, Any]:
        return {"nodeInfo": asdict(self.node_info), "output": self.output}


@dataclass(frozen=True)
class GraphResult:
    reasoning: ReasoningResult
    evidence_hash: str
    events: tuple[WorkflowEvent, ...]


def semantic_response_valid(result: ReasoningResult) -> bool:
    text = result.text.strip()
    if len(text) < 12:
        return False
    lowered = text.lower()
    rejected = ("provider route failed", "generic health", "undefined", "null")
    return not any(marker in lowered for marker in rejected)


class GovernedReasoningGraph:
    """Single canonical deterministic request graph; no node has effectful tools."""

    nodes = ("intake", "evidence_context", "advisory_twin", "reason", "semantic_verify")

    def run(self, message: str, context: dict[str, Any], reasoner: Reasoner) -> GraphResult:
        objective = message.strip()
        if not objective:
            raise GraphInputError("MESSAGE_REQUIRED")
        if len(objective) > 20_000:
            raise GraphInputError("MESSAGE_TOO_LARGE")

        events: list[WorkflowEvent] = []
        events.append(
            WorkflowEvent(
                NodeInfo("intake", 1),
                {"accepted": True, "contentHash": semantic_fingerprint({"message": objective})},
            )
        )
        events.append(
            WorkflowEvent(
                NodeInfo("evidence_context", 2),
                {
                    "capabilityCount": len(context.get("capabilities", [])),
                    "doctrineCount": len(context.get("principles", [])),
                    "externalContentTrustedAsAuthority": False,
                },
            )
        )
        events.append(
            WorkflowEvent(
                NodeInfo("advisory_twin", 3),
                {
                    "credentialAccess": False,
                    "permitAuthority": False,
                    "effectfulPathsAllowed": 0,
                    "challenge": "separate observation, inference and unknown",
                },
            )
        )
        result = reasoner.respond(objective, context)
        events.append(
            WorkflowEvent(
                NodeInfo("reason", 4),
                {
                    "provider": result.provider,
                    "model": result.model,
                    "apiVersion": result.api_version,
                    "responseHash": semantic_fingerprint({"text": result.text}),
                },
            )
        )
        if not semantic_response_valid(result):
            raise SemanticVerificationError("SEMANTIC_FRUIT_INVALID")
        evidence_hash = semantic_fingerprint(
            {
                "objective": objective,
                "provider": result.provider,
                "model": result.model,
                "apiVersion": result.api_version,
                "response": result.text,
            }
        )
        events.append(
            WorkflowEvent(
                NodeInfo("semantic_verify", 5),
                {"passed": True, "evidenceHash": evidence_hash},
            )
        )
        return GraphResult(result, evidence_hash, tuple(events))
