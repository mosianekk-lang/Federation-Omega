from __future__ import annotations

import json
import hashlib
import hmac
import os
import secrets
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from .anchor import TrustedAnchorStore
from .models import PROOF_ORDER, CloudEvent, ProofStage
from .proof import ProofKernel
from .util import (
    canonical_json,
    canonical_utc,
    digest_json,
    parse_utc,
    reject_sensitive,
    require_finite_number,
    require_int,
    require_nonempty,
    utc_now,
)


_JSON_TABLES = {"assets", "edges", "providers", "heartbeats", "receipts", "blockers"}


class FabricStore:
    def __init__(
        self,
        path: str | Path,
        *,
        proof_kernel: ProofKernel | None = None,
        integrity_key: bytes | None = None,
        integrity_authority_id: str = "",
        anchor_store: TrustedAnchorStore | None = None,
        expected_store_id: str = "",
    ):
        self.path = Path(path)
        self._proof_kernel = proof_kernel
        if integrity_key is not None and len(integrity_key) < 32:
            raise ValueError("integrity key must contain at least 256 bits")
        if integrity_key is not None and not integrity_authority_id.strip():
            raise ValueError("integrity authority identity required")
        if integrity_key is not None and anchor_store is None:
            raise ValueError("independent trusted anchor store required")
        if integrity_key is not None and not expected_store_id.strip():
            raise ValueError("independently configured expected store identity required")
        self._integrity_key = integrity_key
        self._integrity_authority_id = integrity_authority_id
        self._anchor_store = anchor_store
        self._expected_store_id = expected_store_id.strip()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA busy_timeout=10000")
        return con

    def _assert_current_integrity_connection(self, con: sqlite3.Connection) -> None:
        if self._integrity_key is None:
            return
        store_id = con.execute(
            "SELECT value FROM fabric_metadata WHERE key='store_id'"
        ).fetchone()["value"]
        assert self._anchor_store is not None
        result = self._integrity_from_connection(
            con,
            integrity_key=self._integrity_key,
            integrity_authority_id=self._integrity_authority_id,
            expected_anchor=self._anchor_store.read(store_id),
            expected_store_id=self._expected_store_id,
        )
        if result["state"] != "OK":
            raise PermissionError("trusted pre-write integrity verification failed")

    @contextmanager
    def _verified_write(self):
        self.initialize()
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            self._assert_current_integrity_connection(con)
            yield con
            if self._integrity_key is not None:
                self._seal_with_connection(con)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS assets(
          id TEXT PRIMARY KEY, document TEXT NOT NULL, content_hash TEXT NOT NULL,
          observed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS edges(
          id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
          document TEXT NOT NULL, content_hash TEXT NOT NULL, observed_at TEXT NOT NULL,
          FOREIGN KEY(source_id) REFERENCES assets(id),
          FOREIGN KEY(target_id) REFERENCES assets(id)
        );
        CREATE TABLE IF NOT EXISTS providers(
          id TEXT PRIMARY KEY, document TEXT NOT NULL, content_hash TEXT NOT NULL,
          observed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS heartbeats(
          id TEXT PRIMARY KEY, node_id TEXT NOT NULL, document TEXT NOT NULL,
          content_hash TEXT NOT NULL, observed_at TEXT NOT NULL,
          FOREIGN KEY(node_id) REFERENCES assets(id)
        );
        CREATE TABLE IF NOT EXISTS events(
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
          event_type TEXT NOT NULL, source TEXT NOT NULL, subject TEXT,
          traceparent TEXT NOT NULL, document TEXT NOT NULL, content_hash TEXT NOT NULL,
          created_at TEXT NOT NULL, previous_hash TEXT NOT NULL DEFAULT '',
          chain_hash TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS receipts(
          id TEXT PRIMARY KEY, document TEXT NOT NULL, content_hash TEXT NOT NULL,
          observed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS blockers(
          id TEXT PRIMARY KEY, document TEXT NOT NULL, content_hash TEXT NOT NULL,
          observed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS idempotency(
          key TEXT PRIMARY KEY, action_id TEXT NOT NULL, request_hash TEXT NOT NULL,
          result_hash TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outbox(
          id TEXT PRIMARY KEY, document TEXT NOT NULL, state TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, available_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dead_letters(
          id TEXT PRIMARY KEY, document TEXT NOT NULL, reason TEXT NOT NULL,
          failed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS formation_permits(
          token_hash TEXT PRIMARY KEY, contract_hash TEXT NOT NULL,
          mission_id TEXT NOT NULL, action_id TEXT NOT NULL,
          state TEXT NOT NULL, issued_at TEXT NOT NULL, expires_at TEXT NOT NULL,
          consumed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS execution_journal(
          key TEXT PRIMARY KEY, contract_hash TEXT NOT NULL,
          request_hash TEXT NOT NULL, provider_id TEXT NOT NULL,
          action_id TEXT NOT NULL, state TEXT NOT NULL,
          fence_token TEXT NOT NULL, result_hash TEXT, result TEXT,
          event_id TEXT, started_at TEXT NOT NULL, completed_at TEXT,
          detail TEXT
        );
        CREATE TABLE IF NOT EXISTS mission_authority(
          mission_id TEXT PRIMARY KEY, current_version INTEGER NOT NULL,
          state TEXT NOT NULL, gate_decision TEXT NOT NULL,
          maximum_authority_class TEXT NOT NULL, maximum_cost REAL NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS effect_lease(
          id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL,
          fence_token TEXT, contract_hash TEXT, acquired_at TEXT, released_at TEXT
        );
        CREATE TABLE IF NOT EXISTS integrity_checkpoints(
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_count INTEGER NOT NULL,
          event_chain_root TEXT NOT NULL, state_root TEXT NOT NULL,
          observed_at TEXT NOT NULL, authority_id TEXT NOT NULL,
          signature TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fabric_metadata(
          key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        """
        with self._connect() as con:
            con.executescript(schema)
            store_id = self._expected_store_id or "STORE-" + secrets.token_hex(16)
            con.execute(
                "INSERT OR IGNORE INTO fabric_metadata(key,value) VALUES('store_id',?)",
                (store_id,),
            )
            actual_store_id = con.execute(
                "SELECT value FROM fabric_metadata WHERE key='store_id'"
            ).fetchone()["value"]
            if self._expected_store_id and actual_store_id != self._expected_store_id:
                raise PermissionError("database store identity does not match trusted configuration")
            event_columns = {row[1] for row in con.execute("PRAGMA table_info(events)")}
            migrated_event_chain = False
            if "previous_hash" not in event_columns:
                con.execute("ALTER TABLE events ADD COLUMN previous_hash TEXT NOT NULL DEFAULT ''")
                migrated_event_chain = True
            if "chain_hash" not in event_columns:
                con.execute("ALTER TABLE events ADD COLUMN chain_hash TEXT NOT NULL DEFAULT ''")
                migrated_event_chain = True
            if migrated_event_chain:
                previous_hash = "0" * 64
                for row in con.execute("SELECT sequence,id,content_hash FROM events ORDER BY sequence"):
                    chain_hash = digest_json(
                        {
                            "previous_hash": previous_hash,
                            "event_id": row["id"],
                            "content_hash": row["content_hash"],
                        }
                    )
                    con.execute(
                        "UPDATE events SET previous_hash=?,chain_hash=? WHERE sequence=?",
                        (previous_hash, chain_hash, row["sequence"]),
                    )
                    previous_hash = chain_hash

    @property
    def integrity_configured(self) -> bool:
        return self._integrity_key is not None

    def provision_integrity(self) -> dict[str, Any]:
        """One-time Genesis seal for a new empty database and absent external anchor."""
        self.initialize()
        if self._integrity_key is None:
            return {"state": "UNANCHORED", "provisioned": False}
        with self._connect() as con:
            local_count = con.execute(
                "SELECT COUNT(*) FROM integrity_checkpoints"
            ).fetchone()[0]
            store_id = con.execute(
                "SELECT value FROM fabric_metadata WHERE key='store_id'"
            ).fetchone()["value"]
        assert self._anchor_store is not None
        external = self._anchor_store.read(store_id)
        if local_count or external is not None:
            integrity = self.integrity_check()
            if integrity["state"] == "OK":
                return {**integrity, "provisioned": False, "already_provisioned": True}
            raise PermissionError("Genesis provisioning requires absent local and external anchors")
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            result = self._seal_with_connection(con, allow_genesis=True)
            con.commit()
            return {**result, "provisioned": True}
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _validate_snapshot(snapshot: dict[str, Any]) -> None:
        if snapshot.get("schema") != "CFBE-ACF-ESTATE-SNAPSHOT-V1":
            raise ValueError("unsupported snapshot schema")
        parse_utc(str(snapshot.get("snapshot_at", "")))
        for key in ("assets", "edges", "providers", "heartbeats"):
            if not isinstance(snapshot.get(key), list):
                raise ValueError(f"snapshot.{key} must be a list")
        reject_sensitive(snapshot)
        ids = [str(item.get("id", "")) for item in snapshot["assets"]]
        if any(not value for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("asset identifiers must be unique and nonempty")

    def apply_snapshot(self, snapshot: dict[str, Any]) -> dict[str, int]:
        self.initialize()
        self._validate_snapshot(snapshot)
        observed = canonical_utc(str(snapshot["snapshot_at"]))
        counts = {key: len(snapshot[key]) for key in ("assets", "edges", "providers", "heartbeats")}
        with self._verified_write() as con:
            existing = {row[0] for row in con.execute("SELECT id FROM assets")}
            incoming = {str(item["id"]) for item in snapshot["assets"]}
            known = existing | incoming
            for edge in snapshot["edges"]:
                if edge.get("source_id") not in known or edge.get("target_id") not in known:
                    raise ValueError("edge endpoint missing from estate")
            for heartbeat in snapshot["heartbeats"]:
                if heartbeat.get("node_id") not in known:
                    raise ValueError("heartbeat node missing from estate")
            for table in ("assets", "providers"):
                for item in snapshot[table]:
                    document = canonical_json(item)
                    con.execute(
                        f"""INSERT INTO {table}(id,document,content_hash,observed_at)
                        VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                        document=excluded.document,content_hash=excluded.content_hash,
                        observed_at=excluded.observed_at
                        WHERE julianday(excluded.observed_at) >= julianday({table}.observed_at)""",
                        (str(item["id"]), document, digest_json(item), observed),
                    )
            for edge in snapshot["edges"]:
                document = canonical_json(edge)
                con.execute(
                    """INSERT INTO edges(id,source_id,target_id,document,content_hash,observed_at)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,target_id=excluded.target_id,
                    document=excluded.document,content_hash=excluded.content_hash,
                    observed_at=excluded.observed_at
                    WHERE julianday(excluded.observed_at) >= julianday(edges.observed_at)""",
                    (edge["id"], edge["source_id"], edge["target_id"], document, digest_json(edge), observed),
                )
            for heartbeat in snapshot["heartbeats"]:
                item_observed = canonical_utc(str(heartbeat.get("observed_at", observed)))
                document = canonical_json(heartbeat)
                con.execute(
                    """INSERT INTO heartbeats(id,node_id,document,content_hash,observed_at)
                    VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    node_id=excluded.node_id,document=excluded.document,
                    content_hash=excluded.content_hash,observed_at=excluded.observed_at
                    WHERE julianday(excluded.observed_at) >= julianday(heartbeats.observed_at)""",
                    (heartbeat["id"], heartbeat["node_id"], document, digest_json(heartbeat), item_observed),
                )
        return counts

    def list_documents(self, table: str) -> list[dict[str, Any]]:
        if table not in _JSON_TABLES:
            raise ValueError("unsupported table")
        self.initialize()
        with self._connect() as con:
            return [json.loads(row["document"]) for row in con.execute(f"SELECT document FROM {table} ORDER BY id")]

    def snapshot(self) -> dict[str, Any]:
        integrity = self.integrity_check()
        if integrity["state"] != "OK":
            raise ValueError("application integrity verification failed")
        return {
            "schema": "CFBE-ACF-ESTATE-READBACK-V1",
            "read_at": utc_now(),
            **{name: self.list_documents(name) for name in ("assets", "edges", "providers", "heartbeats", "blockers")},
        }

    def append_event(self, event: CloudEvent) -> dict[str, Any]:
        self.initialize()
        value = event.to_dict()
        reject_sensitive(value, "event")
        document = canonical_json(value)
        content_hash = digest_json(value)
        with self._verified_write() as con:
            existing = con.execute(
                "SELECT content_hash,chain_hash FROM events WHERE id=?", (event.id,)
            ).fetchone()
            if existing:
                if existing["content_hash"] != content_hash:
                    raise ValueError("event id collision with different content")
                return {
                    "id": event.id,
                    "content_hash": content_hash,
                    "chain_hash": existing["chain_hash"],
                    "reused": True,
                }
            prior = con.execute(
                "SELECT chain_hash FROM events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = prior["chain_hash"] if prior else "0" * 64
            chain_hash = digest_json(
                {"previous_hash": previous_hash, "event_id": event.id, "content_hash": content_hash}
            )
            con.execute(
                """INSERT INTO events(
                id,event_type,source,subject,traceparent,document,content_hash,created_at,
                previous_hash,chain_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.id, event.type, event.source, event.subject, event.traceparent,
                    document, content_hash, canonical_utc(event.time), previous_hash, chain_hash,
                ),
            )
        return {
            "id": event.id,
            "content_hash": content_hash,
            "chain_hash": chain_hash,
            "reused": False,
        }

    def record_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        self.initialize()
        if self._proof_kernel is None:
            raise PermissionError("trusted proof kernel is not configured")
        reject_sensitive(receipt)
        self._proof_kernel.verify(receipt)
        receipt_id = str(receipt.get("receipt_id", ""))
        if not receipt_id:
            raise ValueError("receipt_id required")
        observed = str(receipt.get("observed_at", ""))
        parse_utc(observed)
        document = canonical_json(receipt)
        content_hash = digest_json(receipt)
        with self._verified_write() as con:
            existing = con.execute("SELECT content_hash FROM receipts WHERE id=?", (receipt_id,)).fetchone()
            if existing and existing["content_hash"] != content_hash:
                raise ValueError("receipt mutation prohibited")
            if not existing:
                source_stage = ProofStage(receipt.get("from_stage"))
                target_stage = ProofStage(receipt.get("to_stage"))
                source_index = PROOF_ORDER.index(source_stage)
                if source_index + 1 >= len(PROOF_ORDER) or PROOF_ORDER[source_index + 1] != target_stage:
                    raise ValueError("receipt stages cannot be skipped")
                rows = con.execute("SELECT document FROM receipts ORDER BY observed_at,id").fetchall()
                related = [
                    json.loads(row["document"])
                    for row in rows
                    if json.loads(row["document"]).get("mission_id") == receipt.get("mission_id")
                    and json.loads(row["document"]).get("mission_version") == receipt.get("mission_version")
                    and json.loads(row["document"]).get("action_id") == receipt.get("action_id")
                    and json.loads(row["document"]).get("provider_id") == receipt.get("provider_id")
                ]
                if related:
                    predecessor = related[-1]
                    if receipt.get("previous_receipt_hash") != predecessor.get("body_hash"):
                        raise ValueError("receipt predecessor hash mismatch")
                    if receipt.get("from_stage") != predecessor.get("to_stage"):
                        raise ValueError("receipt chain stage mismatch")
                elif receipt.get("from_stage") != "UNKNOWN" or receipt.get(
                    "previous_receipt_hash"
                ) != "0" * 64:
                    raise ValueError("receipt chain must begin at UNKNOWN genesis")
            con.execute(
                "INSERT OR IGNORE INTO receipts(id,document,content_hash,observed_at) VALUES(?,?,?,?)",
                (receipt_id, document, content_hash, observed),
            )
        return {"receipt_id": receipt_id, "content_hash": content_hash}

    def record_blockers(self, blockers: Iterable[dict[str, Any]]) -> int:
        self.initialize()
        count = 0
        with self._verified_write() as con:
            for blocker in blockers:
                reject_sensitive(blocker)
                blocker_id = str(blocker.get("id", ""))
                if not blocker_id:
                    raise ValueError("blocker.id required")
                observed = canonical_utc(str(blocker.get("observed_at", utc_now())))
                document = canonical_json(blocker)
                con.execute(
                    """INSERT INTO blockers(id,document,content_hash,observed_at)
                    VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    document=excluded.document,content_hash=excluded.content_hash,
                    observed_at=excluded.observed_at""",
                    (blocker_id, document, digest_json(blocker), observed),
                )
                count += 1
        return count

    def reconcile_blockers(
        self,
        *,
        desired_state_id: str,
        generation_hash: str,
        blockers: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Atomically supersede repaired blockers and persist the current generation."""
        self.initialize()
        current = [dict(item) for item in blockers]
        current_ids = {str(item["id"]) for item in current}
        now = utc_now()
        with self._verified_write() as con:
            rows = con.execute("SELECT id,document FROM blockers").fetchall()
            for row in rows:
                value = json.loads(row["document"])
                if (
                    value.get("desired_state_id") == desired_state_id
                    and value.get("state") == "OPEN"
                    and row["id"] not in current_ids
                ):
                    value["state"] = "SUPERSEDED"
                    value["resolved_at"] = now
                    value["resolved_by_generation"] = generation_hash
                    con.execute(
                        "UPDATE blockers SET document=?,content_hash=?,observed_at=? WHERE id=?",
                        (canonical_json(value), digest_json(value), now, row["id"]),
                    )
            for blocker in current:
                reject_sensitive(blocker)
                blocker["desired_state_id"] = desired_state_id
                blocker["generation_hash"] = generation_hash
                blocker["state"] = "OPEN"
                observed = canonical_utc(str(blocker.get("observed_at", now)))
                document = canonical_json(blocker)
                con.execute(
                    """INSERT INTO blockers(id,document,content_hash,observed_at)
                    VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    document=excluded.document,content_hash=excluded.content_hash,
                    observed_at=excluded.observed_at""",
                    (str(blocker["id"]), document, digest_json(blocker), observed),
                )
            active_rows = con.execute("SELECT document FROM blockers ORDER BY id").fetchall()
            active = [
                json.loads(row["document"])
                for row in active_rows
                if json.loads(row["document"]).get("desired_state_id") == desired_state_id
                and json.loads(row["document"]).get("state") == "OPEN"
            ]
        return active

    def active_blockers(self, desired_state_id: str | None = None) -> list[dict[str, Any]]:
        values = self.list_documents("blockers")
        return [
            value
            for value in values
            if value.get("state") == "OPEN"
            and (desired_state_id is None or value.get("desired_state_id") == desired_state_id)
        ]

    def get_idempotent(self, key: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as con:
            row = con.execute("SELECT result FROM idempotency WHERE key=?", (key,)).fetchone()
            return json.loads(row["result"]) if row else None

    def put_idempotent(self, key: str, action_id: str, request: Any, result: Any) -> dict[str, Any]:
        self.initialize()
        reject_sensitive(request, "idempotency_request")
        reject_sensitive(result, "idempotency_result")
        request_hash, result_hash = digest_json(request), digest_json(result)
        with self._verified_write() as con:
            row = con.execute(
                "SELECT request_hash,result_hash,result FROM idempotency WHERE key=?", (key,)
            ).fetchone()
            if row:
                if row["request_hash"] != request_hash:
                    raise ValueError("idempotency key reused with different request")
                return json.loads(row["result"])
            con.execute(
                """INSERT INTO idempotency(key,action_id,request_hash,result_hash,result,created_at)
                VALUES(?,?,?,?,?,?)""",
                (key, action_id, request_hash, result_hash, canonical_json(result), utc_now()),
            )
        return result

    def register_formation_permit(
        self,
        *,
        token_hash: str,
        contract_hash: str,
        mission_id: str,
        action_id: str,
        issued_at: str,
        expires_at: str,
    ) -> None:
        self.initialize()
        with self._verified_write() as con:
            con.execute(
                """INSERT INTO formation_permits(
                token_hash,contract_hash,mission_id,action_id,state,issued_at,expires_at)
                VALUES(?,?,?,?,?,?,?)""",
                (
                    token_hash, contract_hash, mission_id, action_id, "ISSUED",
                    canonical_utc(issued_at), canonical_utc(expires_at),
                ),
            )

    def set_mission_authority(
        self,
        *,
        mission_id: str,
        current_version: int,
        state: str,
        gate_decision: str,
        maximum_authority_class: str,
        maximum_cost: float,
    ) -> None:
        if state not in {"ACTIVE", "STOPPED", "SUPERSEDED"}:
            raise ValueError("invalid mission authority state")
        if gate_decision not in {"EXECUTE", "HOLD", "CANCEL"}:
            raise ValueError("invalid mission gate decision")
        if maximum_authority_class not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
            raise ValueError("invalid mission authority ceiling")
        mission_id = str(require_nonempty(mission_id, "mission_id"))
        current_version = require_int(current_version, "current_version", minimum=1)
        maximum_cost = require_finite_number(maximum_cost, "maximum_cost")
        self.initialize()
        with self._verified_write() as con:
            con.execute(
                """INSERT INTO mission_authority(
                mission_id,current_version,state,gate_decision,maximum_authority_class,
                maximum_cost,updated_at) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(mission_id) DO UPDATE SET
                current_version=excluded.current_version,state=excluded.state,
                gate_decision=excluded.gate_decision,
                maximum_authority_class=excluded.maximum_authority_class,
                maximum_cost=excluded.maximum_cost,updated_at=excluded.updated_at""",
                (
                    mission_id, current_version, state, gate_decision,
                    maximum_authority_class, maximum_cost, utc_now(),
                ),
            )

    def assert_mission_authority(
        self,
        *,
        mission_id: str,
        mission_version: int,
        authority_class: str,
        maximum_cost: float,
    ) -> dict[str, Any]:
        self.initialize()
        if self.integrity_check()["state"] != "OK":
            raise PermissionError("mission authority integrity verification failed")
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM mission_authority WHERE mission_id=?", (mission_id,)
            ).fetchone()
        if row is None:
            raise PermissionError("mission is not registered with Formation")
        if row["state"] != "ACTIVE" or row["gate_decision"] != "EXECUTE":
            raise PermissionError("mission is stopped, held or superseded")
        if row["current_version"] != mission_version:
            raise PermissionError("mission version is not current")
        authority_rank = {f"A{index}": index for index in range(6)}
        if authority_rank[authority_class] > authority_rank[row["maximum_authority_class"]]:
            raise PermissionError("contract authority exceeds mission ceiling")
        if maximum_cost > float(row["maximum_cost"]):
            raise PermissionError("contract cost exceeds mission ceiling")
        return dict(row)

    def execution_result(self, key: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as con:
            row = con.execute(
                "SELECT state,result,contract_hash,request_hash FROM execution_journal WHERE key=?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            return {
                "state": row["state"],
                "result": json.loads(row["result"]) if row["result"] else None,
                "contract_hash": row["contract_hash"],
                "request_hash": row["request_hash"],
            }

    def authorize_and_reserve_execution(
        self,
        *,
        token_hash: str,
        key: str,
        contract_hash: str,
        mission_id: str,
        mission_version: int,
        authority_class: str,
        maximum_cost: float,
        request_hash: str,
        provider_id: str,
        action_id: str,
        fence_token: str,
        effectful: bool,
    ) -> str:
        self.initialize()
        if self.integrity_check()["state"] != "OK":
            raise PermissionError("execution authority integrity verification failed")
        if authority_class not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
            raise ValueError("invalid execution authority class")
        mission_version = require_int(mission_version, "mission_version", minimum=1)
        maximum_cost = require_finite_number(maximum_cost, "maximum_cost")
        if not isinstance(effectful, bool):
            raise ValueError("effectful must be a JSON boolean")
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            self._assert_current_integrity_connection(con)
            mission = con.execute(
                "SELECT * FROM mission_authority WHERE mission_id=?", (mission_id,)
            ).fetchone()
            if mission is None:
                raise PermissionError("mission is not registered with Formation")
            if mission["state"] != "ACTIVE" or mission["gate_decision"] != "EXECUTE":
                raise PermissionError("mission is stopped, held or superseded")
            if mission["current_version"] != mission_version:
                raise PermissionError("mission version is not current")
            authority_rank = {f"A{index}": index for index in range(6)}
            if authority_rank[authority_class] > authority_rank[mission["maximum_authority_class"]]:
                raise PermissionError("contract authority exceeds mission ceiling")
            if maximum_cost > float(mission["maximum_cost"]):
                raise PermissionError("contract cost exceeds mission ceiling")
            permit = con.execute(
                """SELECT contract_hash,mission_id,action_id,state,expires_at
                FROM formation_permits WHERE token_hash=?""",
                (token_hash,),
            ).fetchone()
            if permit is None:
                raise PermissionError("formation permit not issued by trusted authority")
            if (
                permit["contract_hash"] != contract_hash
                or permit["mission_id"] != mission_id
                or permit["action_id"] != action_id
            ):
                raise PermissionError("formation permit contract binding mismatch")
            if permit["state"] != "ISSUED":
                raise PermissionError("formation permit already consumed")
            if parse_utc(permit["expires_at"]) <= parse_utc(utc_now()):
                raise PermissionError("formation permit expired")
            row = con.execute(
                "SELECT contract_hash,request_hash,state FROM execution_journal WHERE key=?",
                (key,),
            ).fetchone()
            if row:
                if row["contract_hash"] != contract_hash or row["request_hash"] != request_hash:
                    raise ValueError("idempotency key binding collision")
                con.commit()
                return str(row["state"])
            if effectful:
                lease = con.execute("SELECT state FROM effect_lease WHERE id=1").fetchone()
                if lease and lease["state"] in {"ACTIVE", "HELD_UNKNOWN"}:
                    raise RuntimeError("global effect lease is active or held unknown")
                con.execute(
                    """INSERT INTO effect_lease(
                    id,state,fence_token,contract_hash,acquired_at,released_at)
                    VALUES(1,'ACTIVE',?,?,?,NULL)
                    ON CONFLICT(id) DO UPDATE SET state='ACTIVE',fence_token=excluded.fence_token,
                    contract_hash=excluded.contract_hash,acquired_at=excluded.acquired_at,
                    released_at=NULL""",
                    (fence_token, contract_hash, utc_now()),
                )
            consumed_at = utc_now()
            updated = con.execute(
                """UPDATE formation_permits SET state='CONSUMED',consumed_at=?
                WHERE token_hash=? AND state='ISSUED'""",
                (consumed_at, token_hash),
            ).rowcount
            if updated != 1:
                raise PermissionError("formation permit already consumed")
            con.execute(
                """INSERT INTO execution_journal(
                key,contract_hash,request_hash,provider_id,action_id,state,fence_token,started_at)
                VALUES(?,?,?,?,?,'PENDING',?,?)""",
                (key, contract_hash, request_hash, provider_id, action_id, fence_token, utc_now()),
            )
            if self._integrity_key is not None:
                self._seal_with_connection(con)
            con.commit()
            return "RESERVED"
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def complete_execution(
        self,
        *,
        key: str,
        fence_token: str,
        result: dict[str, Any],
        event: CloudEvent,
    ) -> None:
        self.initialize()
        reject_sensitive(result, "adapter_result")
        event_value = event.to_dict()
        reject_sensitive(event_value, "event")
        event_document = canonical_json(event_value)
        event_content_hash = digest_json(event_value)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            self._assert_current_integrity_connection(con)
            row = con.execute(
                "SELECT state,fence_token FROM execution_journal WHERE key=?", (key,)
            ).fetchone()
            if row is None or row["state"] != "PENDING" or row["fence_token"] != fence_token:
                raise RuntimeError("execution fence lost or state ambiguous")
            prior = con.execute(
                "SELECT chain_hash FROM events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = prior["chain_hash"] if prior else "0" * 64
            chain_hash = digest_json(
                {
                    "previous_hash": previous_hash,
                    "event_id": event.id,
                    "content_hash": event_content_hash,
                }
            )
            con.execute(
                """INSERT INTO events(
                id,event_type,source,subject,traceparent,document,content_hash,created_at,
                previous_hash,chain_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.id, event.type, event.source, event.subject, event.traceparent,
                    event_document, event_content_hash, canonical_utc(event.time),
                    previous_hash, chain_hash,
                ),
            )
            result_document = canonical_json(result)
            con.execute(
                """UPDATE execution_journal SET state='COMMITTED',result_hash=?,result=?,
                event_id=?,completed_at=? WHERE key=? AND fence_token=? AND state='PENDING'""",
                (digest_json(result), result_document, event.id, utc_now(), key, fence_token),
            )
            con.execute(
                """UPDATE effect_lease SET state='IDLE',released_at=?
                WHERE id=1 AND fence_token=? AND state='ACTIVE'""",
                (utc_now(), fence_token),
            )
            if self._integrity_key is not None:
                self._seal_with_connection(con)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def mark_execution_ambiguous(self, *, key: str, fence_token: str, detail: str) -> None:
        self.initialize()
        with self._verified_write() as con:
            con.execute(
                """UPDATE execution_journal SET state='UNKNOWN',detail=?,completed_at=?
                WHERE key=? AND fence_token=? AND state='PENDING'""",
                (detail[:500], utc_now(), key, fence_token),
            )
            con.execute(
                """UPDATE effect_lease SET state='HELD_UNKNOWN',released_at=NULL
                WHERE id=1 AND fence_token=? AND state='ACTIVE'""",
                (fence_token,),
            )

    def verified_provider_stages(
        self,
        *,
        mission_id: str,
        mission_version: int,
        action_id: str,
    ) -> dict[str, str]:
        self.initialize()
        if self._proof_kernel is None:
            return {}
        stages: dict[str, str] = {}
        predecessors: dict[str, str] = {}
        with self._connect() as con:
            for row in con.execute("SELECT document FROM receipts ORDER BY observed_at,id"):
                value = json.loads(row["document"])
                if (
                    value.get("mission_id") != mission_id
                    or value.get("mission_version") != mission_version
                    or value.get("action_id") != action_id
                ):
                    continue
                self._proof_kernel.verify(value)
                provider_id = str(value["provider_id"])
                current = stages.get(provider_id, "UNKNOWN")
                previous = predecessors.get(provider_id, "0" * 64)
                if value.get("from_stage") != current:
                    raise ValueError("stored proof chain stage mismatch")
                if value.get("previous_receipt_hash") != previous:
                    raise ValueError("stored proof predecessor mismatch")
                source = ProofStage(current)
                target = ProofStage(value["to_stage"])
                index = PROOF_ORDER.index(source)
                if index + 1 >= len(PROOF_ORDER) or PROOF_ORDER[index + 1] != target:
                    raise ValueError("stored proof stages cannot be skipped")
                stages[provider_id] = target.value
                predecessors[provider_id] = str(value["body_hash"])
        return stages

    @staticmethod
    def _state_root(con: sqlite3.Connection) -> str:
        state: dict[str, Any] = {}
        for table in sorted(_JSON_TABLES):
            state[table] = [
                [row["id"], row["content_hash"]]
                for row in con.execute(
                    f"SELECT id,content_hash FROM {table} ORDER BY id"
                )
            ]
        state["events"] = [
            [row["sequence"], row["id"], row["chain_hash"]]
            for row in con.execute(
                "SELECT sequence,id,chain_hash FROM events ORDER BY sequence"
            )
        ]
        state["idempotency"] = [
            [row["key"], row["request_hash"], row["result_hash"]]
            for row in con.execute(
                "SELECT key,request_hash,result_hash FROM idempotency ORDER BY key"
            )
        ]
        state["execution_journal"] = [
            [
                row["key"], row["contract_hash"], row["request_hash"], row["state"],
                row["result_hash"], row["event_id"],
            ]
            for row in con.execute(
                """SELECT key,contract_hash,request_hash,state,result_hash,event_id
                FROM execution_journal ORDER BY key"""
            )
        ]
        state["formation_permits"] = [
            [
                row["token_hash"], row["contract_hash"], row["mission_id"],
                row["action_id"], row["state"], row["expires_at"],
            ]
            for row in con.execute(
                """SELECT token_hash,contract_hash,mission_id,action_id,state,expires_at
                FROM formation_permits ORDER BY token_hash"""
            )
        ]
        state["mission_authority"] = [
            [
                row["mission_id"], row["current_version"], row["state"],
                row["gate_decision"], row["maximum_authority_class"], row["maximum_cost"],
            ]
            for row in con.execute(
                """SELECT mission_id,current_version,state,gate_decision,
                maximum_authority_class,maximum_cost FROM mission_authority ORDER BY mission_id"""
            )
        ]
        state["effect_lease"] = [
            [row["id"], row["state"], row["fence_token"], row["contract_hash"]]
            for row in con.execute(
                "SELECT id,state,fence_token,contract_hash FROM effect_lease ORDER BY id"
            )
        ]
        return digest_json(state)

    def _seal_with_connection(
        self, con: sqlite3.Connection, *, allow_genesis: bool = False
    ) -> dict[str, Any]:
        if self._integrity_key is None:
            return {"state": "UNANCHORED"}
        con.row_factory = sqlite3.Row
        event_count = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        last = con.execute(
            "SELECT chain_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        store_id = con.execute(
            "SELECT value FROM fabric_metadata WHERE key='store_id'"
        ).fetchone()["value"]
        if self._expected_store_id and store_id != self._expected_store_id:
            raise PermissionError("database store identity does not match trusted configuration")
        assert self._anchor_store is not None
        trusted_before = self._anchor_store.read(store_id)
        latest = con.execute(
            "SELECT * FROM integrity_checkpoints ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if allow_genesis:
            if trusted_before is not None or latest is not None:
                raise PermissionError("Genesis provisioning requires absent local and external anchors")
            mutable_tables = (
                "assets", "edges", "providers", "heartbeats", "events", "receipts",
                "blockers", "idempotency", "outbox", "dead_letters", "formation_permits",
                "execution_journal", "mission_authority", "effect_lease",
            )
            if any(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in mutable_tables):
                raise PermissionError("Genesis provisioning requires a new empty database")
        else:
            if trusted_before is None or latest is None:
                raise PermissionError("trusted prior checkpoint required before resealing")
            prior_payload = {
                "checkpoint_id": latest["id"],
                "event_count": latest["event_count"],
                "event_chain_root": latest["event_chain_root"],
                "state_root": latest["state_root"],
                "observed_at": latest["observed_at"],
                "authority_id": latest["authority_id"],
            }
            prior_signature = hmac.new(
                self._integrity_key,
                canonical_json({"store_id": store_id, **prior_payload}).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if prior_payload != trusted_before or not hmac.compare_digest(
                latest["signature"], prior_signature
            ):
                raise PermissionError("trusted prior checkpoint mismatch")
        anchor = {
            "event_count": event_count,
            "event_chain_root": last["chain_hash"] if last else "0" * 64,
            "state_root": self._state_root(con),
            "observed_at": utc_now(),
            "authority_id": self._integrity_authority_id,
        }
        cursor = con.execute(
            """INSERT INTO integrity_checkpoints(
            event_count,event_chain_root,state_root,observed_at,authority_id,signature)
            VALUES(?,?,?,?,?,'')""",
            (
                anchor["event_count"], anchor["event_chain_root"], anchor["state_root"],
                anchor["observed_at"], anchor["authority_id"],
            ),
        )
        anchor["checkpoint_id"] = int(cursor.lastrowid)
        signed_payload = {"store_id": store_id, **anchor}
        signature = hmac.new(
            self._integrity_key,
            canonical_json(signed_payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        con.execute(
            "UPDATE integrity_checkpoints SET signature=? WHERE id=?",
            (signature, anchor["checkpoint_id"]),
        )
        self._anchor_store.commit(store_id, anchor)
        return {**anchor, "signature": signature, "state": "SEALED"}

    def seal_integrity_checkpoint(self) -> dict[str, Any]:
        self.initialize()
        if self._integrity_key is None:
            return {"state": "UNANCHORED"}
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            self._assert_current_integrity_connection(con)
            result = self._seal_with_connection(con)
            con.commit()
            return result
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _integrity_from_connection(
        con: sqlite3.Connection,
        *,
        integrity_key: bytes | None = None,
        integrity_authority_id: str = "",
        expected_anchor: dict[str, Any] | None = None,
        expected_store_id: str = "",
    ) -> dict[str, Any]:
        con.row_factory = sqlite3.Row
        sqlite_result = con.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required = {
            "assets", "edges", "providers", "heartbeats", "events", "receipts",
            "blockers", "idempotency", "execution_journal", "formation_permits",
            "mission_authority", "effect_lease", "integrity_checkpoints", "fabric_metadata",
        }
        issues = []
        if not required.issubset(tables):
            issues.append("missing_tables:" + ",".join(sorted(required - tables)))
        counts: dict[str, int] = {}
        for table in sorted(required & tables):
            counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in sorted(_JSON_TABLES & tables):
            for row in con.execute(f"SELECT id,document,content_hash FROM {table}"):
                try:
                    value = json.loads(row["document"])
                    if digest_json(value) != row["content_hash"]:
                        issues.append(f"row_hash_mismatch:{table}:{row['id']}")
                except Exception:
                    issues.append(f"invalid_json:{table}:{row['id']}")
        previous_hash = "0" * 64
        if "events" in tables:
            for row in con.execute(
                "SELECT id,document,content_hash,previous_hash,chain_hash FROM events ORDER BY sequence"
            ):
                try:
                    value = json.loads(row["document"])
                    expected_content = digest_json(value)
                    expected_chain = digest_json(
                        {
                            "previous_hash": previous_hash,
                            "event_id": row["id"],
                            "content_hash": expected_content,
                        }
                    )
                    if row["content_hash"] != expected_content:
                        issues.append(f"event_content_hash_mismatch:{row['id']}")
                    if row["previous_hash"] != previous_hash or row["chain_hash"] != expected_chain:
                        issues.append(f"event_chain_mismatch:{row['id']}")
                    previous_hash = row["chain_hash"]
                except Exception:
                    issues.append(f"invalid_event:{row['id']}")
        if "idempotency" in tables:
            for row in con.execute("SELECT key,result,result_hash FROM idempotency"):
                try:
                    if digest_json(json.loads(row["result"])) != row["result_hash"]:
                        issues.append(f"idempotency_hash_mismatch:{row['key']}")
                except Exception:
                    issues.append(f"invalid_idempotency_result:{row['key']}")
        if "execution_journal" in tables:
            for row in con.execute(
                "SELECT key,state,result,result_hash FROM execution_journal WHERE state='COMMITTED'"
            ):
                try:
                    if not row["result"] or digest_json(json.loads(row["result"])) != row["result_hash"]:
                        issues.append(f"execution_hash_mismatch:{row['key']}")
                except Exception:
                    issues.append(f"invalid_execution_result:{row['key']}")
        anchor_state = "UNCONFIGURED"
        if integrity_key is not None:
            store_row = con.execute(
                "SELECT value FROM fabric_metadata WHERE key='store_id'"
            ).fetchone()
            store_id = store_row["value"] if store_row else ""
            if not expected_store_id or store_id != expected_store_id:
                issues.append("database_store_identity_mismatch")
            checkpoint = con.execute(
                "SELECT * FROM integrity_checkpoints ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if checkpoint is None:
                issues.append("integrity_checkpoint_missing")
                anchor_state = "MISSING"
            else:
                payload = {
                    "checkpoint_id": checkpoint["id"],
                    "event_count": checkpoint["event_count"],
                    "event_chain_root": checkpoint["event_chain_root"],
                    "state_root": checkpoint["state_root"],
                    "observed_at": checkpoint["observed_at"],
                    "authority_id": checkpoint["authority_id"],
                }
                expected_signature = hmac.new(
                    integrity_key,
                    canonical_json({"store_id": store_id, **payload}).encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
                current_count = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                current_root = previous_hash
                current_state_root = FabricStore._state_root(con)
                if checkpoint["authority_id"] != integrity_authority_id:
                    issues.append("integrity_authority_mismatch")
                if not hmac.compare_digest(checkpoint["signature"], expected_signature):
                    issues.append("integrity_checkpoint_signature_invalid")
                if checkpoint["event_count"] != current_count:
                    issues.append("anchored_event_count_mismatch")
                if checkpoint["event_chain_root"] != current_root:
                    issues.append("anchored_event_root_mismatch")
                if checkpoint["state_root"] != current_state_root:
                    issues.append("anchored_state_root_mismatch")
                if expected_anchor is None:
                    issues.append("external_trusted_anchor_missing")
                elif any(expected_anchor.get(key) != value for key, value in payload.items()):
                    issues.append("external_trusted_anchor_mismatch")
                anchor_state = "VERIFIED" if not issues else "FAILED"
        state = "OK" if sqlite_result == "ok" and not issues else "FAILED"
        return {
            "state": state,
            "sqlite": sqlite_result,
            "application_issues": sorted(set(issues)),
            "event_chain_root": previous_hash,
            "integrity_anchor": anchor_state,
            "counts": counts,
        }

    def integrity_check(self) -> dict[str, Any]:
        self.initialize()
        with self._connect() as con:
            store_id = con.execute(
                "SELECT value FROM fabric_metadata WHERE key='store_id'"
            ).fetchone()["value"]
            expected_anchor = (
                self._anchor_store.read(store_id) if self._anchor_store is not None else None
            )
            return self._integrity_from_connection(
                con,
                integrity_key=self._integrity_key,
                integrity_authority_id=self._integrity_authority_id,
                expected_anchor=expected_anchor,
                expected_store_id=self._expected_store_id,
            )

    def backup(self, destination: str | Path) -> dict[str, Any]:
        self.initialize()
        if self._integrity_key is None:
            raise PermissionError("signed backup requires a configured integrity authority")
        self.seal_integrity_checkpoint()
        if self.integrity_check()["state"] != "OK":
            raise ValueError("source integrity failed")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as source, sqlite3.connect(target) as out:
            source.backup(out)
        with target.open("rb") as handle:
            os.fsync(handle.fileno())
        integrity = FabricStore(
            target,
            integrity_key=self._integrity_key,
            integrity_authority_id=self._integrity_authority_id,
            anchor_store=self._anchor_store,
            expected_store_id=self._expected_store_id,
        ).integrity_check()
        if integrity["state"] != "OK":
            raise ValueError("backup integrity failed")
        file_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest = {
            "schema": "CFBE-ACF-BACKUP-MANIFEST-V2",
            "database_sha256": file_hash,
            "created_at": utc_now(),
            "authority_id": self._integrity_authority_id,
            "integrity": integrity,
        }
        manifest["signature"] = hmac.new(
            self._integrity_key,
            canonical_json(manifest).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        manifest_path = Path(str(target) + ".manifest.json")
        fd, temp_name = tempfile.mkstemp(
            dir=manifest_path.parent, prefix=manifest_path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(canonical_json(manifest))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, manifest_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return {
            "destination": str(target),
            "manifest": str(manifest_path),
            "sha256": file_hash,
            "integrity": integrity,
        }

    @classmethod
    def restore(
        cls,
        backup: str | Path,
        destination: str | Path,
        *,
        integrity_key: bytes,
        integrity_authority_id: str,
        anchor_store: TrustedAnchorStore,
        expected_store_id: str,
        proof_kernel: ProofKernel | None = None,
    ) -> "FabricStore":
        if len(integrity_key) < 32 or not integrity_authority_id.strip():
            raise ValueError("trusted integrity authority is required for restore")
        backup_path = Path(backup)
        if not backup_path.is_file() or backup_path.stat().st_size == 0:
            raise FileNotFoundError("backup database does not exist")
        manifest_path = Path(str(backup_path) + ".manifest.json")
        if not manifest_path.is_file():
            raise ValueError("backup provenance manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "CFBE-ACF-BACKUP-MANIFEST-V2":
            raise ValueError("unsupported backup manifest")
        signature = str(manifest.pop("signature", ""))
        expected_signature = hmac.new(
            integrity_key,
            canonical_json(manifest).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if manifest.get("authority_id") != integrity_authority_id or not hmac.compare_digest(
            signature, expected_signature
        ):
            raise ValueError("backup manifest signature invalid")
        actual_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
        if actual_hash != manifest.get("database_sha256"):
            raise ValueError("backup provenance hash mismatch")
        source_con = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
        source_con.row_factory = sqlite3.Row
        try:
            source_store_id = source_con.execute(
                "SELECT value FROM fabric_metadata WHERE key='store_id'"
            ).fetchone()["value"]
            source_integrity = cls._integrity_from_connection(
                source_con,
                integrity_key=integrity_key,
                integrity_authority_id=integrity_authority_id,
                expected_anchor=anchor_store.read(source_store_id),
                expected_store_id=expected_store_id,
            )
        finally:
            source_con.close()
        if source_integrity["state"] != "OK":
            raise ValueError("backup integrity failed")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=target.parent, prefix=target.name + ".", suffix=".restore"
        )
        os.close(fd)
        temp_path = Path(temp_name)
        prior: Path | None = None
        try:
            shutil.copy2(backup_path, temp_path)
            temp_con = sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)
            temp_con.row_factory = sqlite3.Row
            try:
                temp_store_id = temp_con.execute(
                    "SELECT value FROM fabric_metadata WHERE key='store_id'"
                ).fetchone()["value"]
                temp_integrity = cls._integrity_from_connection(
                    temp_con,
                    integrity_key=integrity_key,
                    integrity_authority_id=integrity_authority_id,
                    expected_anchor=anchor_store.read(temp_store_id),
                    expected_store_id=expected_store_id,
                )
            finally:
                temp_con.close()
            if temp_integrity["state"] != "OK":
                raise ValueError("restored integrity failed before activation")
            with temp_path.open("rb") as handle:
                os.fsync(handle.fileno())
            if target.exists():
                prior = target.with_name(target.name + ".previous." + secrets.token_hex(6))
                os.replace(target, prior)
            os.replace(temp_path, target)
        except Exception:
            if prior and prior.exists() and not target.exists():
                os.replace(prior, target)
            raise
        finally:
            if temp_path.exists():
                temp_path.unlink()
        restored = cls(
            target,
            proof_kernel=proof_kernel,
            integrity_key=integrity_key,
            integrity_authority_id=integrity_authority_id,
            anchor_store=anchor_store,
            expected_store_id=expected_store_id,
        )
        if restored.integrity_check()["state"] != "OK":
            if prior and prior.exists():
                os.replace(prior, target)
            raise ValueError("restored integrity failed after activation")
        return restored
