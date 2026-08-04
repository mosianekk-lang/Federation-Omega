#!/usr/bin/env python3
"""Phoenix provider cutover v3.2 with mandatory exact owner authorization.

Dry-run remains side-effect free and requires no mandate. Apply mode is rejected
before provider access unless a short-lived authorization capsule is valid and
matches the exact command scope, source commit and Core/Ops archive digests.
Only a hash-bound decision is persisted; the authorization capsule and provider
credential are never copied into the provider receipt.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent

V31_CANDIDATES = [
    HERE / "provider_cutover_v3_1_base.py",
    HERE / "provider_cutover_v3_1.py",
]
V31_PATH = next((path for path in V31_CANDIDATES if path.is_file()), None)
if V31_PATH is None:
    raise RuntimeError("Phoenix v3.1 exact-lease controller is missing")

AUTH_CANDIDATES = [
    HERE / "provider_cutover_authorization.py",
]
AUTH_PATH = next((path for path in AUTH_CANDIDATES if path.is_file()), None)
if AUTH_PATH is None:
    raise RuntimeError("Phoenix owner-authorization verifier is missing")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V31 = _load("phoenix_provider_cutover_v3_1_base", V31_PATH)
AUTH = _load("phoenix_provider_cutover_authorization", AUTH_PATH)


@dataclass(frozen=True)
class AuthorizedInvocation:
    argv: list[str]
    decision: dict[str, Any] | None
    decision_receipt: Path | None


def _wrapper_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument(
        "--authorization-receipt",
        type=Path,
        default=Path("phoenix-provider-cutover-authorization-decision.json"),
    )
    return parser


def _base_scope_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument("--core-public", action="store_true")
    parser.add_argument("--replace-existing-main", action="store_true")
    parser.add_argument("--archive-legacy", action="store_true")
    parser.add_argument(
        "--authority-mode",
        choices=["auto", "user", "installation"],
        default="auto",
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def _authority_mode_for_base(value: str) -> str:
    return {
        "USER_SCOPED": "user",
        "INSTALLATION_TEMPLATE": "installation",
    }[value]


def _require_scope_match(payload: dict[str, Any], scope: argparse.Namespace) -> str:
    actions = payload["actions"]
    comparisons = {
        "core_private": (payload["core_private"], not scope.core_public),
        "actions.replace_existing_main": (
            actions["replace_existing_main"],
            scope.replace_existing_main,
        ),
        "actions.archive_legacy": (actions["archive_legacy"], scope.archive_legacy),
    }
    for field, (authorized, requested) in comparisons.items():
        if authorized is not requested:
            raise AUTH.AuthorizationError(
                f"authorization scope mismatch for {field}: "
                f"authorized={authorized!r}, requested={requested!r}"
            )

    exact_mode = _authority_mode_for_base(payload["authority_mode"])
    if scope.authority_mode not in {"auto", exact_mode}:
        raise AUTH.AuthorizationError(
            "authorization authority_mode does not match requested provider route"
        )
    return exact_mode


def _write_decision(path: Path, decision: dict[str, Any]) -> None:
    receipt = dict(decision)
    receipt["schema"] = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2"
    receipt["receipt_sha256"] = AUTH.canonical_sha256(receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prepare_invocation(
    argv: Sequence[str],
    *,
    now: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> AuthorizedInvocation:
    """Validate wrapper arguments and return an exact base-controller command."""

    wrapper, remaining = _wrapper_parser().parse_known_args(list(argv))
    scope, unknown = _base_scope_parser().parse_known_args(remaining)
    if unknown:
        # Unknown base arguments are intentionally preserved for the v3 engine.
        pass

    if not scope.apply:
        if wrapper.authorization or wrapper.source_sha:
            raise AUTH.AuthorizationError(
                "authorization inputs are prohibited in dry-run mode"
            )
        return AuthorizedInvocation(list(remaining), None, None)

    if wrapper.authorization is None:
        raise AUTH.AuthorizationError("--authorization is required with --apply")
    if not wrapper.source_sha:
        raise AUTH.AuthorizationError("--source-sha is required with --apply")
    if not wrapper.authorization.is_file():
        raise AUTH.AuthorizationError(
            f"authorization file not found: {wrapper.authorization}"
        )

    payload = json.loads(wrapper.authorization.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AUTH.AuthorizationError("authorization must be a JSON object")

    environment = dict(os.environ if environ is None else environ)
    provider_sha = environment.get("GITHUB_SHA")
    if provider_sha and provider_sha != wrapper.source_sha:
        raise AUTH.AuthorizationError(
            "--source-sha does not match provider-native GITHUB_SHA"
        )

    decision = AUTH.validate_authorization(
        payload,
        now=(now or datetime.now(timezone.utc)),
        source_sha=wrapper.source_sha,
        core_archive_sha256=AUTH.file_sha256(scope.core_archive),
        ops_archive_sha256=AUTH.file_sha256(scope.ops_archive),
    )
    exact_mode = _require_scope_match(payload, scope)

    sanitized = list(remaining)
    if scope.authority_mode == "auto":
        sanitized.extend(["--authority-mode", exact_mode])

    decision = dict(decision)
    decision.update(
        {
            "command_scope_verified": True,
            "provider_native_source_sha_verified": (
                provider_sha == wrapper.source_sha if provider_sha else None
            ),
            "provider_authority_mode_pinned": exact_mode,
            "core_private": not scope.core_public,
            "ops_private": True,
            "replace_existing_main": scope.replace_existing_main,
            "archive_legacy": scope.archive_legacy,
            "authorization_capsule_persisted": False,
            "provider_credential_persisted": False,
        }
    )
    _write_decision(wrapper.authorization_receipt, decision)
    return AuthorizedInvocation(
        sanitized,
        decision,
        wrapper.authorization_receipt,
    )


def _install_receipt_binding(decision: dict[str, Any]) -> None:
    original = V31.V3.write_receipt

    def write_bound_receipt(path: Path, payload: dict[str, Any]) -> None:
        bound = dict(payload)
        bound["owner_authorization"] = {
            "authorization_id": decision["authorization_id"],
            "authorization_sha256": decision["authorization_sha256"],
            "source_sha": decision["source_sha"],
            "core_archive_sha256": decision["core_archive_sha256"],
            "ops_archive_sha256": decision["ops_archive_sha256"],
            "authority_mode": decision["authority_mode"],
            "expires_at": decision["expires_at"],
            "command_scope_verified": decision["command_scope_verified"],
            "authorization_capsule_persisted": False,
            "provider_credential_persisted": False,
        }
        original(path, bound)

    V31.V3.write_receipt = write_bound_receipt


def main(argv: Sequence[str] | None = None) -> int:
    original_argv = list(sys.argv)
    supplied = list(sys.argv[1:] if argv is None else argv)
    try:
        invocation = prepare_invocation(supplied)
        if invocation.decision is not None:
            _install_receipt_binding(invocation.decision)
        sys.argv = [original_argv[0], *invocation.argv]
        return V31.main()
    except (AUTH.AuthorizationError, json.JSONDecodeError) as exc:
        print(f"Phoenix authorization rejected: {exc}", file=sys.stderr)
        return 2
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
