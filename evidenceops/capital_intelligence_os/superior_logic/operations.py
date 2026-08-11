from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_operation_id(value: str) -> str:
    operation_id = value.strip()
    if not _OPERATION_ID.fullmatch(operation_id):
        raise ValueError(
            "operation_id must be 8-128 characters and contain only letters, numbers, '.', '_', ':' or '-'."
        )
    return operation_id


def request_fingerprint(operation_type: str, request_payload: dict[str, Any]) -> str:
    envelope = canonical_json({"operation_type": operation_type, "request": request_payload})
    return hashlib.sha256(envelope.encode("utf-8")).hexdigest()


class OperationConflictError(ValueError):
    """Raised when an operation identifier is reused for a different request."""


@dataclass(frozen=True)
class OperationReceipt:
    operation_id: str
    operation_type: str
    request_hash: str
    principal: str
    target: str
    event_id: str
    result: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "request_hash": self.request_hash,
            "principal": self.principal,
            "target": self.target,
            "event_id": self.event_id,
            "result": self.result,
            "created_at": self.created_at,
        }


class OperationJournal:
    """Durable replay receipts stored in the runtime's existing SQLite transaction."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_receipts(
              operation_id TEXT PRIMARY KEY,
              operation_type TEXT NOT NULL,
              request_hash TEXT NOT NULL,
              principal TEXT NOT NULL,
              target TEXT NOT NULL,
              event_id TEXT UNIQUE NOT NULL,
              result_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )

    def replay(
        self,
        operation_id: str,
        operation_type: str,
        request_payload: dict[str, Any],
    ) -> OperationReceipt | None:
        operation_id = normalize_operation_id(operation_id)
        expected_hash = request_fingerprint(operation_type, request_payload)
        row = self.db.execute(
            "SELECT * FROM operation_receipts WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if row is None:
            return None
        if row["operation_type"] != operation_type or row["request_hash"] != expected_hash:
            raise OperationConflictError(
                "operation_id already exists for a different operation type or request payload."
            )
        return self._receipt(row)

    def record(
        self,
        *,
        operation_id: str,
        operation_type: str,
        request_payload: dict[str, Any],
        principal: str,
        target: str,
        event_id: str,
        result: dict[str, Any],
    ) -> OperationReceipt:
        operation_id = normalize_operation_id(operation_id)
        request_hash = request_fingerprint(operation_type, request_payload)
        created_at = utcnow()
        self.db.execute(
            "INSERT INTO operation_receipts(operation_id,operation_type,request_hash,principal,target,event_id,result_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                operation_id,
                operation_type,
                request_hash,
                principal,
                target,
                event_id,
                canonical_json(result),
                created_at,
            ),
        )
        return OperationReceipt(
            operation_id,
            operation_type,
            request_hash,
            principal,
            target,
            event_id,
            result,
            created_at,
        )

    def get(self, operation_id: str) -> OperationReceipt | None:
        operation_id = normalize_operation_id(operation_id)
        row = self.db.execute(
            "SELECT * FROM operation_receipts WHERE operation_id=?", (operation_id,)
        ).fetchone()
        return self._receipt(row) if row is not None else None

    @staticmethod
    def _receipt(row: sqlite3.Row) -> OperationReceipt:
        return OperationReceipt(
            operation_id=row["operation_id"],
            operation_type=row["operation_type"],
            request_hash=row["request_hash"],
            principal=row["principal"],
            target=row["target"],
            event_id=row["event_id"],
            result=json.loads(row["result_json"]),
            created_at=row["created_at"],
        )
