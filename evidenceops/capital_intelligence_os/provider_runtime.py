from __future__ import annotations

import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .local_runtime import LocalRuntimeApplication
from .policy import RuntimePolicy

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PROVIDER_MAX_HTTP_BODY_BYTES = 256_000
PROVIDER_SAFE_ROUTES = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/ready"),
        ("GET", "/v1/verify"),
        ("POST", "/v1/events"),
    }
)


class ProviderRuntimeConfig:
    """Fail-closed configuration for a provider-hosted CIOS candidate.

    Configuration proves only what the process was asked to run. Provider identity,
    deployment and revision state require separate provider-native readback.
    """

    def __init__(
        self,
        *,
        bearer_token: str,
        db_path: str = "",
        audit_path: str = "",
        storage_backend: str = "sqlite",
        database_url: str = "",
        audit_database_url: str = "",
        pool_max_size: int = 8,
        apply_migrations: bool = False,
        expected_source_sha: str,
        runtime_source_sha: str,
        runtime_identity: str,
        tenant_id: str,
        runtime_user_id: str,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        if len(bearer_token) < 24:
            raise ValueError("CIOS_BEARER_TOKEN must be at least 24 characters")
        if not _SHA_RE.fullmatch(expected_source_sha) or not _SHA_RE.fullmatch(runtime_source_sha):
            raise ValueError("source SHAs must be lowercase 40-character Git commit SHAs")
        if expected_source_sha != runtime_source_sha:
            raise ValueError("runtime source SHA does not match expected source SHA")
        if not runtime_identity.strip():
            raise ValueError("CIOS_RUNTIME_IDENTITY is required")
        if not tenant_id.strip() or not runtime_user_id.strip():
            raise ValueError("provider runtime requires a fixed tenant and runtime user")
        if storage_backend not in {"sqlite", "postgres"}:
            raise ValueError("CIOS_STORAGE_BACKEND must be sqlite or postgres")
        if storage_backend == "sqlite":
            if db_path.strip() in {"", ":memory:"} or audit_path.strip() in {"", ":memory:"}:
                raise ValueError("SQLite provider candidate requires persistent database and audit paths")
            if Path(db_path).resolve() == Path(audit_path).resolve():
                raise ValueError("database and audit paths must differ")
        else:
            if not database_url.strip() or not audit_database_url.strip():
                raise ValueError("PostgreSQL provider runtime requires state and audit database URLs")
            if database_url.strip() == audit_database_url.strip():
                raise ValueError("state and audit database URLs must differ")
            if not 1 <= int(pool_max_size) <= 16:
                raise ValueError("CIOS_DB_POOL_MAX_SIZE must be between 1 and 16")
        if not 1 <= int(port) <= 65535:
            raise ValueError("PORT must be between 1 and 65535")
        self.bearer_token = bearer_token
        self.db_path = db_path
        self.audit_path = audit_path
        self.storage_backend = storage_backend
        self.database_url = database_url
        self.audit_database_url = audit_database_url
        self.pool_max_size = int(pool_max_size)
        self.apply_migrations = bool(apply_migrations)
        self.expected_source_sha = expected_source_sha
        self.runtime_source_sha = runtime_source_sha
        self.runtime_identity = runtime_identity
        self.tenant_id = tenant_id
        self.runtime_user_id = runtime_user_id
        self.host = host
        self.port = int(port)

    @classmethod
    def from_environment(cls) -> "ProviderRuntimeConfig":
        required = {
            "CIOS_BEARER_TOKEN": os.environ.get("CIOS_BEARER_TOKEN", ""),
            "CIOS_EXPECTED_SOURCE_SHA": os.environ.get("CIOS_EXPECTED_SOURCE_SHA", ""),
            "CIOS_RUNTIME_SOURCE_SHA": os.environ.get("CIOS_RUNTIME_SOURCE_SHA", ""),
            "CIOS_RUNTIME_IDENTITY": os.environ.get("CIOS_RUNTIME_IDENTITY", ""),
            "CIOS_TENANT_ID": os.environ.get("CIOS_TENANT_ID", ""),
            "CIOS_RUNTIME_USER_ID": os.environ.get("CIOS_RUNTIME_USER_ID", ""),
        }
        missing = sorted(name for name, value in required.items() if not value)
        if missing:
            raise RuntimeError(f"missing required provider-runtime configuration: {','.join(missing)}")
        backend = os.environ.get("CIOS_STORAGE_BACKEND", "postgres")
        return cls(
            bearer_token=required["CIOS_BEARER_TOKEN"],
            db_path=os.environ.get("CIOS_DB_PATH", ""),
            audit_path=os.environ.get("CIOS_AUDIT_PATH", ""),
            storage_backend=backend,
            database_url=os.environ.get("CIOS_DATABASE_URL", ""),
            audit_database_url=os.environ.get("CIOS_AUDIT_DATABASE_URL", ""),
            pool_max_size=int(os.environ.get("CIOS_DB_POOL_MAX_SIZE", "8")),
            apply_migrations=os.environ.get("CIOS_APPLY_MIGRATIONS", "false").lower() == "true",
            expected_source_sha=required["CIOS_EXPECTED_SOURCE_SHA"],
            runtime_source_sha=required["CIOS_RUNTIME_SOURCE_SHA"],
            runtime_identity=required["CIOS_RUNTIME_IDENTITY"],
            tenant_id=required["CIOS_TENANT_ID"],
            runtime_user_id=required["CIOS_RUNTIME_USER_ID"],
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8080")),
        )


class ProviderRuntimeApplication(LocalRuntimeApplication):
    """Provider-hostable wrapper around the already-tested CIOS safe API surface."""

    def __init__(self, config: ProviderRuntimeConfig) -> None:
        self.config = config
        state_store = None
        audit_ledger = None
        if config.storage_backend == "postgres":
            from .postgres_audit import PostgresAuditLedger
            from .postgres_store import PostgresStateStore

            state_store = PostgresStateStore(
                config.database_url,
                max_pool_size=config.pool_max_size,
                apply_migrations=config.apply_migrations,
            )
            audit_ledger = PostgresAuditLedger(
                config.audit_database_url,
                max_pool_size=min(config.pool_max_size, 8),
                apply_migrations=config.apply_migrations,
            )
        super().__init__(
            config.db_path or None,
            config.audit_path or None,
            config.bearer_token,
            state_store=state_store,
            audit_ledger=audit_ledger,
            enable_documents=False,
        )
        self.policy = RuntimePolicy(
            config.bearer_token,
            runtime_roles=("operator",),
            safe_routes=PROVIDER_SAFE_ROUTES,
            fixed_tenant_id=config.tenant_id,
            fixed_user_id=config.runtime_user_id,
        )
        self._provider_request_lock = (
            threading.RLock() if config.storage_backend == "sqlite" else None
        )

    def handle(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, dict[str, Any]]:
        if len(body) > PROVIDER_MAX_HTTP_BODY_BYTES:
            return 413, {"error": "REQUEST_TOO_LARGE"}
        if self._provider_request_lock is not None:
            with self._provider_request_lock:
                status, payload = super().handle(method, path, headers, body)
        else:
            status, payload = super().handle(method, path, headers, body)
        normalized = path.split("?", 1)[0]
        if status == 200 and normalized in {"/health", "/ready"}:
            payload = dict(payload)
            payload.update(
                {
                    "runtime_mode": "PROVIDER_CANDIDATE",
                    "production_persistence_candidate": self.config.storage_backend == "postgres",
                    "runtime_source_sha": self.config.runtime_source_sha,
                    "declared_runtime_identity": self.config.runtime_identity,
                    "provider_identity_readback_verified": False,
                    "provider_deployment_verified": False,
                    "external_effects_enabled": False,
                    "fixed_tenant_binding": True,
                    "document_routes_enabled": False,
                    "storage_backend": self.config.storage_backend,
                    "managed_persistence_configured": self.config.storage_backend == "postgres",
                    "append_only_audit_configured": self.config.storage_backend == "postgres",
                    "horizontal_persistence_verified": self.config.storage_backend == "postgres",
                    "truth_boundary": (
                        "This response proves bounded application runtime semantics only. "
                        "Provider identity, revision and deployment require independent provider-native readback."
                    ),
                }
            )
        return status, payload


class _ProviderHandler(BaseHTTPRequestHandler):
    server_version = "CIOSProviderCandidate/1.0-rc8"

    def _dispatch(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if length < 0 or length > PROVIDER_MAX_HTTP_BODY_BYTES:
            payload = {"error": "REQUEST_TOO_LARGE"}
            data = json.dumps(payload).encode()
            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        body = self.rfile.read(length) if length else b""
        status, payload = self.server.app.handle(
            self.command,
            self.path,
            {key: value for key, value in self.headers.items()},
            body,
        )
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


class ProviderRuntimeServer(ThreadingHTTPServer):
    def __init__(self, app: ProviderRuntimeApplication) -> None:
        self.app = app
        super().__init__((app.config.host, app.config.port), _ProviderHandler)


def main() -> None:
    config = ProviderRuntimeConfig.from_environment()
    app = ProviderRuntimeApplication(config)
    server = ProviderRuntimeServer(app)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
