#!/usr/bin/env python3
"""Prepare a fail-closed provider-attested authorization intake.

This module verifies, but does not create, three independent owner/provider
proof objects:

1. a provider-native owner-identity attestation receipt;
2. a fresh provider-authority receipt; and
3. an exact, short-lived owner authorization decision bound to both receipts.

It performs no provider request, repository mutation, authorization
consumption, external communication, or commercial-gate advancement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IDENTITY_RECEIPT_SCHEMA = (
    "FEDOMEGA-PHOENIX-PROVIDER-AUTHENTICATED-OWNER-ATTESTATION-RECEIPT-1"
)
DECISION_SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-3"
INTAKE_SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-ATTESTED-AUTHORIZATION-INTAKE-1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_AGE_SECONDS = 300


class ProviderAttestedAuthorizationError(RuntimeError):
    """Fail-closed provider-attested authorization intake error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderAttestedAuthorizationError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise ProviderAttestedAuthorizationError(f"{label} must be a JSON object")
    return payload


def _valid_hash(value: object, *, field: str) -> str:
    digest = str(value or "").lower()
    if not HEX64.fullmatch(digest):
        raise ProviderAttestedAuthorizationError(
            f"{field} must be a lowercase SHA-256"
        )
    return digest


def _verify_self_hash(
    payload: dict[str, Any], *, field: str, label: str
) -> str:
    claimed = _valid_hash(payload.get(field), field=field)
    body = dict(payload)
    body.pop(field, None)
    if canonical_sha256(body) != claimed:
        raise ProviderAttestedAuthorizationError(
            f"{label} hash verification failed"
        )
    return claimed


def _parse_time(value: object, *, field: str) -> datetime:
    raw = str(value or "")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProviderAttestedAuthorizationError(
            f"{field} is not a valid timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise ProviderAttestedAuthorizationError(
            f"{field} must include timezone"
        )
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _verify_freshness(
    *, observed_at: datetime, now: datetime, max_age_seconds: int, label: str
) -> None:
    age = (now - observed_at).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise ProviderAttestedAuthorizationError(
            f"{label} is outside the freshness window"
        )


def verify_identity_receipt(
    receipt: dict[str, Any], *, now: datetime, max_age_seconds: int = MAX_AGE_SECONDS
) -> dict[str, Any]:
    if receipt.get("schema") != IDENTITY_RECEIPT_SCHEMA:
        raise ProviderAttestedAuthorizationError(
            "provider identity receipt schema mismatch"
        )
    receipt_sha = _verify_self_hash(
        receipt, field="receipt_sha256", label="provider identity receipt"
    )
    if receipt.get("capture_mode") != "PROVIDER_NATIVE":
        raise ProviderAttestedAuthorizationError(
            "provider identity receipt is not provider-native"
        )
    required_true = (
        "owner_identity_authenticity_proven",
        "provider_native_attestation_readback_present",
        "owner_execution_present",
        "owner_attestation_present",
    )
    if any(receipt.get(field) is not True for field in required_true):
        raise ProviderAttestedAuthorizationError(
            "provider identity receipt does not prove the required owner facts"
        )
    required_false = (
        "owner_authorization_present",
        "provider_authority_created",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
        "credential_value_recorded",
    )
    if any(receipt.get(field) is not False for field in required_false):
        raise ProviderAttestedAuthorizationError(
            "provider identity receipt contains an unsafe authority claim"
        )
    repository = str(receipt.get("repository_full_name") or "")
    if not REPOSITORY.fullmatch(repository):
        raise ProviderAttestedAuthorizationError(
            "provider identity repository binding is invalid"
        )
    owner_login = str(receipt.get("owner_login") or "")
    if repository.split("/", 1)[0] != owner_login:
        raise ProviderAttestedAuthorizationError(
            "provider identity owner/repository binding mismatch"
        )
    comment_id = receipt.get("comment_id")
    if not isinstance(comment_id, int) or comment_id <= 0:
        raise ProviderAttestedAuthorizationError(
            "provider identity comment binding is invalid"
        )
    verified_at = _parse_time(receipt.get("verified_at"), field="verified_at")
    _verify_freshness(
        observed_at=verified_at,
        now=now,
        max_age_seconds=max_age_seconds,
        label="provider identity receipt",
    )
    return {
        "receipt_sha256": receipt_sha,
        "owner_login": owner_login,
        "repository_full_name": repository,
        "comment_id": comment_id,
        "verified_at": _format_time(verified_at),
    }


