#!/usr/bin/env python3
"""Canonical guarded Phoenix provider cutover launcher.

This is the only supported apply entrypoint in the exported Ops plane. It
verifies the live legacy main head before authorization reservation, rechecks it
after APPLY_STARTED and immediately before the provider controller, and binds
the same source SHA into the provider receipt before authorization completion.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "provider_cutover.py"
API = "https://api.github.com"
API_VERSION = "2026-03-10"
HEX40 = __import__("re").compile(r"^[0-9a-fA-F]{40}$")
GUARD_SCHEMA = "FEDOMEGA-PHOENIX-LIVE-SOURCE-APPLY-GUARD-1"


def _load_base() -> Any:
    if not BASE_PATH.is_file():
        raise RuntimeError("base provider cutover coordinator is missing")
    spec = importlib.util.spec_from_file_location("phoenix_cutover_guard_base", BASE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base()
GuardError = BASE.AuthorizedCutoverError


def live_source_head(owner: str, legacy: str) -> str:
    token = os.getenv("GH_ADMIN_TOKEN", "")
    if not token:
        raise GuardError("GH_ADMIN_TOKEN is required for live source-head verification")
    request = urllib.request.Request(
        f"{API}/repos/{owner}/{legacy}/git/ref/heads/main",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "federation-omega-phoenix-live-source-guard",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        raise GuardError("live legacy main could not be read from GitHub") from exc
    observed = payload.get("object", {}).get("sha")
    if not isinstance(observed, str) or not HEX40.fullmatch(observed):
        raise GuardError("live legacy main returned an invalid SHA")
    return observed.lower()


def verify_live_source(expected: str, owner: str, legacy: str, reader: Callable[[str, str], str]) -> str:
    if not isinstance(expected, str) or not HEX40.fullmatch(expected):
        raise GuardError("expected source SHA is invalid")
    observed = reader(owner, legacy)
    if not isinstance(observed, str) or not HEX40.fullmatch(observed):
        raise GuardError("source-head reader returned an invalid SHA")
    observed = observed.lower()
    expected = expected.lower()
    if observed != expected:
        raise GuardError(
            "live legacy main moved after authorization: "
            f"expected {expected}, observed {observed}"
        )
    return observed


def guarded_receipt_verifier(path: Path, preflight: dict[str, Any], *, owner: str, core: str, ops: str):
    verified = BASE._ORIGINAL_VERIFY_PROVIDER_RECEIPT(path, preflight, owner=owner, core=core, ops=ops)
    receipt = verified["receipt"]
    if receipt.get("source_sha") != preflight.get("source_sha"):
        raise GuardError("provider receipt source_sha does not match authorized source")
    return verified


def guarded_runner(expected_source: str, owner: str, legacy: str, reader: Callable[[str, str], str]):
    def run(command: list[str]) -> int:
        verify_live_source(expected_source, owner, legacy, reader)
        guarded_controller = HERE / "provider_cutover_v3_live_guard.py"
        if not guarded_controller.is_file():
            raise GuardError("guarded provider controller is missing")
        guarded = list(command)
        guarded[1] = str(guarded_controller)
        guarded.extend(["--expected-source-sha", expected_source])
        environment = os.environ.copy()
        environment["FEDOMEGA_GUARDED_APPLY"] = "1"
        completed = subprocess.run(guarded, env=environment, check=False)
        return completed.returncode
    return run


def execute_guarded_cutover(
    decision: dict[str, Any],
    *,
    state_dir: Path,
    execution_id: str,
    source_sha: str,
    core_archive: Path,
    ops_archive: Path,
    provider_receipt_path: Path,
    owner: str = "mosianekk-lang",
    legacy: str = "Federation-Omega",
    core: str = "Federation-Omega-Core",
    ops: str = "Federation-Omega-Ops",
    now: datetime | None = None,
    provider_authority_available: bool | None = None,
    source_head_reader: Callable[[str, str], str] = live_source_head,
) -> dict[str, Any]:
    authority = bool(os.getenv("GH_ADMIN_TOKEN")) if provider_authority_available is None else provider_authority_available
    if authority:
        observed = verify_live_source(source_sha, owner, legacy, source_head_reader)
    else:
        observed = None

    original_verify = BASE.verify_provider_receipt
    BASE._ORIGINAL_VERIFY_PROVIDER_RECEIPT = original_verify
    BASE.verify_provider_receipt = guarded_receipt_verifier
    try:
        result = BASE.execute_authorized_cutover(
            decision,
            state_dir=state_dir,
            execution_id=execution_id,
            source_sha=source_sha,
            core_archive=core_archive,
            ops_archive=ops_archive,
            provider_receipt_path=provider_receipt_path,
            owner=owner,
            legacy=legacy,
            core=core,
            ops=ops,
            now=now,
            provider_authority_available=authority,
            runner=guarded_runner(source_sha, owner, legacy, source_head_reader),
        )
    finally:
        BASE.verify_provider_receipt = original_verify
        delattr(BASE, "_ORIGINAL_VERIFY_PROVIDER_RECEIPT")
    result["live_source_guard"] = {
        "schema": GUARD_SCHEMA,
        "pre_reservation_head_sha": observed,
        "pre_reservation_verified": observed == source_sha.lower() if observed else False,
        "pre_mutation_recheck_required": True,
        "provider_receipt_source_binding_required": True,
        "legacy_entrypoint_technically_blocked": False,
        "legacy_entrypoint_status": "DEPRECATED_NON_CANONICAL_DO_NOT_APPLY_DIRECTLY",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument("--provider-receipt", type=Path, default=Path("phoenix-provider-cutover-v3-receipt.json"))
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--legacy", default="Federation-Omega")
    parser.add_argument("--core", default="Federation-Omega-Core")
    parser.add_argument("--ops", default="Federation-Omega-Ops")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    decision = json.loads(args.decision.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    if not args.apply:
        result = BASE.prepare_execution(
            decision,
            source_sha=args.source_sha,
            core_archive=args.core_archive,
            ops_archive=args.ops_archive,
            now=now,
        )
        result["status"] = "PREPARED_PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED"
        result["canonical_apply_entrypoint"] = "provider_cutover_guarded.py"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    result = execute_guarded_cutover(
        decision,
        state_dir=args.state_dir,
        execution_id=args.execution_id,
        source_sha=args.source_sha,
        core_archive=args.core_archive,
        ops_archive=args.ops_archive,
        provider_receipt_path=args.provider_receipt,
        owner=args.owner,
        legacy=args.legacy,
        core=args.core,
        ops=args.ops,
        now=now,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
