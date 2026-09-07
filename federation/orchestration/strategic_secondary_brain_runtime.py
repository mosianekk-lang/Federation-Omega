"""Durable provider-neutral runtime kernel for Strategic FUSE Secondary Brain.

This module deliberately performs no network or provider effects. It defines the
state, idempotency, recovery, heartbeat and semantic-receipt contract a private
provider adapter must satisfy before Strategic FUSE may be called RUNNING.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import time
from typing import Sequence

from federation.orchestration.strategic_secondary_brain import (
    ActionDisposition,
    AuthorityClass,
    StrategicCompiler,
    StrategicHypothesis,
    StrategicOption,
    StrategicPacket,
    StrategicSignal,
)


class RuntimeStatus(str, Enum):
    HEALTHY = "HEALTHY"
    NO_MATERIAL_DELTA = "NO_MATERIAL_DELTA"
    HELD_AUTHORITY = "HELD_AUTHORITY"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True)
class StrategicEvent:
    event_id: str
    cursor: str
    observed_at: float
    signal: StrategicSignal

    @property
    def fingerprint(self) -> str:
        payload = {
            "event_id": self.event_id,
            "cursor": self.cursor,
            "signal_fingerprint": self.signal.fingerprint,
        }
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class RuntimeCheckpoint:
    source_main: str
    last_cursor: str | None = None
    processed_event_fingerprints: tuple[str, ...] = ()
    last_packet_fingerprint: str | None = None
    last_success_at: float | None = None
    next_due_at: float | None = None
    heartbeat_seq: int = 0
    consecutive_failures: int = 0
    last_failure_fingerprint: str | None = None

    @property
    def fingerprint(self) -> str:
        return sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class RuntimeReceipt:
    run_id: str
    status: RuntimeStatus
    started_at: float
    completed_at: float
    source_main: str
    input_event_ids: tuple[str, ...]
    executed_event_ids: tuple[str, ...]
    deduped_event_ids: tuple[str, ...]
    packet_fingerprint: str | None
    disposition: ActionDisposition | None
    authority: AuthorityClass
    missed_run_recovered: bool
    resumed_after_failure: bool
    semantic_readback_required: bool
    checkpoint_fingerprint: str

    @property
    def fingerprint(self) -> str:
        return sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class RuntimeStep:
    checkpoint: RuntimeCheckpoint
    receipt: RuntimeReceipt
    packet: StrategicPacket | None


class StrategicRuntimeKernel:
    """Deterministic crash-resumable wrapper around :class:`StrategicCompiler`."""

    def __init__(
        self,
        *,
        cadence_seconds: int = 3600,
        dedupe_window: int = 4096,
        compiler: StrategicCompiler | None = None,
    ) -> None:
        if cadence_seconds <= 0:
            raise ValueError("cadence_seconds must be positive")
        if dedupe_window <= 0:
            raise ValueError("dedupe_window must be positive")
        self.cadence_seconds = cadence_seconds
        self.dedupe_window = dedupe_window
        self.compiler = compiler or StrategicCompiler()

    def heartbeat(self, checkpoint: RuntimeCheckpoint, *, now: float | None = None) -> RuntimeCheckpoint:
        """Advance only the liveness sequence; never manufacture execution proof."""
        _ = time.time() if now is None else now
        return replace(checkpoint, heartbeat_seq=checkpoint.heartbeat_seq + 1)

    def record_failure(
        self,
        checkpoint: RuntimeCheckpoint,
        *,
        failure_fingerprint: str,
    ) -> RuntimeCheckpoint:
        """Persist a failure without advancing cursor or dedupe state."""
        if not failure_fingerprint:
            raise ValueError("failure_fingerprint is required")
        return replace(
            checkpoint,
            consecutive_failures=checkpoint.consecutive_failures + 1,
            last_failure_fingerprint=failure_fingerprint,
        )

    def step(
        self,
        *,
        checkpoint: RuntimeCheckpoint,
        events: Sequence[StrategicEvent],
        hypotheses: Sequence[StrategicHypothesis],
        options: Sequence[StrategicOption],
        source_main: str,
        now: float | None = None,
    ) -> RuntimeStep:
        now = time.time() if now is None else now
        if checkpoint.source_main and checkpoint.source_main != source_main:
            # Source epoch movement is explicit rather than silently inherited.
            checkpoint = replace(checkpoint, source_main=source_main)

        seen = set(checkpoint.processed_event_fingerprints)
        executed: list[StrategicEvent] = []
        deduped: list[StrategicEvent] = []
        local_seen: set[str] = set()
        for event in events:
            fp = event.fingerprint
            if fp in seen or fp in local_seen:
                deduped.append(event)
                continue
            local_seen.add(fp)
            executed.append(event)

        missed = checkpoint.next_due_at is not None and now > checkpoint.next_due_at
        resumed = checkpoint.consecutive_failures > 0 or checkpoint.last_failure_fingerprint is not None
        packet: StrategicPacket | None = None
        status = RuntimeStatus.NO_MATERIAL_DELTA
        authority = AuthorityClass.A0
        disposition: ActionDisposition | None = None

        if executed:
            packet = self.compiler.compile(
                signals=[event.signal for event in executed],
                hypotheses=hypotheses,
                options=options,
                now=now,
            )
            authority = packet.authority
            disposition = packet.disposition
            if packet.disposition is ActionDisposition.HOLD_AUTHORITY:
                status = RuntimeStatus.HELD_AUTHORITY
            elif packet.disposition in (
                ActionDisposition.QUEUE_SAFE,
                ActionDisposition.RESEARCH,
                ActionDisposition.ARCHIVE,
            ):
                status = RuntimeStatus.HEALTHY

        merged = list(checkpoint.processed_event_fingerprints)
        merged.extend(event.fingerprint for event in executed)
        merged = merged[-self.dedupe_window :]
        last_cursor = executed[-1].cursor if executed else checkpoint.last_cursor
        next_due = now + self.cadence_seconds
        new_checkpoint = RuntimeCheckpoint(
            source_main=source_main,
            last_cursor=last_cursor,
            processed_event_fingerprints=tuple(merged),
            last_packet_fingerprint=packet.fingerprint if packet else checkpoint.last_packet_fingerprint,
            last_success_at=now,
            next_due_at=next_due,
            heartbeat_seq=checkpoint.heartbeat_seq + 1,
            consecutive_failures=0,
            last_failure_fingerprint=None,
        )
        basis = {
            "source_main": source_main,
            "checkpoint_before": checkpoint.fingerprint,
            "checkpoint_after": new_checkpoint.fingerprint,
            "event_ids": [event.event_id for event in executed],
            "packet": packet.fingerprint if packet else None,
            "now": now,
        }
        run_id = "SFRUN-" + sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()[:16].upper()
        receipt = RuntimeReceipt(
            run_id=run_id,
            status=status,
            started_at=now,
            completed_at=now,
            source_main=source_main,
            input_event_ids=tuple(event.event_id for event in events),
            executed_event_ids=tuple(event.event_id for event in executed),
            deduped_event_ids=tuple(event.event_id for event in deduped),
            packet_fingerprint=packet.fingerprint if packet else None,
            disposition=disposition,
            authority=authority,
            missed_run_recovered=missed,
            resumed_after_failure=resumed,
            semantic_readback_required=bool(executed),
            checkpoint_fingerprint=new_checkpoint.fingerprint,
        )
        return RuntimeStep(new_checkpoint, receipt, packet)


def provider_runtime_acceptance_contract() -> dict[str, object]:
    """Machine-readable minimum contract for a provider binding.

    Returning the contract is effect-free. A provider adapter must independently
    prove each item; source presence never promotes runtime maturity.
    """
    return {
        "schema": "STRATEGIC_FUSE_PROVIDER_RUNTIME_V1",
        "required": [
            "private_provider_identity",
            "durable_checkpoint_store",
            "event_or_poll_signal_source",
            "scheduled_reconciliation",
            "heartbeat_and_health",
            "idempotent_event_dedupe",
            "missed_run_recovery",
            "crash_resume_without_cursor_advance",
            "fSED_six_ledger_read_write",
            "semantic_execution_receipt",
            "post_write_provider_readback",
            "forecast_calibration_receipt",
            "a0_a1_only_automatic_effects",
            "a2_exact_authority_hold",
        ],
        "forbidden_inference": [
            "source_equals_running",
            "heartbeat_equals_semantic_execution",
            "generic_http_200_equals_action_readback",
            "scheduler_metadata_equals_provider_runtime",
        ],
    }
