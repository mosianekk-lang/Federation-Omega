#!/usr/bin/env python3
"""Durable one-time consumption gate for Phoenix cutover authorization decisions.

The v20 authorization verifier proves that a short-lived owner mandate matches an
exact source commit and exact Core/Ops archives. This module closes the replay
gap between that decision and a future provider apply by reserving each
authorization hash exactly once in a private execution-plane state directory.

No provider call, repository mutation, credential read or external commercial
action is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DECISION_SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-1"
USE_SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-USE-1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]{12,128}$")
SECRET_KEYS = {"token", "secret", "password", "api_key", "credential_value"}
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
)
TERMINAL_STATES = {"VERIFIED", "ABORTED"}


class AuthorizationUseError(RuntimeError):
    """Fail-closed authorization-consumption error."""


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise AuthorizationUseError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorizationUseError(f"{field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise AuthorizationUseError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def reject_secret_material(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                raise AuthorizationUseError(f"secret-bearing field prohibited: {path}.{key}")
            reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise AuthorizationUseError(f"secret-shaped value prohibited at {path}")


def validate_decision(decision: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    reject_secret_material(decision, "decision")
    if decision.get("schema") != DECISION_SCHEMA:
        raise AuthorizationUseError("unsupported authorization decision schema")
    if decision.get("status") != "AUTHORIZED_APPLY":
        raise AuthorizationUseError("authorization decision is not AUTHORIZED_APPLY")
    if decision.get("owner_authority_preserved") is not True:
        raise AuthorizationUseError("owner authority is not preserved")
    if decision.get("credential_value_recorded") is not False:
        raise AuthorizationUseError("credential-value boundary is not preserved")
    if decision.get("external_commercial_gates_advanced") is not False:
        raise AuthorizationUseError("external commercial gates must remain unchanged")

    authorization_id = decision.get("authorization_id")
    if not isinstance(authorization_id, str) or not IDENTIFIER.fullmatch(authorization_id):
        raise AuthorizationUseError("authorization_id is invalid")

    authorization_sha256 = decision.get("authorization_sha256")
    source_sha = decision.get("source_sha")
    core_sha = decision.get("core_archive_sha256")
    ops_sha = decision.get("ops_archive_sha256")
    if not isinstance(authorization_sha256, str) or not HEX64.fullmatch(authorization_sha256):
        raise AuthorizationUseError("authorization_sha256 is invalid")
    if not isinstance(source_sha, str) or not HEX40.fullmatch(source_sha):
        raise AuthorizationUseError("source_sha is invalid")
    for field, value in (("core_archive_sha256", core_sha), ("ops_archive_sha256", ops_sha)):
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            raise AuthorizationUseError(f"{field} is invalid")

    expires_at = parse_time(decision.get("expires_at"), "expires_at")
    if expires_at <= now.astimezone(timezone.utc):
        raise AuthorizationUseError("authorization decision has expired")

    return {
        "authorization_id": authorization_id,
        "authorization_sha256": authorization_sha256,
        "source_sha": source_sha,
        "core_archive_sha256": core_sha,
        "ops_archive_sha256": ops_sha,
        "authority_mode": decision.get("authority_mode"),
        "expires_at": expires_at.isoformat(),
    }


def _directory_fsync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_record(path: Path) -> dict[str, Any]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorizationUseError(f"authorization-use record is unreadable: {path.name}") from exc
    expected = record.get("record_sha256")
    body = dict(record)
    body.pop("record_sha256", None)
    if not isinstance(expected, str) or expected != canonical_sha256(body):
        raise AuthorizationUseError(f"authorization-use record failed integrity verification: {path.name}")
    return record


def _atomic_replace(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(record)
    body.pop("record_sha256", None)
    body["record_sha256"] = canonical_sha256(body)
    payload = json.dumps(body, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        os.chmod(temp_path, 0o600)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)
    _directory_fsync(path.parent)


def reserve_authorization(
    decision: dict[str, Any],
    *,
    state_dir: Path,
    execution_id: str,
    now: datetime,
) -> dict[str, Any]:
    if not IDENTIFIER.fullmatch(execution_id):
        raise AuthorizationUseError("execution_id is invalid")
    validated = validate_decision(decision, now=now)
    state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    path = state_dir / f"{validated['authorization_sha256']}.json"
    created_at = now.astimezone(timezone.utc).isoformat()
    record = {
        "schema": USE_SCHEMA,
        "state": "RESERVED",
        "execution_id": execution_id,
        **validated,
        "created_at": created_at,
        "updated_at": created_at,
        "provider_apply_performed": False,
        "provider_receipt_sha256": None,
        "credential_value_recorded": False,
        "external_commercial_gates_advanced": False,
    }
    body = dict(record)
    body["record_sha256"] = canonical_sha256(body)
    encoded = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode()

    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        existing = _read_record(path)
        if (
            existing.get("execution_id") == execution_id
            and existing.get("authorization_sha256") == validated["authorization_sha256"]
            and existing.get("source_sha") == validated["source_sha"]
            and existing.get("core_archive_sha256") == validated["core_archive_sha256"]
            and existing.get("ops_archive_sha256") == validated["ops_archive_sha256"]
        ):
            result = dict(existing)
            result["reservation_result"] = "IDEMPOTENT_EXISTING"
            return result
        raise AuthorizationUseError("authorization has already been consumed by another execution")

    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _directory_fsync(state_dir)
    result = dict(body)
    result["reservation_result"] = "RESERVED_NEW"
    return result


def transition_authorization(
    *,
    state_dir: Path,
    authorization_sha256: str,
    execution_id: str,
    target_state: str,
    now: datetime,
    provider_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    if not HEX64.fullmatch(authorization_sha256):
        raise AuthorizationUseError("authorization_sha256 is invalid")
    if not IDENTIFIER.fullmatch(execution_id):
        raise AuthorizationUseError("execution_id is invalid")
    if target_state not in {"APPLY_STARTED", "VERIFIED", "ABORTED"}:
        raise AuthorizationUseError("target_state is invalid")
    if provider_receipt_sha256 is not None and not HEX64.fullmatch(provider_receipt_sha256):
        raise AuthorizationUseError("provider_receipt_sha256 is invalid")

    path = state_dir / f"{authorization_sha256}.json"
    record = _read_record(path)
    if record.get("execution_id") != execution_id:
        raise AuthorizationUseError("execution_id does not own this authorization reservation")
    current = record.get("state")

    if current == target_state:
        if target_state == "VERIFIED" and record.get("provider_receipt_sha256") != provider_receipt_sha256:
            raise AuthorizationUseError("verified receipt conflicts with the existing terminal record")
        result = dict(record)
        result["transition_result"] = "IDEMPOTENT_EXISTING"
        return result
    if current in TERMINAL_STATES:
        raise AuthorizationUseError(f"authorization use is terminal: {current}")
    if target_state == "APPLY_STARTED" and current != "RESERVED":
        raise AuthorizationUseError(f"cannot start apply from {current}")
    if target_state in TERMINAL_STATES and current != "APPLY_STARTED":
        raise AuthorizationUseError(f"cannot finish apply from {current}")
    if target_state == "VERIFIED" and provider_receipt_sha256 is None:
        raise AuthorizationUseError("VERIFIED requires provider_receipt_sha256")
    if target_state == "ABORTED" and provider_receipt_sha256 is not None:
        raise AuthorizationUseError("ABORTED must not carry a provider receipt")

    updated = dict(record)
    updated.pop("record_sha256", None)
    updated["state"] = target_state
    updated["updated_at"] = now.astimezone(timezone.utc).isoformat()
    updated["provider_apply_performed"] = target_state == "VERIFIED"
    updated["provider_receipt_sha256"] = provider_receipt_sha256
    _atomic_replace(path, updated)
    result = _read_record(path)
    result["transition_result"] = "TRANSITIONED"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    reserve = subparsers.add_parser("reserve")
    reserve.add_argument("--decision", type=Path, required=True)
    reserve.add_argument("--state-dir", type=Path, required=True)
    reserve.add_argument("--execution-id", required=True)

    transition = subparsers.add_parser("transition")
    transition.add_argument("--state-dir", type=Path, required=True)
    transition.add_argument("--authorization-sha256", required=True)
    transition.add_argument("--execution-id", required=True)
    transition.add_argument("--target-state", required=True)
    transition.add_argument("--provider-receipt-sha256")

    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.command == "reserve":
        decision = json.loads(args.decision.read_text(encoding="utf-8"))
        result = reserve_authorization(
            decision,
            state_dir=args.state_dir,
            execution_id=args.execution_id,
            now=now,
        )
    else:
        result = transition_authorization(
            state_dir=args.state_dir,
            authorization_sha256=args.authorization_sha256,
            execution_id=args.execution_id,
            target_state=args.target_state,
            provider_receipt_sha256=args.provider_receipt_sha256,
            now=now,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
