"""AAA adapter for the live CFRE/Bubbles chat-failure recovery path.

The base CFRE receipt is preserved as evidence. This adapter adds an effective
recovery plan that applies Formation-Omega route-fingerprint memory before a
retry is selected. Route memory is persisted in the ordinary recovery
checkpoint so later cycles learn without a separate provider or database.
No provider effect is performed here.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping

from formation_omega.aaa_workflow import (
    AAALearningEvent,
    RouteAttempt,
    RouteOutcome,
    abstract_learning,
    route_retry_decision,
)

from .chat_failure_resilience import evaluate_failure


SCHEMA = "EVIDENCEOPS-CHAT-FAILURE-AAA-1"
MAX_ROUTE_MEMORY = 16


def _sha256(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _route_outcome(value: object) -> RouteOutcome:
    try:
        return RouteOutcome(str(value).upper())
    except ValueError:
        return RouteOutcome.FAILURE


def _parse_history_rows(rows: object, objective: str) -> list[RouteAttempt]:
    if not isinstance(rows, (list, tuple)):
        return []

    history: list[RouteAttempt] = []
    for index, item in enumerate(rows):
        if not isinstance(item, Mapping):
            continue
        route_fingerprint = str(item.get("route_fingerprint") or "")
        if not route_fingerprint:
            continue
        history.append(
            RouteAttempt(
                route_id=str(item.get("route_id") or f"history-{index}"),
                objective=str(item.get("objective") or objective),
                route_fingerprint=route_fingerprint,
                precondition_fingerprint=str(item.get("precondition_fingerprint") or ""),
                outcome=_route_outcome(item.get("outcome") or "FAILURE"),
                attempted_at=str(item.get("attempted_at") or "1970-01-01T00:00:00+00:00"),
                owner_burden=float(item.get("owner_burden") or 0.0),
                proof_quality=float(item.get("proof_quality") or 0.0),
            )
        )
    return history


def _history(
    event: Mapping[str, Any],
    previous_checkpoint: Mapping[str, Any] | None,
    objective: str,
) -> tuple[RouteAttempt, ...]:
    """Merge explicit and checkpoint-carried route memory, newest record wins."""

    combined = []
    if previous_checkpoint:
        combined.extend(_parse_history_rows(previous_checkpoint.get("aaa_route_history", ()), objective))
    combined.extend(_parse_history_rows(event.get("route_history", ()), objective))

    # One current record per route/precondition/outcome is enough to suppress an
    # unchanged retry. Keep the newest evidence and a small bounded history.
    latest: dict[tuple[str, str, str, str], RouteAttempt] = {}
    for item in combined:
        key = (
            item.objective,
            item.route_fingerprint,
            item.precondition_fingerprint,
            item.outcome.value,
        )
        prior = latest.get(key)
        if prior is None or item.attempted_at >= prior.attempted_at:
            latest[key] = item
    ordered = sorted(latest.values(), key=lambda item: item.attempted_at)
    return tuple(ordered[-MAX_ROUTE_MEMORY:])


def _persist_route_memory(
    effective: dict[str, Any],
    history: Iterable[RouteAttempt],
    current: RouteAttempt | None,
) -> int:
    checkpoint = effective.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return 0

    records = list(history)
    if current is not None:
        # evaluate_failure_with_aaa is called because the current operation
        # failed/stalled/blocked. Persist that adverse fact for the next cycle.
        records.append(
            RouteAttempt(
                route_id=current.route_id,
                objective=current.objective,
                route_fingerprint=current.route_fingerprint,
                precondition_fingerprint=current.precondition_fingerprint,
                outcome=RouteOutcome.FAILURE,
                attempted_at=current.attempted_at,
                owner_burden=current.owner_burden,
                proof_quality=current.proof_quality,
            )
        )

    latest: dict[tuple[str, str, str, str], RouteAttempt] = {}
    for item in records:
        key = (
            item.objective,
            item.route_fingerprint,
            item.precondition_fingerprint,
            item.outcome.value,
        )
        prior = latest.get(key)
        if prior is None or item.attempted_at >= prior.attempted_at:
            latest[key] = item
    bounded = sorted(latest.values(), key=lambda item: item.attempted_at)[-MAX_ROUTE_MEMORY:]
    checkpoint["aaa_route_history"] = [asdict(item) for item in bounded]
    return len(bounded)


def _rewrite_effective_recovery(
    recovery: dict[str, Any],
    *,
    retry_allowed: bool,
) -> dict[str, Any]:
    effective = json.loads(json.dumps(recovery))
    if retry_allowed or effective.get("next_automated_action") != "RETRY_SAME_ATOMIC_ACTION":
        return effective

    steps = list(effective.get("recovery_steps") or [])
    rewritten: list[dict[str, Any]] = []
    inserted_distinct_route = False
    for step in steps:
        if step.get("action") == "RETRY_SAME_ATOMIC_ACTION":
            rewritten.append(
                {
                    **step,
                    "action": "SUPPRESS_UNCHANGED_FAILED_ROUTE",
                    "mode": "AAA_ROUTE_MEMORY",
                    "retry_safe": False,
                    "rationale": "The same route already failed under unchanged preconditions; repeating it is suppressed.",
                }
            )
            rewritten.append(
                {
                    "order": float(step.get("order", 3)) + 0.1,
                    "action": "DISCOVER_MATERIALLY_DIFFERENT_ROUTE",
                    "mode": "AAA_ROUTE_CHALLENGER",
                    "automated": True,
                    "retry_safe": True,
                    "requires_external_executor": False,
                    "stop_on_success": True,
                    "rationale": "Continue the objective through a distinct eligible route instead of an unchanged retry.",
                }
            )
            inserted_distinct_route = True
        else:
            rewritten.append(step)

    effective["recovery_steps"] = rewritten
    if inserted_distinct_route:
        effective["next_automated_action"] = "DISCOVER_MATERIALLY_DIFFERENT_ROUTE"
    return effective


def evaluate_failure_with_aaa(
    event: dict[str, Any],
    *,
    previous_checkpoint: dict[str, Any] | None = None,
    mission_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run CFRE, apply AAA route memory, then persist learning in the checkpoint."""

    base = evaluate_failure(
        event,
        previous_checkpoint=previous_checkpoint,
        mission_packet=mission_packet,
    )
    base_dict = asdict(base)

    objective = str(event.get("objective") or event.get("active_directive") or "recover chat failure")
    route_fingerprint = str(event.get("route_fingerprint") or "")
    precondition_fingerprint = str(event.get("precondition_fingerprint") or "")
    history = _history(event, previous_checkpoint, objective)

    current_route = None
    retry = None
    if route_fingerprint:
        current_route = RouteAttempt(
            route_id=str(event.get("route_id") or "current-route"),
            objective=objective,
            route_fingerprint=route_fingerprint,
            precondition_fingerprint=precondition_fingerprint,
            outcome=RouteOutcome.NEAR_MISS,
            attempted_at=str(
                event.get("attempted_at")
                or datetime.now(timezone.utc).isoformat()
            ),
            owner_burden=float(event.get("owner_burden") or 0.0),
            proof_quality=float(event.get("proof_quality") or 0.0),
        )
        retry = route_retry_decision(current_route, history)

    retry_allowed = True if retry is None else retry.retry_allowed
    effective = _rewrite_effective_recovery(base_dict, retry_allowed=retry_allowed)
    memory_count = _persist_route_memory(effective, history, current_route)

    learning_events: list[AAALearningEvent] = []
    if retry is not None and not retry.retry_allowed:
        learning_events.append(
            AAALearningEvent(
                event_id=str(event.get("event_id") or base.event_id),
                category="UNCHANGED_ROUTE_FAILURE",
                objective=objective,
                result="unchanged route suppressed",
                evidence_ids=tuple(
                    str(item)
                    for item in event.get("evidence_ids", ())
                    if item is not None
                ),
                route_fingerprint=route_fingerprint,
                precondition_fingerprint=precondition_fingerprint,
                owner_burden=float(event.get("owner_burden") or 0.0),
            )
        )

    genes = abstract_learning(learning_events)
    body = {
        "schema": SCHEMA,
        "base_recovery": base_dict,
        "effective_recovery": effective,
        "aaa_route_retry": asdict(retry) if retry is not None else None,
        "aaa_route_memory_count": memory_count,
        "aaa_learning_genes": [asdict(gene) for gene in genes],
        "provider_effects": False,
        "truth_boundary": (
            "AAA may change the local recovery route selection only. It does not prove "
            "provider authority, external execution, or repair of the underlying service."
        ),
    }
    body["aaa_receipt_sha256"] = _sha256(body)
    return body


__all__ = ["MAX_ROUTE_MEMORY", "SCHEMA", "evaluate_failure_with_aaa"]
