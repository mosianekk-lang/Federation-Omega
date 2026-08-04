#!/usr/bin/env python3
"""Authorization-enforced Phoenix provider cutover coordinator.

This module is the only supported cutover entrypoint in the exported private
Ops plane. It binds a fresh owner authorization decision, the durable one-time
authorization-use record, the exact source commit, and exact Core/Ops archives
to one provider apply.

A provider process failure, missing receipt, or invalid receipt after apply has
started is treated as an unknown provider outcome. The coordinator never retries
that apply automatically; it requires reconciliation of the existing attempt.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
EXECUTION_SCHEMA = "FEDOMEGA-PHOENIX-AUTHORIZED-CUTOVER-EXECUTION-1"
PREFLIGHT_SCHEMA = "FEDOMEGA-PHOENIX-AUTHORIZED-CUTOVER-PREFLIGHT-1"
PROVIDER_RECEIPT_SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-CUTOVER-3"
ALLOWED_AUTHORITY_MODES = {"USER_SCOPED", "INSTALLATION_TEMPLATE"}


def _load_authorization_module() -> Any:
    path = HERE / "provider_cutover_authorization_use.py"
    if not path.is_file():
        raise RuntimeError("provider cutover authorization-use module is missing")
    spec = importlib.util.spec_from_file_location(
        "phoenix_provider_cutover_authorization_use", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load_authorization_module()
HEX40 = AUTH.HEX40
HEX64 = AUTH.HEX64


class AuthorizedCutoverError(RuntimeError):
    """Fail-closed authorization, binding, or provider-proof error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _authorization_state_path(state_dir: Path, authorization_sha256: str) -> Path:
    if not isinstance(authorization_sha256, str) or not HEX64.fullmatch(
        authorization_sha256
    ):
        raise AuthorizedCutoverError("authorization_sha256 is invalid")
    return state_dir / f"{authorization_sha256}.json"


def _read_existing_authorization_use(
    decision: dict[str, Any],
    *,
    state_dir: Path,
    execution_id: str,
    source_sha: str,
    core_sha256: str,
    ops_sha256: str,
) -> dict[str, Any] | None:
    authorization_sha256 = decision.get("authorization_sha256")
    path = _authorization_state_path(state_dir, authorization_sha256)
    if not path.is_file():
        return None

    try:
        record = AUTH._read_record(path)  # integrity-verified durable v21 record
    except AUTH.AuthorizationUseError as exc:
        raise AuthorizedCutoverError(str(exc)) from exc

    expected = {
        "execution_id": execution_id,
        "authorization_id": decision.get("authorization_id"),
        "authorization_sha256": authorization_sha256,
        "source_sha": source_sha,
        "core_archive_sha256": core_sha256,
        "ops_archive_sha256": ops_sha256,
    }
    mismatches = sorted(
        key for key, value in expected.items() if record.get(key) != value
    )
    if mismatches:
        raise AuthorizedCutoverError(
            "existing authorization-use record conflicts with this execution: "
            f"{mismatches}"
        )
    return record


def prepare_execution(
    decision: dict[str, Any],
    *,
    source_sha: str,
    core_archive: Path,
    ops_archive: Path,
    now: datetime,
) -> dict[str, Any]:
    try:
        validated = AUTH.validate_decision(decision, now=now)
    except AUTH.AuthorizationUseError as exc:
        raise AuthorizedCutoverError(str(exc)) from exc

    if not isinstance(source_sha, str) or not HEX40.fullmatch(source_sha):
        raise AuthorizedCutoverError("source_sha is invalid")
    if validated["source_sha"] != source_sha:
        raise AuthorizedCutoverError(
            "source_sha does not match the authorization decision"
        )
    if not core_archive.is_file() or not ops_archive.is_file():
        raise AuthorizedCutoverError("Core and Ops archives are required")

    core_sha = sha256_file(core_archive)
    ops_sha = sha256_file(ops_archive)
    if core_sha != validated["core_archive_sha256"]:
        raise AuthorizedCutoverError(
            "Core archive digest does not match the authorization decision"
        )
    if ops_sha != validated["ops_archive_sha256"]:
        raise AuthorizedCutoverError(
            "Ops archive digest does not match the authorization decision"
        )

    authority_mode = validated.get("authority_mode")
    if authority_mode not in ALLOWED_AUTHORITY_MODES:
        raise AuthorizedCutoverError("authorization decision authority_mode is invalid")

    return {
        "schema": PREFLIGHT_SCHEMA,
        "status": "READY_FOR_OWNER_AUTHORISED_PROVIDER_APPLY",
        "authorization_id": validated["authorization_id"],
        "authorization_sha256": validated["authorization_sha256"],
        "source_sha": source_sha,
        "core_archive_sha256": core_sha,
        "ops_archive_sha256": ops_sha,
        "authority_mode": authority_mode,
        "expires_at": validated["expires_at"],
        "provider_apply_performed": False,
        "credential_value_recorded": False,
        "external_commercial_gates_advanced": False,
    }


