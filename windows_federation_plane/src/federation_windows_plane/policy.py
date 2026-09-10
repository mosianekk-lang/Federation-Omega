from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .models import TaskEnvelope


MAX_HASH_BYTES = 32 * 1024 * 1024


class ExecutionPolicy:
    """Fail-closed task and path policy. No arbitrary process execution exists."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve(strict=True)

    def authorize(self, task: TaskEnvelope) -> Mapping[str, Any]:
        task.validate()
        if task.task_type in {"health", "inventory"}:
            if task.parameters:
                raise ValueError("TASK_PARAMETERS_NOT_ALLOWED")
            return {}
        if task.task_type == "hash_workspace_file":
            if set(task.parameters) != {"relative_path"}:
                raise ValueError("HASH_TASK_REQUIRES_ONLY_RELATIVE_PATH")
            raw = task.parameters.get("relative_path")
            if not isinstance(raw, str) or not raw or "\x00" in raw:
                raise ValueError("RELATIVE_PATH_INVALID")
            relative = Path(raw)
            if relative.is_absolute():
                raise ValueError("ABSOLUTE_PATH_DENIED")
            candidate = (self.workspace / relative).resolve(strict=False)
            try:
                candidate.relative_to(self.workspace)
            except ValueError as exc:
                raise ValueError("PATH_ESCAPE_DENIED") from exc
            if not candidate.is_file():
                raise ValueError("HASH_TARGET_FILE_REQUIRED")
            if candidate.stat().st_size > MAX_HASH_BYTES:
                raise ValueError("HASH_TARGET_TOO_LARGE")
            return {"path": candidate, "relative_path": candidate.relative_to(self.workspace).as_posix()}
        raise ValueError("TASK_TYPE_NOT_IMPLEMENTED")
