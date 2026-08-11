#!/usr/bin/env python3
"""Validate an owner-issued Phoenix cutover authorization bound to provider authority.

This module performs no provider mutation. It extends the v1 owner authorization
capsule by binding the decision to one exact, hash-valid provider-authority
receipt and its repository-creation endpoint. A just-in-time GET-only re-probe
is still required by the private Ops execution entrypoint before any provider
state or provider call may occur.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phoenix.provider_cutover_authorization import (
    AuthorizationError,
    canonical_sha256,
    file_sha256,
    validate_authorization,
)

SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-2"
DECISION_SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2"
AUTHORITY_RECEIPT_SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_ENDPOINTS = {
    "USER_SCOPED": "/user/repos",
    "INSTALLATION_TEMPLATE": "/repos/mosianekk-lang/Federation-Omega/generate",
}


def verify_authority_receipt_binding(receipt: dict[str, Any]) -> dict[str, str]:
    if receipt.get("schema") != AUTHORITY_RECEIPT_SCHEMA:
        raise AuthorizationError("provider authority receipt schema is invalid")
    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        raise AuthorizationError("provider authority receipt SHA-256 is invalid")
    if canonical_sha256(body) != claimed:
        raise AuthorizationError("provider authority receipt hash verification failed")
    if receipt.get("status") != "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY":
        raise AuthorizationError("provider authority receipt is not ready")
    route = receipt.get("route")
    if not isinstance(route, dict):
        raise AuthorizationError("provider authority receipt route is missing")
    mode = route.get("authority_mode")
    endpoint = route.get("repository_creation_endpoint")
    if mode not in ALLOWED_ENDPOINTS:
        raise AuthorizationError("provider authority mode is invalid")
    if endpoint != ALLOWED_ENDPOINTS[mode]:
        raise AuthorizationError("provider authority endpoint is invalid for mode")
    if receipt.get("owner_authorization_still_required") is not True:
        raise AuthorizationError("provider authority receipt weakens owner authority")
    for field in (
        "provider_apply_performed",
        "provider_mutation_performed",
        "credential_value_recorded",
    ):
        if receipt.get(field) is not False:
            raise AuthorizationError(f"provider authority receipt has unsafe {field}")
    return {
        "receipt_sha256": claimed,
        "authority_mode": mode,
        "repository_creation_endpoint": endpoint,
    }


def validate_authorization_v2(
    payload: dict[str, Any],
    *,
    authority_receipt: dict[str, Any],
    now: datetime,
    source_sha: str,
    core_archive_sha256: str,
    ops_archive_sha256: str,
) -> dict[str, Any]:
    if payload.get("schema") != SCHEMA:
        raise AuthorizationError(f"schema must equal {SCHEMA!r}")

    v1_payload = dict(payload)
    v1_payload["schema"] = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-1"
    v1_payload.pop("provider_authority_receipt_sha256", None)
    v1_payload.pop("repository_creation_endpoint", None)
    base = validate_authorization(
        v1_payload,
        now=now,
        source_sha=source_sha,
        core_archive_sha256=core_archive_sha256,
        ops_archive_sha256=ops_archive_sha256,
    )
    binding = verify_authority_receipt_binding(authority_receipt)
    if payload.get("provider_authority_receipt_sha256") != binding["receipt_sha256"]:
        raise AuthorizationError("provider_authority_receipt_sha256 must bind the exact receipt")
    if payload.get("repository_creation_endpoint") != binding["repository_creation_endpoint"]:
        raise AuthorizationError("repository_creation_endpoint must bind the exact provider route")
    if payload.get("authority_mode") != binding["authority_mode"]:
        raise AuthorizationError("authority_mode must match the bound provider receipt")

    decision = dict(base)
    decision.update(
        {
            "schema": DECISION_SCHEMA,
            "provider_authority_receipt_sha256": binding["receipt_sha256"],
            "repository_creation_endpoint": binding["repository_creation_endpoint"],
            "provider_authority_binding_required": True,
            "owner_authority_preserved": True,
            "credential_value_recorded": False,
            "external_commercial_gates_advanced": False,
        }
    )
    decision["authorization_sha256"] = canonical_sha256(payload)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--provider-authority-receipt", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.authorization.read_text(encoding="utf-8"))
    authority_receipt = json.loads(
        args.provider_authority_receipt.read_text(encoding="utf-8")
    )
    decision = validate_authorization_v2(
        payload,
        authority_receipt=authority_receipt,
        now=datetime.now(timezone.utc),
        source_sha=args.source_sha,
        core_archive_sha256=file_sha256(args.core_archive),
        ops_archive_sha256=file_sha256(args.ops_archive),
    )
    receipt = dict(decision)
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    args.receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