def verify_authority_receipt(
    receipt: dict[str, Any], *, now: datetime, max_age_seconds: int = MAX_AGE_SECONDS
) -> dict[str, Any]:
    receipt_sha = _verify_self_hash(
        receipt, field="receipt_sha256", label="provider authority receipt"
    )
    if receipt.get("provider") != "github":
        raise ProviderAttestedAuthorizationError(
            "provider authority receipt provider mismatch"
        )
    if receipt.get("credential_value_recorded") is not False:
        raise ProviderAttestedAuthorizationError(
            "provider authority receipt records credential material"
        )
    if receipt.get("provider_apply_performed") is not False:
        raise ProviderAttestedAuthorizationError(
            "provider authority receipt already claims provider apply"
        )
    route = receipt.get("route")
    if not isinstance(route, dict):
        raise ProviderAttestedAuthorizationError(
            "provider authority route is missing"
        )
    authority_mode = route.get("authority_mode")
    if authority_mode not in {
        "USER_SCOPED_ADMIN",
        "ALL_REPOSITORIES_INSTALLATION_ADMIN",
    }:
        raise ProviderAttestedAuthorizationError(
            "provider authority mode is insufficient"
        )
    endpoint = str(route.get("repository_creation_endpoint") or "")
    if not endpoint.startswith("https://api.github.com/"):
        raise ProviderAttestedAuthorizationError(
            "provider authority endpoint is invalid"
        )
    observed_at = _parse_time(receipt.get("observed_at"), field="observed_at")
    _verify_freshness(
        observed_at=observed_at,
        now=now,
        max_age_seconds=max_age_seconds,
        label="provider authority receipt",
    )
    return {
        "receipt_sha256": receipt_sha,
        "authority_mode": authority_mode,
        "repository_creation_endpoint": endpoint,
        "observed_at": _format_time(observed_at),
    }


def verify_decision(
    decision: dict[str, Any],
    *,
    identity: dict[str, Any],
    authority: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    if decision.get("schema") != DECISION_SCHEMA:
        raise ProviderAttestedAuthorizationError(
            "owner authorization decision schema mismatch"
        )
    decision_sha = _verify_self_hash(
        decision, field="decision_sha256", label="owner authorization decision"
    )
    if decision.get("status") != "AUTHORIZED_APPLY":
        raise ProviderAttestedAuthorizationError(
            "owner authorization decision is not approved"
        )
    if decision.get("owner_authority_preserved") is not True:
        raise ProviderAttestedAuthorizationError(
            "owner authorization decision weakens owner authority"
        )
    if decision.get("provider_apply_performed") is not False:
        raise ProviderAttestedAuthorizationError(
            "owner authorization decision already claims provider apply"
        )
    if decision.get("external_commercial_gates_advanced") is not False:
        raise ProviderAttestedAuthorizationError(
            "owner authorization decision advances external commercial gates"
        )
    expected = {
        "provider_identity_receipt_sha256": identity["receipt_sha256"],
        "provider_authority_receipt_sha256": authority["receipt_sha256"],
        "owner_login": identity["owner_login"],
        "repository_full_name": identity["repository_full_name"],
        "comment_id": identity["comment_id"],
        "authority_mode": authority["authority_mode"],
        "repository_creation_endpoint": authority["repository_creation_endpoint"],
    }
    mismatches = sorted(
        field for field, value in expected.items() if decision.get(field) != value
    )
    if mismatches:
        raise ProviderAttestedAuthorizationError(
            f"owner authorization decision binding mismatch: {mismatches}"
        )
    issued_at = _parse_time(decision.get("issued_at"), field="issued_at")
    expires_at = _parse_time(decision.get("expires_at"), field="expires_at")
    if not issued_at <= now <= expires_at:
        raise ProviderAttestedAuthorizationError(
            "owner authorization decision is not currently valid"
        )
    if (expires_at - issued_at).total_seconds() > MAX_AGE_SECONDS:
        raise ProviderAttestedAuthorizationError(
            "owner authorization decision exceeds the maximum validity window"
        )
    return {
        "decision_sha256": decision_sha,
        "issued_at": _format_time(issued_at),
        "expires_at": _format_time(expires_at),
    }


def build_intake(
    *,
    identity_receipt: dict[str, Any],
    authority_receipt: dict[str, Any],
    decision: dict[str, Any],
    now: datetime,
    max_age_seconds: int = MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Verify all bindings and produce a non-executing intake receipt."""

    identity = verify_identity_receipt(
        identity_receipt, now=now, max_age_seconds=max_age_seconds
    )
    authority = verify_authority_receipt(
        authority_receipt, now=now, max_age_seconds=max_age_seconds
    )
    verified_decision = verify_decision(
        decision, identity=identity, authority=authority, now=now
    )
    body: dict[str, Any] = {
        "schema": INTAKE_SCHEMA,
        "status": (
            "PROVIDER_ATTESTED_AUTHORIZATION_INTAKE_VERIFIED_"
            "LIVE_REPROBE_AND_OWNER_RESERVED_APPLY_REQUIRED"
        ),
        "verified_at": _format_time(now),
        "provider": "github",
        "provider_identity": identity,
        "provider_authority": authority,
        "owner_authorization": verified_decision,
        "owner_authority_preserved": True,
        "provider_request_performed": False,
        "provider_apply_performed": False,
        "authorization_consumption_state_created": False,
        "credential_value_recorded": False,
        "external_communication_performed": False,
        "external_commercial_gate_advanced": False,
    }
    body["intake_sha256"] = canonical_sha256(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-receipt", type=Path, required=True)
    parser.add_argument("--authority-receipt", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-age-seconds", type=int, default=MAX_AGE_SECONDS)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    result = build_intake(
        identity_receipt=_load_json(args.identity_receipt, "identity receipt"),
        authority_receipt=_load_json(args.authority_receipt, "authority receipt"),
        decision=_load_json(args.decision, "owner authorization decision"),
        now=now,
        max_age_seconds=args.max_age_seconds,
    )
    encoded = canonical_bytes(result) + b"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
