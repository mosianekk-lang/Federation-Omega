from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Mapping
import json
import sqlite3

from .learning import LearningEvent
from .models import Claim, Domain, EvidenceRef, EvidenceStatus, Event, InformationClass, canonical_json, stable_sha256, utc_now_iso


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


class SqliteStateStore:
    """Tenant-scoped durable state store for local/private execution adapters.

    SQLite is the reference implementation; production persistence may be
    replaced provided the same transaction, idempotency and isolation
    semantics remain intact.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def close(self) -> None:
        self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def _init_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
              tenant_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              source TEXT NOT NULL,
              subject_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              domain TEXT NOT NULL,
              information_class TEXT NOT NULL,
              materiality REAL NOT NULL,
              occurred_at TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (tenant_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS claims (
              tenant_id TEXT NOT NULL,
              claim_id TEXT NOT NULL,
              subject_id TEXT NOT NULL,
              predicate TEXT NOT NULL,
              value_json TEXT NOT NULL,
              status TEXT NOT NULL,
              evidence_json TEXT NOT NULL,
              information_class TEXT NOT NULL,
              domain TEXT NOT NULL,
              confidence REAL NOT NULL,
              assumptions_json TEXT NOT NULL,
              supersedes TEXT,
              created_at TEXT NOT NULL,
              fingerprint TEXT NOT NULL,
              PRIMARY KEY (tenant_id, claim_id)
            );
            CREATE INDEX IF NOT EXISTS idx_claims_tenant_subject ON claims(tenant_id, subject_id, predicate);
            CREATE TABLE IF NOT EXISTS dependencies (
              tenant_id TEXT NOT NULL,
              source_subject TEXT NOT NULL,
              dependent_subject TEXT NOT NULL,
              PRIMARY KEY (tenant_id, source_subject, dependent_subject)
            );
            CREATE TABLE IF NOT EXISTS idempotency (
              tenant_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              request_hash TEXT NOT NULL,
              result_json TEXT NOT NULL,
              result_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (tenant_id, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS learning_events (
              tenant_id TEXT NOT NULL,
              sequence_no INTEGER NOT NULL,
              event_type TEXT NOT NULL,
              category TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              previous_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (tenant_id, sequence_no),
              UNIQUE (tenant_id, event_hash)
            );
            CREATE TABLE IF NOT EXISTS restrictions (
              tenant_id TEXT NOT NULL,
              restriction_id TEXT NOT NULL,
              issuer_id TEXT,
              security_id TEXT,
              reason TEXT NOT NULL,
              information_class TEXT NOT NULL,
              start_at TEXT NOT NULL,
              review_at TEXT,
              cleared_at TEXT,
              PRIMARY KEY (tenant_id, restriction_id)
            );
            CREATE INDEX IF NOT EXISTS idx_restrictions_lookup ON restrictions(tenant_id, issuer_id, security_id, cleared_at);
            CREATE TABLE IF NOT EXISTS outcome_consents (
              tenant_id TEXT PRIMARY KEY,
              share_aggregated INTEGER NOT NULL,
              minimum_cohort INTEGER NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outcomes (
              observation_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              cohort TEXT NOT NULL,
              metric TEXT NOT NULL,
              predicted REAL NOT NULL,
              actual REAL NOT NULL,
              observed_at TEXT NOT NULL,
              metadata_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_outcomes_cohort_metric ON outcomes(cohort, metric);
            """
        )

    def quick_check(self) -> bool:
        return self._connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"

    def append_event(self, tenant_id: str, event: Event) -> bool:
        event.validate()
        payload = _plain(event.payload)
        digest = stable_sha256(payload)
        cur = self._connection.execute(
            """INSERT OR IGNORE INTO events
            (tenant_id,event_id,event_type,source,subject_id,payload_json,domain,information_class,materiality,occurred_at,payload_hash,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tenant_id, event.event_id, event.event_type, event.source, event.subject_id, canonical_json(payload), event.domain.value,
             event.information_class.value, event.materiality, event.occurred_at, digest, utc_now_iso()),
        )
        return cur.rowcount == 1

    def load_events(self, tenant_id: str) -> list[Event]:
        rows = self._connection.execute("SELECT * FROM events WHERE tenant_id=? ORDER BY created_at,event_id", (tenant_id,)).fetchall()
        return [Event(
            event_type=r["event_type"], source=r["source"], subject_id=r["subject_id"], payload=json.loads(r["payload_json"]),
            domain=Domain(r["domain"]), information_class=InformationClass(r["information_class"]), materiality=float(r["materiality"]),
            event_id=r["event_id"], occurred_at=r["occurred_at"]
        ) for r in rows]

    def save_claim(self, tenant_id: str, claim: Claim) -> None:
        claim.validate()
        self._connection.execute(
            """INSERT INTO claims
            (tenant_id,claim_id,subject_id,predicate,value_json,status,evidence_json,information_class,domain,confidence,assumptions_json,supersedes,created_at,fingerprint)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id,claim_id) DO UPDATE SET
              value_json=excluded.value_json,status=excluded.status,evidence_json=excluded.evidence_json,
              information_class=excluded.information_class,domain=excluded.domain,confidence=excluded.confidence,
              assumptions_json=excluded.assumptions_json,supersedes=excluded.supersedes,fingerprint=excluded.fingerprint
            """,
            (tenant_id, claim.claim_id, claim.subject_id, claim.predicate, canonical_json(claim.value), claim.status.value,
             canonical_json([_plain(e) for e in claim.evidence]), claim.information_class.value, claim.domain.value, claim.confidence,
             canonical_json(claim.assumptions), claim.supersedes, claim.created_at, claim.fingerprint()),
        )

    def load_claims(self, tenant_id: str) -> list[Claim]:
        rows = self._connection.execute("SELECT * FROM claims WHERE tenant_id=? ORDER BY created_at,claim_id", (tenant_id,)).fetchall()
        result: list[Claim] = []
        for r in rows:
            evidence = [EvidenceRef(**e) for e in json.loads(r["evidence_json"])]
            result.append(Claim(
                subject_id=r["subject_id"], predicate=r["predicate"], value=json.loads(r["value_json"]),
                status=EvidenceStatus(r["status"]), evidence=evidence, information_class=InformationClass(r["information_class"]),
                domain=Domain(r["domain"]), confidence=float(r["confidence"]), assumptions=list(json.loads(r["assumptions_json"])),
                supersedes=r["supersedes"], claim_id=r["claim_id"], created_at=r["created_at"]
            ))
        return result

    def add_dependency(self, tenant_id: str, source_subject: str, dependent_subject: str) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO dependencies(tenant_id,source_subject,dependent_subject) VALUES (?,?,?)",
            (tenant_id, source_subject, dependent_subject),
        )

    def load_dependencies(self, tenant_id: str) -> list[tuple[str, str]]:
        rows = self._connection.execute("SELECT source_subject,dependent_subject FROM dependencies WHERE tenant_id=? ORDER BY source_subject,dependent_subject", (tenant_id,)).fetchall()
        return [(r[0], r[1]) for r in rows]

    def get_idempotency_record(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        row = self._connection.execute("SELECT request_hash,result_json,result_hash FROM idempotency WHERE tenant_id=? AND idempotency_key=?", (tenant_id, key)).fetchone()
        if not row:
            return None
        return {"request_hash": row["request_hash"], "result": json.loads(row["result_json"]), "result_hash": row["result_hash"]}

    def get_idempotent_result(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        record = self.get_idempotency_record(tenant_id, key)
        return record["result"] if record else None

    def save_idempotent_result(self, tenant_id: str, key: str, result: Mapping[str, Any], request_hash: str = "") -> str:
        plain = _plain(result)
        digest = stable_sha256(plain)
        self._connection.execute(
            "INSERT OR REPLACE INTO idempotency(tenant_id,idempotency_key,request_hash,result_json,result_hash,created_at) VALUES (?,?,?,?,?,?)",
            (tenant_id, key, request_hash, canonical_json(plain), digest, utc_now_iso()),
        )
        return digest

    def append_learning(self, tenant_id: str, event_type: str, category: str, payload: Mapping[str, Any]) -> LearningEvent:
        row = self._connection.execute("SELECT sequence_no,event_hash FROM learning_events WHERE tenant_id=? ORDER BY sequence_no DESC LIMIT 1", (tenant_id,)).fetchone()
        sequence = (row[0] + 1) if row else 1
        previous = row[1] if row else "GENESIS"
        created = utc_now_iso()
        digest = LearningEvent.calculate_hash(event_type, category, _plain(payload), previous, created)
        self._connection.execute(
            "INSERT INTO learning_events(tenant_id,sequence_no,event_type,category,payload_json,previous_hash,event_hash,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (tenant_id, sequence, event_type, category, canonical_json(_plain(payload)), previous, digest, created),
        )
        return LearningEvent(event_type, category, dict(_plain(payload)), previous, created, digest)

    def verify_learning_chain(self, tenant_id: str) -> bool:
        rows = self._connection.execute("SELECT * FROM learning_events WHERE tenant_id=? ORDER BY sequence_no", (tenant_id,)).fetchall()
        previous = "GENESIS"
        for r in rows:
            payload = json.loads(r["payload_json"])
            expected = LearningEvent.calculate_hash(r["event_type"], r["category"], payload, r["previous_hash"], r["created_at"])
            if r["previous_hash"] != previous or r["event_hash"] != expected:
                return False
            previous = r["event_hash"]
        return True

    def tenant_state_digest(self, tenant_id: str) -> str:
        claims = [dict(r) for r in self._connection.execute("SELECT * FROM claims WHERE tenant_id=? ORDER BY claim_id", (tenant_id,)).fetchall()]
        deps = [dict(r) for r in self._connection.execute("SELECT * FROM dependencies WHERE tenant_id=? ORDER BY source_subject,dependent_subject", (tenant_id,)).fetchall()]
        events = [dict(r) for r in self._connection.execute("SELECT * FROM events WHERE tenant_id=? ORDER BY event_id", (tenant_id,)).fetchall()]
        learning = [dict(r) for r in self._connection.execute("SELECT * FROM learning_events WHERE tenant_id=? ORDER BY sequence_no", (tenant_id,)).fetchall()]
        return stable_sha256({"claims": claims, "dependencies": deps, "events": events, "learning": learning})

    def count_rows(self, table: str, tenant_id: str) -> int:
        if table not in {"events", "claims", "dependencies", "idempotency", "learning_events", "restrictions", "outcomes"}:
            raise ValueError("unsupported table")
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_id=?", (tenant_id,)).fetchone()[0])
