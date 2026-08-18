#!/usr/bin/env python3
"""Bind GitHub Airlock execution to the exact admitted source identity.

This tool is intentionally local and read-only with respect to providers. It
creates or verifies a hash-bound execution-identity receipt for the Airlock
workflow and marks the Phoenix exporter as executed only after its dedicated
test suite exits successfully.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "FEDOMEGA-AIRLOCK-EXECUTION-IDENTITY-1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class IdentityError(RuntimeError):
    """Raised when execution identity cannot be proved exactly."""


def _require_sha(name: str, value: str) -> str:
    normalized = value.strip().lower()
    if not _SHA40.fullmatch(normalized):
        raise IdentityError(f"{name} must be an exact lowercase 40-hex SHA")
    return normalized


def _git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        raise IdentityError(
            f"git {' '.join(args)} failed without a verified result"
        ) from None
    return process.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receipt_digest(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["receipt_sha256"] = _receipt_digest(payload)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    temporary.replace(path)


def _read_verified(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityError(
            "execution identity receipt is unavailable or invalid"
        ) from exc
    claimed = payload.get("receipt_sha256")
    if not isinstance(claimed, str) or claimed != _receipt_digest(payload):
        raise IdentityError("execution identity receipt hash mismatch")
    if payload.get("schema") != SCHEMA:
        raise IdentityError("execution identity receipt schema mismatch")
    return payload


def bind(args: argparse.Namespace) -> int:
    root = args.repo_root.resolve()
    report = args.report.resolve()
    event_name = args.event.strip()
    if event_name not in {
        "pull_request",
        "merge_group",
        "push",
        "workflow_dispatch",
    }:
        raise IdentityError(f"unsupported event: {event_name}")

    base_sha = _require_sha("base_sha", args.base)
    admitted_head_sha = _require_sha("admitted_head_sha", args.head)
    event_sha = _require_sha("event_sha", args.event_sha)

    workflow_path = Path(args.workflow)
    exporter_path = Path(args.exporter)
    for label, relative in (
        ("workflow", workflow_path),
        ("phoenix exporter", exporter_path),
    ):
        if relative.is_absolute() or ".." in relative.parts:
            raise IdentityError(f"{label} path must be repository-relative")
        if not (root / relative).is_file():
            raise IdentityError(f"{label} file is missing from admitted checkout")

    checkout_sha = _require_sha("checkout_sha", _git(root, "rev-parse", "HEAD"))
    if checkout_sha != admitted_head_sha:
        raise IdentityError(
            "EXECUTION_HEAD_MISMATCH: checked-out SHA does not equal admitted head"
        )

    checkout_tree_sha = _require_sha(
        "checkout_tree_sha", _git(root, "rev-parse", f"{checkout_sha}^{{tree}}")
    )
    workflow_blob_sha = _require_sha(
        "workflow_blob_sha",
        _git(root, "rev-parse", f"{checkout_sha}:{workflow_path.as_posix()}"),
    )
    exporter_blob_sha = _require_sha(
        "exporter_blob_sha",
        _git(root, "rev-parse", f"{checkout_sha}:{exporter_path.as_posix()}"),
    )

    event_sha_role = (
        "GITHUB_GENERATED_MERGE_REF_OBSERVATION_ONLY"
        if event_name == "pull_request" and event_sha != admitted_head_sha
        else "ADMITTED_EXECUTION_HEAD"
    )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "IDENTITY_BOUND",
        "repository": args.repository,
        "event_name": event_name,
        "base_sha": base_sha,
        "admitted_head_sha": admitted_head_sha,
        "event_sha": event_sha,
        "event_sha_role": event_sha_role,
        "checkout": {
            "sha": checkout_sha,
            "tree_sha": checkout_tree_sha,
            "matches_admitted_head": True,
        },
        "workflow": {
            "path": workflow_path.as_posix(),
            "git_blob_sha": workflow_blob_sha,
            "sha256": _sha256_file(root / workflow_path),
        },
        "phoenix_exporter": {
            "path": exporter_path.as_posix(),
            "git_blob_sha": exporter_blob_sha,
            "sha256": _sha256_file(root / exporter_path),
            "execution_status": "PENDING_DEDICATED_TEST_SUITE",
        },
        "github_run": {
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
        },
        "truth_boundary": {
            "provider_execution": False,
            "credential_discovery": False,
            "source_mutation": False,
            "main_mutation": False,
            "merge_authorized": False,
        },
    }
    _write_atomic(report, payload)
    print(
        "AIRLOCK_EXECUTION_IDENTITY_BOUND "
        f"head={admitted_head_sha} tree={checkout_tree_sha} "
        f"exporter_sha256={payload['phoenix_exporter']['sha256']}"
    )
    return 0


def mark_phoenix_verified(args: argparse.Namespace) -> int:
    report = args.report.resolve()
    payload = _read_verified(report)
    exporter = payload.get("phoenix_exporter")
    if not isinstance(exporter, dict):
        raise IdentityError("phoenix exporter identity is absent")
    if exporter.get("execution_status") == "DEDICATED_TEST_SUITE_PASSED":
        print("AIRLOCK_PHOENIX_EXPORTER_ALREADY_VERIFIED")
        return 0
    if exporter.get("execution_status") != "PENDING_DEDICATED_TEST_SUITE":
        raise IdentityError("phoenix exporter is in an invalid execution state")
    exporter["execution_status"] = "DEDICATED_TEST_SUITE_PASSED"
    exporter["test_suite"] = args.test_suite
    exporter["test_command"] = args.test_command
    exporter["proof"] = "BOUND_CHECKOUT_PROCESS_EXIT_0"
    payload["status"] = "VERIFIED"
    _write_atomic(report, payload)
    print(
        "AIRLOCK_PHOENIX_EXPORTER_VERIFIED "
        f"sha256={exporter['sha256']} suite={args.test_suite}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    payload = _read_verified(args.report.resolve())
    checkout = payload.get("checkout", {})
    exporter = payload.get("phoenix_exporter", {})
    if payload.get("status") != "VERIFIED":
        raise IdentityError("execution identity receipt is not verified")
    if checkout.get("sha") != payload.get("admitted_head_sha"):
        raise IdentityError("receipt checkout/head identity drift")
    if exporter.get("execution_status") != "DEDICATED_TEST_SUITE_PASSED":
        raise IdentityError("phoenix exporter execution is not verified")
    print(
        "AIRLOCK_EXECUTION_IDENTITY_VERIFIED "
        f"head={payload['admitted_head_sha']} "
        f"receipt_sha256={payload['receipt_sha256']}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)

    bind_parser = commands.add_parser("bind")
    bind_parser.add_argument("--repo-root", type=Path, default=Path("."))
    bind_parser.add_argument("--repository", required=True)
    bind_parser.add_argument("--event", required=True)
    bind_parser.add_argument("--base", required=True)
    bind_parser.add_argument("--head", required=True)
    bind_parser.add_argument("--event-sha", required=True)
    bind_parser.add_argument("--workflow", required=True)
    bind_parser.add_argument("--exporter", required=True)
    bind_parser.add_argument("--run-id", required=True)
    bind_parser.add_argument("--run-attempt", required=True)
    bind_parser.add_argument("--report", type=Path, required=True)
    bind_parser.set_defaults(handler=bind)

    mark_parser = commands.add_parser("mark-phoenix-verified")
    mark_parser.add_argument("--report", type=Path, required=True)
    mark_parser.add_argument("--test-suite", required=True)
    mark_parser.add_argument("--test-command", required=True)
    mark_parser.set_defaults(handler=mark_phoenix_verified)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--report", type=Path, required=True)
    verify_parser.set_defaults(handler=verify)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except IdentityError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
