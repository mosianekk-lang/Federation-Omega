#!/usr/bin/env python3
"""Durable, local SOVARA mission runtime.

The runtime provides transactional mission state, append-only hash-chained
events, idempotency, fencing leases, bounded retries, dead letters,
compensation, cancellation, checkpoints, structured spans and portable
backup/restore.  It is deliberately provider-neutral and has no network,
credential, shell, connector or deployment client.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterator, Mapping

from federation_capability_broker import OWNER_ID, canonical_sha256, reject_secret_material


RUNTIME_CONTRACT = "SOVARA_DURABLE_MISSION_RUNTIME_V1"
MISSION_STATES = {
    "RUNNING", "CANCEL_REQUESTED", "COMPENSATING", "COMPENSATED",
    "COMPENSATION_FAILED", "COMPLETED", "FAILED",
}
TASK_STATES = {
    "QUEUED", "RUNNING", "RETRY_WAIT", "COMPLETED", "DEAD_LETTER",
    "COMPENSATED", "COMPENSATION_FAILED", "CANCELLED",
}


class DurableRuntimeError(RuntimeError):
    code = "DURABLE_RUNTIME_ERROR"


class IntegrityViolation(DurableRuntimeError):
    code = "INTEGRITY_VIOLATION"


class IdempotencyConflict(DurableRuntimeError):
    code = "IDEMPOTENCY_CONFLICT"


class LeaseConflict(DurableRuntimeError):
    code = "LEASE_CONFLICT"


class InvalidTransition(DurableRuntimeError):
    code = "INVALID_TRANSITION"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise DurableRuntimeError("timestamps require timezone information")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise DurableRuntimeError("invalid UTC timestamp") from exc
    return _utc(parsed)


def _json(value: Any) -> str:
    reject_secret_material(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True, slots=True)
class LeaseFence:
    resource_id: str
    mission_id: str
    holder_id: str
    fence: int
    expires_at: str


@dataclass(frozen=True, slots=True)
class BackupReceipt:
    contract: str
    source_path: str
    backup_path: str
    sha256: str
    byte_count: int
    integrity: str


class DurableMissionRuntime:
    """SQLite-backed durable mission state with fail-closed invariants."""

    def __init__(
        self,
        path: str | Path,
        *,
        owner_id: str = OWNER_ID,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if owner_id != OWNER_ID:
            raise DurableRuntimeError("runtime owner identity mismatch")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.owner_id = owner_id
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._create_schema()

    def _now(self) -> datetime:
        return _utc(self._clock())

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runtime_meta(
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS missions(
              mission_id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              state TEXT NOT NULL,
              input_json TEXT NOT NULL,
              result_json TEXT,
              cancel_requested INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              event_head_hash TEXT NOT NULL DEFAULT '',
              event_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              mission_id TEXT NOT NULL REFERENCES missions(mission_id),
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              occurred_at TEXT NOT NULL,
              prev_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL UNIQUE,
              idempotency_key TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS events_mission_seq
              ON events(mission_id, seq);
            CREATE TABLE IF NOT EXISTS leases(
              resource_id TEXT PRIMARY KEY,
              mission_id TEXT NOT NULL REFERENCES missions(mission_id),
              holder_id TEXT NOT NULL,
              fence INTEGER NOT NULL,
              expires_at TEXT NOT NULL,
              state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks(
              task_id TEXT PRIMARY KEY,
              mission_id TEXT NOT NULL REFERENCES missions(mission_id),
              state TEXT NOT NULL,
              attempt INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL,
              retry_at TEXT,
              lease_resource_id TEXT,
              lease_holder_id TEXT,
              lease_fence INTEGER,
              started_at TEXT,
              input_json TEXT NOT NULL,
              result_json TEXT,
              last_error TEXT,
              compensation_json TEXT,
              completed_seq INTEGER,
              idempotency_key TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS tasks_due
              ON tasks(state, retry_at);
            CREATE TABLE IF NOT EXISTS dead_letters(
              task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
              mission_id TEXT NOT NULL,
              error TEXT NOT NULL,
              failed_at TEXT NOT NULL,
              attempt INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints(
              mission_id TEXT NOT NULL REFERENCES missions(mission_id),
              version INTEGER NOT NULL,
              event_seq INTEGER NOT NULL,
              state_json TEXT NOT NULL,
              state_sha256 TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY(mission_id, version)
            );
            CREATE TABLE IF NOT EXISTS spans(
              span_id TEXT PRIMARY KEY,
              mission_id TEXT NOT NULL REFERENCES missions(mission_id),
              parent_span_id TEXT,
              operation TEXT NOT NULL,
              kind TEXT NOT NULL,
              status TEXT NOT NULL,
              attributes_json TEXT NOT NULL,
              input_sha256 TEXT,
              output_sha256 TEXT,
              started_at TEXT NOT NULL,
              ended_at TEXT NOT NULL,
              sensitive_content_captured INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        existing_task_columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(tasks)")
        }
        for column, declaration in (
            ("lease_resource_id", "TEXT"),
            ("lease_holder_id", "TEXT"),
            ("lease_fence", "INTEGER"),
            ("started_at", "TEXT"),
        ):
            if column not in existing_task_columns:
                self._conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} {declaration}")
        self._conn.execute(
            "INSERT OR IGNORE INTO runtime_meta(key,value) VALUES('contract',?)",
            (RUNTIME_CONTRACT,),
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO runtime_meta(key,value) VALUES('owner_id',?)",
            (OWNER_ID,),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DurableMissionRuntime":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _mission(self, conn: sqlite3.Connection, mission_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM missions WHERE mission_id=?", (mission_id,)
        ).fetchone()
        if row is None:
            raise DurableRuntimeError(f"unknown mission: {mission_id}")
        return row

    def _append_event(
        self,
        conn: sqlite3.Connection,
        mission_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not event_type or not idempotency_key:
            raise DurableRuntimeError("event type and idempotency key are required")
        payload_json = _json(dict(payload))
        duplicate = conn.execute(
            "SELECT * FROM events WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if duplicate is not None:
            if (
                duplicate["mission_id"] != mission_id
                or duplicate["event_type"] != event_type
                or duplicate["payload_json"] != payload_json
            ):
                raise IdempotencyConflict("idempotency key reused for different event")
            return dict(duplicate)
        mission = self._mission(conn, mission_id)
        occurred_at = _utc_text(self._now())
        prev_hash = mission["event_head_hash"]
        binding = {
            "missionId": mission_id,
            "eventType": event_type,
            "payload": json.loads(payload_json),
            "occurredAt": occurred_at,
            "prevHash": prev_hash,
            "idempotencyKey": idempotency_key,
        }
        event_hash = canonical_sha256(binding)
        cursor = conn.execute(
            """
            INSERT INTO events(
              mission_id,event_type,payload_json,occurred_at,prev_hash,event_hash,
              idempotency_key
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                mission_id, event_type, payload_json, occurred_at, prev_hash,
                event_hash, idempotency_key,
            ),
        )
        conn.execute(
            """
            UPDATE missions
               SET event_head_hash=?, event_count=event_count+1, updated_at=?
             WHERE mission_id=?
            """,
            (event_hash, occurred_at, mission_id),
        )
        return dict(
            conn.execute("SELECT * FROM events WHERE seq=?", (cursor.lastrowid,)).fetchone()
        )

    def append_event(
        self,
        mission_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self._transaction() as conn:
            return self._append_event(
                conn, mission_id, event_type, payload, idempotency_key
            )

    def create_mission(
        self,
        mission_id: str,
        mission_input: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not mission_id:
            raise DurableRuntimeError("mission ID is required")
        input_json = _json(dict(mission_input))
        now = _utc_text(self._now())
        with self._transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM missions WHERE mission_id=?", (mission_id,)
            ).fetchone()
            if existing is not None:
                if existing["input_json"] != input_json:
                    raise IdempotencyConflict("mission ID reused with different input")
                return self.mission_snapshot(mission_id, connection=conn)
            conn.execute(
                """
                INSERT INTO missions(
                  mission_id,owner_id,state,input_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (mission_id, OWNER_ID, "RUNNING", input_json, now, now),
            )
            self._append_event(
                conn,
                mission_id,
                "MISSION_CREATED",
                {"ownerId": OWNER_ID, "inputSha256": canonical_sha256(mission_input)},
                idempotency_key,
            )
            return self.mission_snapshot(mission_id, connection=conn)

    def mission_snapshot(
        self, mission_id: str, *, connection: sqlite3.Connection | None = None
    ) -> dict[str, Any]:
        conn = connection or self._conn
        row = self._mission(conn, mission_id)
        tasks = conn.execute(
            "SELECT task_id,state,attempt,max_attempts,retry_at,last_error "
            "FROM tasks WHERE mission_id=? ORDER BY task_id",
            (mission_id,),
        ).fetchall()
        return {
            "missionId": mission_id,
            "ownerId": row["owner_id"],
            "state": row["state"],
            "cancelRequested": bool(row["cancel_requested"]),
            "eventCount": row["event_count"],
            "eventHeadSha256": row["event_head_hash"],
            "input": json.loads(row["input_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "tasks": [dict(item) for item in tasks],
        }

    def enqueue_task(
        self,
        mission_id: str,
        task_id: str,
        task_input: Mapping[str, Any],
        *,
        max_attempts: int = 3,
        compensation: Mapping[str, Any] | None = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not 1 <= max_attempts <= 10:
            raise DurableRuntimeError("max attempts must be between one and ten")
        input_json = _json(dict(task_input))
        compensation_json = _json(dict(compensation)) if compensation else None
        with self._transaction() as conn:
            mission = self._mission(conn, mission_id)
            if mission["cancel_requested"]:
                raise InvalidTransition("cannot enqueue after cancellation")
            existing = conn.execute(
                "SELECT * FROM tasks WHERE task_id=? OR idempotency_key=?",
                (task_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["task_id"] != task_id
                    or existing["mission_id"] != mission_id
                    or existing["input_json"] != input_json
                ):
                    raise IdempotencyConflict("task idempotency conflict")
                return dict(existing)
            conn.execute(
                """
                INSERT INTO tasks(
                  task_id,mission_id,state,max_attempts,input_json,
                  compensation_json,idempotency_key
                ) VALUES(?,?, 'QUEUED',?,?,?,?)
                """,
                (
                    task_id, mission_id, max_attempts, input_json,
                    compensation_json, idempotency_key,
                ),
            )
            self._append_event(
                conn,
                mission_id,
                "TASK_ENQUEUED",
                {
                    "taskId": task_id,
                    "inputSha256": canonical_sha256(task_input),
                    "compensationRegisteredBeforeEffect": bool(compensation),
                },
                f"{idempotency_key}:event",
            )
            return dict(
                conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            )

    def acquire_lease(
        self,
        mission_id: str,
        resource_id: str,
        holder_id: str,
        *,
        ttl_seconds: int = 60,
    ) -> LeaseFence:
        if not 1 <= ttl_seconds <= 120:
            raise LeaseConflict("lease TTL must be from one to 120 seconds")
        now = self._now()
        expires = now + timedelta(seconds=ttl_seconds)
        with self._transaction() as conn:
            self._mission(conn, mission_id)
            row = conn.execute(
                "SELECT * FROM leases WHERE resource_id=?", (resource_id,)
            ).fetchone()
            if row is not None and row["state"] == "ACTIVE":
                active = _parse_utc(row["expires_at"]) > now
                if active and (
                    row["mission_id"] != mission_id or row["holder_id"] != holder_id
                ):
                    raise LeaseConflict("resource has an unexpired lease")
                if active:
                    return LeaseFence(
                        resource_id, mission_id, holder_id, row["fence"], row["expires_at"]
                    )
            fence = int(row["fence"]) + 1 if row is not None else 1
            conn.execute(
                """
                INSERT INTO leases(resource_id,mission_id,holder_id,fence,expires_at,state)
                VALUES(?,?,?,?,?,'ACTIVE')
                ON CONFLICT(resource_id) DO UPDATE SET
                  mission_id=excluded.mission_id,
                  holder_id=excluded.holder_id,
                  fence=excluded.fence,
                  expires_at=excluded.expires_at,
                  state='ACTIVE'
                """,
                (resource_id, mission_id, holder_id, fence, _utc_text(expires)),
            )
            self._append_event(
                conn,
                mission_id,
                "LEASE_ACQUIRED",
                {
                    "resourceId": resource_id,
                    "holderId": holder_id,
                    "fence": fence,
                    "expiresAt": _utc_text(expires),
                },
                f"lease:{resource_id}:{fence}",
            )
            return LeaseFence(
                resource_id, mission_id, holder_id, fence, _utc_text(expires)
            )

    def _validate_lease(
        self, conn: sqlite3.Connection, lease: LeaseFence
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM leases WHERE resource_id=?", (lease.resource_id,)
        ).fetchone()
        if row is None:
            raise LeaseConflict("lease not found")
        if (
            row["mission_id"] != lease.mission_id
            or row["holder_id"] != lease.holder_id
            or row["fence"] != lease.fence
            or row["state"] != "ACTIVE"
            or _parse_utc(row["expires_at"]) <= self._now()
        ):
            raise LeaseConflict("lease expired, superseded or mismatched")
        return row

    def heartbeat(self, lease: LeaseFence, *, ttl_seconds: int = 60) -> LeaseFence:
        if not 1 <= ttl_seconds <= 120:
            raise LeaseConflict("heartbeat TTL out of bounds")
        with self._transaction() as conn:
            self._validate_lease(conn, lease)
            expires = self._now() + timedelta(seconds=ttl_seconds)
            conn.execute(
                "UPDATE leases SET expires_at=? WHERE resource_id=? AND fence=?",
                (_utc_text(expires), lease.resource_id, lease.fence),
            )
            self._append_event(
                conn,
                lease.mission_id,
                "LEASE_HEARTBEAT",
                {
                    "resourceId": lease.resource_id,
                    "holderId": lease.holder_id,
                    "fence": lease.fence,
                    "expiresAt": _utc_text(expires),
                },
                f"heartbeat:{lease.resource_id}:{lease.fence}:{_utc_text(expires)}",
            )
            return LeaseFence(
                lease.resource_id, lease.mission_id, lease.holder_id,
                lease.fence, _utc_text(expires),
            )

    def start_task(self, task_id: str, lease: LeaseFence) -> dict[str, Any]:
        with self._transaction() as conn:
            self._validate_lease(conn, lease)
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None or row["mission_id"] != lease.mission_id:
                raise InvalidTransition("task and lease mission mismatch")
            if row["state"] not in {"QUEUED", "RETRY_WAIT"}:
                raise InvalidTransition("task is not startable")
            if row["state"] == "RETRY_WAIT" and row["retry_at"]:
                if _parse_utc(row["retry_at"]) > self._now():
                    raise InvalidTransition("retry backoff has not elapsed")
            mission = self._mission(conn, row["mission_id"])
            if mission["cancel_requested"]:
                raise InvalidTransition("mission cancellation requested")
            attempt = row["attempt"] + 1
            conn.execute(
                """
                UPDATE tasks
                   SET state='RUNNING',attempt=?,retry_at=NULL,
                       lease_resource_id=?,lease_holder_id=?,lease_fence=?,started_at=?
                 WHERE task_id=?
                """,
                (
                    attempt, lease.resource_id, lease.holder_id, lease.fence,
                    _utc_text(self._now()), task_id,
                ),
            )
            self._append_event(
                conn,
                row["mission_id"],
                "TASK_STARTED",
                {
                    "taskId": task_id,
                    "attempt": attempt,
                    "resourceId": lease.resource_id,
                    "holderId": lease.holder_id,
                    "fence": lease.fence,
                },
                f"task-start:{task_id}:{attempt}",
            )
            return dict(
                conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            )

    def recover_orphaned_tasks(
        self,
        mission_id: str,
        *,
        idempotency_key: str,
        base_backoff_seconds: int = 1,
    ) -> dict[str, Any]:
        """Fence and reschedule RUNNING tasks whose persisted worker lease was lost."""
        if not idempotency_key:
            raise DurableRuntimeError("recovery idempotency key is required")
        if not 1 <= base_backoff_seconds <= 300:
            raise DurableRuntimeError("recovery backoff must be from one to 300 seconds")
        with self._transaction() as conn:
            self._mission(conn, mission_id)
            duplicate = conn.execute(
                "SELECT * FROM events WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if duplicate is not None:
                if (
                    duplicate["mission_id"] != mission_id
                    or duplicate["event_type"] != "ORPHANED_TASKS_RECOVERED"
                ):
                    raise IdempotencyConflict(
                        "recovery idempotency key reused for different event"
                    )
                return json.loads(duplicate["payload_json"])

            recovered: list[dict[str, Any]] = []
            rows = conn.execute(
                "SELECT * FROM tasks WHERE mission_id=? AND state='RUNNING' "
                "ORDER BY task_id",
                (mission_id,),
            ).fetchall()
            now = self._now()
            for row in rows:
                lease = None
                if row["lease_resource_id"]:
                    lease = conn.execute(
                        "SELECT * FROM leases WHERE resource_id=?",
                        (row["lease_resource_id"],),
                    ).fetchone()
                lease_is_current = bool(
                    lease is not None
                    and lease["mission_id"] == mission_id
                    and lease["holder_id"] == row["lease_holder_id"]
                    and lease["fence"] == row["lease_fence"]
                    and lease["state"] == "ACTIVE"
                    and _parse_utc(lease["expires_at"]) > now
                )
                if lease_is_current:
                    continue

                error = "WORKER_LEASE_LOST"
                if row["attempt"] < row["max_attempts"]:
                    delay = min(
                        base_backoff_seconds * (2 ** max(0, row["attempt"] - 1)),
                        300,
                    )
                    retry_at = _utc_text(now + timedelta(seconds=delay))
                    outcome = "RETRY_WAIT"
                else:
                    retry_at = None
                    outcome = "DEAD_LETTER"
                conn.execute(
                    "UPDATE tasks SET state=?,retry_at=?,last_error=? WHERE task_id=?",
                    (outcome, retry_at, error, row["task_id"]),
                )
                if outcome == "DEAD_LETTER":
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO dead_letters(
                          task_id,mission_id,error,failed_at,attempt
                        ) VALUES(?,?,?,?,?)
                        """,
                        (
                            row["task_id"], mission_id, error, _utc_text(now),
                            row["attempt"],
                        ),
                    )
                recovered.append(
                    {
                        "taskId": row["task_id"],
                        "attempt": row["attempt"],
                        "leaseResourceId": row["lease_resource_id"],
                        "leaseHolderId": row["lease_holder_id"],
                        "leaseFence": row["lease_fence"],
                        "outcome": outcome,
                        "retryAt": retry_at,
                    }
                )

            receipt = {
                "contract": "SOVARA_ORPHAN_RECOVERY_RECEIPT_V1",
                "missionId": mission_id,
                "observedAt": _utc_text(now),
                "recoveredCount": len(recovered),
                "retryWaitCount": sum(
                    item["outcome"] == "RETRY_WAIT" for item in recovered
                ),
                "deadLetterCount": sum(
                    item["outcome"] == "DEAD_LETTER" for item in recovered
                ),
                "tasks": recovered,
            }
            self._append_event(
                conn,
                mission_id,
                "ORPHANED_TASKS_RECOVERED",
                receipt,
                idempotency_key,
            )
            return receipt

    def complete_task(
        self,
        task_id: str,
        result: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        result_json = _json(dict(result))
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise InvalidTransition("unknown task")
            if row["state"] == "COMPLETED":
                if row["result_json"] != result_json:
                    raise IdempotencyConflict("completion result changed")
                return dict(row)
            if row["state"] != "RUNNING":
                raise InvalidTransition("only running tasks can complete")
            event = self._append_event(
                conn,
                row["mission_id"],
                "TASK_COMPLETED",
                {"taskId": task_id, "resultSha256": canonical_sha256(result)},
                idempotency_key,
            )
            conn.execute(
                """
                UPDATE tasks
                   SET state='COMPLETED',result_json=?,last_error=NULL,
                       completed_seq=?
                 WHERE task_id=?
                """,
                (result_json, event["seq"], task_id),
            )
            return dict(
                conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            )

    def fail_task(
        self,
        task_id: str,
        error: str,
        *,
        retryable: bool,
        base_backoff_seconds: int = 1,
    ) -> dict[str, Any]:
        if not error:
            raise DurableRuntimeError("failure requires an error")
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None or row["state"] != "RUNNING":
                raise InvalidTransition("only running tasks can fail")
            if retryable and row["attempt"] < row["max_attempts"]:
                delay = min(base_backoff_seconds * (2 ** max(0, row["attempt"] - 1)), 300)
                retry_at = _utc_text(self._now() + timedelta(seconds=delay))
                state = "RETRY_WAIT"
            else:
                retry_at = None
                state = "DEAD_LETTER"
            conn.execute(
                "UPDATE tasks SET state=?,retry_at=?,last_error=? WHERE task_id=?",
                (state, retry_at, error, task_id),
            )
            self._append_event(
                conn,
                row["mission_id"],
                "TASK_RETRY_SCHEDULED" if state == "RETRY_WAIT" else "TASK_DEAD_LETTERED",
                {
                    "taskId": task_id,
                    "attempt": row["attempt"],
                    "retryable": retryable,
                    "retryAt": retry_at,
                    "errorSha256": hashlib.sha256(error.encode()).hexdigest(),
                },
                f"task-fail:{task_id}:{row['attempt']}",
            )
            if state == "DEAD_LETTER":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO dead_letters(
                      task_id,mission_id,error,failed_at,attempt
                    ) VALUES(?,?,?,?,?)
                    """,
                    (
                        task_id, row["mission_id"], error, _utc_text(self._now()),
                        row["attempt"],
                    ),
                )
            return dict(
                conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            )

    def due_tasks(self, mission_id: str) -> list[dict[str, Any]]:
        now = _utc_text(self._now())
        rows = self._conn.execute(
            """
            SELECT * FROM tasks
             WHERE mission_id=?
               AND (state='QUEUED' OR (state='RETRY_WAIT' AND retry_at<=?))
             ORDER BY task_id
            """,
            (mission_id, now),
        ).fetchall()
        return [dict(row) for row in rows]

    def request_cancel(self, mission_id: str, *, reason: str) -> dict[str, Any]:
        if not reason:
            raise DurableRuntimeError("cancellation requires a reason")
        with self._transaction() as conn:
            mission = self._mission(conn, mission_id)
            if mission["cancel_requested"]:
                return self.mission_snapshot(mission_id, connection=conn)
            conn.execute(
                """
                UPDATE missions
                   SET cancel_requested=1,state='CANCEL_REQUESTED'
                 WHERE mission_id=?
                """,
                (mission_id,),
            )
            conn.execute(
                "UPDATE tasks SET state='CANCELLED' "
                "WHERE mission_id=? AND state IN ('QUEUED','RETRY_WAIT')",
                (mission_id,),
            )
            self._append_event(
                conn,
                mission_id,
                "MISSION_CANCEL_REQUESTED",
                {"reasonSha256": hashlib.sha256(reason.encode()).hexdigest()},
                f"mission-cancel:{mission_id}",
            )
            return self.mission_snapshot(mission_id, connection=conn)

    def compensate(
        self,
        mission_id: str,
        executor: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM tasks
             WHERE mission_id=? AND state='COMPLETED' AND compensation_json IS NOT NULL
             ORDER BY completed_seq DESC
            """,
            (mission_id,),
        ).fetchall()
        outcomes: list[dict[str, Any]] = []
        with self._transaction() as conn:
            conn.execute(
                "UPDATE missions SET state='COMPENSATING' WHERE mission_id=?",
                (mission_id,),
            )
        for row in rows:
            compensation = json.loads(row["compensation_json"])
            try:
                result = dict(executor(row["task_id"], compensation))
                reject_secret_material(result)
            except Exception as exc:
                with self._transaction() as conn:
                    conn.execute(
                        "UPDATE tasks SET state='COMPENSATION_FAILED',last_error=? "
                        "WHERE task_id=?",
                        (str(exc), row["task_id"]),
                    )
                    conn.execute(
                        "UPDATE missions SET state='COMPENSATION_FAILED' WHERE mission_id=?",
                        (mission_id,),
                    )
                    self._append_event(
                        conn,
                        mission_id,
                        "COMPENSATION_FAILED",
                        {
                            "taskId": row["task_id"],
                            "errorSha256": hashlib.sha256(str(exc).encode()).hexdigest(),
                        },
                        f"compensation-failed:{row['task_id']}",
                    )
                raise DurableRuntimeError("compensation failed") from exc
            with self._transaction() as conn:
                conn.execute(
                    "UPDATE tasks SET state='COMPENSATED',result_json=? WHERE task_id=?",
                    (_json(result), row["task_id"]),
                )
                self._append_event(
                    conn,
                    mission_id,
                    "TASK_COMPENSATED",
                    {
                        "taskId": row["task_id"],
                        "resultSha256": canonical_sha256(result),
                    },
                    f"compensated:{row['task_id']}",
                )
            outcomes.append({"taskId": row["task_id"], "result": result})
        with self._transaction() as conn:
            conn.execute(
                "UPDATE missions SET state='COMPENSATED' WHERE mission_id=?",
                (mission_id,),
            )
            self._append_event(
                conn,
                mission_id,
                "MISSION_COMPENSATED",
                {"taskCount": len(outcomes)},
                f"mission-compensated:{mission_id}",
            )
        return outcomes

    def complete_mission(
        self,
        mission_id: str,
        result: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        result_json = _json(dict(result))
        with self._transaction() as conn:
            mission = self._mission(conn, mission_id)
            if mission["state"] == "COMPLETED":
                if mission["result_json"] != result_json:
                    raise IdempotencyConflict("mission completion changed")
                return self.mission_snapshot(mission_id, connection=conn)
            unfinished = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE mission_id=? "
                "AND state NOT IN ('COMPLETED','COMPENSATED','CANCELLED')",
                (mission_id,),
            ).fetchone()[0]
            if unfinished:
                raise InvalidTransition("mission has unfinished tasks")
            self._append_event(
                conn,
                mission_id,
                "MISSION_COMPLETED",
                {"resultSha256": canonical_sha256(result)},
                idempotency_key,
            )
            conn.execute(
                "UPDATE missions SET state='COMPLETED',result_json=? WHERE mission_id=?",
                (result_json, mission_id),
            )
            return self.mission_snapshot(mission_id, connection=conn)

    def verify_event_chain(self, mission_id: str) -> dict[str, Any]:
        mission = self._mission(self._conn, mission_id)
        rows = self._conn.execute(
            "SELECT * FROM events WHERE mission_id=? ORDER BY seq", (mission_id,)
        ).fetchall()
        prev_hash = ""
        for row in rows:
            binding = {
                "missionId": row["mission_id"],
                "eventType": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "occurredAt": row["occurred_at"],
                "prevHash": row["prev_hash"],
                "idempotencyKey": row["idempotency_key"],
            }
            if row["prev_hash"] != prev_hash:
                raise IntegrityViolation(f"event chain predecessor mismatch at {row['seq']}")
            if canonical_sha256(binding) != row["event_hash"]:
                raise IntegrityViolation(f"event hash mismatch at {row['seq']}")
            prev_hash = row["event_hash"]
        if len(rows) != mission["event_count"] or prev_hash != mission["event_head_hash"]:
            raise IntegrityViolation("mission event head or count mismatch")
        return {
            "valid": True,
            "missionId": mission_id,
            "eventCount": len(rows),
            "headSha256": prev_hash,
        }

    def checkpoint(self, mission_id: str) -> dict[str, Any]:
        chain = self.verify_event_chain(mission_id)
        state = self.mission_snapshot(mission_id)
        state_json = _json(state)
        with self._transaction() as conn:
            version = conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM checkpoints WHERE mission_id=?",
                (mission_id,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO checkpoints(
                  mission_id,version,event_seq,state_json,state_sha256,created_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    mission_id, version, chain["eventCount"], state_json,
                    canonical_sha256(state), _utc_text(self._now()),
                ),
            )
            return {
                "missionId": mission_id,
                "version": version,
                "eventCount": chain["eventCount"],
                "stateSha256": canonical_sha256(state),
            }

    def replay(self, mission_id: str) -> dict[str, Any]:
        chain = self.verify_event_chain(mission_id)
        events = self._conn.execute(
            "SELECT seq,event_type,payload_json,event_hash FROM events "
            "WHERE mission_id=? ORDER BY seq",
            (mission_id,),
        ).fetchall()
        return {
            "contract": RUNTIME_CONTRACT,
            "mission": self.mission_snapshot(mission_id),
            "chain": chain,
            "events": [
                {
                    "seq": row["seq"],
                    "type": row["event_type"],
                    "payload": json.loads(row["payload_json"]),
                    "eventSha256": row["event_hash"],
                }
                for row in events
            ],
        }

    def record_span(
        self,
        mission_id: str,
        operation: str,
        *,
        kind: str,
        status: str,
        attributes: Mapping[str, Any] | None = None,
        input_value: Any | None = None,
        output_value: Any | None = None,
        parent_span_id: str | None = None,
    ) -> dict[str, Any]:
        attributes = dict(attributes or {})
        reject_secret_material(attributes)
        started = _utc_text(self._now())
        binding = {
            "missionId": mission_id,
            "operation": operation,
            "kind": kind,
            "attributes": attributes,
            "startedAt": started,
        }
        span_id = "SPAN-" + canonical_sha256(binding)[:24]
        input_hash = canonical_sha256(input_value) if input_value is not None else None
        output_hash = canonical_sha256(output_value) if output_value is not None else None
        with self._transaction() as conn:
            self._mission(conn, mission_id)
            conn.execute(
                """
                INSERT OR REPLACE INTO spans(
                  span_id,mission_id,parent_span_id,operation,kind,status,
                  attributes_json,input_sha256,output_sha256,started_at,ended_at,
                  sensitive_content_captured
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,0)
                """,
                (
                    span_id, mission_id, parent_span_id, operation, kind, status,
                    _json(attributes), input_hash, output_hash, started,
                    _utc_text(self._now()),
                ),
            )
        return {
            "spanId": span_id,
            "operation": operation,
            "kind": kind,
            "status": status,
            "inputSha256": input_hash,
            "outputSha256": output_hash,
            "sensitiveContentCaptured": False,
        }

    def integrity_check(self) -> str:
        rows = self._conn.execute("PRAGMA integrity_check").fetchall()
        result = "\n".join(str(row[0]) for row in rows)
        if result != "ok":
            raise IntegrityViolation(result)
        return result

    def backup(self, destination: str | Path) -> BackupReceipt:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._conn.execute("PRAGMA wal_checkpoint(FULL)")
        target = sqlite3.connect(destination)
        try:
            self._conn.backup(target)
        finally:
            target.close()
        payload = destination.read_bytes()
        check = sqlite3.connect(destination)
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            check.close()
        if integrity != "ok":
            raise IntegrityViolation("backup integrity check failed")
        return BackupReceipt(
            contract="SOVARA_SQLITE_BACKUP_RECEIPT_V1",
            source_path=str(self.path),
            backup_path=str(destination),
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
            integrity=integrity,
        )

    @staticmethod
    def restore(source: str | Path, destination: str | Path) -> BackupReceipt:
        source = Path(source)
        destination = Path(destination)
        if not source.is_file():
            raise DurableRuntimeError("backup source missing")
        destination.parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(source)
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
        runtime = DurableMissionRuntime(destination)
        try:
            integrity = runtime.integrity_check()
        finally:
            runtime.close()
        payload = destination.read_bytes()
        return BackupReceipt(
            contract="SOVARA_SQLITE_RESTORE_RECEIPT_V1",
            source_path=str(source),
            backup_path=str(destination),
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
            integrity=integrity,
        )


__all__ = [
    "RUNTIME_CONTRACT", "BackupReceipt", "DurableMissionRuntime",
    "DurableRuntimeError", "IdempotencyConflict", "IntegrityViolation",
    "InvalidTransition", "LeaseConflict", "LeaseFence",
]
