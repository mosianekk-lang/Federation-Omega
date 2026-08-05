#!/usr/bin/env python3
"""Canonical Phoenix cutover launcher with exact owner/provider-authority binding.

This wrapper performs no provider mutation of its own. It requires an owner
authorization decision that is bound to the exact initial provider-authority
receipt and repository-creation endpoint, then delegates to the existing
freshness, semantic, just-in-time continuity, candidate, source and one-time-use
guards.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
SCHEMA = "FEDOMEGA-PHOENIX-OWNER-AUTHORITY-BOUND-EXECUTION-1"
DECISION_SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class OwnerAuthorityBindingError(RuntimeError):
    """Fail-closed owner/provider authority binding error."""


def _load_authority_bound_module() -> Any:
    path = HERE / "provider_cutover_authority_bound.py"
    if not path.is_file():
        raise OwnerAuthorityBindingError(
            "required module is missing: provider_cutover_authority_bound.py"
        )
    spec = importlib.util.spec_from_file_location(
        "phoenix_owner_authority_bound_base", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OwnerAuthorityBindingError(f"{label} is missing or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise OwnerAuthorityBindingError(f"{label} must be a JSON object")
    return payload


def verify_owner_authority_binding(
    decision: dict[str, Any], authority_receipt: dict[str, Any]
) -> dict[str, Any]:
    if decision.get("schema") != DECISION_SCHEMA:
        raise OwnerAuthorityBindingError("owner authorization decision schema is invalid")
    if decision.get("status") != "AUTHORIZED_APPLY":
        raise OwnerAuthorityBindingError("owner authorization decision is not approved")
    if decision.get("provider_authority_binding_required") is not True:
        raise OwnerAuthorityBindingError("owner decision does not require provider binding")
    if decision.get("owner_authority_preserved") is not True:
        raise OwnerAuthorityBindingError("owner decision weakens owner authority")
    if decision.get("credential_value_recorded") is not False:
        raise OwnerAuthorityBindingError("owner decision records credential material")
    if decision.get("external_commercial_gates_advanced") is not False:
        raise OwnerAuthorityBindingError("owner decision advances external commercial gates")

    claimed = authority_receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        raise OwnerAuthorityBindingError("provider authority receipt SHA-256 is invalid")
    body = dict(authority_receipt)
    body.pop("receipt_sha256", None)
    base = _load_authority_bound_module()
    if base.canonical_sha256(body) != claimed:
        raise OwnerAuthorityBindingError("provider authority receipt hash verification failed")

    route = authority_receipt.get("route")
    if not isinstance(route, dict):
        raise OwnerAuthorityBindingError("provider authority receipt route is missing")
    expected = {
        "provider_authority_receipt_sha256": claimed,
        "authority_mode": route.get("authority_mode"),
        "repository_creation_endpoint": route.get("repository_creation_endpoint"),
    }
    mismatches = sorted(
        field for field, value in expected.items() if decision.get(field) != value
    )
    if mismatches:
        raise OwnerAuthorityBindingError(
            f"owner decision conflicts with provider authority receipt: {mismatches}"
        )
    return {
        "status": "OWNER_AUTHORITY_BINDING_VERIFIED",
        "provider_authority_receipt_sha256": claimed,
        "authority_mode": expected["authority_mode"],
        "repository_creation_endpoint": expected["repository_creation_endpoint"],
        "credential_value_recorded": False,
        "provider_apply_performed": False,
    }


def execute_owner_authority_bound_cutover(
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
    max_receipt_age_seconds: int = 300,
) -> dict[str, Any]:
    try:
        binding = verify_owner_authority_binding(decision, authority_receipt)
    except OwnerAuthorityBindingError as exc:
        return {
            "schema": SCHEMA,
            "status": "OWNER_AUTHORITY_BINDING_INVALIDATED",
            "binding_error": str(exc),
            "provider_apply_invoked": False,
            "authorization_state_created": state_dir.exists(),
            "credential_value_recorded": False,
        }

    base = _load_authority_bound_module()
    result = base.execute_authority_bound_cutover(
        candidate,
        decision,
        authority_receipt,
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
        provider_authority_available=provider_authority_available,
        source_head_reader=source_head_reader,
        authority_reprobe=authority_reprobe,
        max_receipt_age_seconds=max_receipt_age_seconds,
    )
    result["owner_authority_binding"] = binding
    result["canonical_apply_entrypoint"] = (
        "provider_cutover_owner_authority_bound.py"
    )
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
    parser.add_argument("--authority-max-age-seconds", type=int, default=300)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    candidate = load_json(args.candidate, "candidate manifest")
    decision = load_json(args.decision, "authorization decision")
    authority_receipt = load_json(args.authority_receipt, "authority receipt")
    binding = verify_owner_authority_binding(decision, authority_receipt)
    if not args.apply:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "OWNER_AUTHORITY_BINDING_VERIFIED_LIVE_REPROBE_REQUIRED_FOR_APPLY",
                    "owner_authority_binding": binding,
                    "provider_apply_invoked": False,
                    "credential_value_recorded": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    result = execute_owner_authority_bound_cutover(
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
        max_receipt_age_seconds=args.authority_max_age_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"VERIFIED", "IDEMPOTENT_VERIFIED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
