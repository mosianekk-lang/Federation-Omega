from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from time import perf_counter_ns
from typing import Any

from federation.bubbles_tool_payload_firewall import (
    DiagnosticExtractor,
    ToolPayloadBudget,
    ToolPayloadFirewall,
    ToolPayloadObservation,
)


@dataclass(frozen=True, slots=True)
class ChatBridgeIngressReceipt:
    schema: str
    state: str
    tool_name: str
    content_kind: str
    action: str
    reasons: tuple[str, ...]
    raw_admitted: bool
    diagnostic_required: bool
    raw_sha256: str
    raw_chars: int
    raw_lines: int
    bounded_sha256: str
    bounded_chars: int
    bounded_lines: int
    reduction_percent: float
    redaction_applied: bool
    processing_ms: float
    external_effects: int
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ChatBridgeIngressResult:
    receipt: ChatBridgeIngressReceipt
    bounded_payload: str


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class ChatBridgeToolPayloadIngress:
    """Runtime adapter that applies Bubbles payload policy before diagnostic hydration.

    The adapter is provider-neutral and effect-free. It does not grant connector,
    provider, deployment or ChatGPT interception authority. A serving host must call
    this adapter before placing raw tool diagnostics into its active reasoning state.
    """

    def __init__(self, budget: ToolPayloadBudget | None = None) -> None:
        self.budget = budget or ToolPayloadBudget(
            max_raw_chars=24_000,
            max_raw_lines=300,
            max_diagnostic_chars=6_000,
            max_diagnostic_lines=80,
            tail_lines=10,
        )
        self.firewall = ToolPayloadFirewall(self.budget)
        self.extractor = DiagnosticExtractor(self.budget)

    def ingest(
        self,
        *,
        tool_name: str,
        payload: str,
        content_kind: str = "provider_log",
        contains_sensitive_hint: bool = False,
    ) -> ChatBridgeIngressResult:
        started = perf_counter_ns()
        text = str(payload)
        lines = text.splitlines()
        decision = self.firewall.evaluate(
            ToolPayloadObservation(
                tool_name=tool_name,
                payload_chars=len(text),
                line_count=len(lines),
                content_kind=content_kind,
                contains_sensitive_hint=contains_sensitive_hint,
            )
        )

        if decision.admit_raw:
            bounded = text
            raw_sha = _sha(text)
            redaction_applied = False
        else:
            capsule = self.extractor.extract(text)
            bounded = capsule.excerpt
            raw_sha = capsule.raw_sha256
            redaction_applied = capsule.redaction_applied

        bounded_lines = len(bounded.splitlines()) if bounded else 0
        if len(bounded) > self.budget.max_raw_chars:
            raise RuntimeError("CHATBRIDGE_INGRESS_BOUNDED_PAYLOAD_EXCEEDS_RAW_BUDGET")
        if decision.diagnostic_required and len(bounded) > self.budget.max_diagnostic_chars:
            raise RuntimeError("CHATBRIDGE_INGRESS_DIAGNOSTIC_EXCEEDS_BUDGET")
        if decision.diagnostic_required and bounded_lines > self.budget.max_diagnostic_lines:
            raise RuntimeError("CHATBRIDGE_INGRESS_DIAGNOSTIC_LINE_BUDGET_EXCEEDED")

        reduction = 0.0 if not text else max(0.0, 1.0 - (len(bounded) / len(text))) * 100.0
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0
        unsigned = {
            "schema": "CHATBRIDGE-TOOL-PAYLOAD-INGRESS-1",
            "state": "RAW_ADMITTED" if decision.admit_raw else "BOUNDED_DIAGNOSTIC",
            "tool_name": tool_name,
            "content_kind": content_kind,
            "action": decision.action,
            "reasons": list(decision.reasons),
            "raw_admitted": decision.admit_raw,
            "diagnostic_required": decision.diagnostic_required,
            "raw_sha256": raw_sha,
            "raw_chars": len(text),
            "raw_lines": len(lines),
            "bounded_sha256": _sha(bounded),
            "bounded_chars": len(bounded),
            "bounded_lines": bounded_lines,
            "reduction_percent": round(reduction, 6),
            "redaction_applied": redaction_applied,
            "processing_ms": round(elapsed_ms, 6),
            "external_effects": 0,
        }
        receipt_sha = sha256(_stable_json(unsigned).encode("utf-8")).hexdigest()
        receipt = ChatBridgeIngressReceipt(
            **{**unsigned, "reasons": tuple(unsigned["reasons"]), "receipt_sha256": receipt_sha}
        )
        return ChatBridgeIngressResult(receipt=receipt, bounded_payload=bounded)
