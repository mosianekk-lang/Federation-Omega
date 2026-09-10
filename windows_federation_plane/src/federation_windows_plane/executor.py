from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sys
from typing import Any

from .models import TaskEnvelope, TaskReceipt, task_sha256, utc_now
from .policy import ExecutionPolicy


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class WindowsPlane:
    def __init__(self, workspace: Path, *, require_windows: bool = True) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.require_windows = require_windows
        self.policy = ExecutionPolicy(self.workspace)

    def _runner_identity(self) -> dict[str, Any]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "hostname_sha256": hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest(),
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "source_sha": os.environ.get("FEDERATION_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
            "github_event_sha": os.environ.get("GITHUB_SHA"),
        }

    def execute(self, task: TaskEnvelope) -> TaskReceipt:
        started = utc_now()
        if self.require_windows and platform.system() != "Windows":
            raise RuntimeError("WINDOWS_RUNTIME_REQUIRED")
        authorized = self.policy.authorize(task)
        if task.task_type == "health":
            result: dict[str, Any] = {
                "status": "healthy",
                "plane_version": "1.0.0",
                "allowlisted_tasks": ["health", "inventory", "hash_workspace_file"],
                "arbitrary_command_execution": False,
            }
        elif task.task_type == "inventory":
            result = {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "architecture": platform.machine(),
                "python_implementation": platform.python_implementation(),
                "python_version": platform.python_version(),
                "workspace_exists": self.workspace.is_dir(),
                "workspace_path_disclosed": False,
            }
        elif task.task_type == "hash_workspace_file":
            path = authorized["path"]
            result = {
                "relative_path": authorized["relative_path"],
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        else:
            raise ValueError("TASK_TYPE_NOT_IMPLEMENTED")
        return TaskReceipt(
            schema="FEDERATION-WINDOWS-RECEIPT-V1",
            task_id=task.task_id,
            correlation_id=task.correlation_id,
            task_type=task.task_type,
            state="COMPLETED_VERIFIED_LOCAL",
            started_at=started,
            completed_at=utc_now(),
            runner=self._runner_identity(),
            task=asdict(task),
            result=result,
            task_sha256=task_sha256(task),
            result_sha256=_sha256_json(result),
        )
