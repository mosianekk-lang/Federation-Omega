#!/usr/bin/env python3
"""Canonical authority-bound Phoenix provider cutover launcher.

The launcher requires a hash-valid, recent provider-authority receipt and a
just-in-time GET-only authority re-probe before it delegates to the candidate,
live-source and one-time authorization guards. It records no credential value
and makes no provider mutation of its own.
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
SCHEMA = "FEDOMEGA-PHOENIX-AUTHORITY-BOUND-EXECUTION-2"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
DEFAULT_MAX_RECEIPT_AGE_SECONDS = 300
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 30


class AuthorityBoundError(RuntimeError):
    """Fail-closed authority-receipt, continuity or delegation error."""


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


def _load_module(filename: str, module_name: str) -> Any:
    path = HERE / filename
    if not path.is_file():
        raise AuthorityBoundError(f"required module is missing: {filename}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_candidate_module() -> Any:
    return _load_module(
        "provider_cutover_candidate.py",
        "phoenix_authority_bound_candidate",
    )


def _load_probe_module() -> Any:
    return _load_module(
        "provider_authority_probe.py",
        "phoenix_authority_bound_probe",
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuthorityBoundError("authority time must include a timezone")
    return value.astimezone(timezone.utc)


def _parse_observed_at(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityBoundError("authority receipt observed_at is missing")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        observed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AuthorityBoundError(
            "authority receipt observed_at is not valid ISO-8601"
        ) from exc
    return _utc(observed)


def _verify_freshness(
    receipt: dict[str, Any],
    *,
    now: datetime,
    max_age_seconds: int,
    max_future_skew_seconds: int,
) -> dict[str, Any]:
    if max_age_seconds <= 0:
        raise AuthorityBoundError("authority receipt max age must be positive")
    if max_future_skew_seconds < 0:
        raise AuthorityBoundError("authority future skew cannot be negative")
    observed = _parse_observed_at(receipt.get("observed_at"))
    current = _utc(now)
    age_seconds = (current - observed).total_seconds()
    if age_seconds < -max_future_skew_seconds:
        raise AuthorityBoundError("authority receipt observed_at is in the future")
    if age_seconds > max_age_seconds:
        raise AuthorityBoundError("authority receipt is stale")
    return {
        "observed_at": observed.isoformat(),
        "age_seconds": max(0.0, round(age_seconds, 6)),
        "max_age_seconds": max_age_seconds,
        "max_future_skew_seconds": max_future_skew_seconds,
    }


def verify_authority_receipt(
    receipt: dict[str, Any],
    *,
    candidate: dict[str, Any],
    decision: dict[str, Any],
    owner: str,
    legacy: str,
    core: str,
    ops: str,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_RECEIPT_AGE_SECONDS,
    max_future_skew_seconds: int = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
) -> dict[str, Any]:
    if receipt.get("schema") != "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1":
        raise AuthorityBoundError("authority receipt schema is invalid")
    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        raise AuthorityBoundError("authority receipt SHA-256 is invalid")
    if claimed != canonical_sha256(body):
        raise AuthorityBoundError(
            "authority receipt embedded SHA-256 verification failed"
        )
    if receipt.get("status") != "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY":
        raise AuthorityBoundError("provider authority is not ready")

    freshness = _verify_freshness(
        receipt,
        now=now or datetime.now(timezone.utc),
        max_age_seconds=max_age_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
    )
    blockers = receipt.get("blockers")
    if blockers != []:
        raise AuthorityBoundError("authority receipt contains blockers")
    checks = receipt.get("checks")
    if not isinstance(checks, dict) or any(value is not True for value in checks.values()):
        raise AuthorityBoundError("authority receipt contains failed or invalid checks")

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
        "repository_creation_endpoint": route.get("repository_creation_endpoint"),
        "legacy_main_sha": receipt["legacy_main_sha"],
        "core_target_exists": receipt.get("core_target_exists"),
        "ops_target_exists": receipt.get("ops_target_exists"),
        "freshness": freshness,
        "credential_value_recorded": False,
    }


def _default_authority_reprobe(
    *,
    owner: str,
    legacy: str,
    core: str,
    ops: str,
    now: datetime,
) -> dict[str, Any]:
    token = os.getenv("GH_ADMIN_TOKEN", "")
    if not token:
        raise AuthorityBoundError(
            "just-in-time authority re-probe requires GH_ADMIN_TOKEN"
        )
    probe = _load_probe_module()
    return probe.probe_authority(
        probe.GitHubReadClient(token),
        owner=owner,
        legacy=legacy,
        core=core,
        ops=ops,
        now=now,
    )


def _continuity_projection(proof: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority_mode": proof.get("authority_mode"),
        "repository_creation_endpoint": proof.get("repository_creation_endpoint"),
        "legacy_main_sha": proof.get("legacy_main_sha"),
        "core_target_exists": proof.get("core_target_exists"),
        "ops_target_exists": proof.get("ops_target_exists"),
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
    authority_reprobe: Callable[[], dict[str, Any]] | None = None,
    max_receipt_age_seconds: int = DEFAULT_MAX_RECEIPT_AGE_SECONDS,
) -> dict[str, Any]:
    current = _utc(now or datetime.now(timezone.utc))
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
        initial_proof = verify_authority_receipt(
            authority_receipt,
            candidate=candidate,
            decision=decision,
            owner=owner,
            legacy=legacy,
            core=core,
            ops=ops,
            now=current,
            max_age_seconds=max_receipt_age_seconds,
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

    try:
        live_receipt = (
            authority_reprobe()
            if authority_reprobe is not None
            else _default_authority_reprobe(
                owner=owner,
                legacy=legacy,
                core=core,
                ops=ops,
                now=current,
            )
        )
        live_proof = verify_authority_receipt(
            live_receipt,
            candidate=candidate,
            decision=decision,
            owner=owner,
            legacy=legacy,
            core=core,
            ops=ops,
            now=current,
            max_age_seconds=max_receipt_age_seconds,
        )
    except (AuthorityBoundError, OSError, RuntimeError) as exc:
        return {
            "schema": SCHEMA,
            "status": "AUTHORITY_REPROBE_FAILED",
            "authority_error": str(exc),
            "provider_apply_invoked": False,
            "authorization_state_created": state_dir.exists(),
            "credential_value_recorded": False,
        }

    initial_projection = _continuity_projection(initial_proof)
    live_projection = _continuity_projection(live_proof)
    if initial_projection != live_projection:
        changed = sorted(
            key
            for key in initial_projection
            if initial_projection.get(key) != live_projection.get(key)
        )
        return {
            "schema": SCHEMA,
            "status": "AUTHORITY_CONTINUITY_INVALIDATED",
            "authority_error": f"authority continuity changed: {changed}",
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
        now=current,
        provider_authority_available=True,
        source_head_reader=source_head_reader,
    )
    result["provider_authority"] = {
        "status": "AUTHORITY_CONTINUITY_VERIFIED",
        "initial_receipt_sha256": initial_proof["receipt_sha256"],
        "live_receipt_sha256": live_proof["receipt_sha256"],
        "authority_mode": live_proof["authority_mode"],
        "legacy_main_sha": live_proof["legacy_main_sha"],
        "initial_freshness": initial_proof["freshness"],
        "live_freshness": live_proof["freshness"],
        "continuity_projection": live_projection,
        "just_in_time_reprobe_get_only": True,
        "credential_value_recorded": False,
    }
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
    parser.add_argument(
        "--authority-max-age-seconds",
        type=int,
        default=DEFAULT_MAX_RECEIPT_AGE_SECONDS,
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    candidate = load_json(args.candidate, "candidate manifest")
    decision = load_json(args.decision, "authorization decision")
    authority_receipt = load_json(args.authority_receipt, "authority receipt")
    current = datetime.now(timezone.utc)
    if not args.apply:
        proof = verify_authority_receipt(
            authority_receipt,
            candidate=candidate,
            decision=decision,
            owner=args.owner,
            legacy=args.legacy,
            core=args.core,
            ops=args.ops,
            now=current,
            max_age_seconds=args.authority_max_age_seconds,
        )
        result = {
            "schema": SCHEMA,
            "status": "AUTHORITY_RECEIPT_VERIFIED_LIVE_REPROBE_REQUIRED_FOR_APPLY",
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
        now=current,
        max_receipt_age_seconds=args.authority_max_age_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if str(result.get("status", "")).startswith("VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
