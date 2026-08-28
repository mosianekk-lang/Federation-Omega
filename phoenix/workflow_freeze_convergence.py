from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "FEDOMEGA-PHOENIX-EXECUTION-FREEZE-4"
PROVIDER_MANAGED = {"dynamic/dependabot/dependabot-updates"}


def canonical_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def required_from_policy(path: Path) -> set[str]:
    """Return the single canonical required-workflow set from Airlock policy.

    Phoenix must not maintain an independent copy of the workflow allowlist. The
    active allowlist and execution-quarantine keep-active projection are required to
    agree; disagreement fails closed instead of allowing a false-green convergence.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    active = set(payload.get("active_workflow_allowlist", []))
    keep_active = set(payload.get("execution_quarantine", {}).get("keep_active", []))
    if not active:
        raise ValueError("AIRLOCK_POLICY_ACTIVE_WORKFLOW_ALLOWLIST_EMPTY")
    if active != keep_active:
        missing_from_quarantine = sorted(active - keep_active)
        extra_in_quarantine = sorted(keep_active - active)
        raise ValueError(
            "AIRLOCK_POLICY_WORKFLOW_SET_DRIFT:"
            f"missing_from_quarantine={missing_from_quarantine}:"
            f"extra_in_quarantine={extra_in_quarantine}"
        )
    return active


def workflow_rows(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t", 3)
        if len(fields) == 4:
            workflow_id, workflow_path, state, name = fields
            result.append(
                {
                    "id": int(workflow_id),
                    "path": workflow_path,
                    "state": state,
                    "name": name,
                }
            )
    return result


def mutation_rows(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t", 1)
        if len(fields) == 2:
            workflow_id, workflow_path = fields
            result.append({"id": int(workflow_id), "path": workflow_path})
    return result


def required_rows(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t", 3)
        if len(fields) == 4:
            workflow_id, workflow_path, state, attempt = fields
            result.append(
                {
                    "id": int(workflow_id) if workflow_id.isdigit() else None,
                    "path": workflow_path,
                    "state": state,
                    "attempt": int(attempt),
                }
            )
    return result


def build_receipt(
    *,
    repository: str,
    source_sha: str,
    run_id: int,
    run_attempt: int,
    required_workflows: Iterable[str],
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    required_readback: list[dict[str, Any]],
    disabled: list[dict[str, Any]],
    enabled: list[dict[str, Any]],
    errors: list[str],
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    required = set(required_workflows)
    if not required:
        raise ValueError("REQUIRED_WORKFLOW_SET_EMPTY")
    active_after = sorted(row["path"] for row in after if row["state"] == "active")
    provider_managed_active = sorted(
        path for path in active_after if path in PROVIDER_MANAGED
    )
    unexpected_active = sorted(
        path
        for path in active_after
        if path not in required and path not in PROVIDER_MANAGED
    )
    required_by_path = {row["path"]: row for row in required_readback}
    missing_required = sorted(
        path
        for path in required
        if required_by_path.get(path, {}).get("state") != "active"
    )
    unexpected_required_readback = sorted(
        path for path in required_by_path if path not in required
    )
    max_attempt = max(
        (int(row.get("attempt", 0)) for row in required_readback), default=0
    )
    verified = (
        bool(after)
        and not errors
        and not unexpected_active
        and not missing_required
        and not unexpected_required_readback
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "repository": repository,
        "source_sha": source_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "recorded_at": (recorded_at or datetime.now(timezone.utc)).isoformat(),
        "workflow_policy_authority": "governance/github_airlock_policy.json",
        "required_active_workflows": sorted(required),
        "required_workflow_readback": sorted(
            required_readback, key=lambda row: row["path"]
        ),
        "required_workflow_readback_method": (
            "POLICY_DERIVED_INDIVIDUAL_WORKFLOW_ENDPOINT_BOUNDED_CONVERGENCE"
        ),
        "convergence_attempt_count": max_attempt,
        "provider_managed_allowlist": sorted(PROVIDER_MANAGED),
        "provider_managed_active": provider_managed_active,
        "provider_managed_control_plane": "DEPENDABOT_REPOSITORY_SETTINGS",
        "workflow_count_before": len(before),
        "workflow_count_after": len(after),
        "disabled_count_this_run": len(disabled),
        "disabled_paths_this_run": sorted(row["path"] for row in disabled),
        "disabled_total_after": sum(
            1 for row in after if row["state"] == "disabled_manually"
        ),
        "enabled_count_this_run": len(enabled),
        "enabled_paths_this_run": sorted(row["path"] for row in enabled),
        "active_after_list_endpoint": active_after,
        "unexpected_active": unexpected_active,
        "missing_required": missing_required,
        "unexpected_required_readback": unexpected_required_readback,
        "errors": errors,
        "source_mutation_attempted": False,
        "status": "VERIFIED" if verified else "READBACK_FAILED",
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--required-readback", type=Path, required=True)
    parser.add_argument("--disabled", type=Path, required=True)
    parser.add_argument("--enabled", type=Path, required=True)
    parser.add_argument("--errors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors = (
        args.errors.read_text(encoding="utf-8").splitlines()
        if args.errors.exists()
        else []
    )
    try:
        required = required_from_policy(args.policy)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        required = set()
        errors.append(str(exc))

    if not required:
        payload = {
            "schema": SCHEMA,
            "repository": os.environ["GITHUB_REPOSITORY"],
            "source_sha": os.environ["GITHUB_SHA"],
            "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "workflow_policy_authority": str(args.policy),
            "required_active_workflows": [],
            "errors": errors or ["REQUIRED_WORKFLOW_SET_EMPTY"],
            "source_mutation_attempted": False,
            "status": "READBACK_FAILED",
        }
        payload["receipt_sha256"] = canonical_sha256(payload)
    else:
        payload = build_receipt(
            repository=os.environ["GITHUB_REPOSITORY"],
            source_sha=os.environ["GITHUB_SHA"],
            run_id=int(os.environ["GITHUB_RUN_ID"]),
            run_attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
            required_workflows=required,
            before=workflow_rows(args.before),
            after=workflow_rows(args.after),
            required_readback=required_rows(args.required_readback),
            disabled=mutation_rows(args.disabled),
            enabled=mutation_rows(args.enabled),
            errors=errors,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
