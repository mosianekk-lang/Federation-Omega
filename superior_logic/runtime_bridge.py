from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping

from .engineering_runtime import WorkspaceReceipt, WorkspaceSpec


def _safe(raw: str) -> str:
    p = PurePosixPath(raw)
    if p.is_absolute() or not p.parts or ".." in p.parts:
        raise ValueError(f"unsafe path: {raw}")
    return p.as_posix()


@dataclass(frozen=True, slots=True)
class SandboxExecutionRequest:
    task_id: str
    command: tuple[str, ...]
    input_files: Mapping[str, str]
    export_paths: tuple[str, ...] = ()
    allowed_executables: tuple[str, ...] = ()
    timeout_seconds: float = 15.0


@dataclass(frozen=True, slots=True)
class RuntimeExecutionReceipt:
    task_id: str
    workspace_id: str
    status: str
    execution_verified: bool
    readback_verified: bool
    rollback_verified: bool
    persistence_verified: bool
    result_hash: str
    ledger_entry_hash: str


class FederationRuntimeBridge:
    """Thin SLOS bridge to admitted Federation sandbox/runtime components; it creates no second executor."""

    sandbox_module = "alpha_omega_v30.sandbox_fleet"
    persistent_module = "federation.autopilot_suites_v1.persistent_mission_sandbox"

    def execute_disposable(
        self,
        workspace: WorkspaceSpec,
        workspace_receipt: WorkspaceReceipt,
        request: SandboxExecutionRequest,
        *,
        ledger_path: str,
    ) -> RuntimeExecutionReceipt:
        if workspace_receipt.workspace_id != workspace.workspace_id or not workspace_receipt.prepared:
            raise PermissionError("workspace is not prepared/verified")
        if not request.task_id.strip() or not request.command:
            raise ValueError("task identity/command required")
        input_files = {_safe(p): text for p, text in request.input_files.items()}
        export_paths = tuple(_safe(p) for p in request.export_paths)
        executable = request.command[0]
        if request.allowed_executables and executable not in request.allowed_executables:
            raise PermissionError("requested executable is not allowlisted")
        writable = set(workspace.writable_paths)
        for path in input_files:
            if writable and path not in writable and not any(path.startswith(x.rstrip("/") + "/") for x in writable):
                raise PermissionError(f"input path outside workspace write-set: {path}")

        mod = importlib.import_module(self.sandbox_module)
        policy = mod.SandboxPolicy(
            timeout_seconds=request.timeout_seconds,
            allowed_executables=request.allowed_executables,
        )
        ledger = mod.ReceiptLedger(ledger_path)
        runner = mod.OperationalSandbox(policy, ledger)
        task = mod.SandboxTask(
            task_id=request.task_id,
            command=request.command,
            input_files=input_files,
            export_paths=export_paths,
        )
        result = runner.run(task)
        return RuntimeExecutionReceipt(
            task_id=request.task_id,
            workspace_id=workspace.workspace_id,
            status=str(result.get("status", "ERROR")),
            execution_verified=bool(result.get("execution_verified")),
            readback_verified=bool(result.get("readback_verified")),
            rollback_verified=bool(result.get("rollback_verified")),
            persistence_verified=bool(result.get("persistence_verified")),
            result_hash=str(result.get("result_hash", "")),
            ledger_entry_hash=str(result.get("ledger_entry_hash", "")),
        )

    def open_persistent_workspace(
        self,
        workspace: WorkspaceSpec,
        workspace_receipt: WorkspaceReceipt,
        *,
        root: str,
        ttl_seconds: int = 86_400,
        max_bytes: int = 5_000_000,
    ):
        if workspace_receipt.workspace_id != workspace.workspace_id or not workspace_receipt.prepared:
            raise PermissionError("workspace is not prepared/verified")
        mod = importlib.import_module(self.persistent_module)
        return mod.PersistentMissionSandbox(root, workspace.workspace_id, ttl_seconds=ttl_seconds, max_bytes=max_bytes)
