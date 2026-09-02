from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Mapping

try:
    from .sol_62_frontier_primitives import ConstraintError, digest, stable_json, utc_now
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from sol_62_frontier_primitives import ConstraintError, digest, stable_json, utc_now
    from sol_62_runtime import Sol62Runtime


HOSTED_STATE_SCHEMA = "FDOF-HOSTED-STATE-CAPSULE-V1"
HOSTED_STATE_VERSION = "1.0.0"
GENERATION_ANCHOR = "GEN16/6fa54e31"

# Persist only coordination/runtime facts required for continuity. Authority is
# intentionally excluded so a state artifact can never manufacture or replay
# provider permission in a later runner.
PERSISTED_TABLES = (
    "events",
    "state",
    "idempotency",
    "leases",
    "effects",
    "proofs",
    "budgets",
    "schemas",
    "values_ledger",
)
EXCLUDED_TABLES = ("authority_leases",)

_SECRET_MARKERS = (
    "sk-",
    "ghp_",
    "github_pat_",
    "AIza",
    "Bearer ",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
)


@dataclass(frozen=True)
class CapsuleStatus:
    schema: str
    version: str
    generation_anchor: str
    source_version: str
    capsule_sha256: str
    event_chain_valid: bool
    persisted_tables: tuple[str, ...]
    excluded_authority_lease_count: int


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__fdof_bytes_b64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _json_restore(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__fdof_bytes_b64__"}:
            return base64.b64decode(value["__fdof_bytes_b64__"])
        return {key: _json_restore(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_restore(item) for item in value]
    return value


def _reject_secret_material(value: Any) -> None:
    rendered = stable_json(_json_safe(value))
    marker = next((item for item in _SECRET_MARKERS if item in rendered), None)
    if marker:
        raise ConstraintError(f"HOSTED_STATE_SECRET_MATERIAL_FORBIDDEN:{marker}")


def _table_exists(runtime: Sol62Runtime, table: str) -> bool:
    row = runtime.control.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(runtime: Sol62Runtime, table: str) -> list[str]:
    return [str(row["name"]) for row in runtime.control.db.execute(f'PRAGMA table_info("{table}")')]


def _export_table(runtime: Sol62Runtime, table: str) -> dict[str, Any]:
    if not _table_exists(runtime, table):
        return {"columns": [], "rows": []}
    columns = _columns(runtime, table)
    rows = []
    for row in runtime.control.db.execute(f'SELECT * FROM "{table}"'):
        rows.append({column: _json_safe(row[column]) for column in columns})
    rows.sort(key=stable_json)
    return {"columns": columns, "rows": rows}


def export_capsule(
    runtime: Sol62Runtime,
    *,
    source_version: str,
    generation_anchor: str = GENERATION_ANCHOR,
    parent_artifact_ref: str = "",
) -> dict[str, Any]:
    if generation_anchor != GENERATION_ANCHOR:
        raise ConstraintError("HOSTED_STATE_GENERATION_ANCHOR_MISMATCH")
    if not source_version:
        raise ConstraintError("HOSTED_STATE_SOURCE_VERSION_REQUIRED")
    if not runtime.control.verify_event_chain():
        raise ConstraintError("HOSTED_STATE_EVENT_CHAIN_INVALID")

    tables = {table: _export_table(runtime, table) for table in PERSISTED_TABLES}
    authority_count = 0
    if _table_exists(runtime, "authority_leases"):
        authority_count = int(
            runtime.control.db.execute("SELECT COUNT(*) AS n FROM authority_leases").fetchone()["n"]
        )

    core = {
        "schema": HOSTED_STATE_SCHEMA,
        "version": HOSTED_STATE_VERSION,
        "generation_anchor": generation_anchor,
        "source_version": source_version,
        "created_at": utc_now(),
        "parent_artifact_ref": parent_artifact_ref,
        "tables": tables,
        "excluded": {
            "authority_leases": {
                "persisted": False,
                "row_count_at_export": authority_count,
                "reason": "AUTHORITY_NEVER_TRANSFERS_ACROSS_HOSTED_RUNS",
            }
        },
    }
    _reject_secret_material(core)
    return {**core, "capsule_sha256": digest(core)}


def verify_capsule(
    capsule: Mapping[str, Any], *, expected_generation_anchor: str = GENERATION_ANCHOR
) -> CapsuleStatus:
    candidate = dict(capsule)
    capsule_sha = str(candidate.pop("capsule_sha256", ""))
    if candidate.get("schema") != HOSTED_STATE_SCHEMA:
        raise ConstraintError("HOSTED_STATE_SCHEMA_MISMATCH")
    if candidate.get("version") != HOSTED_STATE_VERSION:
        raise ConstraintError("HOSTED_STATE_VERSION_MISMATCH")
    if candidate.get("generation_anchor") != expected_generation_anchor:
        raise ConstraintError("HOSTED_STATE_GENERATION_ANCHOR_MISMATCH")
    if capsule_sha != digest(candidate):
        raise ConstraintError("HOSTED_STATE_CAPSULE_DIGEST_MISMATCH")
    tables = candidate.get("tables")
    if not isinstance(tables, Mapping):
        raise ConstraintError("HOSTED_STATE_TABLES_MISSING")
    unexpected = sorted(set(tables) - set(PERSISTED_TABLES))
    if unexpected:
        raise ConstraintError("HOSTED_STATE_UNEXPECTED_TABLE:" + ",".join(unexpected))
    if "authority_leases" in tables:
        raise ConstraintError("HOSTED_STATE_AUTHORITY_TRANSFER_FORBIDDEN")
    _reject_secret_material(candidate)
    excluded = candidate.get("excluded", {}).get("authority_leases", {})
    return CapsuleStatus(
        schema=str(candidate["schema"]),
        version=str(candidate["version"]),
        generation_anchor=str(candidate["generation_anchor"]),
        source_version=str(candidate.get("source_version", "")),
        capsule_sha256=capsule_sha,
        event_chain_valid=True,
        persisted_tables=tuple(sorted(tables)),
        excluded_authority_lease_count=int(excluded.get("row_count_at_export", 0)),
    )


def restore_capsule(
    runtime: Sol62Runtime,
    capsule: Mapping[str, Any],
    *,
    expected_generation_anchor: str = GENERATION_ANCHOR,
) -> CapsuleStatus:
    status = verify_capsule(capsule, expected_generation_anchor=expected_generation_anchor)
    tables = capsule["tables"]

    with runtime.control.tx() as db:
        # Child rows reference idempotency; clearing in this order avoids FK
        # violations even when restoring into a previously used local runtime.
        clear_order = (
            "effects",
            "proofs",
            "leases",
            "idempotency",
            "state",
            "events",
            "budgets",
            "schemas",
            "values_ledger",
        )
        for table in clear_order:
            if _table_exists(runtime, table):
                db.execute(f'DELETE FROM "{table}"')

        # Restore parents before children where FK relationships exist.
        restore_order = (
            "events",
            "state",
            "idempotency",
            "leases",
            "proofs",
            "budgets",
            "schemas",
            "values_ledger",
            "effects",
        )
        for table in restore_order:
            table_payload = tables.get(table, {"columns": [], "rows": []})
            columns = list(table_payload.get("columns", []))
            rows = list(table_payload.get("rows", []))
            if not columns and rows:
                raise ConstraintError(f"HOSTED_STATE_COLUMNS_MISSING:{table}")
            actual_columns = set(_columns(runtime, table))
            if not set(columns) <= actual_columns:
                raise ConstraintError(f"HOSTED_STATE_COLUMN_MISMATCH:{table}")
            if not rows:
                continue
            quoted = ",".join(f'"{column}"' for column in columns)
            placeholders = ",".join("?" for _ in columns)
            statement = f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})'
            for row in rows:
                values = [_json_restore(row[column]) for column in columns]
                db.execute(statement, values)

    if not runtime.control.verify_event_chain():
        raise ConstraintError("HOSTED_STATE_RESTORED_EVENT_CHAIN_INVALID")
    authority_count = int(
        runtime.control.db.execute("SELECT COUNT(*) AS n FROM authority_leases").fetchone()["n"]
    )
    if authority_count:
        raise ConstraintError("HOSTED_STATE_AUTHORITY_LEASE_RESTORED")
    return status


def write_capsule(path: str, capsule: Mapping[str, Any]) -> None:
    verify_capsule(capsule)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(dict(capsule), handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")


def read_capsule(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        capsule = json.load(handle)
    verify_capsule(capsule)
    return capsule
