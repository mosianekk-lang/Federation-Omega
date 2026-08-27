from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import local
from typing import Any, Iterator, Mapping
import json

from .learning import LearningEvent
from .models import (
    Claim,
    Domain,
    EvidenceRef,
    EvidenceStatus,
    Event,
    InformationClass,
    canonical_json,
    stable_sha256,
    utc_now_iso,
)
from .store import _plain


class PostgresStateStore:
    """Pooled, tenant-scoped PostgreSQL implementation of the CIOS state contract."""

    def __init__(
        self,
        dsn: str,
        *,
        min_pool_size: int = 1,
        max_pool_size: int = 8,
        timeout_seconds: float = 10.0,
        apply_migrations: bool = False,
        pool_factory: Any | None = None,
    ) -> None:
        if not dsn.strip():
            raise ValueError("PostgreSQL DSN is required")
        if not 1 <= min_pool_size <= max_pool_size <= 16:
            raise ValueError("PostgreSQL pool must satisfy 1 <= min <= max <= 16")
        if pool_factory is None:
            try:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL runtime requires psycopg and psycopg_pool"
                ) from exc
            pool_factory = lambda: ConnectionPool(
                conninfo=dsn,
                min_size=min_pool_size,
                max_size=max_pool_size,
                timeout=timeout_seconds,
                kwargs={"autocommit": True, "row_factory": dict_row},
                check=ConnectionPool.check_connection,
                open=True,
            )
        self.dsn = dsn
        self._pool = pool_factory()
        self._local = local()
        if apply_migrations:
            self.apply_migrations()

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        active = getattr(self._local, "connection", None)
        if active is not None:
            yield active
            return
        with self._pool.connection() as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        if getattr(self._local, "connection", None) is not None:
            raise RuntimeError("nested store transactions are not supported")
        with self._pool.connection() as connection:
            with connection.transaction():
                self._local.connection = connection
                try:
                    yield connection
                finally:
                    self._local.connection = None

    def apply_migrations(self) -> None:
        sql = (Path(__file__).with_name("migrations") / "0001_postgres_state.sql").read_text(
            encoding="utf-8"
        )
        with self._pool.connection() as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("cios-state-migrations",))
                connection.execute(sql)

    @staticmethod
    def _decoded(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    def quick_check(self) -> bool:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT to_regclass('public.cios_events') AS events, "
                    "to_regclass('public.cios_idempotency') AS idempotency"
                ).fetchone()
            return bool(row and row["events"] and row["idempotency"])
        except Exception:
            return False

    def append_event(self, tenant_id: str, event: Event) -> bool:
        event.validate()
        payload = _plain(event.payload)
        with self._connection() as connection:
            row = connection.execute(
                """INSERT INTO cios_events
                (tenant_id,event_id,event_type,source,subject_id,payload_json,domain,information_class,materiality,occurred_at,payload_hash,created_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id,event_id) DO NOTHING
                RETURNING event_id""",
                (
                    tenant_id,
                    event.event_id,
                    event.event_type,
                    event.source,
                    event.subject_id,
                    canonical_json(payload),
                    event.domain.value,
                    event.information_class.value,
                    event.materiality,
                    event.occurred_at,
                    stable_sha256(payload),
                    utc_now_iso(),
                ),
            ).fetchone()
        return row is not None

    def load_events(self, tenant_id: str) -> list[Event]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM cios_events WHERE tenant_id=%s ORDER BY created_at,event_id",
                (tenant_id,),
            ).fetchall()
        return [
            Event(
                event_type=row["event_type"],
                source=row["source"],
                subject_id=row["subject_id"],
                payload=self._decoded(row["payload_json"]),
                domain=Domain(row["domain"]),
                information_class=InformationClass(row["information_class"]),
                materiality=float(row["materiality"]),
                event_id=row["event_id"],
                occurred_at=row["occurred_at"],
            )
            for row in rows
        ]

    def save_claim(self, tenant_id: str, claim: Claim) -> None:
        claim.validate()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO cios_claims
                (tenant_id,claim_id,subject_id,predicate,value_json,status,evidence_json,information_class,domain,confidence,assumptions_json,supersedes,created_at,fingerprint)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (tenant_id,claim_id) DO UPDATE SET
                  value_json=excluded.value_json,status=excluded.status,evidence_json=excluded.evidence_json,
                  information_class=excluded.information_class,domain=excluded.domain,confidence=excluded.confidence,
                  assumptions_json=excluded.assumptions_json,supersedes=excluded.supersedes,fingerprint=excluded.fingerprint""",
                (
                    tenant_id,
                    claim.claim_id,
                    claim.subject_id,
                    claim.predicate,
                    canonical_json(claim.value),
                    claim.status.value,
                    canonical_json([_plain(item) for item in claim.evidence]),
                    claim.information_class.value,
                    claim.domain.value,
                    claim.confidence,
                    canonical_json(claim.assumptions),
                    claim.supersedes,
                    claim.created_at,
                    claim.fingerprint(),
                ),
            )

    def load_claims(self, tenant_id: str) -> list[Claim]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM cios_claims WHERE tenant_id=%s ORDER BY created_at,claim_id",
                (tenant_id,),
            ).fetchall()
        result: list[Claim] = []
        for row in rows:
            evidence = [EvidenceRef(**item) for item in self._decoded(row["evidence_json"])]
            result.append(
                Claim(
                    subject_id=row["subject_id"],
                    predicate=row["predicate"],
                    value=self._decoded(row["value_json"]),
                    status=EvidenceStatus(row["status"]),
                    evidence=evidence,
                    information_class=InformationClass(row["information_class"]),
                    domain=Domain(row["domain"]),
                    confidence=float(row["confidence"]),
                    assumptions=list(self._decoded(row["assumptions_json"])),
                    supersedes=row["supersedes"],
                    claim_id=row["claim_id"],
                    created_at=row["created_at"],
                )
            )
        return result

    def add_dependency(self, tenant_id: str, source_subject: str, dependent_subject: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO cios_dependencies(tenant_id,source_subject,dependent_subject) "
                "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (tenant_id, source_subject, dependent_subject),
            )

    def load_dependencies(self, tenant_id: str) -> list[tuple[str, str]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT source_subject,dependent_subject FROM cios_dependencies "
                "WHERE tenant_id=%s ORDER BY source_subject,dependent_subject",
                (tenant_id,),
            ).fetchall()
        return [(row["source_subject"], row["dependent_subject"]) for row in rows]

    def get_idempotency_record(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT request_hash,result_json,result_hash FROM cios_idempotency "
                "WHERE tenant_id=%s AND idempotency_key=%s",
                (tenant_id, key),
            ).fetchone()
        if row is None:
            return None
        return {
            "request_hash": row["request_hash"],
            "result": self._decoded(row["result_json"]),
            "result_hash": row["result_hash"],
        }

    def get_idempotent_result(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        record = self.get_idempotency_record(tenant_id, key)
        return record["result"] if record else None

    def save_idempotent_result(
        self,
        tenant_id: str,
        key: str,
        result: Mapping[str, Any],
        request_hash: str = "",
    ) -> str:
        plain = _plain(result)
        digest = stable_sha256(plain)
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO cios_idempotency
                (tenant_id,idempotency_key,request_hash,result_json,result_hash,created_at)
                VALUES (%s,%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT (tenant_id,idempotency_key) DO UPDATE SET
                  request_hash=excluded.request_hash,result_json=excluded.result_json,
                  result_hash=excluded.result_hash,created_at=excluded.created_at""",
                (tenant_id, key, request_hash, canonical_json(plain), digest, utc_now_iso()),
            )
        return digest

    def append_learning(
        self,
        tenant_id: str,
        event_type: str,
        category: str,
        payload: Mapping[str, Any],
    ) -> LearningEvent:
        with self._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"cios-learning:{tenant_id}",))
            row = connection.execute(
                "SELECT sequence_no,event_hash FROM cios_learning_events "
                "WHERE tenant_id=%s ORDER BY sequence_no DESC LIMIT 1 FOR UPDATE",
                (tenant_id,),
            ).fetchone()
            sequence = int(row["sequence_no"]) + 1 if row else 1
            previous = row["event_hash"] if row else "GENESIS"
            created = utc_now_iso()
            plain = _plain(payload)
            digest = LearningEvent.calculate_hash(event_type, category, plain, previous, created)
            connection.execute(
                """INSERT INTO cios_learning_events
                (tenant_id,sequence_no,event_type,category,payload_json,previous_hash,event_hash,created_at)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                (tenant_id, sequence, event_type, category, canonical_json(plain), previous, digest, created),
            )
        return LearningEvent(event_type, category, dict(plain), previous, created, digest)

    def verify_learning_chain(self, tenant_id: str) -> bool:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM cios_learning_events WHERE tenant_id=%s ORDER BY sequence_no",
                (tenant_id,),
            ).fetchall()
        previous = "GENESIS"
        for row in rows:
            payload = self._decoded(row["payload_json"])
            expected = LearningEvent.calculate_hash(
                row["event_type"], row["category"], payload, row["previous_hash"], row["created_at"]
            )
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                return False
            previous = row["event_hash"]
        return True

    def tenant_state_digest(self, tenant_id: str) -> str:
        tables = {
            "claims": ("cios_claims", "claim_id"),
            "dependencies": ("cios_dependencies", "source_subject,dependent_subject"),
            "events": ("cios_events", "event_id"),
            "learning": ("cios_learning_events", "sequence_no"),
        }
        state: dict[str, list[dict[str, Any]]] = {}
        with self._connection() as connection:
            for label, (table, order) in tables.items():
                rows = connection.execute(
                    f"SELECT * FROM {table} WHERE tenant_id=%s ORDER BY {order}",
                    (tenant_id,),
                ).fetchall()
                state[label] = [dict(row) for row in rows]
        return stable_sha256(state)

    def count_rows(self, table: str, tenant_id: str) -> int:
        allowed = {
            "events": "cios_events",
            "claims": "cios_claims",
            "dependencies": "cios_dependencies",
            "idempotency": "cios_idempotency",
            "learning_events": "cios_learning_events",
            "restrictions": "cios_restrictions",
            "outcomes": "cios_outcomes",
        }
        if table not in allowed:
            raise ValueError("unsupported table")
        with self._connection() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {allowed[table]} WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()
        return int(row["count"])
