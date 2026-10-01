from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Mapping

from fuse_genesis.resident_host import HostState

try:
    from .sol_62_frontier_primitives import digest
except ImportError:
    from sol_62_frontier_primitives import digest


SCHEMA = "SOL62_GENESIS_CLIENT_WAKE_V1"
BUILD_SCHEMA = "SOL62_GENESIS_CLIENT_BUILD_V1"


class Sol62GenesisWakeBridge:
    """Durable handoff from SOL client missions to the existing Genesis resident executor.

    This adapter does not schedule. Google Apps Script remains the estate clock,
    Genesis remains the resident executor, and SOL remains mission truth.
    """

    def __init__(self, resident_root: str | Path) -> None:
        self.resident_root = Path(resident_root)

    def enqueue(
        self,
        packet: Mapping[str, Any],
        *,
        now_epoch: float | None = None,
    ) -> dict[str, Any]:
        if packet.get("task_type") != "SOL62_CLIENT_WAKE":
            raise ValueError("SOL62_WAKE_PACKET_REQUIRED")
        mission_id = str(packet.get("mission_id") or "")
        if not mission_id:
            raise ValueError("MISSION_ID_REQUIRED")
        now = time.time() if now_epoch is None else float(now_epoch)
        task_id = "sol62-wake-" + digest(
            {
                "mission_id": mission_id,
                "reason": packet.get("reason"),
                "next_retry_epoch": packet.get("next_retry_epoch"),
            }
        )[:24]
        idem = "SOL62-WAKE:" + digest(
            {
                "mission_id": mission_id,
                "next_retry_epoch": packet.get("next_retry_epoch"),
                "completion_predicate": packet.get("completion_predicate"),
            }
        )
        state = HostState(self.resident_root)
        try:
            stored = state.enqueue(task_id, idem, dict(packet), now)
            return {
                "schema": SCHEMA,
                "task_id": stored,
                "idempotency_key": idem,
                "mission_id": mission_id,
                "scheduled_by": "EXTERNAL_ESTATE_CLOCK",
                "executor": "FUSE_GENESIS_RESIDENT_EXECUTOR_V2",
                "truth_root": "SOL_6_2",
            }
        finally:
            state.close()

    def enqueue_build(
        self,
        packet: Mapping[str, Any],
        *,
        now_epoch: float | None = None,
    ) -> dict[str, Any]:
        if packet.get("task_type") != "SOL62_CLIENT_BUILD":
            raise ValueError("SOL62_BUILD_PACKET_REQUIRED")
        mission_id = str(packet.get("mission_id") or "")
        if not mission_id:
            raise ValueError("MISSION_ID_REQUIRED")
        now = time.time() if now_epoch is None else float(now_epoch)
        task_id = "sol62-build-" + digest(
            {
                "mission_id": mission_id,
                "transition_id": packet.get("transition_id"),
                "reason": packet.get("reason"),
                "source_frontier": packet.get("source_frontier"),
                "plan": packet.get("codeforge", {}).get("plan_sha256"),
            }
        )[:24]
        idem = "SOL62-BUILD:" + digest(
            {
                "mission_id": mission_id,
                "transition_id": packet.get("transition_id"),
                "source_frontier": packet.get("source_frontier"),
                "plan": packet.get("codeforge", {}).get("plan_sha256"),
            }
        )
        state = HostState(self.resident_root)
        try:
            stored = state.enqueue(task_id, idem, dict(packet), now)
            return {
                "schema": BUILD_SCHEMA,
                "task_id": stored,
                "idempotency_key": idem,
                "mission_id": mission_id,
                "scheduled_by": "EXTERNAL_ESTATE_CLOCK",
                "executor": "FUSE_GENESIS_RESIDENT_EXECUTOR_V2",
                "build_engine": "FUSE_HYPERCUBE_CODEFORGE",
                "truth_root": "SOL_6_2",
            }
        finally:
            state.close()

    @staticmethod
    def handler(
        wake_fn: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        build_fn: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> Callable[[Mapping[str, Any]], Mapping[str, Any]]:
        def _handle(payload: Mapping[str, Any]) -> Mapping[str, Any]:
            task_type = payload.get("task_type")
            if task_type == "SOL62_CLIENT_WAKE":
                return dict(wake_fn(payload))
            if task_type == "SOL62_CLIENT_BUILD":
                if build_fn is None:
                    raise RuntimeError("SOL62_BUILD_HANDLER_UNBOUND")
                return dict(build_fn(payload))
            raise ValueError("UNSUPPORTED_RESIDENT_TASK")
        return _handle
