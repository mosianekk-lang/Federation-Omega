from __future__ import annotations

"""Bounded CFBE context-efficiency courts.

These helpers measure retrieval/context efficiency and a deterministic Bubbles
payload-governor shadow. They never authorize provider effects, deploy anything,
or claim native ChatGPT interception.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from federation.bubbles_hyperperformance import (
    ContextPressureGovernor,
    ContextPressureObservation,
)
from federation.bubbles_tool_payload_firewall import (
    DiagnosticExtractor,
    ToolPayloadFirewall,
    ToolPayloadObservation,
)

SCHEMA = "CFBE_FITNESS_CONTEXT_EFFICIENCY_V1"


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RetrievalEfficiencyReceipt:
    broad_context_units: int
    canonical_context_units: int
    broad_calls: int
    canonical_calls: int
    source_accuracy_equal: bool
    privacy_expansion: bool
    context_reduction_ratio: float
    call_delta: int
    state: str
    receipt_sha256: str


def evaluate_retrieval_efficiency(
    *,
    broad_context_units: int,
    canonical_context_units: int,
    broad_calls: int,
    canonical_calls: int,
    source_accuracy_equal: bool,
    privacy_expansion: bool = False,
) -> RetrievalEfficiencyReceipt:
    if broad_context_units <= 0 or canonical_context_units < 0:
        raise ValueError("RETRIEVAL_CONTEXT_UNITS_INVALID")
    if broad_calls <= 0 or canonical_calls <= 0:
        raise ValueError("RETRIEVAL_CALL_COUNTS_INVALID")
    reduction = max(0.0, 1.0 - (canonical_context_units / broad_context_units))
    state = (
        "POSITIVE_CONTEXT_SIGNAL"
        if source_accuracy_equal and not privacy_expansion and canonical_context_units < broad_context_units
        else "NO_POSITIVE_SIGNAL"
    )
    payload = {
        "schema": SCHEMA,
        "broad_context_units": broad_context_units,
        "canonical_context_units": canonical_context_units,
        "broad_calls": broad_calls,
        "canonical_calls": canonical_calls,
        "source_accuracy_equal": source_accuracy_equal,
        "privacy_expansion": privacy_expansion,
        "context_reduction_ratio": round(reduction, 6),
        "call_delta": canonical_calls - broad_calls,
        "state": state,
    }
    return RetrievalEfficiencyReceipt(
        broad_context_units=broad_context_units,
        canonical_context_units=canonical_context_units,
        broad_calls=broad_calls,
        canonical_calls=canonical_calls,
        source_accuracy_equal=source_accuracy_equal,
        privacy_expansion=privacy_expansion,
        context_reduction_ratio=round(reduction, 6),
        call_delta=canonical_calls - broad_calls,
        state=state,
        receipt_sha256=_hash(payload),
    )


@dataclass(frozen=True, slots=True)
class BubblesContextShadowReceipt:
    raw_chars: int
    raw_lines: int
    diagnostic_chars: int
    diagnostic_lines: int
    evidence_count: int
    evidence_recalled: int
    evidence_recall_ratio: float
    context_reduction_ratio: float
    redaction_applied: bool
    raw_context_action: str
    bounded_context_action: str
    provider_effect_authorized: bool
    native_chat_interception_proven: bool
    state: str
    receipt_sha256: str


def _fixed_payload() -> tuple[str, tuple[str, ...]]:
    lines = [
        f"telemetry-{index:04d} ordinary bounded observation " + ("x" * 70)
        for index in range(1600)
    ]
    lines[99] = "EVIDENCE_ALPHA error provider denied at authority gate token=abc123"
    lines[799] = "EVIDENCE_BETA conclusion semantic readback mismatch"
    lines[1499] = "EVIDENCE_GAMMA timeout recovery route selected"
    return "\n".join(lines), ("EVIDENCE_ALPHA", "EVIDENCE_BETA", "EVIDENCE_GAMMA")


def run_bubbles_context_shadow() -> BubblesContextShadowReceipt:
    payload, evidence_ids = _fixed_payload()
    firewall = ToolPayloadFirewall()
    observation = ToolPayloadObservation(
        tool_name="fixed_shadow_tool",
        payload_chars=len(payload),
        line_count=len(payload.splitlines()),
        content_kind="provider_log",
        contains_sensitive_hint=True,
    )
    decision = firewall.evaluate(observation)
    if decision.admit_raw or not decision.diagnostic_required:
        raise AssertionError("BUBBLES_SHADOW_EXPECTED_BOUNDED_DIAGNOSTIC")
    capsule = DiagnosticExtractor().extract(payload)
    recalled = sum(1 for item in evidence_ids if item in capsule.excerpt)
    raw_pressure = ContextPressureGovernor().evaluate(
        ContextPressureObservation(
            active_sources=6,
            heavy_sources=2,
            tool_results=8,
            tool_payload_chars=len(payload),
            estimated_capsule_chars=20_000,
        )
    )
    bounded_pressure = ContextPressureGovernor().evaluate(
        ContextPressureObservation(
            active_sources=6,
            heavy_sources=2,
            tool_results=8,
            tool_payload_chars=len(capsule.excerpt),
            estimated_capsule_chars=20_000,
        )
    )
    recall_ratio = recalled / len(evidence_ids)
    reduction = 1.0 - (len(capsule.excerpt) / len(payload))
    state = (
        "POSITIVE_BOUNDED_SHADOW"
        if recall_ratio == 1.0
        and capsule.redaction_applied
        and "abc123" not in capsule.excerpt
        and raw_pressure.admitted is False
        and bounded_pressure.admitted is True
        else "SHADOW_GUARDRAIL_NOT_MET"
    )
    payload_for_hash = {
        "schema": SCHEMA,
        "raw_chars": len(payload),
        "raw_lines": len(payload.splitlines()),
        "diagnostic_chars": len(capsule.excerpt),
        "diagnostic_lines": capsule.selected_lines,
        "evidence_count": len(evidence_ids),
        "evidence_recalled": recalled,
        "evidence_recall_ratio": round(recall_ratio, 6),
        "context_reduction_ratio": round(reduction, 6),
        "redaction_applied": capsule.redaction_applied,
        "raw_context_action": raw_pressure.action,
        "bounded_context_action": bounded_pressure.action,
        "provider_effect_authorized": False,
        "native_chat_interception_proven": False,
        "state": state,
    }
    return BubblesContextShadowReceipt(
        raw_chars=len(payload),
        raw_lines=len(payload.splitlines()),
        diagnostic_chars=len(capsule.excerpt),
        diagnostic_lines=capsule.selected_lines,
        evidence_count=len(evidence_ids),
        evidence_recalled=recalled,
        evidence_recall_ratio=round(recall_ratio, 6),
        context_reduction_ratio=round(reduction, 6),
        redaction_applied=capsule.redaction_applied,
        raw_context_action=raw_pressure.action,
        bounded_context_action=bounded_pressure.action,
        provider_effect_authorized=False,
        native_chat_interception_proven=False,
        state=state,
        receipt_sha256=_hash(payload_for_hash),
    )


def benchmark_summary() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "bubbles_context_shadow": asdict(run_bubbles_context_shadow()),
        "truth_boundary": {
            "provider_effect_authorized": False,
            "native_chat_interception_proven": False,
            "owner_value_proven": False,
            "stable_promotion_authorized": False,
        },
    }