def verify_provider_receipt(
    path: Path,
    preflight: dict[str, Any],
    *,
    owner: str,
    core: str,
    ops: str,
) -> dict[str, Any]:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorizedCutoverError(
            "provider receipt is missing or unreadable"
        ) from exc

    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if (
        not isinstance(claimed, str)
        or not HEX64.fullmatch(claimed)
        or claimed != canonical_sha256(body)
    ):
        raise AuthorizedCutoverError(
            "provider receipt failed embedded integrity verification"
        )

    checks = {
        "schema": receipt.get("schema") == PROVIDER_RECEIPT_SCHEMA,
        "status": receipt.get("status") == "VERIFIED",
        "owner": receipt.get("owner") == owner,
        "core": receipt.get("core") == core,
        "ops": receipt.get("ops") == ops,
        "core_archive": (
            receipt.get("core_archive_sha256")
            == preflight["core_archive_sha256"]
        ),
        "ops_archive": (
            receipt.get("ops_archive_sha256")
            == preflight["ops_archive_sha256"]
        ),
        "core_readback": receipt.get("core_readback", {}).get("verified") is True,
        "ops_readback": receipt.get("ops_readback", {}).get("verified") is True,
        "legacy_actions_disabled": receipt.get("legacy_actions_disabled") is True,
        "credential_boundary": receipt.get("credential_value_recorded") is False,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise AuthorizedCutoverError(
            f"provider receipt failed semantic verification: {failed}"
        )

    return {
        "receipt": receipt,
        "file_sha256": sha256_file(path),
        "checks": checks,
    }


def build_provider_command(
    *,
    owner: str,
    legacy: str,
    core: str,
    ops: str,
    core_archive: Path,
    ops_archive: Path,
    preflight: dict[str, Any],
    receipt_path: Path,
) -> list[str]:
    controller = HERE / "provider_cutover_v3_1.py"
    if not controller.is_file():
        raise AuthorizedCutoverError(
            "provider cutover v3.1 controller is missing"
        )
    return [
        sys.executable,
        str(controller),
        "--owner",
        owner,
        "--legacy",
        legacy,
        "--core",
        core,
        "--ops",
        ops,
        "--core-archive",
        str(core_archive),
        "--ops-archive",
        str(ops_archive),
        "--expected-core-sha256",
        preflight["core_archive_sha256"],
        "--expected-ops-sha256",
        preflight["ops_archive_sha256"],
        "--authority-mode",
        str(preflight["authority_mode"]),
        "--apply",
        "--receipt",
        str(receipt_path),
    ]


def default_runner(command: list[str]) -> int:
    completed = subprocess.run(
        command,
        env=os.environ.copy(),
        check=False,
    )
    return completed.returncode


def _result(
    status: str,
    *,
    preflight: dict[str, Any],
    authorization_use: dict[str, Any] | None,
    provider_apply_invoked: bool,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "schema": EXECUTION_SCHEMA,
        "status": status,
        "preflight": preflight,
        "authorization_use": authorization_use,
        "provider_apply_invoked": provider_apply_invoked,
        "credential_value_recorded": False,
        "external_commercial_gates_advanced": False,
        **extra,
    }


def execute_authorized_cutover(
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
    runner: Callable[[list[str]], int] = default_runner,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)

    if not core_archive.is_file() or not ops_archive.is_file():
        raise AuthorizedCutoverError("Core and Ops archives are required")
    core_sha = sha256_file(core_archive)
    ops_sha = sha256_file(ops_archive)
    existing = _read_existing_authorization_use(
        decision,
        state_dir=state_dir,
        execution_id=execution_id,
        source_sha=source_sha,
        core_sha256=core_sha,
        ops_sha256=ops_sha,
    )

    if existing is None or existing.get("state") == "RESERVED":
        preflight = prepare_execution(
            decision,
            source_sha=source_sha,
            core_archive=core_archive,
            ops_archive=ops_archive,
            now=current,
        )
    else:
        authority_mode = existing.get("authority_mode")
        if authority_mode not in ALLOWED_AUTHORITY_MODES:
            raise AuthorizedCutoverError(
                "authorization-use authority_mode is invalid"
            )
        preflight = {
            "schema": PREFLIGHT_SCHEMA,
            "status": "DURABLE_AUTHORIZATION_USE_RECONCILIATION",
            "authorization_id": existing["authorization_id"],
            "authorization_sha256": existing["authorization_sha256"],
            "source_sha": existing["source_sha"],
            "core_archive_sha256": existing["core_archive_sha256"],
            "ops_archive_sha256": existing["ops_archive_sha256"],
            "authority_mode": authority_mode,
            "expires_at": existing["expires_at"],
            "provider_apply_performed": existing.get(
                "provider_apply_performed", False
            ),
            "credential_value_recorded": False,
            "external_commercial_gates_advanced": False,
        }

    if existing is not None:
        state = existing.get("state")
        if state == "VERIFIED":
            return _result(
                "VERIFIED_IDEMPOTENT",
                preflight=preflight,
                authorization_use=existing,
                provider_apply_invoked=False,
                automatic_retry_performed=False,
            )
        if state == "ABORTED":
            raise AuthorizedCutoverError("authorization use is terminal: ABORTED")
        if state == "APPLY_STARTED":
            if provider_receipt_path.is_file():
                try:
                    verified = verify_provider_receipt(
                        provider_receipt_path,
                        preflight,
                        owner=owner,
                        core=core,
                        ops=ops,
                    )
                except AuthorizedCutoverError as exc:
                    return _result(
                        "PROVIDER_OUTCOME_RECONCILIATION_REQUIRED",
                        preflight=preflight,
                        authorization_use=existing,
                        provider_apply_invoked=False,
                        automatic_retry_performed=False,
                        provider_receipt_error=str(exc),
                    )
                terminal = AUTH.transition_authorization(
                    state_dir=state_dir,
                    authorization_sha256=preflight["authorization_sha256"],
                    execution_id=execution_id,
                    target_state="VERIFIED",
                    provider_receipt_sha256=verified["file_sha256"],
                    now=current,
                )
                return _result(
                    "VERIFIED_FROM_EXISTING_PROVIDER_RECEIPT",
                    preflight=preflight,
                    authorization_use=terminal,
                    provider_apply_invoked=False,
                    automatic_retry_performed=False,
                    provider_receipt=verified,
                )
            return _result(
                "PROVIDER_OUTCOME_RECONCILIATION_REQUIRED",
                preflight=preflight,
                authorization_use=existing,
                provider_apply_invoked=False,
                automatic_retry_performed=False,
            )

    authority_available = (
        bool(os.getenv("GH_ADMIN_TOKEN"))
        if provider_authority_available is None
        else provider_authority_available
    )
    if not authority_available:
        return _result(
            "PROVIDER_BLOCKED_NO_FRESH_GITHUB_AUTHORITY",
            preflight=preflight,
            authorization_use=existing,
            provider_apply_invoked=False,
            automatic_retry_performed=False,
        )

    command = build_provider_command(
        owner=owner,
        legacy=legacy,
        core=core,
        ops=ops,
        core_archive=core_archive,
        ops_archive=ops_archive,
        preflight=preflight,
        receipt_path=provider_receipt_path,
    )

    if existing is None:
        try:
            reservation = AUTH.reserve_authorization(
                decision,
                state_dir=state_dir,
                execution_id=execution_id,
                now=current,
            )
        except AUTH.AuthorizationUseError as exc:
            raise AuthorizedCutoverError(str(exc)) from exc
    else:
        reservation = existing

    try:
        started = AUTH.transition_authorization(
            state_dir=state_dir,
            authorization_sha256=preflight["authorization_sha256"],
            execution_id=execution_id,
            target_state="APPLY_STARTED",
            now=current,
        )
    except AUTH.AuthorizationUseError as exc:
        raise AuthorizedCutoverError(str(exc)) from exc

    provider_error: str | None = None
    try:
        exit_code = int(runner(command))
    except Exception as exc:
        exit_code = -1
        provider_error = f"{type(exc).__name__}: {exc}"

    if provider_receipt_path.is_file():
        try:
            verified = verify_provider_receipt(
                provider_receipt_path,
                preflight,
                owner=owner,
                core=core,
                ops=ops,
            )
        except AuthorizedCutoverError as exc:
            return _result(
                "PROVIDER_OUTCOME_RECONCILIATION_REQUIRED",
                preflight=preflight,
                authorization_use=started,
                provider_apply_invoked=True,
                provider_exit_code=exit_code,
                provider_error=provider_error,
                provider_receipt_error=str(exc),
                automatic_retry_performed=False,
            )

        terminal = AUTH.transition_authorization(
            state_dir=state_dir,
            authorization_sha256=preflight["authorization_sha256"],
            execution_id=execution_id,
            target_state="VERIFIED",
            provider_receipt_sha256=verified["file_sha256"],
            now=current,
        )
        return _result(
            "VERIFIED",
            preflight=preflight,
            authorization_use=terminal,
            provider_apply_invoked=True,
            provider_exit_code=exit_code,
            provider_error=provider_error,
            provider_receipt=verified,
            automatic_retry_performed=False,
        )

    return _result(
        "PROVIDER_OUTCOME_RECONCILIATION_REQUIRED",
        preflight=preflight,
        authorization_use=started,
        provider_apply_invoked=True,
        provider_exit_code=exit_code,
        provider_error=provider_error,
        automatic_retry_performed=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--source-sha", required=True)
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

    decision = json.loads(args.decision.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    if not args.apply:
        result = prepare_execution(
            decision,
            source_sha=args.source_sha,
            core_archive=args.core_archive,
            ops_archive=args.ops_archive,
            now=now,
        )
        result["status"] = (
            "PREPARED_PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    result = execute_authorized_cutover(
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
