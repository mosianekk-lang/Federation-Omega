from __future__ import annotations

"""Durable automatic resume binding for resolved SOL62 interruptions.

This adapter does not create a scheduler or authority plane. It bridges a
resolved interruption into the already-existing Genesis resident wake queue.
Effect authority remains separately enforced by SOL62/FUSE at execution time.
"""

import time
from typing import Any, Mapping, Protocol


SCHEMA = "SOL62_INTERRUPTION_AUTO_RESUME_V1"
VERSION = "1.0.0"


class ResumeClient(Protocol):
    def open_interruptions(self, mission_id: str) -> list[dict[str, Any]]: ...
    def resume_packet(self, mission_id: str, *, reason: str) -> dict[str, Any]: ...


class WakeBridge(Protocol):
    def enqueue(
        self,
        packet: Mapping[str, Any],
        *,
        now_epoch: float | None = None,
    ) -> dict[str, Any]: ...


def enqueue_after_interruption_resolution(
    *,
    client: ResumeClient,
    bridge: WakeBridge,
    mission_id: str,
    decision: str,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    if not mission_id.strip():
        raise ValueError("MISSION_ID_REQUIRED")
    normalized = str(decision or "").strip().upper()
    if normalized not in {"RESUME", "APPROVE", "REJECT", "CANCEL"}:
        raise ValueError("INVALID_INTERRUPTION_DECISION")

    if normalized not in {"RESUME", "APPROVE"}:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission_id,
            "decision": normalized,
            "queued": False,
            "reason": "TERMINAL_OR_NONRESUME_DECISION",
            "effect_authorized": False,
            "authority_expansion": False,
        }

    remaining = client.open_interruptions(mission_id)
    if remaining:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission_id,
            "decision": normalized,
            "queued": False,
            "reason": "OTHER_INTERRUPTION_REMAINS_OPEN",
            "open_interruption_ids": [
                str(item.get("interruption_id") or "") for item in remaining
            ],
            "effect_authorized": False,
            "authority_expansion": False,
        }

    packet = client.resume_packet(
        mission_id,
        reason=f"INTERRUPTION_{normalized}_AUTO_RESUME",
    )
    receipt = bridge.enqueue(
        packet,
        now_epoch=time.time() if now_epoch is None else float(now_epoch),
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mission_id": mission_id,
        "decision": normalized,
        "queued": True,
        "reason": "RESOLVED_INTERRUPTION_DURABLE_WAKE_ENQUEUED",
        "resume_packet_checkpoint": packet["durability_checkpoint_key"],
        "replay_guard_verified": bool(packet["replay_guard_verified"]),
        "wake_receipt": receipt,
        "effect_authorized": False,
        "authority_expansion": False,
        "truth_boundary": (
            "INTERRUPTION_RESOLVED_AND_WAKE_QUEUED"
            "!=WAKE_EXECUTED!=EFFECT_AUTHORIZED!=MISSION_VERIFIED_REALITY"
        ),
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "enqueue_after_interruption_resolution",
]
