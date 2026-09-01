from __future__ import annotations

"""Bubbles–CFBE Ω non-interrupting multi-stream continuity fabric.

This is a durable command-stream arbiter, not a background executor.

A new owner command is additive by default and never silently cancels older
unfinished work. Existing work is resumed from durable lane state on the next
available execution cycle. Only explicit pause/cancel/replace operations may
stop another command stream.

CFBE remains authoritative for work selection/ranking. Bubbles remains
responsible for bounded lane execution. This module persists command/lane
continuity, leases and host-yield semantics; it never claims ChatGPT continues
running after the host ends a turn.
"""

import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA = "BUBBLES_CFBE_NONINTERRUPTING_MULTISTREAM_V1"


class CommandState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class ContinuityLaneState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    HOLD_READBACK = "HOLD_READBACK"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PathRole(str, Enum):
    PRIMARY = "PRIMARY"
    CHALLENGER = "CHALLENGER"
    FALLBACK = "FALLBACK"


class EffectClass(str, Enum):
    NO_EFFECT = "NO_EFFECT"
    REVERSIBLE_INTERNAL = "REVERSIBLE_INTERNAL"
    REVERSIBLE_EXTERNAL = "REVERSIBLE_EXTERNAL"
    HIGH_CONSEQUENCE = "HIGH_CONSEQUENCE"


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    command_id: str
    mission_id: str
    intent_sha256: str
    priority: float = 50.0
    source_ref: str = ""

    def validate(self) -> None:
        if not self.command_id.strip():
            raise ValueError("COMMAND_ID_REQUIRED")
        if not self.mission_id.strip():
            raise ValueError("MISSION_ID_REQUIRED")
        if len(self.intent_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.intent_sha256.lower()
        ):
            raise ValueError("INTENT_SHA256_REQUIRED")
        if not 0.0 <= float(self.priority) <= 100.0:
            raise ValueError("COMMAND_PRIORITY_OUT_OF_RANGE")


@dataclass(frozen=True, slots=True)
class ContinuityLaneSpec:
    lane_id: str
    command_id: str
    mission_id: str
    path_id: str
    path_role: PathRole = PathRole.PRIMARY
    dependencies: tuple[str, ...] = ()
    concurrency_group: str = ""
    effect_class: EffectClass = EffectClass.NO_EFFECT
    effect_permit_ref: str = ""
    checkpoint_ref: str = ""
    priority_delta: float = 0.0

    def validate(self) -> None:
        for label, value in (
            ("LANE_ID", self.lane_id),
            ("COMMAND_ID", self.command_id),
            ("MISSION_ID", self.mission_id),
            ("PATH_ID", self.path_id),
        ):
            if not str(value).strip():
                raise ValueError(f"{label}_REQUIRED")


@dataclass(frozen=True, slots=True)
class LaneLease:
    lane_id: str
    command_id: str
    mission_id: str
    path_id: str
    path_role: str
    effect_class: str
    lease_owner: str
    lease_expires_at: float
    checkpoint_ref: str
    attempt: int


@dataclass(frozen=True, slots=True)
class ContinuityReceipt:
    schema: str
    active_commands: int
    paused_commands: int
    unfinished_lanes: int
    running_lanes: int
    hold_readback_lanes: int
    host_background_execution_claimed: bool
    new_command_cancels_prior_work_by_default: bool
    explicit_control_required_for_pause_cancel_replace: bool


def intent_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_tuple(values: Iterable[str]) -> str:
    return json.dumps(tuple(values), separators=(",", ":"))


