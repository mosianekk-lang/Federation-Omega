#!/usr/bin/env python3
"""Canonical authority-bound Phoenix provider cutover launcher.

The launcher requires a hash-valid, GET-only provider-authority receipt before
it delegates to the candidate, live-source and one-time authorization guards.
It records no credential value and makes no provider mutation of its own.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
SCHEMA = "FEDOMEGA-PHOENIX-AUTHORITY-BOUND-EXECUTION-1"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class AuthorityBoundError(RuntimeError):
    """Fail-closed authority-receipt or delegation error."""


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorityBoundError(f"{label} is missing or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AuthorityBoundError(f"{label} must be a JSON object")
    return payload


def _load_candidate_module() -> Any:
    path = HERE / "provider_cutover_candidate.py"
    if not path.is_file():
        raise AuthorityBoundError("candidate launcher is missing")
    spec = importlib.util.spec_from_file_location("phoenix_authority_bound_candidate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_authority_receipt(
    receipt: dict[str, Any],
    *,
    candidate: dict[str, Any],
    decision: dict[str, Any],
    owner: str,
    legacy: str,
    core: str,
    ops: str,
) -> dict[str, Any]:
    if receipt.get("schema") != "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1":
        raise AuthorityBoundError("authority receipt schema is invalid")
    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        raise AuthorityBoundError("authority receipt SHA-256 is invalid")
    if claimed != canonical_sha256(body):
        raise AuthorityBoundError("authority receipt embedded SHA-256 verification failed")
    if receipt.get("status") != "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY":
        raise AuthorityBoundError("provider authority is not ready")
    exact = {
        "owner": owner,
        "legacy": legacy,
        "core": core,
        "ops": ops,
        "legacy_main_sha": candidate.get("source_sha"),
    }
    mismatches = sorted(key for key, value in exact.items() if receipt.get(key) != value)
    if mismatches:
        raise AuthorityBoundError(
            f"authority receipt conflicts with candidate target: {mismatches}"
        )
    route = receipt.get("route")
    if not isinstance(route, dict):
        raise AuthorityBoundError("authority receipt route is missing")
    if route.get("authority_mode") != decision.get("authority_mode"):
        raise AuthorityBoundError("authority receipt mode does not match decision")
    if receipt.get("owner_authorization_still_required") is not True:
        raise AuthorityBoundError("authority receipt weakens owner authorization boundary")
    for field in (
        "provider_apply_performed",
        "provider_mutation_performed",
        "credential_value_recorded",
    ):
        if receipt.get(field) is not False:
            raise AuthorityBoundError(f"authority receipt has unsafe {field}")
    return {
        "status": receipt["status"],
        "receipt_sha256": claimed,
        "authority_mode": route["authority_mode"],
        "legacy_main_sha": receipt["legacy_main_sha"],
        "credential_value_recorded": False,
    }


def execute_authority_bound_cutover(
    candidate: dict[str, Any],
    decision: dict[str, Any],
    authority_receipt: dict[str, Any],
    *,
    state_dir: Path,
    execution_id: str,
    core_archive: Path,
    ops_archive: Path,
    provider_receipt_path: Path,
    owner: str = "mosianekk-lang",
    legacy: str = "Federation-Omega",
    core: str = "Federation-Omega-Core",
    ops: str = "Federation-Omega-Ops",
    now: datetime | None = None,
    provider_authority_available: bool | None = None,
    source_head_reader: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    candidate_module = _load_candidate_module()
    authority_available = (
        bool(os.getenv("GH_ADMIN_TOKEN"))
        if provider_authority_available is None
        else provider_authority_available
    )
    if not authority_available:
        return {
            "schema": SCHEMA,
            "status": "AUTHORITY_BLOCKED_NO_PRIVATE_CREDENTIAL",
            "provider_apply_invoked": False,
            "authorization_state_created": state_dir.exists(),
            "credential_value_recorded": False,
        }
    try:
        proof = verify_authority_receipt(
            authority_receipt,
            candidate=candidate,
            decision=decision,
            owner=owner,
            legacy=legacy,
            core=core,
            ops=ops,
        )
    except AuthorityBoundError as exc:
        return {
            "schema": SCHEMA,
            "status": "AUTHORITY_INVALIDATED",
            "authority_error": str(exc),
            "provider_apply_invoked": False,
            "authorization_state_created": state_dir.exists(),
            "credential_value_recorded": False,
        }
    result = candidate_module.execute_candidate_cutover(
        candidate,
        decision,
        state_dir=state_dir,
        execution_id=execution_id,
        core_archive=core_archive,
        ops_archive=ops_archive,
        provider_receipt_path=provider_receipt_path,
        owner=owner,
        legacy=legacy,
        core=core,
        ops=ops,
        now=now,
        provider_authority_available=True,
        source_head_reader=source_head_reader,
    )
    result["provider_authority"] = proof
    result["canonical_apply_entrypoint"] = "provider_cutover_authority_bound.py"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--authority-receipt", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument(
        "--provider-receipt",
        type=Path,
        default=Path("phoenix-provider-cutover-v3-receipt.json"),
    )
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--legacy", default="Federation-Omega")
    parser.add_argument("--core", default="Federation-Omega-Core")
    parser.add_argument("--ops", default="Federation-Omega-Ops")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    candidate = load_json(args.candidate, "candidate manifest")
    decision = load_json(args.decision, "authorization decision")
    authority_receipt = load_json(args.authority_receipt, "authority receipt")
    if not args.apply:
        proof = verify_authority_receipt(
            authority_receipt,
            candidate=candidate,
            decision=decision,
            owner=args.owner,
            legacy=args.legacy,
            core=args.core,
            ops=args.ops,
        )
        result = {
            "schema": SCHEMA,
            "status": "AUTHORITY_RECEIPT_VERIFIED_APPLY_NOT_REQUESTED",
            "provider_authority": proof,
            "provider_apply_invoked": False,
            "credential_value_recorded": False,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    result = execute_authority_bound_cutover(
        candidate,
        decision,
        authority_receipt,
        state_dir=args.state_dir,
        execution_id=args.execution_id,
        core_archive=args.core_archive,
        ops_archive=args.ops_archive,
        provider_receipt_path=args.provider_receipt,
        owner=args.owner,
        legacy=args.legacy,
        core=args.core,
        ops=args.ops,
        now=datetime.now(timezone.utc),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if str(result.get("status", "")).startswith("VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
