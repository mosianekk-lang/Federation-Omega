from __future__ import annotations

"""Restart-safe local persistence for the existing deterministic Result Fabric.

This module is deliberately a thin storage adapter. It reuses the canonical
``DeterministicAction``, ``CachedResult`` and ``CacheDecision`` contracts from
Bubbles hyperperformance and adds only local SQLite durability. It does not
create provider, distributed-cache, serving, financial or publication
authority.
"""

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from federation.bubbles_frontier_hyperperformance import (
    CacheDecision,
    CachedResult,
    DeterministicAction,
)

_HEX = frozenset("0123456789abcdef")
_SCHEMA = "FEDERATION-DURABLE-DETERMINISTIC-RESULT-CACHE-V1"


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _require_sha256(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(ch not in _HEX for ch in normalized):
        raise ValueError(f"{label}_SHA256_REQUIRED")
    return normalized


def _identity_payload(action: DeterministicAction) -> dict[str, str]:
    return {
        "action": action.action,
        "source_sha256": _require_sha256(action.source_sha256, "SOURCE"),
        "input_sha256": _require_sha256(action.input_sha256, "INPUT"),
        "environment_sha256": _require_sha256(action.environment_sha256, "ENVIRONMENT"),
        "proof_scope": action.proof_scope,
        "effect_class": action.effect_class,
    }


def _entry_payload(action: DeterministicAction, result: CachedResult) -> dict[str, object]:
    return {
        "schema": _SCHEMA,
        "cache_key": result.cache_key,
        "identity": _identity_payload(action),
        "result": asdict(result),
    }


class SQLiteDeterministicResultCache:
    """Durable local index for exact deterministic ``NO_EFFECT`` result reuse.

    The SQLite file is caller-selected and may coexist beside other Federation
    SQLite stores. Rows are immutable by cache key, hash-bound, read back before
    commit, and validated again on lookup. Only the cache index is persistent;
    result bytes remain outside this adapter and are addressed by ``result_ref``
    plus ``result_sha256``.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS result_fabric_cache_v1 (
                cache_key TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                input_sha256 TEXT NOT NULL,
                environment_sha256 TEXT NOT NULL,
                proof_scope TEXT NOT NULL,
                effect_class TEXT NOT NULL,
                result_ref TEXT NOT NULL,
                result_sha256 TEXT NOT NULL,
                proof_refs_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                entry_sha256 TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS result_fabric_cache_result_idx
              ON result_fabric_cache_v1(result_sha256);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteDeterministicResultCache":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _row_identity(row: sqlite3.Row) -> dict[str, str]:
        return {
            "action": str(row["action"]),
            "source_sha256": str(row["source_sha256"]),
            "input_sha256": str(row["input_sha256"]),
            "environment_sha256": str(row["environment_sha256"]),
            "proof_scope": str(row["proof_scope"]),
            "effect_class": str(row["effect_class"]),
        }

    @classmethod
    def _decode_row(cls, row: sqlite3.Row) -> CachedResult:
        try:
            raw_refs = json.loads(str(row["proof_refs_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("CACHE_DURABLE_RECORD_CORRUPT") from exc
        if not isinstance(raw_refs, list) or any(not isinstance(item, str) for item in raw_refs):
            raise ValueError("CACHE_DURABLE_RECORD_CORRUPT")
        refs = tuple(raw_refs)
        if not refs or tuple(sorted(set(refs))) != refs:
            raise ValueError("CACHE_DURABLE_RECORD_CORRUPT")
        result = CachedResult(
            cache_key=str(row["cache_key"]),
            result_ref=str(row["result_ref"]),
            result_sha256=_require_sha256(str(row["result_sha256"]), "CACHE_RESULT"),
            proof_refs=refs,
            recorded_at=str(row["recorded_at"]),
        )
        payload = {
            "schema": _SCHEMA,
            "cache_key": result.cache_key,
            "identity": cls._row_identity(row),
            "result": asdict(result),
        }
        if _digest(payload) != str(row["entry_sha256"]):
            raise ValueError("CACHE_DURABLE_RECORD_CORRUPT")
        return result

    def lookup(self, action: DeterministicAction, *, now: str) -> CacheDecision:
        action.validate(now=now)
        key = action.cache_key()
        row = self.connection.execute(
            "SELECT * FROM result_fabric_cache_v1 WHERE cache_key=?",
            (key,),
        ).fetchone()
        if row is None:
            return CacheDecision(
                "MISS",
                key,
                False,
                reason="No equivalent verified durable deterministic result is indexed.",
            )
        try:
            result = self._decode_row(row)
        except ValueError as exc:
            if str(exc) == "CACHE_DURABLE_RECORD_CORRUPT":
                return CacheDecision(
                    "HOLD_CORRUPT_RECORD",
                    key,
                    False,
                    reason="Durable result row failed its content-integrity contract.",
                )
            raise
        if self._row_identity(row) != _identity_payload(action):
            return CacheDecision(
                "HOLD_IDENTITY_MISMATCH",
                key,
                False,
                reason="Durable row identity does not match the requested deterministic action.",
            )
        if not result.proof_refs:
            return CacheDecision(
                "HOLD_MISSING_PROOF",
                key,
                False,
                reason="Indexed durable result lacks proof references.",
            )
        return CacheDecision(
            "HIT",
            key,
            True,
            result_ref=result.result_ref,
            result_sha256=result.result_sha256,
            proof_refs=result.proof_refs,
            reason=(
                "Exact source/input/environment/proof-scope identity matched a hash-bound local "
                "durable row; no provider or serving effect is authorized."
            ),
        )

    def record(
        self,
        action: DeterministicAction,
        *,
        result_ref: str,
        result_sha256: str,
        proof_refs: Iterable[str],
        recorded_at: str,
        now: str,
    ) -> CacheDecision:
        action.validate(now=now)
        if not result_ref.strip():
            raise ValueError("CACHE_RESULT_REF_REQUIRED")
        digest = _require_sha256(result_sha256, "CACHE_RESULT")
        refs = tuple(sorted({item.strip() for item in proof_refs if item.strip()}))
        if not refs:
            raise ValueError("CACHE_PROOF_REFS_REQUIRED")
        key = action.cache_key()
        candidate = CachedResult(key, result_ref, digest, refs, recorded_at)
        identity = _identity_payload(action)
        entry_sha = _digest(_entry_payload(action, candidate))

        cursor = self.connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            existing_row = cursor.execute(
                "SELECT * FROM result_fabric_cache_v1 WHERE cache_key=?",
                (key,),
            ).fetchone()
            if existing_row is not None:
                try:
                    existing = self._decode_row(existing_row)
                except ValueError as exc:
                    raise ValueError("CACHE_DURABLE_RECORD_CORRUPT") from exc
                if self._row_identity(existing_row) != identity:
                    raise ValueError("CACHE_DURABLE_IDENTITY_MISMATCH")
                if existing != candidate:
                    raise ValueError("CACHE_RESULT_CONFLICT")
                self.connection.commit()
                return CacheDecision(
                    "IDEMPOTENT_RECORD",
                    key,
                    True,
                    result_ref=existing.result_ref,
                    result_sha256=existing.result_sha256,
                    proof_refs=existing.proof_refs,
                    reason="Exact durable deterministic result already exists; no duplicate row was written.",
                )

            cursor.execute(
                """INSERT INTO result_fabric_cache_v1
                   (cache_key,action,source_sha256,input_sha256,environment_sha256,proof_scope,effect_class,
                    result_ref,result_sha256,proof_refs_json,recorded_at,entry_sha256)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    key,
                    identity["action"],
                    identity["source_sha256"],
                    identity["input_sha256"],
                    identity["environment_sha256"],
                    identity["proof_scope"],
                    identity["effect_class"],
                    candidate.result_ref,
                    candidate.result_sha256,
                    _stable_json(list(candidate.proof_refs)),
                    candidate.recorded_at,
                    entry_sha,
                ),
            )
            readback = cursor.execute(
                "SELECT * FROM result_fabric_cache_v1 WHERE cache_key=?",
                (key,),
            ).fetchone()
            if readback is None:
                raise ValueError("CACHE_DURABLE_READBACK_MISSING")
            restored = self._decode_row(readback)
            if restored != candidate or self._row_identity(readback) != identity:
                raise ValueError("CACHE_DURABLE_READBACK_MISMATCH")
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return CacheDecision(
            "RECORDED",
            key,
            True,
            result_ref=candidate.result_ref,
            result_sha256=candidate.result_sha256,
            proof_refs=candidate.proof_refs,
            reason="Immutable deterministic result persisted and semantically read back from local SQLite.",
        )

    def verify(self) -> dict[str, object]:
        rows = self.connection.execute(
            "SELECT * FROM result_fabric_cache_v1 ORDER BY cache_key"
        ).fetchall()
        corrupt_keys: list[str] = []
        for row in rows:
            try:
                self._decode_row(row)
            except ValueError:
                corrupt_keys.append(str(row["cache_key"]))
        return {
            "schema": _SCHEMA,
            "record_count": len(rows),
            "valid": not corrupt_keys,
            "corrupt_cache_keys": tuple(corrupt_keys),
            "local_persistence": True,
            "distributed_cache": False,
            "provider_cache": False,
            "serving_authority": False,
            "external_effects": 0,
        }


__all__ = ["SQLiteDeterministicResultCache"]
