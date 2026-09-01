from __future__ import annotations

"""Fail-closed Kimmie adapter over the shared multistream continuity fabric.

This module executes no model calls and grants no external-effect authority.
It supplies the production controls required before a host may bind real
workers: a default stop switch, fenced leases, heartbeats, bounded retries,
and a durable dead-letter queue.
"""

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from bubbles.chat_governor_omega3.continuity import (
    CommandEnvelope,
    ContinuityLaneSpec,
    EffectClass,
    MultistreamContinuityFabric,
    PathRole,
    intent_sha256,
)


SCHEMA = "KIMMIE-WORKFORCE-RUNTIME-ADAPTER-V1"


@dataclass(frozen=True, slots=True)
class RuntimeLease:
    lane_id: str
    worker_id: str
    attempt: int
    lease_token: str
    lease_expires_at: float


class KimmieRuntimeAdapter:
    def __init__(self, db_path: str | Path, *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("MAX_ATTEMPTS_MUST_BE_POSITIVE")
        self.db_path = str(Path(db_path))
        self.max_attempts = int(max_attempts)
        self.fabric = MultistreamContinuityFabric(self.db_path)
        self._bootstrap()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _bootstrap(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS kimmie_runtime_control(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    state TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimmie_runtime_heartbeats(
                    worker_id TEXT PRIMARY KEY,
                    lane_id TEXT NOT NULL,
                    lease_token_sha256 TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    lease_expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimmie_runtime_failures(
                    lane_id TEXT PRIMARY KEY,
                    failure_count INTEGER NOT NULL,
                    last_error TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimmie_runtime_dlq(
                    lane_id TEXT PRIMARY KEY,
                    error TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    dead_lettered_at REAL NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO kimmie_runtime_control(singleton,state,updated_at) VALUES(1,'STOPPED',?)",
                (time.time(),),
            )
        finally:
            conn.close()

    def start(self, *, explicit: bool = False, now: float | None = None) -> None:
        if not explicit:
            raise PermissionError("EXPLICIT_RUNTIME_START_REQUIRED")
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            conn.execute("UPDATE kimmie_runtime_control SET state='RUNNING',updated_at=? WHERE singleton=1", (when,))
        finally:
            conn.close()

    def stop(self, *, explicit: bool = False, now: float | None = None) -> None:
        if not explicit:
            raise PermissionError("EXPLICIT_RUNTIME_STOP_REQUIRED")
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            conn.execute("UPDATE kimmie_runtime_control SET state='STOPPED',updated_at=? WHERE singleton=1", (when,))
        finally:
            conn.close()

    def is_running(self) -> bool:
        conn = self._connect()
        try:
            return conn.execute("SELECT state FROM kimmie_runtime_control WHERE singleton=1").fetchone()["state"] == "RUNNING"
        finally:
            conn.close()

    def register_packet(self, packet: Mapping[str, Any], *, now: float | None = None) -> dict[str, object]:
        lane_id = str(packet.get("packet_id") or "").strip()
        bot_id = str(packet.get("bot_id") or "").strip()
        if not lane_id or not bot_id:
            raise ValueError("PACKET_AND_BOT_ID_REQUIRED")
        authority = str(packet.get("authority") or "")
        if authority not in {"A0", "A1", "A0_OR_REVERSIBLE_A1_ONLY"}:
            raise PermissionError("KIMMIE_PACKET_AUTHORITY_PROHIBITED")
        command_id = f"KIMMIE-{lane_id}"
        mission_id = str(packet.get("lane_scope") or "KIMMIE-NO-EFFECT")
        command = CommandEnvelope(
            command_id=command_id,
            mission_id=mission_id,
            intent_sha256=intent_sha256(json.dumps(dict(packet), sort_keys=True, separators=(",", ":"))),
            source_ref=lane_id,
        )
        lane = ContinuityLaneSpec(
            lane_id=lane_id,
            command_id=command_id,
            mission_id=mission_id,
            path_id=bot_id,
            path_role=PathRole.PRIMARY,
            effect_class=EffectClass.NO_EFFECT,
            concurrency_group=str(packet.get("lease", {}).get("collision_key") or bot_id),
        )
        return self.fabric.add_command(command, (lane,), now=now)

    def lease_one(self, worker_id: str, *, lease_seconds: float = 60.0, now: float | None = None) -> RuntimeLease | None:
        if not self.is_running():
            return None
        leases = self.fabric.lease_wave(
            worker_id=worker_id,
            max_lanes=1,
            max_per_command=1,
            lease_seconds=lease_seconds,
            now=now,
        )
        if not leases:
            return None
        lease = leases[0]
        if lease.effect_class != EffectClass.NO_EFFECT.value:
            raise PermissionError("KIMMIE_ONLY_NO_EFFECT_LANES_ALLOWED")
        return RuntimeLease(
            lane_id=lease.lane_id,
            worker_id=worker_id,
            attempt=lease.attempt,
            lease_token=lease.lease_token,
            lease_expires_at=lease.lease_expires_at,
        )

    def heartbeat(self, lease: RuntimeLease, *, now: float | None = None, extend_seconds: float = 60.0) -> None:
        import hashlib

        when = time.time() if now is None else float(now)
        checkpoint = f"heartbeat:{when:.6f}"
        self.fabric.checkpoint_lane(
            lease.lane_id,
            checkpoint,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            extend_lease_seconds=extend_seconds,
            now=when,
        )
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO kimmie_runtime_heartbeats(worker_id,lane_id,lease_token_sha256,observed_at,lease_expires_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET lane_id=excluded.lane_id,
                   lease_token_sha256=excluded.lease_token_sha256,observed_at=excluded.observed_at,
                   lease_expires_at=excluded.lease_expires_at""",
                (lease.worker_id, lease.lane_id, hashlib.sha256(lease.lease_token.encode()).hexdigest(), when, when + extend_seconds),
            )
        finally:
            conn.close()

    def complete(self, lease: RuntimeLease, result_ref: str, *, now: float | None = None) -> None:
        self.fabric.complete_lane(
            lease.lane_id,
            result_ref=result_ref,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            now=now,
        )

    def fail(self, lease: RuntimeLease, error: str, *, now: float | None = None) -> str:
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT failure_count FROM kimmie_runtime_failures WHERE lane_id=?", (lease.lane_id,)).fetchone()
            count = (int(row["failure_count"]) if row else 0) + 1
            conn.execute(
                """INSERT INTO kimmie_runtime_failures(lane_id,failure_count,last_error,updated_at)
                   VALUES(?,?,?,?) ON CONFLICT(lane_id) DO UPDATE SET failure_count=excluded.failure_count,
                   last_error=excluded.last_error,updated_at=excluded.updated_at""",
                (lease.lane_id, count, (error or "LANE_FAILED")[:2000], when),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        if count < self.max_attempts:
            self.fabric.yield_worker(lease.worker_id, now=when)
            return "RETRY_READY"
        self.fabric.fail_lane(
            lease.lane_id,
            error=error,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            now=when,
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO kimmie_runtime_dlq(lane_id,error,attempt,dead_lettered_at) VALUES(?,?,?,?)",
                (lease.lane_id, (error or "LANE_FAILED")[:2000], count, when),
            )
        finally:
            conn.close()
        return "DEAD_LETTERED"

    def receipt(self) -> dict[str, Any]:
        snapshot = self.fabric.snapshot()
        conn = self._connect()
        try:
            state = conn.execute("SELECT state,updated_at FROM kimmie_runtime_control WHERE singleton=1").fetchone()
            dlq = [dict(row) for row in conn.execute("SELECT * FROM kimmie_runtime_dlq ORDER BY lane_id")]
            heartbeats = [dict(row) for row in conn.execute("SELECT worker_id,lane_id,observed_at,lease_expires_at FROM kimmie_runtime_heartbeats ORDER BY worker_id")]
        finally:
            conn.close()
        return {
            "schema": SCHEMA,
            "runtime_state": state["state"],
            "runtime_updated_at": state["updated_at"],
            "fabric": snapshot,
            "heartbeats": heartbeats,
            "dead_letters": dlq,
            "provider_model_execution_proven": False,
            "external_effect_authorized": False,
            "stable_promotion_allowed": False,
        }


__all__ = ["KimmieRuntimeAdapter", "RuntimeLease", "SCHEMA"]
