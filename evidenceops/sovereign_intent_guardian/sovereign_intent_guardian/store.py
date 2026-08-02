"""Transactional SQLite control plane for the read-only guardian."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import math
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Any, Iterator, Mapping
import uuid

from .contracts import (
    AuditRequest,
    AuditResult,
    TaskState,
    ValidationError,
    canonical_json,
    parse_json_strict,
)
from .policy import evaluate
from .provider import is_persistable_advisory_record


SCHEMA_VERSION = "SIG-SQLITE-1.0"
HEALTH_CLASSIFICATION = "DURABLE_FOUNDATION_IMPLEMENTED_NOT_DEPLOYED"
WORKER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
SAFE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TRANSIENT_CODES = {
    "SQLITE_BUSY",
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMIT",
    "PROVIDER_5XX",
}
STOP_REASON_CODES = {
    "FORMATION_STOP",
    "SAFETY_STOP",
    "URGENT_STOP",
    "USER_STOP",
}
FAILURE_REASON_CODES = TRANSIENT_CODES | {
    "ADVISORY_RECEIPT_HASH_INVALID",
    "ADVISORY_RECEIPT_PROVIDER_ID_INVALID",
    "ADVISORY_RECEIPT_SCHEMA_INVALID",
    "ADVISORY_RECEIPT_TOO_LARGE",
    "ADVISORY_RECEIPT_VERDICT_INVALID",
    "AUTHORIZATION_FAILURE",
    "SEMANTIC_COMPLETION_REJECTED",
    "UNKNOWN_TERMINAL_FAILURE",
}
SECRET_KEY_RE = re.compile(
    r"(^|[_-])(api[_-]?key|password|passwd|private[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|signing[_-]?key|token|secret|credential|cookie|authorization|bearer|session)($|[_-])",
    re.I,
)
SECRET_VALUE_RE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAIza[0-9A-Za-z_-]{20,}\b|"
    r"\bgh[pousr]_[0-9A-Za-z]{20,}\b|\bsk-[0-9A-Za-z_-]{20,}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|\b(?:password|passwd|api[_ -]?key|token)\s*[:=]\s*\S+|"
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b)",
    re.I,
)


class StoreError(RuntimeError):
    pass


class IdempotencyConflict(StoreError):
    pass


class LeaseRejected(StoreError):
    pass


class StopLatched(StoreError):
    pass


def _contains_secret_like(value: Any, *, key: str = "") -> bool:
    if key and SECRET_KEY_RE.search(key):
        return True
    if isinstance(value, Mapping):
        return any(_contains_secret_like(item, key=str(name)) for name, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_like(item) for item in value)
    return isinstance(value, str) and (
        SECRET_VALUE_RE.search(value) is not None
        or SECRET_KEY_RE.search(value) is not None
    )


def _now(value: float | None = None) -> float:
    moment = time.time() if value is None else value
    if isinstance(moment, bool) or not isinstance(moment, (int, float)):
        raise ValidationError("timestamp_invalid")
    moment = float(moment)
    if not math.isfinite(moment) or moment < 0 or moment > time.time() + 300:
        raise ValidationError("timestamp_invalid")
    return moment


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GuardianStore:
    """Single-host durable queue with fencing and append-only hash chains."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        trusted_attestations: Mapping[str, str] | None = None,
        trusted_resume_records: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        self.path = Path(database_path)
        self.trusted_attestations = dict(trusted_attestations or {})
        if any(
            not isinstance(key, str)
            or not SAFE_REFERENCE_RE.fullmatch(key)
            or _contains_secret_like(key)
            or not isinstance(value, str)
            or not SHA256_RE.fullmatch(value)
            for key, value in self.trusted_attestations.items()
        ):
            raise ValidationError("trusted_attestation_registry_invalid")
        self.trusted_resume_records: dict[str, dict[str, Any]] = {}
        for record_hash, record in (trusted_resume_records or {}).items():
            subject = record.get("subject") if isinstance(record, Mapping) else None
            if (
                not isinstance(record_hash, str)
                or not SHA256_RE.fullmatch(record_hash)
                or not isinstance(record, Mapping)
                or set(record) != {"scope", "subject", "new_mission_version", "expected_generation"}
                or record.get("scope") not in {"GLOBAL", "MISSION", "REQUIREMENT"}
                or not isinstance(subject, str)
                or not SAFE_REFERENCE_RE.fullmatch(subject)
                or _contains_secret_like(subject)
                or isinstance(record.get("new_mission_version"), bool)
                or not isinstance(record.get("new_mission_version"), int)
                or record.get("new_mission_version") < 1
                or isinstance(record.get("expected_generation"), bool)
                or not isinstance(record.get("expected_generation"), int)
                or record.get("expected_generation") < 0
                or _sha(canonical_json(dict(record))) != record_hash
            ):
                raise ValidationError("trusted_resume_registry_invalid")
            self.trusted_resume_records[record_hash] = dict(record)

    def verify_continuity(self, request: AuditRequest) -> bool:
        """Require an exact binding hash from an external, configured verifier registry."""

        expected = self.trusted_attestations.get(request.trusted_attestation_id)
        return (
            expected is not None
            and expected == request.trusted_attestation_hash
            and expected == request.continuity_binding_hash
        )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS sig_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sig_control (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            generation INTEGER NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sig_stop_latches (
            latch_id TEXT PRIMARY KEY,
            scope TEXT NOT NULL CHECK (scope IN ('GLOBAL','MISSION','REQUIREMENT')),
            subject TEXT NOT NULL,
            mission_version INTEGER NOT NULL,
            active INTEGER NOT NULL CHECK (active IN (0,1)),
            generation INTEGER NOT NULL,
            reason_code TEXT NOT NULL,
            authority_record_hash TEXT,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sig_version_floors (
            floor_id TEXT PRIMARY KEY,
            scope TEXT NOT NULL CHECK (scope IN ('GLOBAL','MISSION','REQUIREMENT')),
            subject TEXT NOT NULL,
            minimum_mission_version INTEGER NOT NULL,
            generation INTEGER NOT NULL,
            authority_record_hash TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sig_tasks (
            task_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            request_json TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            mission_id TEXT NOT NULL,
            mission_version INTEGER NOT NULL,
            requirement_ids_json TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL,
            available_at REAL NOT NULL,
            lease_owner TEXT,
            worker_boot_id TEXT,
            lease_token_hash TEXT,
            fence_generation INTEGER NOT NULL DEFAULT 0,
            control_generation INTEGER,
            lease_expires_at REAL,
            result_json TEXT,
            result_hash TEXT,
            advisory_hash TEXT,
            cadence_output_count INTEGER,
            output_ledger_hash TEXT,
            last_error_code TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            completed_at REAL
        );
        CREATE INDEX IF NOT EXISTS sig_tasks_claim_idx
            ON sig_tasks(state, available_at, created_at);
        CREATE TABLE IF NOT EXISTS sig_workers (
            worker_id TEXT NOT NULL,
            boot_id TEXT NOT NULL,
            status TEXT NOT NULL,
            current_task_id TEXT,
            heartbeat_at REAL NOT NULL,
            PRIMARY KEY(worker_id, boot_id)
        );
        CREATE TABLE IF NOT EXISTS sig_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            task_id TEXT,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL UNIQUE,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sig_delivered_outputs (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            occurrence_id TEXT NOT NULL UNIQUE,
            mission_id TEXT NOT NULL,
            mission_version INTEGER NOT NULL,
            payload_hash TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            ledger_hash TEXT NOT NULL UNIQUE,
            delivered_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sig_dead_letters (
            task_id TEXT PRIMARY KEY,
            request_hash TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            attempts INTEGER NOT NULL,
            dead_lettered_at REAL NOT NULL
        );
        """
        connection = self._connect()
        try:
            connection.executescript(schema)
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT value FROM sig_meta WHERE key = 'schema_version'"
            ).fetchone()
            if existing and existing["value"] != SCHEMA_VERSION:
                raise StoreError("SCHEMA_VERSION_MISMATCH")
            connection.execute(
                "INSERT OR IGNORE INTO sig_meta(key,value) VALUES('schema_version',?)",
                (SCHEMA_VERSION,),
            )
            connection.execute(
                "INSERT OR IGNORE INTO sig_control(singleton,generation,updated_at) VALUES(1,0,?)",
                (_now(),),
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        task_id: str | None,
        event_type: str,
        actor: str,
        payload: Mapping[str, Any],
        created_at: float,
    ) -> str:
        previous = connection.execute(
            "SELECT event_hash FROM sig_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else "0" * 64
        body = {
            "event_id": str(uuid.uuid4()),
            "task_id": task_id,
            "event_type": event_type,
            "actor": actor,
            "payload": dict(payload),
            "previous_hash": previous_hash,
            "created_at": created_at,
        }
        event_hash = _sha(canonical_json(body))
        connection.execute(
            """INSERT INTO sig_events(
                event_id,task_id,event_type,actor,payload_json,previous_hash,event_hash,created_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                body["event_id"], task_id, event_type, actor,
                canonical_json(payload), previous_hash, event_hash, created_at,
            ),
        )
        return event_hash

    def enqueue(
        self,
        request: AuditRequest,
        *,
        idempotency_key: str | None = None,
        max_attempts: int = 3,
        now: float | None = None,
    ) -> str:
        moment = _now(now)
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 3:
            raise ValidationError("max_attempts_invalid")
        payload = request.to_dict()
        if _contains_secret_like(payload):
            raise ValidationError("SECRET_LIKE_INPUT_REJECTED")
        if not self.verify_continuity(request):
            raise ValidationError("CONTINUITY_ATTESTATION_UNTRUSTED")
        request_json = canonical_json(payload)
        request_hash = _sha(request_json)
        key = idempotency_key or request_hash
        if not isinstance(key, str) or not 8 <= len(key) <= 200:
            raise ValidationError("idempotency_key_invalid")
        if _contains_secret_like(key):
            raise ValidationError("SECRET_LIKE_IDEMPOTENCY_KEY_REJECTED")
        if not SAFE_REFERENCE_RE.fullmatch(key):
            raise ValidationError("idempotency_key_invalid")
        with self._transaction() as connection:
            if self._active_stop(connection, request):
                raise StopLatched("STOP_LATCHED")
            if request.mission_version < self._minimum_mission_version(connection, request):
                raise ValidationError("MISSION_VERSION_BELOW_FLOOR")
            existing = connection.execute(
                "SELECT task_id,request_hash FROM sig_tasks WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflict("IDEMPOTENCY_KEY_PAYLOAD_CONFLICT")
                return str(existing["task_id"])
            task_id = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO sig_tasks(
                    task_id,idempotency_key,request_json,request_hash,mission_id,
                    mission_version,requirement_ids_json,state,max_attempts,available_at,
                    created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task_id, key, request_json, request_hash, request.mission_id,
                    request.mission_version, canonical_json(list(request.requirement_ids)),
                    TaskState.QUEUED.value, max_attempts, moment, moment, moment,
                ),
            )
            self._append_event(
                connection,
                task_id=task_id,
                event_type="TASK_ENQUEUED",
                actor="formation-router",
                payload={"request_hash": request_hash, "max_attempts": max_attempts},
                created_at=moment,
            )
            return task_id

    def register_worker(
        self,
        worker_id: str,
        boot_id: str,
        *,
        now: float | None = None,
    ) -> None:
        moment = _now(now)
        if (
            not isinstance(worker_id, str)
            or not WORKER_ID_RE.fullmatch(worker_id)
            or re.search(r"owner|kim|user", worker_id, re.I)
            or _contains_secret_like(worker_id)
        ):
            raise ValidationError("worker_id_invalid")
        if (
            not isinstance(boot_id, str)
            or not WORKER_ID_RE.fullmatch(boot_id)
            or _contains_secret_like(boot_id)
        ):
            raise ValidationError("boot_id_invalid")
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO sig_workers(worker_id,boot_id,status,current_task_id,heartbeat_at)
                VALUES(?,?,'IDLE',NULL,?)
                ON CONFLICT(worker_id,boot_id) DO UPDATE SET status='IDLE',heartbeat_at=excluded.heartbeat_at""",
                (worker_id, boot_id, moment),
            )

    def _active_stop(self, connection: sqlite3.Connection, request: AuditRequest) -> sqlite3.Row | None:
        rows = connection.execute(
            "SELECT * FROM sig_stop_latches WHERE active = 1 ORDER BY generation DESC"
        ).fetchall()
        for row in rows:
            if row["scope"] == "GLOBAL":
                return row
            if row["scope"] == "MISSION" and row["subject"] == request.mission_id:
                return row
            if row["scope"] == "REQUIREMENT" and row["subject"] in request.requirement_ids:
                return row
        return None

    def _minimum_mission_version(
        self, connection: sqlite3.Connection, request: AuditRequest
    ) -> int:
        minimum = 0
        for row in connection.execute("SELECT * FROM sig_version_floors"):
            if (
                row["scope"] == "GLOBAL"
                or (row["scope"] == "MISSION" and row["subject"] == request.mission_id)
                or (row["scope"] == "REQUIREMENT" and row["subject"] in request.requirement_ids)
            ):
                minimum = max(minimum, int(row["minimum_mission_version"]))
        return minimum

    def _request_from_row(self, row: sqlite3.Row) -> AuditRequest:
        payload = parse_json_strict(row["request_json"])
        request = AuditRequest.from_dict(payload)
        if request.input_hash != row["request_hash"]:
            raise StoreError("REQUEST_HASH_MISMATCH")
        return request

    def set_stop(
        self,
        *,
        scope: str,
        subject: str,
        mission_version: int,
        reason_code: str,
        now: float | None = None,
    ) -> int:
        moment = _now(now)
        if scope not in {"GLOBAL", "MISSION", "REQUIREMENT"}:
            raise ValidationError("stop_scope_invalid")
        if not isinstance(subject, str) or not SAFE_REFERENCE_RE.fullmatch(subject) or _contains_secret_like(subject):
            raise ValidationError("stop_subject_invalid")
        if (
            not isinstance(reason_code, str)
            or reason_code not in STOP_REASON_CODES
        ):
            raise ValidationError("reason_code_invalid")
        if not isinstance(mission_version, int) or isinstance(mission_version, bool) or mission_version < 1:
            raise ValidationError("mission_version_invalid")
        latch_id = f"{scope}:{subject}"
        with self._transaction() as connection:
            current = connection.execute(
                "SELECT generation FROM sig_control WHERE singleton = 1"
            ).fetchone()
            generation = int(current["generation"]) + 1
            prior = connection.execute(
                "SELECT mission_version FROM sig_stop_latches WHERE latch_id = ?",
                (latch_id,),
            ).fetchone()
            if prior and int(prior["mission_version"]) > mission_version:
                raise StopLatched("STOP_VERSION_CANNOT_DECREASE")
            connection.execute(
                "UPDATE sig_control SET generation=?,updated_at=? WHERE singleton=1",
                (generation, moment),
            )
            connection.execute(
                """INSERT INTO sig_stop_latches(
                    latch_id,scope,subject,mission_version,active,generation,reason_code,
                    authority_record_hash,updated_at
                ) VALUES(?,?,?,?,1,?,?,NULL,?)
                ON CONFLICT(latch_id) DO UPDATE SET
                    mission_version=excluded.mission_version,active=1,generation=excluded.generation,
                    reason_code=excluded.reason_code,authority_record_hash=NULL,updated_at=excluded.updated_at""",
                (latch_id, scope, subject, mission_version, generation, reason_code, moment),
            )
            processing = connection.execute(
                "SELECT * FROM sig_tasks WHERE state = ?",
                (TaskState.PROCESSING.value,),
            ).fetchall()
            for task in processing:
                request = self._request_from_row(task)
                if self._active_stop(connection, request):
                    self._dead_letter_locked(connection, task, "STOP_LATCHED", moment)
            self._append_event(
                connection,
                task_id=None,
                event_type="STOP_LATCHED",
                actor="formation-governor",
                payload={"scope": scope, "subject": subject, "generation": generation, "reason_code": reason_code},
                created_at=moment,
            )
            return generation

    def clear_stop(
        self,
        *,
        scope: str,
        subject: str,
        new_mission_version: int,
        expected_generation: int,
        authority_record_hash: str,
        now: float | None = None,
    ) -> int:
        moment = _now(now)
        if scope not in {"GLOBAL", "MISSION", "REQUIREMENT"}:
            raise ValidationError("stop_scope_invalid")
        if not isinstance(subject, str) or not SAFE_REFERENCE_RE.fullmatch(subject) or _contains_secret_like(subject):
            raise ValidationError("stop_subject_invalid")
        if (
            isinstance(new_mission_version, bool)
            or not isinstance(new_mission_version, int)
            or new_mission_version < 1
        ):
            raise ValidationError("mission_version_invalid")
        if isinstance(expected_generation, bool) or not isinstance(expected_generation, int) or expected_generation < 0:
            raise ValidationError("expected_generation_invalid")
        if not SHA256_RE.fullmatch(authority_record_hash):
            raise ValidationError("authority_record_hash_invalid")
        expected_record = {
            "scope": scope,
            "subject": subject,
            "new_mission_version": new_mission_version,
            "expected_generation": expected_generation,
        }
        if self.trusted_resume_records.get(authority_record_hash) != expected_record:
            raise StopLatched("TRUSTED_RESUME_AUTHORITY_REQUIRED")
        latch_id = f"{scope}:{subject}"
        with self._transaction() as connection:
            control = connection.execute(
                "SELECT generation FROM sig_control WHERE singleton=1"
            ).fetchone()
            latch = connection.execute(
                "SELECT * FROM sig_stop_latches WHERE latch_id=? AND active=1",
                (latch_id,),
            ).fetchone()
            if not latch:
                raise StopLatched("ACTIVE_STOP_REQUIRED")
            if int(control["generation"]) != expected_generation:
                raise StopLatched("STOP_GENERATION_MISMATCH")
            if new_mission_version <= int(latch["mission_version"]):
                raise StopLatched("NEWER_MISSION_VERSION_REQUIRED")
            stale = connection.execute(
                "SELECT * FROM sig_tasks WHERE state IN (?,?,?)",
                (TaskState.QUEUED.value, TaskState.RETRY.value, TaskState.PROCESSING.value),
            ).fetchall()
            for task in stale:
                request = self._request_from_row(task)
                scope_matches = (
                    scope == "GLOBAL"
                    or (scope == "MISSION" and request.mission_id == subject)
                    or (scope == "REQUIREMENT" and subject in request.requirement_ids)
                )
                if scope_matches and request.mission_version < new_mission_version:
                    self._dead_letter_locked(connection, task, "STALE_AFTER_STOP_RESUME", moment)
            generation = expected_generation + 1
            connection.execute(
                "UPDATE sig_control SET generation=?,updated_at=? WHERE singleton=1",
                (generation, moment),
            )
            connection.execute(
                """UPDATE sig_stop_latches SET active=0,generation=?,authority_record_hash=?,updated_at=?
                WHERE latch_id=?""",
                (generation, authority_record_hash, moment, latch_id),
            )
            connection.execute(
                """INSERT INTO sig_version_floors(
                    floor_id,scope,subject,minimum_mission_version,generation,
                    authority_record_hash,updated_at
                ) VALUES(?,?,?,?,?,?,?) ON CONFLICT(floor_id) DO UPDATE SET
                    minimum_mission_version=MAX(minimum_mission_version,excluded.minimum_mission_version),
                    generation=excluded.generation,
                    authority_record_hash=excluded.authority_record_hash,
                    updated_at=excluded.updated_at""",
                (
                    latch_id, scope, subject, new_mission_version, generation,
                    authority_record_hash, moment,
                ),
            )
            self._append_event(
                connection,
                task_id=None,
                event_type="STOP_CLEARED",
                actor="formation-governor",
                payload={
                    "scope": scope, "subject": subject, "generation": generation,
                    "new_mission_version": new_mission_version,
                    "authority_record_hash": authority_record_hash,
                },
                created_at=moment,
            )
            return generation

    def record_delivered_output(
        self,
        *,
        occurrence_id: str,
        mission_id: str,
        mission_version: int,
        payload_hash: str,
        now: float | None = None,
    ) -> tuple[int, str]:
        moment = _now(now)
        if (
            not isinstance(occurrence_id, str)
            or not SAFE_REFERENCE_RE.fullmatch(occurrence_id)
            or _contains_secret_like(occurrence_id)
        ):
            raise ValidationError("occurrence_id_invalid")
        if (
            not isinstance(mission_id, str)
            or not SAFE_REFERENCE_RE.fullmatch(mission_id)
            or _contains_secret_like(mission_id)
        ):
            raise ValidationError("mission_id_invalid")
        if isinstance(mission_version, bool) or not isinstance(mission_version, int) or mission_version < 1:
            raise ValidationError("mission_version_invalid")
        if not SHA256_RE.fullmatch(payload_hash):
            raise ValidationError("payload_hash_invalid")
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT mission_id,mission_version,payload_hash FROM sig_delivered_outputs WHERE occurrence_id=?",
                (occurrence_id,),
            ).fetchone()
            if existing:
                if (
                    existing["mission_id"] != mission_id
                    or int(existing["mission_version"]) != mission_version
                    or existing["payload_hash"] != payload_hash
                ):
                    raise IdempotencyConflict("OUTPUT_OCCURRENCE_CONFLICT")
            else:
                previous = connection.execute(
                    "SELECT ledger_hash FROM sig_delivered_outputs ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                previous_hash = previous["ledger_hash"] if previous else "0" * 64
                body = {
                    "occurrence_id": occurrence_id,
                    "mission_id": mission_id,
                    "mission_version": mission_version,
                    "payload_hash": payload_hash,
                    "previous_hash": previous_hash,
                    "delivered_at": moment,
                }
                ledger_hash = _sha(canonical_json(body))
                connection.execute(
                    """INSERT INTO sig_delivered_outputs(
                        occurrence_id,mission_id,mission_version,payload_hash,previous_hash,ledger_hash,delivered_at
                    ) VALUES(?,?,?,?,?,?,?)""",
                    (occurrence_id, mission_id, mission_version, payload_hash, previous_hash, ledger_hash, moment),
                )
            return self._output_snapshot_locked(connection, mission_id, mission_version)

    def _output_snapshot_locked(
        self,
        connection: sqlite3.Connection,
        mission_id: str,
        mission_version: int,
    ) -> tuple[int, str]:
        rows = connection.execute(
            """SELECT * FROM sig_delivered_outputs
            WHERE mission_id=? AND mission_version=? ORDER BY sequence""",
            (mission_id, mission_version),
        ).fetchall()
        if not rows:
            return 0, "0" * 64
        return len(rows), str(rows[-1]["ledger_hash"])

    def output_snapshot(self, mission_id: str, mission_version: int) -> tuple[int, str]:
        with self._connect() as connection:
            if not self.verify_output_ledger(connection=connection):
                raise StoreError("OUTPUT_LEDGER_INVALID")
            return self._output_snapshot_locked(connection, mission_id, mission_version)

    def verify_output_ledger(self, *, connection: sqlite3.Connection | None = None) -> bool:
        owned = connection is None
        connection = connection or self._connect()
        try:
            previous_hash = "0" * 64
            for row in connection.execute("SELECT * FROM sig_delivered_outputs ORDER BY sequence"):
                body = {
                    "occurrence_id": row["occurrence_id"],
                    "mission_id": row["mission_id"],
                    "mission_version": int(row["mission_version"]),
                    "payload_hash": row["payload_hash"],
                    "previous_hash": previous_hash,
                    "delivered_at": float(row["delivered_at"]),
                }
                if row["previous_hash"] != previous_hash or row["ledger_hash"] != _sha(canonical_json(body)):
                    return False
                previous_hash = row["ledger_hash"]
            return True
        finally:
            if owned:
                connection.close()

    def _dead_letter_locked(
        self,
        connection: sqlite3.Connection,
        task: sqlite3.Row,
        reason_code: str,
        moment: float,
    ) -> None:
        connection.execute(
            """UPDATE sig_tasks SET state=?,lease_owner=NULL,worker_boot_id=NULL,
            lease_token_hash=NULL,lease_expires_at=NULL,last_error_code=?,updated_at=? WHERE task_id=?""",
            (TaskState.DEAD_LETTER.value, reason_code, moment, task["task_id"]),
        )
        connection.execute(
            """INSERT INTO sig_dead_letters(task_id,request_hash,reason_code,attempts,dead_lettered_at)
            VALUES(?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET
            reason_code=excluded.reason_code,attempts=excluded.attempts,dead_lettered_at=excluded.dead_lettered_at""",
            (task["task_id"], task["request_hash"], reason_code, int(task["attempts"]), moment),
        )
        self._append_event(
            connection,
            task_id=task["task_id"],
            event_type="TASK_DEAD_LETTERED",
            actor="guardian-store",
            payload={"reason_code": reason_code, "request_hash": task["request_hash"]},
            created_at=moment,
        )

    def claim_task(
        self,
        worker_id: str,
        boot_id: str,
        *,
        lease_seconds: int = 60,
        now: float | None = None,
    ) -> Mapping[str, Any] | None:
        moment = _now(now)
        if not 15 <= lease_seconds <= 900:
            raise ValidationError("lease_seconds_invalid")
        with self._transaction() as connection:
            worker = connection.execute(
                "SELECT * FROM sig_workers WHERE worker_id=? AND boot_id=?",
                (worker_id, boot_id),
            ).fetchone()
            if not worker:
                raise LeaseRejected("WORKER_IDENTITY_NOT_REGISTERED")
            expired = connection.execute(
                "SELECT * FROM sig_tasks WHERE state=? AND lease_expires_at < ?",
                (TaskState.PROCESSING.value, moment),
            ).fetchall()
            for task in expired:
                if int(task["attempts"]) >= int(task["max_attempts"]):
                    self._dead_letter_locked(connection, task, "LEASE_EXPIRED_ATTEMPTS_EXHAUSTED", moment)
                else:
                    connection.execute(
                        """UPDATE sig_tasks SET state=?,available_at=?,lease_owner=NULL,
                        worker_boot_id=NULL,lease_token_hash=NULL,lease_expires_at=NULL,
                        last_error_code='LEASE_EXPIRED',updated_at=? WHERE task_id=?""",
                        (TaskState.RETRY.value, moment, moment, task["task_id"]),
                    )
            candidates = connection.execute(
                """SELECT * FROM sig_tasks WHERE state IN (?,?) AND available_at <= ?
                ORDER BY created_at,task_id""",
                (TaskState.QUEUED.value, TaskState.RETRY.value, moment),
            ).fetchall()
            selected: sqlite3.Row | None = None
            request: AuditRequest | None = None
            for candidate in candidates:
                parsed = self._request_from_row(candidate)
                if not self.verify_continuity(parsed):
                    self._dead_letter_locked(
                        connection, candidate, "CONTINUITY_ATTESTATION_UNTRUSTED", moment
                    )
                elif parsed.mission_version < self._minimum_mission_version(connection, parsed):
                    self._dead_letter_locked(
                        connection, candidate, "MISSION_VERSION_BELOW_FLOOR", moment
                    )
                elif not self._active_stop(connection, parsed):
                    selected, request = candidate, parsed
                    break
            if selected is None or request is None:
                return None
            control = connection.execute(
                "SELECT generation FROM sig_control WHERE singleton=1"
            ).fetchone()
            token = secrets.token_urlsafe(32)
            token_hash = _sha(token)
            fence = int(selected["fence_generation"]) + 1
            attempts = int(selected["attempts"]) + 1
            generation = int(control["generation"])
            updated = connection.execute(
                """UPDATE sig_tasks SET state=?,attempts=?,lease_owner=?,worker_boot_id=?,
                lease_token_hash=?,fence_generation=?,control_generation=?,lease_expires_at=?,
                updated_at=? WHERE task_id=? AND state IN (?,?)""",
                (
                    TaskState.PROCESSING.value, attempts, worker_id, boot_id,
                    token_hash, fence, generation, moment + lease_seconds, moment,
                    selected["task_id"], TaskState.QUEUED.value, TaskState.RETRY.value,
                ),
            )
            if updated.rowcount != 1:
                raise LeaseRejected("CLAIM_RACE_LOST")
            connection.execute(
                """UPDATE sig_workers SET status='BUSY',current_task_id=?,heartbeat_at=?
                WHERE worker_id=? AND boot_id=?""",
                (selected["task_id"], moment, worker_id, boot_id),
            )
            self._append_event(
                connection,
                task_id=selected["task_id"],
                event_type="TASK_CLAIMED",
                actor=worker_id,
                payload={"boot_id": boot_id, "fence_generation": fence, "attempt": attempts},
                created_at=moment,
            )
            return {
                "task_id": selected["task_id"],
                "request": request,
                "worker_id": worker_id,
                "boot_id": boot_id,
                "lease_token": token,
                "fence_generation": fence,
                "control_generation": generation,
                "lease_expires_at": moment + lease_seconds,
            }

    def _validate_lease(
        self,
        connection: sqlite3.Connection,
        lease: Mapping[str, Any],
        moment: float,
    ) -> tuple[sqlite3.Row, AuditRequest]:
        task = connection.execute(
            "SELECT * FROM sig_tasks WHERE task_id=?",
            (lease.get("task_id"),),
        ).fetchone()
        if not task or task["state"] != TaskState.PROCESSING.value:
            raise LeaseRejected("TASK_NOT_PROCESSING")
        control = connection.execute(
            "SELECT generation FROM sig_control WHERE singleton=1"
        ).fetchone()
        request = self._request_from_row(task)
        valid = (
            task["lease_owner"] == lease.get("worker_id")
            and task["worker_boot_id"] == lease.get("boot_id")
            and task["lease_token_hash"] == _sha(str(lease.get("lease_token") or ""))
            and int(task["fence_generation"]) == int(lease.get("fence_generation", -1))
            and int(task["control_generation"]) == int(lease.get("control_generation", -1))
            and int(control["generation"]) == int(task["control_generation"])
            and float(task["lease_expires_at"]) >= moment
            and self._active_stop(connection, request) is None
        )
        if not valid:
            raise LeaseRejected("LEASE_OR_FENCE_INVALID")
        return task, request

    def heartbeat(
        self,
        lease: Mapping[str, Any],
        *,
        extend_seconds: int = 60,
        now: float | None = None,
    ) -> float:
        moment = _now(now)
        if not 15 <= extend_seconds <= 900:
            raise ValidationError("extend_seconds_invalid")
        with self._transaction() as connection:
            task, _ = self._validate_lease(connection, lease, moment)
            expiry = moment + extend_seconds
            connection.execute(
                """UPDATE sig_tasks SET lease_expires_at=?,updated_at=? WHERE task_id=?
                AND fence_generation=? AND control_generation=?""",
                (expiry, moment, task["task_id"], task["fence_generation"], task["control_generation"]),
            )
            connection.execute(
                """UPDATE sig_workers SET heartbeat_at=?,status='BUSY',current_task_id=?
                WHERE worker_id=? AND boot_id=?""",
                (moment, task["task_id"], lease["worker_id"], lease["boot_id"]),
            )
            return expiry

    def complete_task(
        self,
        lease: Mapping[str, Any],
        result: AuditResult,
        *,
        now: float | None = None,
    ) -> str:
        moment = _now(now)
        result_dict = result.to_dict()
        if not is_persistable_advisory_record(result.advisory):
            raise LeaseRejected("ADVISORY_RECEIPT_INVALID")
        if _contains_secret_like(result_dict):
            raise LeaseRejected("SECRET_LIKE_RESULT_REJECTED")
        result_json = canonical_json(result_dict)
        result_hash = _sha(result_json)
        with self._transaction() as connection:
            task, request = self._validate_lease(connection, lease, moment)
            if result.input_hash != request.input_hash:
                raise LeaseRejected("RESULT_INPUT_HASH_MISMATCH")
            count, ledger_hash = self._output_snapshot_locked(
                connection, request.mission_id, request.mission_version
            )
            if not self._verify_event_chain_locked(connection):
                raise LeaseRejected("EVENT_CHAIN_INVALID")
            if not self.verify_output_ledger(connection=connection):
                raise LeaseRejected("OUTPUT_LEDGER_INVALID")
            if (
                not result.output_ledger_verified
                or result.delivered_output_count != count
                or result.output_ledger_hash != ledger_hash
            ):
                raise LeaseRejected("OUTPUT_LEDGER_SNAPSHOT_MISMATCH")
            expected = evaluate(
                request,
                delivered_output_count=count,
                output_ledger_hash=ledger_hash,
                output_ledger_verified=True,
                advisory_available=result.advisory_available,
                continuity_attestation_verified=self.verify_continuity(request),
            ).to_dict()
            observed_authoritative = dict(result_dict)
            expected_authoritative = dict(expected)
            observed_authoritative["advisory"] = {}
            expected_authoritative["advisory"] = {}
            if canonical_json(observed_authoritative) != canonical_json(expected_authoritative):
                raise LeaseRejected("DETERMINISTIC_RESULT_MISMATCH")
            updated = connection.execute(
                """UPDATE sig_tasks SET state=?,result_json=?,result_hash=?,advisory_hash=?,
                cadence_output_count=?,output_ledger_hash=?,lease_owner=NULL,worker_boot_id=NULL,
                lease_token_hash=NULL,lease_expires_at=NULL,completed_at=?,updated_at=?
                WHERE task_id=? AND state=? AND fence_generation=? AND control_generation=?""",
                (
                    TaskState.COMPLETED.value, result_json, result_hash,
                    _sha(canonical_json(result_dict.get("advisory", {}))), count, ledger_hash,
                    moment, moment, task["task_id"], TaskState.PROCESSING.value,
                    task["fence_generation"], task["control_generation"],
                ),
            )
            if updated.rowcount != 1:
                raise LeaseRejected("FENCED_COMPLETION_REJECTED")
            connection.execute(
                """UPDATE sig_workers SET status='IDLE',current_task_id=NULL,heartbeat_at=?
                WHERE worker_id=? AND boot_id=?""",
                (moment, lease["worker_id"], lease["boot_id"]),
            )
            self._append_event(
                connection,
                task_id=task["task_id"],
                event_type="TASK_COMPLETED",
                actor=lease["worker_id"],
                payload={
                    "result_hash": result_hash,
                    "verdict": result.verdict.value,
                    "authorizes_action": False,
                    "release_authority": "NONE",
                },
                created_at=moment,
            )
            return result_hash

    def fail_task(
        self,
        lease: Mapping[str, Any],
        *,
        reason_code: str,
        transient: bool,
        now: float | None = None,
    ) -> str:
        moment = _now(now)
        if not isinstance(transient, bool):
            raise ValidationError("transient_flag_invalid")
        if (
            not isinstance(reason_code, str)
            or reason_code not in FAILURE_REASON_CODES
        ):
            raise ValidationError("reason_code_invalid")
        with self._transaction() as connection:
            task, _ = self._validate_lease(connection, lease, moment)
            retry = (
                transient
                and reason_code in TRANSIENT_CODES
                and int(task["attempts"]) < int(task["max_attempts"])
            )
            if retry:
                delay = min(300, 5 * (2 ** max(0, int(task["attempts"]) - 1)))
                connection.execute(
                    """UPDATE sig_tasks SET state=?,available_at=?,lease_owner=NULL,
                    worker_boot_id=NULL,lease_token_hash=NULL,lease_expires_at=NULL,
                    last_error_code=?,updated_at=? WHERE task_id=?""",
                    (TaskState.RETRY.value, moment + delay, reason_code, moment, task["task_id"]),
                )
                state = TaskState.RETRY.value
                event_type = "TASK_RETRY_SCHEDULED"
            else:
                self._dead_letter_locked(connection, task, reason_code, moment)
                state = TaskState.DEAD_LETTER.value
                event_type = "TASK_DEAD_LETTERED"
            connection.execute(
                """UPDATE sig_workers SET status='IDLE',current_task_id=NULL,heartbeat_at=?
                WHERE worker_id=? AND boot_id=?""",
                (moment, lease["worker_id"], lease["boot_id"]),
            )
            if retry:
                self._append_event(
                    connection,
                    task_id=task["task_id"],
                    event_type=event_type,
                    actor=lease["worker_id"],
                    payload={"reason_code": reason_code, "transient": True},
                    created_at=moment,
                )
            return state

    def task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sig_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if not row:
                raise StoreError("TASK_NOT_FOUND")
            return dict(row)

    def _verify_event_chain_locked(self, connection: sqlite3.Connection) -> bool:
        previous_hash = "0" * 64
        for row in connection.execute("SELECT * FROM sig_events ORDER BY sequence"):
            body = {
                "event_id": row["event_id"],
                "task_id": row["task_id"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "payload": parse_json_strict(row["payload_json"]),
                "previous_hash": previous_hash,
                "created_at": float(row["created_at"]),
            }
            if row["previous_hash"] != previous_hash or row["event_hash"] != _sha(canonical_json(body)):
                return False
            previous_hash = row["event_hash"]
        return True

    def verify_event_chain(self, *, connection: sqlite3.Connection | None = None) -> bool:
        owned = connection is None
        connection = connection or self._connect()
        try:
            return self._verify_event_chain_locked(connection)
        finally:
            if owned:
                connection.close()

    def semantic_readback(self, task_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sig_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if not row or row["state"] != TaskState.COMPLETED.value:
                raise StoreError("COMPLETED_TASK_REQUIRED")
            request = self._request_from_row(row)
            observed = parse_json_strict(row["result_json"])
            hashes_valid = (
                _sha(row["request_json"]) == row["request_hash"]
                and _sha(row["result_json"]) == row["result_hash"]
            )
            ledger_valid = self.verify_output_ledger(connection=connection)
            expected = evaluate(
                request,
                delivered_output_count=int(row["cadence_output_count"]),
                output_ledger_hash=row["output_ledger_hash"],
                output_ledger_verified=ledger_valid,
                advisory_available=bool(observed.get("advisory_available")),
                continuity_attestation_verified=self.verify_continuity(request),
            ).to_dict()
            observed_authoritative = dict(observed)
            expected_authoritative = dict(expected)
            observed_authoritative["advisory"] = {}
            expected_authoritative["advisory"] = {}
            semantic_match = canonical_json(observed_authoritative) == canonical_json(expected_authoritative)
            event_chain_valid = self.verify_event_chain(connection=connection)
            verified = hashes_valid and ledger_valid and event_chain_valid and semantic_match
            return {
                "task_id": task_id,
                "classification": "SEMANTIC_READBACK_VERIFIED" if verified else "SEMANTIC_READBACK_FAILED",
                "verified": verified,
                "request_hash_valid": hashes_valid,
                "result_hash_valid": hashes_valid,
                "output_ledger_valid": ledger_valid,
                "event_chain_valid": event_chain_valid,
                "deterministic_policy_recomputed": semantic_match,
                "authorizes_action": False,
                "effect_performed": False,
                "release_authority": "NONE",
                "runtime_state": HEALTH_CLASSIFICATION,
            }

    def health(self) -> dict[str, Any]:
        with self._connect() as connection:
            counts = {
                row["state"]: int(row["count"])
                for row in connection.execute(
                    "SELECT state,COUNT(*) AS count FROM sig_tasks GROUP BY state"
                )
            }
            generation = int(
                connection.execute("SELECT generation FROM sig_control WHERE singleton=1").fetchone()["generation"]
            )
            active_stops = int(
                connection.execute("SELECT COUNT(*) AS count FROM sig_stop_latches WHERE active=1").fetchone()["count"]
            )
            version_floors = int(
                connection.execute("SELECT COUNT(*) AS count FROM sig_version_floors").fetchone()["count"]
            )
            last_heartbeat = connection.execute(
                "SELECT MAX(heartbeat_at) AS value FROM sig_workers"
            ).fetchone()["value"]
            schema_row = connection.execute(
                "SELECT value FROM sig_meta WHERE key='schema_version'"
            ).fetchone()
            schema_valid = bool(schema_row and schema_row["value"] == SCHEMA_VERSION)
            event_chain_valid = self.verify_event_chain(connection=connection)
            output_ledger_valid = self.verify_output_ledger(connection=connection)
            return {
                "ok": schema_valid and event_chain_valid and output_ledger_valid,
                "schema_version": SCHEMA_VERSION,
                "schema_valid": schema_valid,
                "classification": HEALTH_CLASSIFICATION,
                "deployed": False,
                "autonomous": False,
                "provider_execution_supported": False,
                "release_authority": "NONE",
                "control_generation": generation,
                "active_stop_latches": active_stops,
                "version_floors": version_floors,
                "task_counts": counts,
                "last_worker_heartbeat": last_heartbeat,
                "event_chain_valid": event_chain_valid,
                "output_ledger_valid": output_ledger_valid,
            }
