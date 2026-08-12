from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping


SYSTEMS = ("CRM", "SIS", "LMS", "ERP", "BI")
ALLOWED_EVENT_FIELDS = {
    "event_id",
    "canonical_student_id",
    "source_system",
    "event_type",
    "status",
    "programme",
    "amount",
}


@dataclass(frozen=True)
class IntegrationEvent:
    event_id: str
    canonical_student_id: str
    source_system: str
    event_type: str
    status: str
    programme: str | None = None
    amount: float | None = None

    def payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class IntegrationReceipt:
    event_id: str
    canonical_student_id: str
    route: tuple[str, ...]
    target_state: str
    semantic_readback: str
    attempt_count: int
    dead_lettered: bool
    payload_sha256: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["route"] = list(self.route)
        return payload


class HigherEdIntegrationLab:
    """Synthetic CRM→SIS→LMS→ERP→BI integration reference.

    The lab proves local integration mechanics only: canonical identity, data
    minimisation, idempotency, retry/dead-letter handling, semantic target
    readback, lineage and reproducible executive KPIs. It is not a real
    university deployment and contains no real student data.
    """

    maturity = "LOCAL_RUNTIME_VERIFIED"

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                canonical_student_id TEXT PRIMARY KEY,
                programme TEXT,
                lifecycle_state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                canonical_student_id TEXT NOT NULL,
                source_system TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS target_state (
                event_id TEXT PRIMARY KEY,
                target_system TEXT NOT NULL,
                semantic_state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lineage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                from_system TEXT NOT NULL,
                to_system TEXT NOT NULL,
                semantic_state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS finance (
                canonical_student_id TEXT PRIMARY KEY,
                outstanding_amount REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS assessments (
                canonical_student_id TEXT NOT NULL,
                status TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def payload_sha256(cls, payload: Mapping[str, object]) -> str:
        return hashlib.sha256(cls._canonical_json(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def validate_event(event: IntegrationEvent) -> None:
        if event.source_system not in SYSTEMS:
            raise ValueError("Unknown source system")
        if not event.event_id.strip() or not event.canonical_student_id.strip():
            raise ValueError("event_id and canonical_student_id are required")
        payload = event.payload()
        unknown = set(payload).difference(ALLOWED_EVENT_FIELDS)
        if unknown:
            raise ValueError(f"Unexpected fields: {sorted(unknown)}")
        if event.amount is not None and event.amount < 0:
            raise ValueError("amount cannot be negative")

    def _route_for(self, event_type: str) -> tuple[str, ...]:
        routes = {
            "APPLICATION_SUBMITTED": ("CRM", "SIS", "BI"),
            "ADMISSION_ACCEPTED": ("CRM", "SIS", "BI"),
            "REGISTERED": ("SIS", "LMS", "ERP", "BI"),
            "LEARNING_ACTIVE": ("LMS", "BI"),
            "ASSESSMENT_COMPLETED": ("LMS", "SIS", "BI"),
            "FEE_BALANCE_UPDATED": ("ERP", "SIS", "BI"),
            "GRADUATED": ("SIS", "LMS", "ERP", "BI"),
        }
        if event_type not in routes:
            raise ValueError(f"Unsupported event_type: {event_type}")
        return routes[event_type]

    def process(self, event: IntegrationEvent, *, fail_first_attempt: bool = False) -> IntegrationReceipt:
        self.validate_event(event)
        payload = event.payload()
        digest = self.payload_sha256(payload)
        existing = self.conn.execute("SELECT * FROM events WHERE event_id = ?", (event.event_id,)).fetchone()
        if existing:
            if existing["payload_sha256"] != digest:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return self._receipt(event.event_id)

        route = self._route_for(event.event_type)
        self.conn.execute(
            "INSERT INTO events(event_id, canonical_student_id, source_system, event_type, payload_sha256, attempt_count, state) VALUES(?,?,?,?,?,0,'QUEUED')",
            (event.event_id, event.canonical_student_id, event.source_system, event.event_type, digest),
        )
        self.conn.commit()

        attempt = 0
        while attempt < 2:
            attempt += 1
            self.conn.execute("UPDATE events SET attempt_count=? WHERE event_id=?", (attempt, event.event_id))
            if fail_first_attempt and attempt == 1:
                self.conn.execute("UPDATE events SET state='RETRY', error='SYNTHETIC_TRANSIENT_FAILURE' WHERE event_id=?", (event.event_id,))
                self.conn.commit()
                continue
            try:
                self._apply_semantics(event, route)
                self.conn.execute("UPDATE events SET state='DONE', error=NULL WHERE event_id=?", (event.event_id,))
                self.conn.commit()
                return self._receipt(event.event_id)
            except Exception as exc:
                self.conn.execute("UPDATE events SET state='RETRY', error=? WHERE event_id=?", (str(exc), event.event_id))
                self.conn.commit()

        self.conn.execute("UPDATE events SET state='DEAD_LETTER' WHERE event_id=?", (event.event_id,))
        self.conn.commit()
        return self._receipt(event.event_id)

    def _apply_semantics(self, event: IntegrationEvent, route: tuple[str, ...]) -> None:
        lifecycle = {
            "APPLICATION_SUBMITTED": "APPLICANT",
            "ADMISSION_ACCEPTED": "ADMITTED",
            "REGISTERED": "REGISTERED",
            "LEARNING_ACTIVE": "ACTIVE_LEARNER",
            "ASSESSMENT_COMPLETED": "ASSESSMENT_ACTIVE",
            "FEE_BALANCE_UPDATED": "FINANCE_UPDATED",
            "GRADUATED": "GRADUATED",
        }[event.event_type]

        current = self.conn.execute("SELECT lifecycle_state, programme FROM students WHERE canonical_student_id=?", (event.canonical_student_id,)).fetchone()
        programme = event.programme if event.programme is not None else (current["programme"] if current else None)
        self.conn.execute(
            "INSERT INTO students(canonical_student_id, programme, lifecycle_state) VALUES(?,?,?) ON CONFLICT(canonical_student_id) DO UPDATE SET programme=excluded.programme, lifecycle_state=excluded.lifecycle_state",
            (event.canonical_student_id, programme, lifecycle),
        )

        if event.event_type == "ASSESSMENT_COMPLETED":
            self.conn.execute("INSERT INTO assessments(canonical_student_id, status) VALUES(?,?)", (event.canonical_student_id, event.status))
        if event.event_type == "FEE_BALANCE_UPDATED":
            self.conn.execute(
                "INSERT INTO finance(canonical_student_id, outstanding_amount) VALUES(?,?) ON CONFLICT(canonical_student_id) DO UPDATE SET outstanding_amount=excluded.outstanding_amount",
                (event.canonical_student_id, float(event.amount or 0.0)),
            )

        for source, target in zip(route, route[1:]):
            self.conn.execute(
                "INSERT INTO lineage(event_id, from_system, to_system, semantic_state) VALUES(?,?,?,?)",
                (event.event_id, source, target, lifecycle),
            )

        target = route[-1]
        self.conn.execute(
            "INSERT OR REPLACE INTO target_state(event_id, target_system, semantic_state) VALUES(?,?,?)",
            (event.event_id, target, lifecycle),
        )

    def _receipt(self, event_id: str) -> IntegrationReceipt:
        event = self.conn.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        if event is None:
            raise KeyError(event_id)
        target = self.conn.execute("SELECT * FROM target_state WHERE event_id=?", (event_id,)).fetchone()
        route = self._route_for(event["event_type"])
        dead = event["state"] == "DEAD_LETTER"
        semantic = "UNVERIFIED" if target is None else str(target["semantic_state"])
        return IntegrationReceipt(
            event_id=str(event["event_id"]),
            canonical_student_id=str(event["canonical_student_id"]),
            route=route,
            target_state=str(event["state"]),
            semantic_readback=semantic,
            attempt_count=int(event["attempt_count"]),
            dead_lettered=dead,
            payload_sha256=str(event["payload_sha256"]),
        )

    def executive_kpis(self) -> dict[str, object]:
        states = {row["lifecycle_state"]: row["count"] for row in self.conn.execute("SELECT lifecycle_state, COUNT(*) AS count FROM students GROUP BY lifecycle_state")}
        completed_assessments = self.conn.execute("SELECT COUNT(*) AS count FROM assessments WHERE status='COMPLETED'").fetchone()["count"]
        outstanding = self.conn.execute("SELECT COALESCE(SUM(outstanding_amount), 0) AS total FROM finance").fetchone()["total"]
        processed = self.conn.execute("SELECT COUNT(*) AS count FROM events WHERE state='DONE'").fetchone()["count"]
        retries = self.conn.execute("SELECT COUNT(*) AS count FROM events WHERE attempt_count > 1").fetchone()["count"]
        return {
            "applications_or_applicants": int(states.get("APPLICANT", 0)),
            "admitted": int(states.get("ADMITTED", 0)),
            "registered": int(states.get("REGISTERED", 0)),
            "active_learners": int(states.get("ACTIVE_LEARNER", 0)),
            "graduated": int(states.get("GRADUATED", 0)),
            "completed_assessments": int(completed_assessments),
            "outstanding_amount_synthetic": float(outstanding),
            "events_processed": int(processed),
            "events_retried": int(retries),
            "truth_boundary": "Synthetic operational metrics from local test data; not real institutional KPIs or student outcomes.",
        }

    def lineage_receipt(self) -> dict[str, object]:
        rows = [dict(row) for row in self.conn.execute("SELECT event_id, from_system, to_system, semantic_state FROM lineage ORDER BY id")]
        payload = {"systems": list(SYSTEMS), "lineage": rows, "maturity": self.maturity}
        payload["sha256"] = self.payload_sha256(payload)
        payload["truth_boundary"] = "Local synthetic integration proof only; no provider deployment or real student data."
        return payload


def run_reference_scenario(events: Iterable[IntegrationEvent]) -> dict[str, object]:
    lab = HigherEdIntegrationLab()
    receipts = [lab.process(event).to_dict() for event in events]
    return {
        "receipts": receipts,
        "kpis": lab.executive_kpis(),
        "lineage": lab.lineage_receipt(),
        "safe_claim": (
            "Implemented and locally verified a synthetic higher-education integration reference spanning CRM, SIS, LMS, ERP and BI with canonical identity, idempotency, retry handling, semantic readback, lineage and executive KPI generation."
        ),
        "forbidden_claims": [
            "deployed at a university",
            "integrated real student systems",
            "processed real student data",
            "improved real retention or throughput",
            "provider verified",
        ],
    }
