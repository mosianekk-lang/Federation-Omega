from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
import json
import threading

from .audit import AuditLedger
from .deal_workspace import DealWorkspaceService
from .durable import DurableAutopilotRuntime
from .models import Domain, Event, InformationClass
from .policy import RuntimePolicy
from .store import SqliteStateStore
from .tenancy import TenantContext
from .vault import DocumentVault


MAX_HTTP_BODY_BYTES = 7_000_000


class LocalRuntimeApplication:
    def __init__(
        self,
        db_path: str | Path,
        audit_path: str | Path,
        bearer_token: str,
        *,
        runtime_roles: Iterable[str] = ("operator", "deal_member"),
    ) -> None:
        self.store = SqliteStateStore(db_path)
        self.audit = AuditLedger(audit_path)
        self.runtime = DurableAutopilotRuntime(self.store)
        self.policy = RuntimePolicy(bearer_token, runtime_roles=runtime_roles)
        self.vault = DocumentVault(db_path)
        self.workspace = DealWorkspaceService(self.vault)

    def close(self) -> None:
        self.vault.close()
        self.store.close()
        self.audit.close()

    def handle(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, dict[str, Any]]:
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        normalized_path = path.split("?", 1)[0]

        def header_value(name: str) -> str | None:
            return normalized_headers.get(name.lower())

        try:
            self.policy.authorize(method, normalized_path)
        except PermissionError as exc:
            self.audit.append(
                header_value("X-Tenant-ID") or "UNKNOWN",
                header_value("X-User-ID") or "UNKNOWN",
                method,
                normalized_path,
                "DENY",
                {"reason": str(exc)},
            )
            return 403, {"error": str(exc)}

        try:
            principal = self.policy.authenticate(
                header_value("Authorization"),
                header_value("X-Tenant-ID"),
                header_value("X-User-ID"),
            )
        except PermissionError as exc:
            self.audit.append(
                header_value("X-Tenant-ID") or "UNKNOWN",
                header_value("X-User-ID") or "UNKNOWN",
                method,
                normalized_path,
                "DENY",
                {"reason": str(exc)},
            )
            return 401, {"error": str(exc)}

        ctx = TenantContext(principal.tenant_id, principal.user_id, principal.roles)
        try:
            if method == "GET" and normalized_path == "/health":
                payload = {
                    "status": "ok",
                    "mode": "LOCAL_CANARY",
                    "database_quick_check": self.store.quick_check(),
                    "vault_quick_check": self.vault.quick_check(),
                    "audit_chain_valid": self.audit.verify(),
                    "live_financial_effects": False,
                }
            elif method == "GET" and normalized_path == "/ready":
                payload = {
                    "ready": self.store.quick_check() and self.vault.quick_check() and self.audit.verify(),
                    "authority_ceiling": "A1_INTERNAL",
                    "runtime_roles": list(principal.roles),
                }
            elif method == "GET" and normalized_path == "/v1/verify":
                from .verify_release import verify

                payload = verify()
            elif method == "POST" and normalized_path == "/v1/events":
                data = json.loads(body.decode() or "{}")
                if not data.get("occurred_at"):
                    raise ValueError("occurred_at is required for idempotent event ingestion")
                event = Event(
                    data["event_type"],
                    data.get("source", "local-api"),
                    data["subject_id"],
                    data.get("payload", {}),
                    Domain(data["domain"]),
                    InformationClass(data["information_class"]),
                    float(data.get("materiality", 0.0)),
                    event_id=data.get("event_id") or __import__("uuid").uuid4().hex,
                    occurred_at=data["occurred_at"],
                )
                payload = self.runtime.process(ctx, event, idempotency_key=header_value("Idempotency-Key"))
            elif method == "POST" and normalized_path == "/v1/documents":
                payload = self.workspace.ingest_payload(ctx, json.loads(body.decode() or "{}"))
            elif method == "POST" and normalized_path == "/v1/search":
                payload = self.workspace.search_payload(ctx, json.loads(body.decode() or "{}"))
            elif method == "GET" and normalized_path == "/v1/diligence":
                payload = self.workspace.ingestion.diligence_status(ctx)
            elif method == "GET" and normalized_path == "/v1/workspace":
                payload = self.workspace.snapshot(ctx)
            else:
                return 403, {"error": "ROUTE_DEFAULT_DENY"}

            self.audit.append(
                principal.tenant_id,
                principal.user_id,
                method,
                normalized_path,
                "ALLOW",
                {"status": 200},
            )
            return 200, payload
        except Exception as exc:
            self.audit.append(
                principal.tenant_id,
                principal.user_id,
                method,
                normalized_path,
                "ERROR",
                {"type": type(exc).__name__},
            )
            return 400, {"error": type(exc).__name__, "detail": str(exc)}


class _Handler(BaseHTTPRequestHandler):
    server_version = "CIOSLocalCanary/1.0-rc5"

    def _dispatch(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if length < 0 or length > MAX_HTTP_BODY_BYTES:
            payload = {"error": "REQUEST_TOO_LARGE"}
            data = json.dumps(payload).encode()
            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        body = self.rfile.read(length) if length else b""
        headers = {key: value for key, value in self.headers.items()}
        status, payload = self.server.app.handle(self.command, self.path, headers, body)
        data = json.dumps(payload, sort_keys=True, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    do_GET = _dispatch
    do_POST = _dispatch

    def log_message(self, *_args: object) -> None:
        return


class LocalRuntimeServer(ThreadingHTTPServer):
    def __init__(self, app: LocalRuntimeApplication, host: str = "127.0.0.1", port: int = 0) -> None:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise PermissionError("LOCAL_CANARY_LOOPBACK_ONLY")
        self.app = app
        super().__init__((host, port), _Handler)

    def start_in_thread(self):
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        return thread
