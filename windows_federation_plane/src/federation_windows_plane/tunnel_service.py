from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
import uuid

from .executor import WindowsPlane
from .models import TaskEnvelope


TUNNEL_ID_PATTERN = re.compile(r"^tunnel_[A-Za-z0-9_-]{16,128}$")
PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
READ_ONLY_TOOLS = ("health", "inventory", "hash_workspace_file")


def validate_tunnel_id(value: str) -> str:
    value = value.strip()
    if not TUNNEL_ID_PATTERN.fullmatch(value):
        raise ValueError("TUNNEL_ID_INVALID")
    return value


def validate_profile(value: str) -> str:
    value = value.strip()
    if not PROFILE_PATTERN.fullmatch(value):
        raise ValueError("TUNNEL_PROFILE_INVALID")
    return value


def stdio_command(python_executable: str, workspace: str) -> str:
    if not python_executable or any(c in python_executable for c in "\r\n\0"):
        raise ValueError("PYTHON_EXECUTABLE_INVALID")
    if not workspace or any(c in workspace for c in "\r\n\0"):
        raise ValueError("WORKSPACE_INVALID")
    return " ".join(
        _quote_windows_arg(value)
        for value in (python_executable, "-m", "federation_windows_plane.tunnel_service", "--workspace", workspace)
    )


def _quote_windows_arg(value: str) -> str:
    """Quote one CreateProcess argument without invoking a shell."""
    if value and not any(c in value for c in ' \t"'):
        return value
    out = ['"']
    slashes = 0
    for char in value:
        if char == "\\":
            slashes += 1
            continue
        if char == '"':
            out.append("\\" * (slashes * 2 + 1))
            out.append('"')
        else:
            out.append("\\" * slashes)
            out.append(char)
        slashes = 0
    out.append("\\" * (slashes * 2))
    out.append('"')
    return "".join(out)


def _instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def execute_read_only_task(
    workspace: Path,
    task_type: str,
    *,
    relative_path: str | None = None,
    require_windows: bool = True,
) -> dict[str, Any]:
    if task_type not in READ_ONLY_TOOLS:
        raise ValueError("TASK_TYPE_NOT_ALLOWLISTED")
    if task_type == "hash_workspace_file" and not relative_path:
        raise ValueError("RELATIVE_PATH_REQUIRED")
    if task_type != "hash_workspace_file" and relative_path:
        raise ValueError("RELATIVE_PATH_NOT_ALLOWED")
    now = datetime.now(timezone.utc)
    task = TaskEnvelope(
        schema="FEDERATION-WINDOWS-TASK-V1",
        task_id="task-" + uuid.uuid4().hex,
        correlation_id="corr-" + uuid.uuid4().hex,
        issued_by="FUSE/FDOF",
        task_type=task_type,
        issued_at=_instant(now - timedelta(seconds=1)),
        expires_at=_instant(now + timedelta(minutes=5)),
        parameters={"relative_path": relative_path} if relative_path else {},
        effect="READ_ONLY",
    )
    return WindowsPlane(workspace, require_windows=require_windows).execute(task).to_dict()


def build_tunnel_server(workspace: Path):
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations

    server = MCPServer(
        "FUSE Windows Private Bridge",
        version="2.5.0",
        instructions=(
            "Private outbound-only Windows bridge. Only typed, read-only, workspace-bounded tools exist. "
            "No shell, process execution, package installation, or arbitrary filesystem access is exposed."
        ),
    )
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(
        title="FUSE Windows health",
        description="Return a privacy-minimized health receipt for the owner Windows node.",
        annotations=read_only,
    )
    def fuse_windows_health() -> dict[str, Any]:
        return execute_read_only_task(workspace, "health")

    @server.tool(
        title="FUSE Windows inventory",
        description="Return privacy-minimized runtime inventory without disclosing the workspace path.",
        annotations=read_only,
    )
    def fuse_windows_inventory() -> dict[str, Any]:
        return execute_read_only_task(workspace, "inventory")

    @server.tool(
        title="Hash a FUSE workspace file",
        description="Hash one existing file below the configured workspace; absolute and escaping paths are denied.",
        annotations=read_only,
    )
    def fuse_windows_hash_workspace_file(relative_path: str) -> dict[str, Any]:
        return execute_read_only_task(workspace, "hash_workspace_file", relative_path=relative_path)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="federation-windows-tunnel")
    parser.add_argument("--workspace", type=Path, default=Path(os.environ.get("FUSE_WINDOWS_WORKSPACE", ".")))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--allow-non-windows-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        workspace = args.workspace.resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError("WORKSPACE_DIRECTORY_REQUIRED")
        if args.self_test:
            receipt = execute_read_only_task(
                workspace,
                "health",
                require_windows=not args.allow_non_windows_test,
            )
            sys.stdout.write(json.dumps({
                "state": "TUNNEL_STDIO_SELF_TEST_VERIFIED",
                "task_sha256": receipt["task_sha256"],
                "result_sha256": receipt["result_sha256"],
                "arbitrary_shell": False,
            }, sort_keys=True) + "\n")
            return 0
        build_tunnel_server(workspace).run(transport="stdio")
        return 0
    except Exception as exc:
        sys.stderr.write(json.dumps({"state": "FAILED_CLOSED", "error": str(exc)}) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
