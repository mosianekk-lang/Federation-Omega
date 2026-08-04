#!/usr/bin/env python3
"""Build Phoenix exports with the user-scoped provider cutover v2 engine."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_base", ROOT / "phoenix" / "build_exports.py"
)
assert SPEC and SPEC.loader
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

PST_REQUEST_PATH = Path(
    "deployment_manifests/evidenceops-pst-v2-phoenix-verify-request.json"
)
PST_COMPLETION_PATH = Path(
    "deployment_receipts/evidenceops-pst-corpus-v2-drive-completion.json"
)
PST_WORKFLOW_FILE = "evidenceops-pst-v2-drive-remote-verify.yml"
PST_WORKFLOW_PATH = f".github/workflows/{PST_WORKFLOW_FILE}"


def stage_ops_v2(root: Path, stage: Path, policy: dict) -> list[BASE.FileRecord]:
    template = root / policy["ops"]["template_prefix"]
    if not template.is_dir():
        raise RuntimeError(f"Ops template missing: {template}")

    records: list[BASE.FileRecord] = []
    for path in sorted(template.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(template).as_posix()
        BASE.copy_file(path, stage / rel)
        records.append(
            BASE.FileRecord(
                path=rel,
                size=path.stat().st_size,
                sha256=BASE.sha256_file(path),
                classification="OPS_INCLUDED",
                reason="APPROVED_OPS_TEMPLATE",
            )
        )

    cutover = root / "phoenix" / "provider_cutover_v2.py"
    if not cutover.is_file():
        raise RuntimeError(f"Provider cutover v2 missing: {cutover}")
    BASE.copy_file(cutover, stage / "provider_cutover.py")
    records.append(
        BASE.FileRecord(
            path="provider_cutover.py",
            size=cutover.stat().st_size,
            sha256=BASE.sha256_file(cutover),
            classification="OPS_INCLUDED",
            reason="USER_SCOPED_PROVIDER_CUTOVER_V2",
        )
    )

    actual = {item.path for item in records}
    missing = sorted(set(policy["ops"]["required_files"]) - actual)
    if missing:
        raise RuntimeError(f"Ops export missing required files: {missing}")
    if any(item.path.startswith(".github/workflows/") for item in records):
        raise RuntimeError("Ops export unexpectedly contains an active workflow")
    return records


def _gh_api(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["gh", "api", *args],
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            "GH_API_FAILED:"
            + json.dumps(
                {
                    "args": args,
                    "returncode": result.returncode,
                    "stdout_tail": result.stdout[-500:],
                    "stderr_tail": result.stderr[-500:],
                },
                sort_keys=True,
            )
        )
    return result


def maybe_dispatch_pst_remote_verifier(root: Path) -> dict:
    """Dispatch the quarantined PST verifier only from the authorised Phoenix run.

    The hook is inert in local execution, tests, pull requests and non-Phoenix
    workflows. It enables one existing verifier, dispatches it, records the
    provider run ID and leaves the existing Phoenix freeze step to disable the
    workflow again. It does not weaken any verification gate or read a secret.
    """

    context = {
        "github_actions": os.environ.get("GITHUB_ACTIONS"),
        "event": os.environ.get("GITHUB_EVENT_NAME"),
        "ref": os.environ.get("GITHUB_REF"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
    }
    authorised = (
        context["github_actions"] == "true"
        and context["event"] == "push"
        and context["ref"] == "refs/heads/main"
        and context["workflow"] == "Phoenix Emergency Execution Freeze"
    )
    if not authorised:
        return {
            "schema": "FEDOMEGA-PST-PHOENIX-DISPATCH-1",
            "status": "SKIPPED_UNAUTHORISED_CONTEXT",
            "context": context,
        }

    request_path = root / PST_REQUEST_PATH
    if not request_path.is_file():
        return {
            "schema": "FEDOMEGA-PST-PHOENIX-DISPATCH-1",
            "status": "SKIPPED_NO_REQUEST",
            "request_path": PST_REQUEST_PATH.as_posix(),
        }

    request = json.loads(request_path.read_text(encoding="utf-8"))
    required_request = {
        "schema": "FEDOMEGA-PST-PHOENIX-VERIFY-REQUEST-1",
        "status": "REQUESTED",
        "workflow_path": PST_WORKFLOW_PATH,
    }
    for key, expected in required_request.items():
        if request.get(key) != expected:
            raise RuntimeError(
                f"PST_VERIFY_REQUEST_INVALID:{key}:{request.get(key)!r}:{expected!r}"
            )
    nonce = request.get("request_nonce")
    if not isinstance(nonce, str) or not nonce.strip():
        raise RuntimeError("PST_VERIFY_REQUEST_INVALID:request_nonce")

    completion_path = root / PST_COMPLETION_PATH
    if completion_path.is_file():
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        if completion.get("status") == "COMPLETE_VERIFIED":
            return {
                "schema": "FEDOMEGA-PST-PHOENIX-DISPATCH-1",
                "status": "SKIPPED_ALREADY_COMPLETE_VERIFIED",
                "request_nonce": nonce,
                "completion_path": PST_COMPLETION_PATH.as_posix(),
            }

    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("PST_VERIFY_DISPATCH_MISSING:GITHUB_REPOSITORY")
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("PST_VERIFY_DISPATCH_MISSING:GH_TOKEN")

    workflow_meta = json.loads(
        _gh_api([f"/repos/{repo}/actions/workflows/{PST_WORKFLOW_FILE}"]).stdout
    )
    workflow_id = int(workflow_meta["id"])
    if workflow_meta.get("path") != PST_WORKFLOW_PATH:
        raise RuntimeError(
            f"PST_VERIFY_WORKFLOW_PATH_MISMATCH:{workflow_meta.get('path')}"
        )

    runs_endpoint = (
        f"/repos/{repo}/actions/workflows/{workflow_id}/runs"
        "?event=workflow_dispatch&branch=main&per_page=20"
    )
    before_payload = json.loads(_gh_api([runs_endpoint]).stdout)
    before_ids = {int(run["id"]) for run in before_payload.get("workflow_runs", [])}

    _gh_api(["-X", "PUT", f"/repos/{repo}/actions/workflows/{workflow_id}/enable"])
    time.sleep(3)

    dispatch_result = None
    for attempt in range(1, 4):
        dispatch_result = _gh_api(
            [
                "-X",
                "POST",
                f"/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
                "-f",
                "ref=main",
            ],
            check=False,
        )
        if dispatch_result.returncode == 0:
            break
        if attempt == 3:
            raise RuntimeError(
                "PST_VERIFY_DISPATCH_FAILED:"
                + json.dumps(
                    {
                        "attempt": attempt,
                        "stdout_tail": dispatch_result.stdout[-500:],
                        "stderr_tail": dispatch_result.stderr[-500:],
                    },
                    sort_keys=True,
                )
            )
        time.sleep(attempt * 4)

    run = None
    for _ in range(20):
        payload = json.loads(_gh_api([runs_endpoint]).stdout)
        candidates = [
            item
            for item in payload.get("workflow_runs", [])
            if int(item["id"]) not in before_ids and item.get("head_branch") == "main"
        ]
        if candidates:
            run = max(candidates, key=lambda item: int(item["id"]))
            break
        time.sleep(2)
    if run is None:
        raise RuntimeError("PST_VERIFY_DISPATCH_RUN_ID_NOT_OBSERVED")

    return {
        "schema": "FEDOMEGA-PST-PHOENIX-DISPATCH-1",
        "status": "DISPATCHED_PROVIDER_RUN_OBSERVED",
        "request_nonce": nonce,
        "repository": repo,
        "workflow_id": workflow_id,
        "workflow_path": PST_WORKFLOW_PATH,
        "workflow_state_before_enable": workflow_meta.get("state"),
        "run_id": int(run["id"]),
        "run_number": int(run["run_number"]),
        "run_attempt": int(run.get("run_attempt", 1)),
        "run_status": run.get("status"),
        "run_conclusion": run.get("conclusion"),
        "head_sha": run.get("head_sha"),
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
        "secret_values_accessed": False,
        "verification_gates_modified": False,
        "expected_requarantine": "PHOENIX_FREEZE_NEXT_STEP",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--policy", type=Path, default=Path("phoenix/export_policy.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("phoenix-export-output")
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    policy = args.policy if args.policy.is_absolute() else root / args.policy
    output = args.output if args.output.is_absolute() else root / args.output

    BASE.stage_ops = stage_ops_v2
    receipt = BASE.build(root, output, policy)
    receipt["pst_remote_verifier_dispatch"] = maybe_dispatch_pst_remote_verifier(root)
    receipt_path = output / "phoenix-export-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