class MultistreamContinuityFabric:
    """Durable command-stream continuity and bounded wave leasing.

    Key invariant: ``add_command(new)`` never changes older commands or lanes.

    Host interruption semantics:
    - stale RUNNING no-effect/internal lanes -> READY from checkpoint;
    - stale RUNNING external/high-consequence lanes -> HOLD_READBACK so a
      possible prior effect is never repeated without semantic readback.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._bootstrap()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _bootstrap(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS continuity_commands(
                command_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                intent_sha256 TEXT NOT NULL,
                priority REAL NOT NULL,
                source_ref TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS continuity_lanes(
                lane_id TEXT PRIMARY KEY,
                command_id TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                path_id TEXT NOT NULL,
                path_role TEXT NOT NULL,
                dependencies_json TEXT NOT NULL,
                concurrency_group TEXT NOT NULL,
                effect_class TEXT NOT NULL,
                effect_permit_ref TEXT NOT NULL,
                state TEXT NOT NULL,
                checkpoint_ref TEXT NOT NULL,
                result_ref TEXT NOT NULL,
                error TEXT NOT NULL,
                priority_delta REAL NOT NULL,
                attempt INTEGER NOT NULL,
                lease_owner TEXT,
                lease_expires_at REAL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(command_id) REFERENCES continuity_commands(command_id)
            );
            CREATE INDEX IF NOT EXISTS idx_continuity_command_state
                ON continuity_commands(state, priority, created_at);
            CREATE INDEX IF NOT EXISTS idx_continuity_lane_state
                ON continuity_lanes(state, command_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_continuity_lane_lease
                ON continuity_lanes(state, lease_expires_at);
            """
        )
        conn.close()

    def add_command(
        self,
        command: CommandEnvelope,
        lanes: Sequence[ContinuityLaneSpec],
        *,
        now: float | None = None,
    ) -> dict[str, object]:
        """Add one independent stream without cancelling older work."""
        command.validate()
        when = time.time() if now is None else float(now)
        lane_ids = [lane.lane_id for lane in lanes]
        if len(lane_ids) != len(set(lane_ids)):
            raise ValueError("DUPLICATE_LANE_ID_IN_COMMAND")
        for lane in lanes:
            lane.validate()
            if lane.command_id != command.command_id or lane.mission_id != command.mission_id:
                raise ValueError("LANE_COMMAND_MISSION_IDENTITY_MISMATCH")

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                "SELECT * FROM continuity_commands WHERE command_id=?",
                (command.command_id,),
            ).fetchone()
            if prior:
                same = (
                    prior["mission_id"] == command.mission_id
                    and prior["intent_sha256"] == command.intent_sha256.lower()
                )
                if not same:
                    raise ValueError("COMMAND_IDEMPOTENCY_CONFLICT")
                conn.execute("COMMIT")
                return {
                    "state": "IDEMPOTENT_COMMAND_REUSE",
                    "command_id": command.command_id,
                    "prior_work_cancelled": False,
                }

            conn.execute(
                """INSERT INTO continuity_commands
                   (command_id,mission_id,intent_sha256,priority,source_ref,state,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    command.command_id,
                    command.mission_id,
                    command.intent_sha256.lower(),
                    float(command.priority),
                    command.source_ref,
                    CommandState.ACTIVE.value,
                    when,
                    when,
                ),
            )
            for lane in lanes:
                missing = [
                    dep
                    for dep in lane.dependencies
                    if dep not in lane_ids
                    and conn.execute(
                        "SELECT 1 FROM continuity_lanes WHERE lane_id=?", (dep,)
                    ).fetchone()
                    is None
                ]
                if missing:
                    raise ValueError(
                        f"UNKNOWN_LANE_DEPENDENCIES:{lane.lane_id}:{','.join(missing)}"
                    )
                conn.execute(
                    """INSERT INTO continuity_lanes
                       (lane_id,command_id,mission_id,path_id,path_role,dependencies_json,
                        concurrency_group,effect_class,effect_permit_ref,state,checkpoint_ref,
                        result_ref,error,priority_delta,attempt,lease_owner,lease_expires_at,
                        created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        lane.lane_id,
                        lane.command_id,
                        lane.mission_id,
                        lane.path_id,
                        lane.path_role.value,
                        _json_tuple(lane.dependencies),
                        lane.concurrency_group,
                        lane.effect_class.value,
                        lane.effect_permit_ref,
                        ContinuityLaneState.READY.value,
                        lane.checkpoint_ref,
                        "",
                        "",
                        float(lane.priority_delta),
                        0,
                        None,
                        None,
                        when,
                        when,
                    ),
                )
            conn.execute("COMMIT")
            return {
                "state": "COMMAND_STREAM_ADDED",
                "command_id": command.command_id,
                "lane_count": len(lanes),
                "prior_work_cancelled": False,
            }
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    @staticmethod
    def _require_explicit(explicit: bool) -> None:
        if not explicit:
            raise PermissionError("EXPLICIT_OWNER_CONTROL_REQUIRED")

    def pause_command(self, command_id: str, *, explicit: bool = False, now: float | None = None) -> None:
        self._require_explicit(explicit)
        self._set_command_state(command_id, CommandState.PAUSED, now=now)

    def resume_command(self, command_id: str, *, explicit: bool = False, now: float | None = None) -> None:
        self._require_explicit(explicit)
        self._set_command_state(command_id, CommandState.ACTIVE, now=now)

    def cancel_command(self, command_id: str, *, explicit: bool = False, now: float | None = None) -> None:
        """Cancel future work without erasing uncertain in-flight effects."""
        self._require_explicit(explicit)
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT state FROM continuity_commands WHERE command_id=?", (command_id,)
            ).fetchone()
            if row is None:
                raise KeyError(command_id)
            conn.execute(
                "UPDATE continuity_commands SET state=?,updated_at=? WHERE command_id=?",
                (CommandState.CANCELLED.value, when, command_id),
            )
            lanes = conn.execute(
                """SELECT lane_id,state,effect_class FROM continuity_lanes
                   WHERE command_id=? AND state NOT IN (?,?)""",
                (
                    command_id,
                    ContinuityLaneState.COMPLETE.value,
                    ContinuityLaneState.CANCELLED.value,
                ),
            ).fetchall()
            for lane in lanes:
                effect = EffectClass(lane["effect_class"])
                uncertain_effect = lane["state"] == ContinuityLaneState.RUNNING.value and effect in {
                    EffectClass.REVERSIBLE_EXTERNAL,
                    EffectClass.HIGH_CONSEQUENCE,
                }
                preserve_readback = lane["state"] == ContinuityLaneState.HOLD_READBACK.value
                next_state = (
                    ContinuityLaneState.HOLD_READBACK.value
                    if uncertain_effect or preserve_readback
                    else ContinuityLaneState.CANCELLED.value
                )
                conn.execute(
                    """UPDATE continuity_lanes
                       SET state=?,lease_owner=NULL,lease_expires_at=NULL,updated_at=?
                       WHERE lane_id=?""",
                    (next_state, when, lane["lane_id"]),
                )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    def replace_command(
        self,
        target_command_id: str,
        replacement: CommandEnvelope,
        lanes: Sequence[ContinuityLaneSpec],
        *,
        explicit: bool = False,
        now: float | None = None,
    ) -> dict[str, object]:
        self._require_explicit(explicit)
        self.cancel_command(target_command_id, explicit=True, now=now)
        result = self.add_command(replacement, lanes, now=now)
        return {
            **result,
            "state": "COMMAND_STREAM_REPLACED",
            "replaced_command_id": target_command_id,
        }

    def _set_command_state(
        self, command_id: str, state: CommandState, *, now: float | None = None
    ) -> None:
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            cursor = conn.execute(
                "UPDATE continuity_commands SET state=?,updated_at=? WHERE command_id=?",
                (state.value, when, command_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(command_id)
        finally:
            conn.close()

    def reconcile_after_host_interrupt(self, *, now: float | None = None) -> dict[str, tuple[str, ...]]:
        """Recover expired leases without pretending the host kept executing."""
        when = time.time() if now is None else float(now)
        conn = self._connect()
        recovered: list[str] = []
        readback_hold: list[str] = []
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """SELECT lane_id,effect_class FROM continuity_lanes
                   WHERE state=? AND lease_expires_at IS NOT NULL AND lease_expires_at<=?""",
                (ContinuityLaneState.RUNNING.value, when),
            ).fetchall()
            for row in rows:
                effect = EffectClass(row["effect_class"])
                if effect in {EffectClass.NO_EFFECT, EffectClass.REVERSIBLE_INTERNAL}:
                    state = ContinuityLaneState.READY.value
                    recovered.append(row["lane_id"])
                else:
                    state = ContinuityLaneState.HOLD_READBACK.value
                    readback_hold.append(row["lane_id"])
                conn.execute(
                    """UPDATE continuity_lanes SET state=?,lease_owner=NULL,
                       lease_expires_at=NULL,updated_at=? WHERE lane_id=?""",
                    (state, when, row["lane_id"]),
                )
            self._reconcile_dependency_blocks(conn, when)
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
        return {
            "recovered_ready": tuple(sorted(recovered)),
            "effect_readback_required": tuple(sorted(readback_hold)),
        }

    def _reconcile_dependency_blocks(self, conn: sqlite3.Connection, when: float) -> None:
        rows = conn.execute(
            "SELECT lane_id,dependencies_json,state FROM continuity_lanes WHERE state IN (?,?)",
            (ContinuityLaneState.READY.value, ContinuityLaneState.WAITING.value),
        ).fetchall()
        terminal_bad = {
            ContinuityLaneState.FAILED.value,
            ContinuityLaneState.BLOCKED.value,
            ContinuityLaneState.CANCELLED.value,
        }
        for row in rows:
            deps = tuple(json.loads(row["dependencies_json"]))
            if not deps:
                continue
            placeholders = ",".join("?" for _ in deps)
            dep_rows = conn.execute(
                f"SELECT lane_id,state FROM continuity_lanes WHERE lane_id IN ({placeholders})",
                deps,
            ).fetchall()
            dep_states = {item["lane_id"]: item["state"] for item in dep_rows}
            if any(dep_states.get(dep) in terminal_bad for dep in deps):
                conn.execute(
                    "UPDATE continuity_lanes SET state=?,error=?,updated_at=? WHERE lane_id=?",
                    (
                        ContinuityLaneState.BLOCKED.value,
                        "DEPENDENCY_TERMINAL_FAILURE",
                        when,
                        row["lane_id"],
                    ),
                )

    @staticmethod
    def _deps_complete(conn: sqlite3.Connection, dependencies_json: str) -> bool:
        deps = tuple(json.loads(dependencies_json))
        if not deps:
            return True
        placeholders = ",".join("?" for _ in deps)
        rows = conn.execute(
            f"SELECT lane_id,state FROM continuity_lanes WHERE lane_id IN ({placeholders})",
            deps,
        ).fetchall()
        states = {row["lane_id"]: row["state"] for row in rows}
        return len(states) == len(deps) and all(
            states[dep] == ContinuityLaneState.COMPLETE.value for dep in deps
        )

    def lease_wave(
        self,
        *,
        worker_id: str,
        max_lanes: int = 4,
        max_per_command: int = 2,
        lease_seconds: float = 60.0,
        now: float | None = None,
        aging_points_per_minute: float = 0.25,
    ) -> tuple[LaneLease, ...]:
        if not worker_id.strip():
            raise ValueError("WORKER_ID_REQUIRED")
        if max_lanes <= 0 or max_per_command <= 0 or lease_seconds <= 0:
            raise ValueError("LEASE_WAVE_LIMITS_MUST_BE_POSITIVE")
        when = time.time() if now is None else float(now)
        self.reconcile_after_host_interrupt(now=when)

        conn = self._connect()
        selected: list[sqlite3.Row] = []
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._reconcile_dependency_blocks(conn, when)
            rows = conn.execute(
                """SELECT l.*,c.priority AS command_priority
                   FROM continuity_lanes l
                   JOIN continuity_commands c ON c.command_id=l.command_id
                   WHERE l.state=? AND c.state=?""",
                (ContinuityLaneState.READY.value, CommandState.ACTIVE.value),
            ).fetchall()

            candidates = []
            for row in rows:
                if not self._deps_complete(conn, row["dependencies_json"]):
                    continue
                effect = EffectClass(row["effect_class"])
                if effect == EffectClass.HIGH_CONSEQUENCE:
                    continue
                if effect == EffectClass.REVERSIBLE_EXTERNAL and not row["effect_permit_ref"]:
                    continue
                age_minutes = max(0.0, (when - float(row["created_at"])) / 60.0)
                score = (
                    float(row["command_priority"])
                    + float(row["priority_delta"])
                    + min(20.0, age_minutes * float(aging_points_per_minute))
                )
                candidates.append((score, float(row["created_at"]), row))
            candidates.sort(key=lambda item: (-item[0], item[1], item[2]["lane_id"]))

            per_command: dict[str, int] = {}
            groups: set[str] = set()
            external_effect_selected = False
            while candidates and len(selected) < max_lanes:
                progressed = False
                for idx, (_, _, row) in enumerate(list(candidates)):
                    command_id = row["command_id"]
                    if per_command.get(command_id, 0) >= max_per_command:
                        continue
                    group = row["concurrency_group"]
                    if group and group in groups:
                        continue
                    effect = EffectClass(row["effect_class"])
                    if effect == EffectClass.REVERSIBLE_EXTERNAL and external_effect_selected:
                        continue
                    selected.append(row)
                    per_command[command_id] = per_command.get(command_id, 0) + 1
                    if group:
                        groups.add(group)
                    if effect == EffectClass.REVERSIBLE_EXTERNAL:
                        external_effect_selected = True
                    candidates.pop(idx)
                    progressed = True
                    break
                if not progressed:
                    break

            leases: list[LaneLease] = []
            for row in selected:
                attempt = int(row["attempt"]) + 1
                expires = when + lease_seconds
                conn.execute(
                    """UPDATE continuity_lanes SET state=?,attempt=?,lease_owner=?,
                       lease_expires_at=?,updated_at=? WHERE lane_id=? AND state=?""",
                    (
                        ContinuityLaneState.RUNNING.value,
                        attempt,
                        worker_id,
                        expires,
                        when,
                        row["lane_id"],
                        ContinuityLaneState.READY.value,
                    ),
                )
                leases.append(
                    LaneLease(
                        lane_id=row["lane_id"],
                        command_id=row["command_id"],
                        mission_id=row["mission_id"],
                        path_id=row["path_id"],
                        path_role=row["path_role"],
                        effect_class=row["effect_class"],
                        lease_owner=worker_id,
                        lease_expires_at=expires,
                        checkpoint_ref=row["checkpoint_ref"],
                        attempt=attempt,
                    )
                )
            conn.execute("COMMIT")
            return tuple(leases)
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    def checkpoint_lane(
        self,
        lane_id: str,
        checkpoint_ref: str,
        *,
        worker_id: str | None = None,
        extend_lease_seconds: float | None = None,
        now: float | None = None,
    ) -> None:
        if not checkpoint_ref.strip():
            raise ValueError("CHECKPOINT_REF_REQUIRED")
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT lease_owner,lease_expires_at FROM continuity_lanes WHERE lane_id=?",
                (lane_id,),
            ).fetchone()
            if row is None:
                raise KeyError(lane_id)
            if worker_id is not None and row["lease_owner"] not in {None, worker_id}:
                raise PermissionError("LANE_LEASE_OWNER_MISMATCH")
            expires = row["lease_expires_at"]
            if extend_lease_seconds is not None:
                if extend_lease_seconds <= 0:
                    raise ValueError("LEASE_EXTENSION_MUST_BE_POSITIVE")
                expires = when + extend_lease_seconds
            conn.execute(
                "UPDATE continuity_lanes SET checkpoint_ref=?,lease_expires_at=?,updated_at=? WHERE lane_id=?",
                (checkpoint_ref, expires, when, lane_id),
            )
        finally:
            conn.close()

    def complete_lane(
        self,
        lane_id: str,
        *,
        result_ref: str,
        worker_id: str | None = None,
        now: float | None = None,
    ) -> None:
        if not result_ref.strip():
            raise ValueError("RESULT_REF_REQUIRED")
        self._finish_lane(
            lane_id,
            ContinuityLaneState.COMPLETE,
            result_ref=result_ref,
            error="",
            worker_id=worker_id,
            now=now,
        )
        self._complete_empty_commands(now=now)

    def fail_lane(
        self,
        lane_id: str,
        *,
        error: str,
        worker_id: str | None = None,
        now: float | None = None,
    ) -> None:
        self._finish_lane(
            lane_id,
            ContinuityLaneState.FAILED,
            result_ref="",
            error=error or "LANE_FAILED",
            worker_id=worker_id,
            now=now,
        )

    def _finish_lane(
        self,
        lane_id: str,
        state: ContinuityLaneState,
        *,
        result_ref: str,
        error: str,
        worker_id: str | None,
        now: float | None,
    ) -> None:
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT lease_owner FROM continuity_lanes WHERE lane_id=?", (lane_id,)
            ).fetchone()
            if row is None:
                raise KeyError(lane_id)
            if worker_id is not None and row["lease_owner"] not in {None, worker_id}:
                raise PermissionError("LANE_LEASE_OWNER_MISMATCH")
            conn.execute(
                """UPDATE continuity_lanes SET state=?,result_ref=?,error=?,
                   lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE lane_id=?""",
                (state.value, result_ref, error[:2000], when, lane_id),
            )
        finally:
            conn.close()

    def record_effect_readback(
        self,
        lane_id: str,
        *,
        effect_observed: bool,
        result_ref: str = "",
        now: float | None = None,
    ) -> None:
        """Resolve an uncertain effect lane after independent semantic readback."""
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT l.state,l.command_id,c.state AS command_state
                   FROM continuity_lanes l
                   JOIN continuity_commands c ON c.command_id=l.command_id
                   WHERE l.lane_id=?""",
                (lane_id,),
            ).fetchone()
            if row is None:
                raise KeyError(lane_id)
            if row["state"] != ContinuityLaneState.HOLD_READBACK.value:
                raise ValueError("LANE_NOT_HOLDING_FOR_READBACK")
            if effect_observed:
                if not result_ref.strip():
                    raise ValueError("OBSERVED_EFFECT_RESULT_REF_REQUIRED")
                new_state = ContinuityLaneState.COMPLETE.value
                new_result = result_ref
            elif row["command_state"] == CommandState.CANCELLED.value:
                new_state = ContinuityLaneState.CANCELLED.value
                new_result = ""
            else:
                new_state = ContinuityLaneState.READY.value
                new_result = ""
            conn.execute(
                """UPDATE continuity_lanes SET state=?,result_ref=?,error='',
                   lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE lane_id=?""",
                (new_state, new_result, when, lane_id),
            )
        finally:
            conn.close()
        self._complete_empty_commands(now=now)

    def yield_worker(
        self,
        worker_id: str,
        *,
        now: float | None = None,
    ) -> dict[str, tuple[str, ...]]:
        """Voluntarily yield before the host ends a turn."""
        when = time.time() if now is None else float(now)
        conn = self._connect()
        ready: list[str] = []
        holds: list[str] = []
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT lane_id,effect_class FROM continuity_lanes WHERE state=? AND lease_owner=?",
                (ContinuityLaneState.RUNNING.value, worker_id),
            ).fetchall()
            for row in rows:
                effect = EffectClass(row["effect_class"])
                if effect in {EffectClass.NO_EFFECT, EffectClass.REVERSIBLE_INTERNAL}:
                    state = ContinuityLaneState.READY.value
                    ready.append(row["lane_id"])
                else:
                    state = ContinuityLaneState.HOLD_READBACK.value
                    holds.append(row["lane_id"])
                conn.execute(
                    """UPDATE continuity_lanes SET state=?,lease_owner=NULL,
                       lease_expires_at=NULL,updated_at=? WHERE lane_id=?""",
                    (state, when, row["lane_id"]),
                )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
        return {
            "ready": tuple(sorted(ready)),
            "effect_readback_required": tuple(sorted(holds)),
        }

    def _complete_empty_commands(self, *, now: float | None = None) -> None:
        when = time.time() if now is None else float(now)
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT command_id FROM continuity_commands WHERE state=?",
                (CommandState.ACTIVE.value,),
            ).fetchall()
            for row in rows:
                unfinished = conn.execute(
                    """SELECT COUNT(*) AS n FROM continuity_lanes
                       WHERE command_id=? AND state NOT IN (?,?)""",
                    (
                        row["command_id"],
                        ContinuityLaneState.COMPLETE.value,
                        ContinuityLaneState.CANCELLED.value,
                    ),
                ).fetchone()["n"]
                if unfinished == 0:
                    conn.execute(
                        "UPDATE continuity_commands SET state=?,updated_at=? WHERE command_id=?",
                        (CommandState.COMPLETE.value, when, row["command_id"]),
                    )
        finally:
            conn.close()

    def snapshot(self) -> dict[str, object]:
        conn = self._connect()
        try:
            commands = [
                dict(row)
                for row in conn.execute(
                    """SELECT command_id,mission_id,intent_sha256,priority,source_ref,state,
                              created_at,updated_at
                       FROM continuity_commands ORDER BY created_at,command_id"""
                ).fetchall()
            ]
            lanes = []
            for row in conn.execute(
                """SELECT lane_id,command_id,mission_id,path_id,path_role,dependencies_json,
                          concurrency_group,effect_class,state,checkpoint_ref,result_ref,error,
                          priority_delta,attempt,lease_owner,lease_expires_at,created_at,updated_at
                   FROM continuity_lanes ORDER BY created_at,lane_id"""
            ).fetchall():
                item = dict(row)
                item["dependencies"] = tuple(json.loads(item.pop("dependencies_json")))
                lanes.append(item)
            return {
                "schema": SCHEMA,
                "commands": commands,
                "lanes": lanes,
                "truth_boundary": {
                    "host_background_execution_claimed": False,
                    "new_command_cancels_prior_work_by_default": False,
                    "explicit_control_required_for_pause_cancel_replace": True,
                },
            }
        finally:
            conn.close()

    def receipt(self) -> ContinuityReceipt:
        snapshot = self.snapshot()
        commands = snapshot["commands"]
        lanes = snapshot["lanes"]
        return ContinuityReceipt(
            schema=SCHEMA,
            active_commands=sum(item["state"] == CommandState.ACTIVE.value for item in commands),
            paused_commands=sum(item["state"] == CommandState.PAUSED.value for item in commands),
            unfinished_lanes=sum(
                item["state"]
                not in {ContinuityLaneState.COMPLETE.value, ContinuityLaneState.CANCELLED.value}
                for item in lanes
            ),
            running_lanes=sum(item["state"] == ContinuityLaneState.RUNNING.value for item in lanes),
            hold_readback_lanes=sum(
                item["state"] == ContinuityLaneState.HOLD_READBACK.value for item in lanes
            ),
            host_background_execution_claimed=False,
            new_command_cancels_prior_work_by_default=False,
            explicit_control_required_for_pause_cancel_replace=True,
        )

    def canonical_receipt_mapping(self) -> dict[str, object]:
        return asdict(self.receipt())
