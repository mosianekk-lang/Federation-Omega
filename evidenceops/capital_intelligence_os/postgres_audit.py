from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
import hashlib

from .audit import AuditLedger, AuditRecord
from .models import canonical_json, utc_now_iso


class PostgresAuditLedger:
    """Append-only PostgreSQL audit chain intended for a separately bound database."""

    def __init__(
        self,
        dsn: str,
        *,
        min_pool_size: int = 1,
        max_pool_size: int = 4,
        timeout_seconds: float = 10.0,
        apply_migrations: bool = False,
        pool_factory: Any | None = None,
    ) -> None:
        if not dsn.strip():
            raise ValueError("audit PostgreSQL DSN is required")
        if not 1 <= min_pool_size <= max_pool_size <= 8:
            raise ValueError("audit pool must satisfy 1 <= min <= max <= 8")
        if pool_factory is None:
            try:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL audit runtime requires psycopg and psycopg_pool"
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
        if apply_migrations:
            self.apply_migrations()

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with self._pool.connection() as connection:
            yield connection

    def apply_migrations(self) -> None:
        sql = (Path(__file__).with_name("migrations") / "0001_postgres_audit.sql").read_text(
            encoding="utf-8"
        )
        with self._connection() as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("cios-audit-migrations",))
                connection.execute(sql)

    def append(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        resource: str,
        outcome: str,
        payload: Mapping[str, Any] | None = None,
    ) -> AuditRecord:
        with self._connection() as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("cios-audit-chain",))
                row = connection.execute(
                    "SELECT sequence_no,record_hash FROM cios_audit_records "
                    "ORDER BY sequence_no DESC LIMIT 1 FOR UPDATE"
                ).fetchone()
                sequence = int(row["sequence_no"]) + 1 if row else 1
                previous = row["record_hash"] if row else "GENESIS"
                created = utc_now_iso()
                payload_hash = hashlib.sha256(
                    canonical_json(dict(payload or {})).encode()
                ).hexdigest()
                digest = AuditLedger._hash(
                    sequence,
                    tenant_id,
                    actor_id,
                    action,
                    resource,
                    outcome,
                    payload_hash,
                    previous,
                    created,
                )
                connection.execute(
                    """INSERT INTO cios_audit_records
                    (sequence_no,tenant_id,actor_id,action,resource,outcome,payload_hash,previous_hash,record_hash,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        sequence,
                        tenant_id,
                        actor_id,
                        action,
                        resource,
                        outcome,
                        payload_hash,
                        previous,
                        digest,
                        created,
                    ),
                )
        return AuditRecord(
            sequence,
            tenant_id,
            actor_id,
            action,
            resource,
            outcome,
            payload_hash,
            previous,
            digest,
            created,
        )

    def verify(self) -> bool:
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    "SELECT * FROM cios_audit_records ORDER BY sequence_no"
                ).fetchall()
        except Exception:
            return False
        previous = "GENESIS"
        for row in rows:
            expected = AuditLedger._hash(
                row["sequence_no"],
                row["tenant_id"],
                row["actor_id"],
                row["action"],
                row["resource"],
                row["outcome"],
                row["payload_hash"],
                row["previous_hash"],
                row["created_at"],
            )
            if row["previous_hash"] != previous or row["record_hash"] != expected:
                return False
            previous = row["record_hash"]
        return True

    def count(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM cios_audit_records"
            ).fetchone()
        return int(row["count"])
