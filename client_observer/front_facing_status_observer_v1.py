from __future__ import annotations

"""FUSE Front-Facing Status Observer v1.

Provider-neutral normalization for owner-visible chat/runtime status telemetry.
The observer consumes telemetry supplied by a bound client/browser/desktop host;
it does not inspect ChatGPT or a browser invisibly.

Privacy rule: raw conversation content is not required.  The observer accepts
recognized status text, UI state booleans, and a one-way visible-output
fingerprint/length so stalls can be detected without persisting message bodies.
"""

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import time
from typing import Any, Mapping

from evidenceops.build_system.aaa_chat_resilience import evaluate_failure_with_aaa


SCHEMA = "FUSE-FRONT-FACING-STATUS-OBSERVER-V1"
VERSION = "1.0.0"

KNOWN_STATUS_PATTERNS = (
    "connection interrupted",
    "waiting for the complete answer",
    "thinking",
    "called tool",
    "generating",
    "reconnecting",
    "something went wrong",
    "error generating",
)


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FrontFacingSnapshot:
    source_id: str
    observed_monotonic: float
    page_family: str
    status_text: str
    response_inflight: bool
    stop_button_visible: bool
    thinking_visible: bool
    tool_activity_visible: bool
    connection_interrupted: bool
    visible_output_fingerprint: str
    visible_output_length: int
    owner_visible_progress: bool

    def validate(self) -> "FrontFacingSnapshot":
        if not self.source_id.strip():
            raise ValueError("FRONT_FACING_SOURCE_ID_REQUIRED")
        if self.observed_monotonic < 0:
            raise ValueError("FRONT_FACING_OBSERVED_MONOTONIC_INVALID")
        if self.visible_output_length < 0:
            raise ValueError("FRONT_FACING_OUTPUT_LENGTH_INVALID")
        if self.visible_output_fingerprint and not self.visible_output_fingerprint.startswith("sha256:"):
            raise ValueError("FRONT_FACING_OUTPUT_FINGERPRINT_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class FrontFacingDecision:
    state: str
    snapshot_digest: str
    no_progress_seconds: float
    status_changed: bool
    output_changed: bool
    failure_event: Mapping[str, Any] | None
    recovery: Mapping[str, Any] | None
    owner_visible_progress_required: bool
    auto_continue_intent: bool


class FrontFacingStatusObserver:
    """Stateful local observer for one front-facing chat/runtime surface."""

    def __init__(
        self,
        *,
        stall_seconds: float = 60.0,
        clock=time.monotonic,
    ) -> None:
        if stall_seconds <= 0:
            raise ValueError("stall_seconds must be positive")
        self.stall_seconds = float(stall_seconds)
        self.clock = clock
        self._last: FrontFacingSnapshot | None = None
        self._last_material_progress_at: float | None = None
        self._last_failure_key = ""

    def ingest(
        self,
        snapshot: FrontFacingSnapshot,
        *,
        mission_packet: Mapping[str, Any] | None = None,
        previous_checkpoint: Mapping[str, Any] | None = None,
    ) -> FrontFacingDecision:
        snapshot = snapshot.validate()
        now = float(snapshot.observed_monotonic)
        prior = self._last

        status_changed = prior is None or snapshot.status_text != prior.status_text
        output_changed = (
            prior is None
            or snapshot.visible_output_fingerprint != prior.visible_output_fingerprint
            or snapshot.visible_output_length != prior.visible_output_length
        )
        material_progress = bool(
            output_changed
            or (
                status_changed
                and snapshot.status_text.strip()
                and snapshot.status_text.strip().lower() not in {
                    "thinking",
                    "generating",
                    "called tool",
                }
            )
        )
        if self._last_material_progress_at is None or material_progress:
            self._last_material_progress_at = now

        no_progress = max(0.0, now - float(self._last_material_progress_at))
        status_lower = snapshot.status_text.lower()
        explicit_error = bool(
            snapshot.connection_interrupted
            or "connection interrupted" in status_lower
            or "something went wrong" in status_lower
            or "error generating" in status_lower
        )
        silent_inflight = bool(
            snapshot.response_inflight
            and no_progress >= self.stall_seconds
            and (
                snapshot.stop_button_visible
                or snapshot.thinking_visible
                or snapshot.tool_activity_visible
            )
        )
        incomplete_reporting = bool(
            snapshot.response_inflight
            and not snapshot.owner_visible_progress
            and no_progress >= self.stall_seconds
        )

        failure_event: dict[str, Any] | None = None
        recovery: Mapping[str, Any] | None = None

        if explicit_error or silent_inflight or incomplete_reporting:
            message = snapshot.status_text.strip() or (
                "Silent long-running front-facing execution with no visible progress"
            )
            failure_event = {
                "event_id": "front-facing-" + _digest({
                    "source": snapshot.source_id,
                    "status": snapshot.status_text,
                    "fingerprint": snapshot.visible_output_fingerprint,
                    "length": snapshot.visible_output_length,
                    "no_progress_bucket": int(no_progress // max(1.0, self.stall_seconds)),
                }).split(":", 1)[1][:24],
                "message": message,
                "status": snapshot.status_text,
                "stage": snapshot.page_family,
                "last_visible_text": snapshot.status_text,
                "no_progress_seconds": no_progress,
                "response_inflight": snapshot.response_inflight,
                "stop_button_visible": snapshot.stop_button_visible,
                "owner_visible_progress": snapshot.owner_visible_progress,
                "incomplete_reporting": incomplete_reporting,
                "progress_state_unknown": silent_inflight,
                "front_facing_observer": True,
                "front_facing_source_id": snapshot.source_id,
            }

            key = _digest({
                "source": snapshot.source_id,
                "status": snapshot.status_text,
                "fingerprint": snapshot.visible_output_fingerprint,
                "failure": explicit_error,
                "stall_epoch": int(no_progress // max(1.0, self.stall_seconds)),
            })
            if key != self._last_failure_key:
                aaa = evaluate_failure_with_aaa(
                    failure_event,
                    previous_checkpoint=dict(previous_checkpoint or {}),
                    mission_packet=dict(mission_packet) if mission_packet is not None else None,
                )
                recovery = aaa["effective_recovery"]
                self._last_failure_key = key

        state = "FRONT_FACING_HEALTHY"
        if explicit_error:
            state = "FRONT_FACING_ERROR"
        elif silent_inflight:
            state = "FRONT_FACING_STALLED"
        elif snapshot.response_inflight:
            state = "FRONT_FACING_RUNNING"

        self._last = snapshot
        return FrontFacingDecision(
            state=state,
            snapshot_digest=_digest(asdict(snapshot)),
            no_progress_seconds=round(no_progress, 6),
            status_changed=status_changed,
            output_changed=output_changed,
            failure_event=failure_event,
            recovery=recovery,
            owner_visible_progress_required=bool(
                state in {"FRONT_FACING_ERROR", "FRONT_FACING_STALLED"}
            ),
            auto_continue_intent=bool(
                isinstance(recovery, Mapping)
                and isinstance(recovery.get("checkpoint"), Mapping)
                and recovery["checkpoint"].get("auto_continue_intent") is True
            ),
        )


def snapshot_from_mapping(value: Mapping[str, Any]) -> FrontFacingSnapshot:
    return FrontFacingSnapshot(
        source_id=str(value.get("source_id") or "unknown-client"),
        observed_monotonic=float(value.get("observed_monotonic") or time.monotonic()),
        page_family=str(value.get("page_family") or "chat"),
        status_text=str(value.get("status_text") or ""),
        response_inflight=bool(value.get("response_inflight")),
        stop_button_visible=bool(value.get("stop_button_visible")),
        thinking_visible=bool(value.get("thinking_visible")),
        tool_activity_visible=bool(value.get("tool_activity_visible")),
        connection_interrupted=bool(value.get("connection_interrupted")),
        visible_output_fingerprint=str(value.get("visible_output_fingerprint") or ""),
        visible_output_length=int(value.get("visible_output_length") or 0),
        owner_visible_progress=bool(value.get("owner_visible_progress", True)),
    )


__all__ = [
    "FrontFacingDecision",
    "FrontFacingSnapshot",
    "FrontFacingStatusObserver",
    "KNOWN_STATUS_PATTERNS",
    "SCHEMA",
    "VERSION",
    "snapshot_from_mapping",
]
