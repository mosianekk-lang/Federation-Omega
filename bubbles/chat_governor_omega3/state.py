from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _now() -> float:
    return time.time()


@dataclass
class EvidencePointer:
    source_id: str
    source_type: str
    title: str = ""
    version: str = ""
    modified_at: str = ""
    verified: bool = False
    verified_at: str = ""
    sha256: str = ""
    findings: List[str] = field(default_factory=list)


class DurableState:
    """Crash-safe SQLite state for missions, evidence, receipts and checkpoints."""

    def __init__(self, path: str = "bubbles_chat_governor_omega3.sqlite3") -> None:
        self.path = path
        self._local = threading.local()
        self._bootstrap()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def _bootstrap(self) -> None:
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS missions(
                mission_id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                mission_type TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                state TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence(
                source_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                version TEXT,
                modified_at TEXT,
                verified INTEGER NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts(
                idempotency_key TEXT PRIMARY KEY,
                mission_id TEXT,
                action TEXT,
                target TEXT,
                success INTEGER NOT NULL,
                semantic_ok INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints(
                checkpoint_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                proof_bearing INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metrics(
                metric_key TEXT PRIMARY KEY,
                ewma REAL NOT NULL,
                samples INTEGER NOT NULL,
                last_value REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS circuit_breakers(
                connector TEXT PRIMARY KEY,
                failures INTEGER NOT NULL,
                opened_at REAL,
                last_error TEXT,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_checkpoint_mission
                ON checkpoints(mission_id, created_at DESC);
            """
        )
        conn.close()

    def save_plan(self, plan: Dict[str, Any], state: str = "ACTIVE") -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO missions(mission_id,objective,mission_type,plan_json,state,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(mission_id) DO UPDATE SET
                     objective=excluded.objective,
                     mission_type=excluded.mission_type,
                     plan_json=excluded.plan_json,
                     state=excluded.state,
                     updated_at=excluded.updated_at""",
                (
                    plan["mission_id"], plan["objective"], plan["mission_type"],
                    json.dumps(plan, sort_keys=True), state, _now(),
                ),
            )

    def put_evidence(self, pointer: EvidencePointer) -> None:
        payload = json.dumps(asdict(pointer), sort_keys=True)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO evidence(source_id,payload_json,version,modified_at,verified,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(source_id) DO UPDATE SET
                     payload_json=excluded.payload_json,
                     version=excluded.version,
                     modified_at=excluded.modified_at,
                     verified=excluded.verified,
                     updated_at=excluded.updated_at""",
                (
                    pointer.source_id, payload, pointer.version, pointer.modified_at,
                    int(pointer.verified), _now(),
                ),
            )

    def get_evidence(self, source_id: str) -> Optional[EvidencePointer]:
        row = self._conn().execute(
            "SELECT payload_json FROM evidence WHERE source_id=?", (source_id,)
        ).fetchone()
        return EvidencePointer(**json.loads(row["payload_json"])) if row else None

    def needs_refresh(self, source_id: str, *, version: str = "", modified_at: str = "") -> bool:
        pointer = self.get_evidence(source_id)
        if pointer is None or not pointer.verified:
            return True
        if version and pointer.version and version != pointer.version:
            return True
        if modified_at and pointer.modified_at and modified_at != pointer.modified_at:
            return True
        return False

    def get_receipt(self, key: str) -> Optional[Dict[str, Any]]:
        row = self._conn().execute(
            "SELECT * FROM receipts WHERE idempotency_key=?", (key,)
        ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["payload"] = json.loads(out.pop("payload_json"))
        return out

    def save_receipt(
        self, *, key: str, mission_id: str, action: str, target: str,
        success: bool, semantic_ok: bool, payload: Any,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO receipts
                   (idempotency_key,mission_id,action,target,success,semantic_ok,payload_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    key, mission_id, action, target, int(success), int(semantic_ok),
                    json.dumps(payload, sort_keys=True, default=str), _now(),
                ),
            )

    def checkpoint(self, mission_id: str, payload: Any, *, proof_bearing: bool) -> str:
        checkpoint_id = f"cp_{uuid.uuid4().hex}"
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO checkpoints VALUES(?,?,?,?,?)",
                (
                    checkpoint_id, mission_id,
                    json.dumps(payload, sort_keys=True, default=str),
                    int(proof_bearing), _now(),
                ),
            )
        return checkpoint_id

    def latest_checkpoint(self, mission_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn().execute(
            "SELECT * FROM checkpoints WHERE mission_id=? ORDER BY created_at DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["payload"] = json.loads(out.pop("payload_json"))
        return out

    def last_proof_checkpoint_at(self, mission_id: str) -> Optional[float]:
        row = self._conn().execute(
            """SELECT created_at FROM checkpoints
               WHERE mission_id=? AND proof_bearing=1
               ORDER BY created_at DESC LIMIT 1""",
            (mission_id,),
        ).fetchone()
        return float(row["created_at"]) if row else None

    def update_metric(self, key: str, value: float, alpha: float = 0.25) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT ewma,samples FROM metrics WHERE metric_key=?", (key,)
            ).fetchone()
            if row:
                ewma = alpha * value + (1.0 - alpha) * float(row["ewma"])
                samples = int(row["samples"]) + 1
            else:
                ewma, samples = value, 1
            conn.execute(
                """INSERT OR REPLACE INTO metrics(metric_key,ewma,samples,last_value,updated_at)
                   VALUES(?,?,?,?,?)""",
                (key, ewma, samples, value, _now()),
            )
        return ewma

    def metric(self, key: str) -> Optional[float]:
        row = self._conn().execute(
            "SELECT ewma FROM metrics WHERE metric_key=?", (key,)
        ).fetchone()
        return float(row["ewma"]) if row else None

    def circuit_state(self, connector: str) -> Dict[str, Any]:
        row = self._conn().execute(
            "SELECT * FROM circuit_breakers WHERE connector=?", (connector,)
        ).fetchone()
        return dict(row) if row else {
            "connector": connector, "failures": 0, "opened_at": None, "last_error": None,
        }

    def circuit_failure(self, connector: str, error: str, *, threshold: int = 3) -> None:
        current = self.circuit_state(connector)
        failures = int(current["failures"]) + 1
        opened_at = _now() if failures >= threshold else current.get("opened_at")
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO circuit_breakers
                   (connector,failures,opened_at,last_error,updated_at)
                   VALUES(?,?,?,?,?)""",
                (connector, failures, opened_at, error[:1000], _now()),
            )

    def circuit_success(self, connector: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO circuit_breakers
                   (connector,failures,opened_at,last_error,updated_at)
                   VALUES(?,?,?,?,?)""",
                (connector, 0, None, None, _now()),
            )

    def circuit_allows(self, connector: str, *, reset_seconds: float = 60.0) -> bool:
        current = self.circuit_state(connector)
        opened_at = current.get("opened_at")
        if opened_at is None:
            return True
        if _now() - float(opened_at) >= reset_seconds:
            self.circuit_success(connector)
            return True
        return False
