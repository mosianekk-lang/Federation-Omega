"""Cross-model handoff reliability protocol.

Provider-neutral control-plane primitive for durable AI-to-AI handoffs.
It does not invoke providers, widen authority, or manufacture execution proof.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from hashlib import sha256
import json
from typing import Optional


class HandoffState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RUNNING = "RUNNING"
    RESPONSE_WRITTEN = "RESPONSE_WRITTEN"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"
    COMPLETE = "COMPLETE"
    RETRY_DUE = "RETRY_DUE"
    ROUTE_SWITCH_REQUIRED = "ROUTE_SWITCH_REQUIRED"
    HELD_OWNER_ONLY = "HELD_OWNER_ONLY"


TERMINAL = {HandoffState.COMPLETE, HandoffState.HELD_OWNER_ONLY}


@dataclass(frozen=True)
class HandoffContract:
    handoff_id: str
    task_id: str
    origin: str
    target: str
    objective_hash: str
    ack_deadline_epoch: int
    run_deadline_epoch: int
    max_same_route_attempts: int = 1
    max_total_attempts: int = 3
    require_response: bool = True
    require_receipt: bool = True
    require_semantic_readback: bool = True

    @property
    def fingerprint(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class HandoffObservation:
    state: HandoffState
    attempt: int
    route: str
    now_epoch: int
    ack_present: bool = False
    running_present: bool = False
    response_present: bool = False
    receipt_present: bool = False
    semantic_readback_ok: bool = False
    same_route_failure_fingerprint: Optional[str] = None
    owner_only_boundary: Optional[str] = None


@dataclass(frozen=True)
class HandoffDecision:
    next_state: HandoffState
    action: str
    reason: str
    notify_owner: bool


def decide(contract: HandoffContract, obs: HandoffObservation) -> HandoffDecision:
    if obs.owner_only_boundary:
        return HandoffDecision(
            HandoffState.HELD_OWNER_ONLY,
            "surface_exact_owner_boundary",
            obs.owner_only_boundary,
            True,
        )

    if obs.response_present and (not contract.require_receipt or obs.receipt_present):
        if not contract.require_semantic_readback or obs.semantic_readback_ok:
            return HandoffDecision(HandoffState.COMPLETE, "close_handoff", "response+receipt+readback proven", False)
        return HandoffDecision(HandoffState.RETRY_DUE, "request_semantic_readback", "receipt exists but semantic readback is missing", False)

    if obs.running_present:
        return HandoffDecision(HandoffState.RUNNING, "continue_waiting_for_bounded_run", "provider run acknowledged", False)

    if obs.ack_present:
        if obs.now_epoch > contract.run_deadline_epoch:
            if obs.attempt >= contract.max_total_attempts:
                return HandoffDecision(HandoffState.ROUTE_SWITCH_REQUIRED, "switch_provider_route", "acknowledged but run deadline exhausted", False)
            return HandoffDecision(HandoffState.RETRY_DUE, "retry_changed_route_or_changed_condition", "acknowledged but no run completion", False)
        return HandoffDecision(HandoffState.ACKNOWLEDGED, "await_run_receipt", "consumer acknowledged", False)

    if obs.now_epoch > contract.ack_deadline_epoch:
        if obs.attempt >= contract.max_total_attempts:
            return HandoffDecision(HandoffState.ROUTE_SWITCH_REQUIRED, "switch_provider_route", "consumer never acknowledged", False)
        if obs.attempt >= contract.max_same_route_attempts:
            return HandoffDecision(HandoffState.ROUTE_SWITCH_REQUIRED, "switch_provider_route", "same-route retry budget exhausted", False)
        return HandoffDecision(HandoffState.RETRY_DUE, "requeue_with_new_nonce", "ack deadline missed", False)

    return HandoffDecision(HandoffState.QUEUED, "await_ack", "within acknowledgement window", False)


def objective_hash(text: str) -> str:
    return sha256(text.encode()).hexdigest()
