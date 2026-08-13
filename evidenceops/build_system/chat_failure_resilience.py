#!/usr/bin/env python3
"""EvidenceOps Chat Failure Resilience Engine (CFRE Ω).

Diagnoses chat/runtime failures, preserves mission state, and emits a bounded,
idempotent recovery route. The engine does not claim control of the ChatGPT UI,
OpenAI service, browser, network, or third-party providers. It makes workflows
resume-safe when those layers fail.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable

from .objective_completion_guard import evaluate as evaluate_completion

SCHEMA = "EVIDENCEOPS-CHAT-FAILURE-RESILIENCE-1"
LEDGER_SCHEMA = "EVIDENCEOPS-CHAT-FAILURE-LEDGER-1"

FAILURE_CLASSES = (
    "TRANSPORT_INTERRUPTION",
    "SERVER_GENERATION_FAILURE",
    "STALL_TIMEOUT",
    "CONTEXT_PRESSURE",
    "TOOL_OR_CONNECTOR_FAILURE",
    "FILE_OR_ATTACHMENT_FAILURE",
    "AUTH_OR_SESSION_FAILURE",
    "RATE_OR_CAPACITY_LIMIT",
    "CLIENT_RESOURCE_FAILURE",
    "USER_INTERRUPTION",
    "UNKNOWN_CHAT_FAILURE",
)

# Patterns are deliberately transparent and conservative. A match is a signal,
# not proof of the underlying provider root cause.
PATTERNS: dict[str, tuple[str, ...]] = {
    "TRANSPORT_INTERRUPTION": (
        r"connection interrupted",
        r"network error",
        r"websocket",
        r"disconnected",
        r"connection (?:lost|closed|reset)",
    ),
    "SERVER_GENERATION_FAILURE": (
        r"error generating (?:a )?response",
        r"something went wrong",
        r"internal server",
        r"failed to (?:generate|produce) (?:an )?answer",
    ),
    "STALL_TIMEOUT": (
        r"waiting for (?:the )?complete answer",
        r"stuck (?:on|at)",
        r"thinking\.{0,3}",
        r"generating\.{0,3}",
        r"timed? ?out",
        r"no progress",
    ),
    "CONTEXT_PRESSURE": (
        r"context (?:window|length|limit)",
        r"maximum context",
        r"conversation (?:is )?too long",
        r"message (?:is )?too long",
        r"token limit",
    ),
    "TOOL_OR_CONNECTOR_FAILURE": (
        r"tool (?:call )?(?:failed|error|timeout|unavailable)",
        r"connector (?:failed|error|timeout|unavailable)",
        r"plugin (?:failed|error|timeout|unavailable)",
        r"provider (?:read|write|call) (?:failed|timeout)",
    ),
    "FILE_OR_ATTACHMENT_FAILURE": (
        r"file not found",
        r"download failed",
        r"upload failed",
        r"attachment (?:failed|missing|unavailable)",
    ),
    "AUTH_OR_SESSION_FAILURE": (
        r"session expired",
        r"authentication (?:failed|required)",
        r"unauthori[sz]ed",
        r"forbidden",
        r"\b401\b",
        r"\b403\b",
        r"sign in again",
    ),
    "RATE_OR_CAPACITY_LIMIT": (
        r"rate limit",
        r"too many requests",
        r"\b429\b",
        r"capacity",
        r"overloaded",
    ),
    "CLIENT_RESOURCE_FAILURE": (
        r"out of memory",
        r"tab (?:crashed|discarded|suspended)",
        r"browser (?:crashed|unresponsive)",
        r"extension conflict",
    ),
    "USER_INTERRUPTION": (
        r"user cancelled",
        r"user canceled",
        r"stop generating",
        r"navigation interrupted",
    ),
}

DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "TRANSPORT_INTERRUPTION": (
        "client network path",
        "long-lived response transport/WebSocket",
        "browser/app connection state",
        "ChatGPT service availability",
    ),
    "SERVER_GENERATION_FAILURE": (
        "model serving path",
        "ChatGPT orchestration service",
        "tool-result integration path when tools are active",
    ),
    "STALL_TIMEOUT": (
        "stream progress/heartbeat",
        "model or tool completion",
        "client render loop",
        "timeout policy",
    ),
    "CONTEXT_PRESSURE": (
        "conversation/context budget",
        "continuity checkpoint quality",
        "prompt/task decomposition",
    ),
    "TOOL_OR_CONNECTOR_FAILURE": (
        "tool availability",
        "connector/provider availability",
        "connector authorization",
        "idempotent replay safety",
    ),
    "FILE_OR_ATTACHMENT_FAILURE": (
        "file persistence",
        "attachment reference validity",
        "file size/format support",
        "artifact regeneration path",
    ),
    "AUTH_OR_SESSION_FAILURE": (
        "session validity",
        "connector/provider credentials",
        "authorization scope",
    ),
    "RATE_OR_CAPACITY_LIMIT": (
        "provider capacity",
        "rate quota",
        "retry/backoff policy",
    ),
    "CLIENT_RESOURCE_FAILURE": (
        "browser/app memory",
        "extension/VPN/proxy interaction",
        "local device health",
    ),
    "USER_INTERRUPTION": (
        "durable checkpoint before interruption",
        "resume token/idempotency key",
    ),
    "UNKNOWN_CHAT_FAILURE": (
        "failure telemetry",
        "durable mission checkpoint",
        "route discovery",
    ),
}


@dataclass(frozen=True)
class FailureCandidate:
    failure_class: str
    score: float
    signals: tuple[str, ...]
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryStep:
    order: int
    action: str
    mode: str
    automated: bool
    retry_safe: bool
    requires_external_executor: bool = False
    stop_on_success: bool = False
    rationale: str = ""


@dataclass(frozen=True)
class RecoveryReceipt:
    schema: str
    event_id: str
    failure_class: str
    confidence: float
    candidates: tuple[FailureCandidate, ...]
    dependencies: tuple[str, ...]
    mission_complete: bool
    completion_claim_permitted: bool
    must_continue: bool
    recovery_mode: str
    recovery_steps: tuple[RecoveryStep, ...]
    checkpoint: dict[str, Any]
    next_automated_action: str
    route_exhausted: bool
    provider_effects_claimed: bool
    generated_at: str
    receipt_sha256: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _text(event: dict[str, Any]) -> str:
    fields = (
        event.get("message"),
        event.get("error"),
        event.get("status"),
        event.get("stage"),
        event.get("last_visible_text"),
    )
    return "\n".join(str(value) for value in fields if value is not None).lower()


def classify_failure(event: dict[str, Any]) -> tuple[FailureCandidate, ...]:
    text = _text(event)
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}

    for failure_class, patterns in PATTERNS.items():
        hits = [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]
        if hits:
            # First transparent signature is strong; additional independent signatures add support.
            scores[failure_class] = min(0.98, 0.70 + 0.08 * (len(hits) - 1))
            evidence[failure_class] = [f"regex:{pattern}" for pattern in hits]

    no_progress = event.get("no_progress_seconds")
    if isinstance(no_progress, (int, float)) and not isinstance(no_progress, bool):
        if no_progress >= 60:
            scores["STALL_TIMEOUT"] = max(scores.get("STALL_TIMEOUT", 0.0), min(0.95, 0.70 + no_progress / 1200))
            evidence.setdefault("STALL_TIMEOUT", []).append(f"no_progress_seconds:{no_progress}")

    turns = event.get("conversation_turns")
    if isinstance(turns, int) and not isinstance(turns, bool) and turns >= 100:
        scores["CONTEXT_PRESSURE"] = max(scores.get("CONTEXT_PRESSURE", 0.0), 0.62)
        evidence.setdefault("CONTEXT_PRESSURE", []).append(f"conversation_turns:{turns}")

    if event.get("tool_inflight") is True:
        scores["TOOL_OR_CONNECTOR_FAILURE"] = max(scores.get("TOOL_OR_CONNECTOR_FAILURE", 0.0), 0.55)
        evidence.setdefault("TOOL_OR_CONNECTOR_FAILURE", []).append("tool_inflight:true")

    if event.get("network_online") is False:
        scores["TRANSPORT_INTERRUPTION"] = max(scores.get("TRANSPORT_INTERRUPTION", 0.0), 0.92)
        evidence.setdefault("TRANSPORT_INTERRUPTION", []).append("network_online:false")

    if event.get("http_status") in {401, 403}:
        scores["AUTH_OR_SESSION_FAILURE"] = max(scores.get("AUTH_OR_SESSION_FAILURE", 0.0), 0.96)
        evidence.setdefault("AUTH_OR_SESSION_FAILURE", []).append(f"http_status:{event['http_status']}")
    if event.get("http_status") == 429:
        scores["RATE_OR_CAPACITY_LIMIT"] = max(scores.get("RATE_OR_CAPACITY_LIMIT", 0.0), 0.97)
        evidence.setdefault("RATE_OR_CAPACITY_LIMIT", []).append("http_status:429")

    if not scores:
        scores["UNKNOWN_CHAT_FAILURE"] = 0.35
        evidence["UNKNOWN_CHAT_FAILURE"] = ["no_known_signature"]

    candidates = [
        FailureCandidate(
            failure_class=name,
            score=round(score, 4),
            signals=tuple(evidence.get(name, ())),
            dependencies=DEPENDENCIES[name],
        )
        for name, score in scores.items()
    ]
    candidates.sort(key=lambda item: (-item.score, item.failure_class))
    return tuple(candidates)


def build_checkpoint(event: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    previous = previous or {}
    checkpoint = {
        "directive": event.get("active_directive") or previous.get("directive"),
        "objective": event.get("objective") or previous.get("objective"),
        "last_proven_state": event.get("last_proven_state") or previous.get("last_proven_state"),
        "last_completed_action": event.get("last_completed_action") or previous.get("last_completed_action"),
        "next_pending_action": event.get("next_pending_action") or previous.get("next_pending_action"),
        "active_artifacts": event.get("active_artifacts") or previous.get("active_artifacts") or [],
        "active_dependencies": event.get("active_dependencies") or previous.get("active_dependencies") or [],
        "tool_inflight": bool(event.get("tool_inflight")),
        "tool_call_id": event.get("tool_call_id") or previous.get("tool_call_id"),
        "conversation_id": event.get("conversation_id") or previous.get("conversation_id"),
        "source_turn_id": event.get("source_turn_id") or previous.get("source_turn_id"),
        "captured_at": _now(),
    }
    identity_material = {
        key: checkpoint.get(key)
        for key in ("directive", "objective", "last_completed_action", "next_pending_action", "tool_call_id", "conversation_id")
    }
    checkpoint["resume_token"] = _stable_sha256(identity_material)
    checkpoint["idempotency_key"] = _stable_sha256({"resume": checkpoint["resume_token"], "pending": checkpoint["next_pending_action"]})
    return checkpoint


def _steps_for(failure_class: str, event: dict[str, Any], checkpoint: dict[str, Any]) -> tuple[RecoveryStep, ...]:
    steps: list[RecoveryStep] = [
        RecoveryStep(1, "PERSIST_MISSION_CHECKPOINT", "LOCAL_DURABLE_STATE", True, True, rationale="Never let transport failure erase directive, proof state, or next action."),
        RecoveryStep(2, "VERIFY_MISSION_NOT_COMPLETE", "OBJECTIVE_COMPLETION_GUARD", True, True, rationale="A failed/stalled response is not a completion receipt."),
    ]

    if failure_class in {"TRANSPORT_INTERRUPTION", "SERVER_GENERATION_FAILURE", "STALL_TIMEOUT", "RATE_OR_CAPACITY_LIMIT"}:
        steps.extend([
            RecoveryStep(3, "RETRY_SAME_ATOMIC_ACTION", "BOUNDED_EXPONENTIAL_BACKOFF", True, True, rationale="Replay only the unfinished atomic action using its idempotency key."),
            RecoveryStep(4, "RESUME_FROM_LAST_PROVEN_CHECKPOINT", "STATEFUL_REPLAY", True, True, stop_on_success=True, rationale="Do not regenerate already-proven work."),
        ])
    elif failure_class == "CONTEXT_PRESSURE":
        steps.extend([
            RecoveryStep(3, "COMPACT_CONTINUITY_STATE", "LOSSLESS_CONTROL_SUMMARY", True, True, rationale="Preserve directives, decisions, proof pointers, blockers, and next action while shedding conversational bulk."),
            RecoveryStep(4, "START_FRESH_EXECUTION_CONTEXT", "CHATBRIDGE_HANDOFF", True, True, True, True, "Resume from the compact checkpoint rather than reconstructing the mission from memory."),
        ])
    elif failure_class == "TOOL_OR_CONNECTOR_FAILURE":
        steps.extend([
            RecoveryStep(3, "READBACK_TOOL_OUTCOME_BEFORE_RETRY", "IDEMPOTENCY_GUARD", True, True, rationale="A timed-out write may have succeeded; verify before replay."),
            RecoveryStep(4, "ISOLATE_FAILED_TOOL_LANE", "ANTI_STALL_ROUTING", True, True, rationale="Continue unaffected lanes while the provider/tool lane is repaired."),
            RecoveryStep(5, "DISCOVER_EQUIVALENT_AUTHORIZED_ROUTE", "CAPABILITY_RESOLUTION", True, True, True, True, "Use an alternate connected executor only when authority and semantics are equivalent."),
        ])
    elif failure_class == "FILE_OR_ATTACHMENT_FAILURE":
        steps.extend([
            RecoveryStep(3, "VERIFY_ARTIFACT_REFERENCE_AND_DIGEST", "ARTIFACT_READBACK", True, True),
            RecoveryStep(4, "REGENERATE_OR_REATTACH_FROM_CANONICAL_SOURCE", "ARTIFACT_RECOVERY", True, True, True, True),
        ])
    elif failure_class == "AUTH_OR_SESSION_FAILURE":
        steps.extend([
            RecoveryStep(3, "PRESERVE_PENDING_ACTION_WITHOUT_REPLAY", "FAIL_CLOSED", True, True, rationale="Do not consume or duplicate an action under uncertain authority."),
            RecoveryStep(4, "RECHECK_AUTHORIZED_EXECUTOR", "CAPABILITY_RESOLUTION", True, True, True, True, "Resume automatically only when the connected surface exposes valid authority again."),
        ])
    elif failure_class == "CLIENT_RESOURCE_FAILURE":
        steps.extend([
            RecoveryStep(3, "WRITE_MINIMAL_CONTINUITY_PACKET", "LOW_RESOURCE_MODE", True, True),
            RecoveryStep(4, "RESUME_ON_HEALTHY_EXECUTION_CONTEXT", "CHATBRIDGE_HANDOFF", True, True, True, True),
        ])
    elif failure_class == "USER_INTERRUPTION":
        steps.append(RecoveryStep(3, "WAIT_FOR_NEXT_USER_TURN_THEN_RESUME", "USER_CONTROLLED_RESUME", False, True, rationale="Do not override an explicit user stop/cancel."))
    else:
        steps.extend([
            RecoveryStep(3, "COLLECT_MINIMUM_FAILURE_TELEMETRY", "DIAGNOSTIC_MODE", True, True),
            RecoveryStep(4, "DISCOVER_LOWEST_RISK_RECOVERY_ROUTE", "CAPABILITY_RESOLUTION", True, True, True, True),
        ])

    # Long/complex operations get a decomposition route regardless of the first failure signature.
    if event.get("atomic_action") is False or event.get("payload_large") is True:
        order = max(step.order for step in steps) + 1
        steps.append(RecoveryStep(order, "DECOMPOSE_INTO_CHECKPOINTED_ATOMIC_STEPS", "CHUNKED_EXECUTION", True, True, rationale="Reduce the blast radius of another interruption."))

    return tuple(steps)


def evaluate_failure(
    event: dict[str, Any],
    *,
    previous_checkpoint: dict[str, Any] | None = None,
    mission_packet: dict[str, Any] | None = None,
) -> RecoveryReceipt:
    candidates = classify_failure(event)
    primary = candidates[0]
    checkpoint = build_checkpoint(event, previous_checkpoint)

    if mission_packet is not None:
        completion = evaluate_completion(mission_packet)
        mission_complete = bool(completion["missionComplete"])
        completion_claim_permitted = bool(completion["completionClaimPermitted"])
    else:
        mission_complete = bool(event.get("mission_complete") is True)
        completion_claim_permitted = mission_complete and bool(event.get("completion_proof") is True)

    steps = _steps_for(primary.failure_class, event, checkpoint)
    route_exhausted = bool(event.get("route_exhaustion_proven") is True)
    explicit_user_stop = primary.failure_class == "USER_INTERRUPTION"
    must_continue = not mission_complete and not route_exhausted and not explicit_user_stop

    if mission_complete:
        recovery_mode = "NO_RECOVERY_REQUIRED"
        next_action = "STOP_MISSION_COMPLETE"
    elif explicit_user_stop:
        recovery_mode = "PRESERVE_AND_AWAIT_USER_RESUME"
        next_action = "WAIT_FOR_USER_RESUME"
    elif route_exhausted:
        recovery_mode = "PRESERVE_BLOCKED_STATE"
        next_action = "WAIT_FOR_NEW_MACHINE_AUTHORITY_OR_CAPABILITY"
    else:
        recovery_mode = "AUTOMATED_RECOVERY"
        next_action = next((step.action for step in steps if step.order >= 3), "DISCOVER_LOWEST_RISK_RECOVERY_ROUTE")

    body = {
        "schema": SCHEMA,
        "event_id": event.get("event_id") or _stable_sha256({"event": event, "checkpoint": checkpoint})[:24],
        "failure_class": primary.failure_class,
        "confidence": primary.score,
        "candidates": [asdict(item) for item in candidates],
        "dependencies": list(primary.dependencies),
        "mission_complete": mission_complete,
        "completion_claim_permitted": completion_claim_permitted,
        "must_continue": must_continue,
        "recovery_mode": recovery_mode,
        "recovery_steps": [asdict(step) for step in steps],
        "checkpoint": checkpoint,
        "next_automated_action": next_action,
        "route_exhausted": route_exhausted,
        "provider_effects_claimed": False,
        "generated_at": _now(),
    }
    digest_body = dict(body)
    digest_body["generated_at"] = "<TIME>"  # deterministic receipt over semantics, not wall clock
    receipt_sha256 = _stable_sha256(digest_body)
    return RecoveryReceipt(
        schema=body["schema"],
        event_id=body["event_id"],
        failure_class=body["failure_class"],
        confidence=body["confidence"],
        candidates=candidates,
        dependencies=primary.dependencies,
        mission_complete=mission_complete,
        completion_claim_permitted=completion_claim_permitted,
        must_continue=must_continue,
        recovery_mode=recovery_mode,
        recovery_steps=steps,
        checkpoint=checkpoint,
        next_automated_action=next_action,
        route_exhausted=route_exhausted,
        provider_effects_claimed=False,
        generated_at=body["generated_at"],
        receipt_sha256=receipt_sha256,
    )


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def append_ledger(path: str | Path, receipt: RecoveryReceipt) -> dict[str, Any]:
    target = Path(path)
    if target.exists():
        ledger = json.loads(target.read_text(encoding="utf-8"))
        if ledger.get("schema") != LEDGER_SCHEMA or not isinstance(ledger.get("events"), list):
            raise ValueError("INVALID_CHAT_FAILURE_LEDGER")
    else:
        ledger = {"schema": LEDGER_SCHEMA, "events": []}
    record = asdict(receipt)
    existing = {item.get("receipt_sha256") for item in ledger["events"] if isinstance(item, dict)}
    if receipt.receipt_sha256 not in existing:
        ledger["events"].append(record)
    ledger["latest_checkpoint"] = receipt.checkpoint
    ledger["latest_receipt_sha256"] = receipt.receipt_sha256
    ledger["event_count"] = len(ledger["events"])
    _atomic_json_write(target, ledger)
    return ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", help="Failure-event JSON file")
    parser.add_argument("--mission", help="Optional Objective Completion Guard mission packet")
    parser.add_argument("--ledger", help="Optional durable recovery ledger JSON path")
    parser.add_argument("--output", help="Optional recovery receipt JSON path")
    args = parser.parse_args(argv)

    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    mission = json.loads(Path(args.mission).read_text(encoding="utf-8")) if args.mission else None
    previous = None
    if args.ledger and Path(args.ledger).exists():
        current = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
        previous = current.get("latest_checkpoint") if isinstance(current, dict) else None

    receipt = evaluate_failure(event, previous_checkpoint=previous, mission_packet=mission)
    rendered = asdict(receipt)
    if args.output:
        _atomic_json_write(Path(args.output), rendered)
    if args.ledger:
        append_ledger(args.ledger, receipt)
    print(json.dumps(rendered, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
