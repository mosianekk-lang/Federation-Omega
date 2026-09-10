from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import uuid

from .executor import WindowsPlane
from .models import TaskEnvelope


def _instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _built_in_task(task_type: str, relative_path: str | None) -> TaskEnvelope:
    now = datetime.now(timezone.utc)
    params = {"relative_path": relative_path} if task_type == "hash_workspace_file" else {}
    return TaskEnvelope(
        schema="FEDERATION-WINDOWS-TASK-V1",
        task_id=f"task-{uuid.uuid4().hex}",
        correlation_id=f"corr-{uuid.uuid4().hex}",
        issued_by="FUSE/FDOF",
        task_type=task_type,
        issued_at=_instant(now - timedelta(seconds=1)),
        expires_at=_instant(now + timedelta(minutes=5)),
        parameters=params,
        effect="READ_ONLY",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="federation-windows")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--task", required=True, choices=("health", "inventory", "hash_workspace_file")
    )
    parser.add_argument("--relative-path")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--allow-non-windows-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.task == "hash_workspace_file" and not args.relative_path:
        parser.error("--relative-path is required for hash_workspace_file")
    if args.task != "hash_workspace_file" and args.relative_path:
        parser.error("--relative-path is only valid for hash_workspace_file")
    try:
        task = _built_in_task(args.task, args.relative_path)
        receipt = WindowsPlane(args.workspace, require_windows=not args.allow_non_windows_test).execute(task)
        payload = json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n"
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(payload, encoding="utf-8")
        sys.stdout.write(payload)
        return 0
    except Exception as exc:
        sys.stderr.write(json.dumps({"state":"FAILED_CLOSED","error":str(exc)}) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
