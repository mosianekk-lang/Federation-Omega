#!/usr/bin/env python3
"""Validate an owner-issued Phoenix provider-cutover authorization capsule.

This module performs no provider mutation. It binds a short-lived owner mandate
to the exact source commit, target repositories, archive digests and requested
cutover authority. Credential values are neither accepted nor persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-1"
EXPECTED_OWNER = "Kim Kagiso Mosiane"
EXPECTED_GITHUB_OWNER = "mosianekk-lang"
EXPECTED_SOURCE_REPOSITORY = "Federation-Omega"
EXPECTED_CORE_REPOSITORY = "Federation-Omega-Core"
EXPECTED_OPS_REPOSITORY = "Federation-Omega-Ops"
CONFIRMATION = "I AUTHORISE THIS EXACT PHOENIX CUTOVER APPLY"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
)


class AuthorizationError(ValueError):
    """Fail-closed authorization validation error."""


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise AuthorizationError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorizationError(f"{field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise AuthorizationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def reject_secret_material(value: Any, path: str = "authorization") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"token", "secret", "password", "api_key", "credential_value"}:
                raise AuthorizationError(f"secret-bearing field prohibited: {path}.{key}")
            reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            raise AuthorizationError(f"secret-shaped value prohibited at {path}")


def require_exact(payload: dict[str, Any], field: str, expected: Any) -> None:
    if payload.get(field) != expected:
        raise AuthorizationError(f"{field} must equal {expected!r}")


def validate_authorization(
    payload: dict[str, Any],
    *,
    now: datetime,
    source_sha: str,
    core_archive_sha256: str,
    ops_archive_sha256: str,
) -> dict[str, Any]:
    reject_secret_material(payload)
    require_exact(payload, "schema", SCHEMA)
    require_exact(payload, "owner_display_name", EXPECTED_OWNER)
    require_exact(payload, "github_owner", EXPECTED_GITHUB_OWNER)
    require_exact(payload, "source_repository", EXPECTED_SOURCE_REPOSITORY)
    require_exact(payload, "core_repository", EXPECTED_CORE_REPOSITORY)
    require_exact(payload, "ops_repository", EXPECTED_OPS_REPOSITORY)
    require_exact(payload, "source_sha", source_sha)
    require_exact(payload, "core_archive_sha256", core_archive_sha256)
    require_exact(payload, "ops_archive_sha256", ops_archive_sha256)
    require_exact(payload, "owner_confirmation", CONFIRMATION)
    require_exact(payload, "credential_source_env", "GH_ADMIN_TOKEN")

    if not HEX40.fullmatch(source_sha):
        raise AuthorizationError("source_sha must be a lowercase 40-character commit SHA")
    for field, digest in (
        ("core_archive_sha256", core_archive_sha256),
        ("ops_archive_sha256", ops_archive_sha256),
    ):
        if not HEX64.fullmatch(digest):
            raise AuthorizationError(f"{field} must be a lowercase SHA-256")

    authority_mode = payload.get("authority_mode")
    if authority_mode not in {"USER_SCOPED", "INSTALLATION_TEMPLATE"}:
        raise AuthorizationError("authority_mode must be USER_SCOPED or INSTALLATION_TEMPLATE")

    issued_at = parse_time(payload.get("issued_at"), "issued_at")
    expires_at = parse_time(payload.get("expires_at"), "expires_at")
    now_utc = now.astimezone(timezone.utc)
    if issued_at > now_utc:
        raise AuthorizationError("authorization is future-dated")
    if expires_at <= now_utc:
        raise AuthorizationError("authorization has expired")
    lifetime = (expires_at - issued_at).total_seconds()
    if lifetime <= 0 or lifetime > 1800:
        raise AuthorizationError("authorization lifetime must be 1-1800 seconds")

    actions = payload.get("actions")
    if not isinstance(actions, dict):
        raise AuthorizationError("actions must be an object")
    required_true = {"provider_apply", "create_core", "create_ops"}
    for action in required_true:
        if actions.get(action) is not True:
            raise AuthorizationError(f"actions.{action} must be true")
    for action in (
        "cloud_run_operation",
        "payment_operation",
        "external_communication",
        "financial_commitment",
        "contract_action",
        "revenue_recognition",
    ):
        if actions.get(action) is not False:
            raise AuthorizationError(f"actions.{action} must be false")
    if actions.get("archive_legacy") not in {True, False}:
        raise AuthorizationError("actions.archive_legacy must be boolean")
    if actions.get("replace_existing_main") not in {True, False}:
        raise AuthorizationError("actions.replace_existing_main must be boolean")

    if payload.get("core_private") not in {True, False}:
        raise AuthorizationError("core_private must be boolean")
    if payload.get("ops_private") is not True:
        raise AuthorizationError("ops_private must be true")

    authorization_id = payload.get("authorization_id")
    nonce = payload.get("nonce")
    if not isinstance(authorization_id, str) or len(authorization_id) < 12:
        raise AuthorizationError("authorization_id must be at least 12 characters")
    if not isinstance(nonce, str) or len(nonce) < 20:
        raise AuthorizationError("nonce must be at least 20 characters")

    normalized = dict(payload)
    return {
        "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-1",
        "status": "AUTHORIZED_APPLY",
        "authorization_id": authorization_id,
        "authorization_sha256": canonical_sha256(normalized),
        "source_sha": source_sha,
        "core_archive_sha256": core_archive_sha256,
        "ops_archive_sha256": ops_archive_sha256,
        "authority_mode": authority_mode,
        "expires_at": expires_at.isoformat(),
        "owner_authority_preserved": True,
        "credential_value_recorded": False,
        "external_commercial_gates_advanced": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.authorization.read_text(encoding="utf-8"))
    decision = validate_authorization(
        payload,
        now=datetime.now(timezone.utc),
        source_sha=args.source_sha,
        core_archive_sha256=file_sha256(args.core_archive),
        ops_archive_sha256=file_sha256(args.ops_archive),
    )
    receipt = dict(decision)
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
