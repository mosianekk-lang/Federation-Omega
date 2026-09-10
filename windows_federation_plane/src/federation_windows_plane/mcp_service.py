from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any
import uuid

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

from .firestore_relay import FirestoreRelay
from .oidc_auth import OIDCTokenVerifier


BASE_SCOPE = "fuse.windows"


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_error(exc: Exception, status: int = 400) -> JSONResponse:
    return JSONResponse({"state": "FAILED_CLOSED", "error": str(exc)}, status_code=status)


def _device_auth(request: Request, body: bytes, relay: Any) -> str:
    device_id = request.headers.get("x-fuse-device-id", "")
    relay.verify_device_request(
        device_id=device_id,
        method=request.method,
        path=request.url.path,
        timestamp=request.headers.get("x-fuse-timestamp", ""),
        nonce=request.headers.get("x-fuse-nonce", ""),
        signature=request.headers.get("x-fuse-signature", ""),
        body=body,
    )
    return device_id


def _require_scope(scope: str = BASE_SCOPE) -> None:
    access = get_access_token()
    if access is None or scope not in access.scopes:
        raise PermissionError("OAUTH_SCOPE_REQUIRED:" + scope)


def build_server(*, relay: Any, issuer: str, resource_url: str, jwks_url: str) -> MCPServer:
    verifier = OIDCTokenVerifier(issuer=issuer, audience=resource_url, jwks_url=jwks_url)
    server = MCPServer(
        "FUSE Windows Sovereign Relay",
        version="1.1.0",
        instructions=(
            "Operate an owner-controlled outbound-only Windows processing plane. "
            "Use only explicit allowlisted tasks and verify terminal receipts."
        ),
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(resource_url),
            required_scopes=[BASE_SCOPE],
            validate_token_resource=True,
        ),
    )

    @server.tool(
        title="FUSE relay health",
        description="Return relay readiness without disclosing workstation secrets.",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    )
    def fuse_relay_health() -> dict[str, Any]:
        _require_scope()
        return {
            "state": "READY",
            "version": "1.1.0",
            "transport": "streamable-http",
            "workstation_listener_required": False,
            "arbitrary_shell": False,
        }

    @server.tool(
        title="List enrolled Windows devices",
        description="List privacy-minimized enrolled-device state and last-seen time.",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    )
    def fuse_list_windows_devices() -> dict[str, Any]:
        _require_scope()
        return {"devices": relay.list_devices()}

    @server.tool(
        title="Issue one-time Windows enrollment",
        description="Issue a five-minute, single-use enrollment grant for the owner's outbound Windows agent.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )
    def fuse_issue_windows_enrollment() -> dict[str, Any]:
        _require_scope()
        return relay.issue_enrollment().public_dict()

    @server.tool(
        title="Submit an allowlisted Windows task",
        description="Queue health, inventory, or workspace-file hashing for an enrolled Windows device.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )
    def fuse_submit_windows_task(
        device_id: str,
        task_type: str,
        relative_path: str | None = None,
    ) -> dict[str, Any]:
        _require_scope()
        if task_type not in {"health", "inventory", "hash_workspace_file"}:
            raise ValueError("TASK_TYPE_NOT_ALLOWLISTED")
        if task_type == "hash_workspace_file" and not relative_path:
            raise ValueError("RELATIVE_PATH_REQUIRED")
        if task_type != "hash_workspace_file" and relative_path:
            raise ValueError("RELATIVE_PATH_NOT_ALLOWED")
        now = datetime.now(timezone.utc)
        task_id = "task-" + uuid.uuid4().hex
        task = {
            "schema": "FEDERATION-WINDOWS-TASK-V1",
            "task_id": task_id,
            "correlation_id": "corr-" + uuid.uuid4().hex,
            "issued_by": "FUSE/FDOF",
            "task_type": task_type,
            "issued_at": _z(now - timedelta(seconds=1)),
            "expires_at": _z(now + timedelta(minutes=5)),
            "parameters": {"relative_path": relative_path} if relative_path else {},
            "effect": "READ_ONLY",
        }
        relay.submit_task(device_id=device_id, task=task, now=now)
        return {"state": "QUEUED", "task_id": task_id, "device_id": device_id}

    @server.tool(
        title="Read Windows task status",
        description="Return queue/completion state and the verified receipt hash for a task.",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    )
    def fuse_windows_task_status(task_id: str) -> dict[str, Any]:
        _require_scope()
        return relay.status(task_id)

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "fuse-windows-relay", "version": "1.1.0"})

    @server.custom_route("/agent/enroll", methods=["POST"], include_in_schema=False)
    async def agent_enroll(request: Request) -> JSONResponse:
        try:
            data = await request.json()
            credential = relay.enroll(
                enrollment_id=str(data.get("enrollment_id") or ""),
                enrollment_token=str(data.get("enrollment_token") or ""),
                device_label=str(data.get("device_label") or ""),
            )
            return JSONResponse(credential.public_dict(), status_code=201)
        except Exception as exc:
            return _json_error(exc, 401)

    @server.custom_route("/agent/poll", methods=["POST"], include_in_schema=False)
    async def agent_poll(request: Request) -> JSONResponse:
        body = await request.body()
        try:
            device_id = _device_auth(request, body, relay)
            item = relay.poll(device_id=device_id)
            if item is None:
                return JSONResponse({"state": "EMPTY"})
            task, lease = item
            return JSONResponse({"state": "LEASED", "task": task, "lease": lease.public_dict()})
        except Exception as exc:
            return _json_error(exc, 401)

    @server.custom_route("/agent/complete", methods=["POST"], include_in_schema=False)
    async def agent_complete(request: Request) -> JSONResponse:
        body = await request.body()
        try:
            device_id = _device_auth(request, body, relay)
            data = json.loads(body)
            receipt = relay.complete(
                device_id=device_id,
                task_id=str(data.get("task_id") or ""),
                lease_token=str(data.get("lease_token") or ""),
                receipt=data.get("receipt") or {},
            )
            return JSONResponse({"state": "ACCEPTED", "task_id": receipt["task_id"]})
        except Exception as exc:
            return _json_error(exc, 401)

    return server


def server_from_env() -> MCPServer:
    required = [
        "GOOGLE_CLOUD_PROJECT", "FUSE_RELAY_ROOT_SECRET", "FUSE_OIDC_ISSUER",
        "FUSE_MCP_RESOURCE_URL", "FUSE_OIDC_JWKS_URL",
    ]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("MISSING_REQUIRED_ENV:" + ",".join(missing))
    relay = FirestoreRelay(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        root_secret=os.environ["FUSE_RELAY_ROOT_SECRET"],
    )
    return build_server(
        relay=relay,
        issuer=os.environ["FUSE_OIDC_ISSUER"],
        resource_url=os.environ["FUSE_MCP_RESOURCE_URL"],
        jwks_url=os.environ["FUSE_OIDC_JWKS_URL"],
    )


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server_from_env().run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
