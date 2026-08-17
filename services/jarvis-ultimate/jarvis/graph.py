from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .core import semantic_fingerprint
from .math_engine import calculate
from .providers import ProviderError, ProviderInvocationError, Reasoner, ReasoningResult


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
    if any(marker in lowered for marker in rejected):
        return False
    # This graph has no effectful executor or trusted provider receipt. Therefore
    # any positive effect-completion assertion must fail closed. A future action
    # lane must validate an action-specific structured readback outside this chat
    # graph instead of allowing prose to stand in for fruit.
    effect_past = re.compile(
        r"\b(?:deployed|sent|deleted|granted|promoted|created|updated|shared|archived|moved|scheduled|forwarded|released|published|uploaded|written|executed|invoked|restored|rolled\s+back)\b"
    )
    effect_noun = r"deployment|rollout|release|promotion|operation|action|task|request|work|email|message|file|resource|permission|access|service"
    completion = r"success|successful|successfully|complete|completed|done|live|ready|finished|passed"
    for match in effect_past.finditer(lowered):
        prefix = lowered[max(0, match.start() - 32):match.start()]
        if not re.search(r"\b(?:not|never|no|cannot|can't|without)\b[^.!?]{0,24}$", prefix):
            return False
    if re.search(rf"\b(?:{effect_noun})\b[^.!?]{{0,48}}\b(?:{completion})\b", lowered):
        return False
    if re.search(rf"\b(?:{completion})\b[^.!?]{{0,48}}\b(?:{effect_noun})\b", lowered):
        return False
    if re.search(r"\b(?:all|every)\s+(?:requested\s+)?(?:task|request|action|work)\s+(?:is|was|has been)\s+(?:done|complete|completed|finished)\b", lowered):
        return False
    return True


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
        if objective.lower().startswith("/math "):
            calculation = calculate(objective[6:])
            result = ReasoningResult(
                text=f"Deterministic result: {calculation.expression} = {calculation.value}",
                provider="deterministic-math",
                model=calculation.engine,
                api_version="local-v1",
            )
        else:
            try:
                result = reasoner.respond(objective, context)
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderInvocationError("REASONER_UNEXPECTED_EXCEPTION") from exc
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
