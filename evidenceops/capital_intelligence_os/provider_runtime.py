from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .local_runtime import LocalRuntimeApplication, MAX_HTTP_BODY_BYTES

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ProviderRuntimeConfig:
    """Fail-closed configuration for a provider-hosted CIOS candidate.

    Configuration proves only what the process was asked to run. Provider identity,
    deployment and revision state require separate provider-native readback.
    """

    def __init__(
        self,
        *,
        bearer_token: str,
        db_path: str,
        audit_path: str,
        expected_source_sha: str,
        runtime_source_sha: str,
        runtime_identity: str,
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
        if db_path.strip() in {"", ":memory:"} or audit_path.strip() in {"", ":memory:"}:
            raise ValueError("provider runtime requires persistent database and audit paths")
        if Path(db_path).resolve() == Path(audit_path).resolve():
            raise ValueError("database and audit paths must differ")
        if not 1 <= int(port) <= 65535:
            raise ValueError("PORT must be between 1 and 65535")
        self.bearer_token = bearer_token
        self.db_path = db_path
        self.audit_path = audit_path
        self.expected_source_sha = expected_source_sha
        self.runtime_source_sha = runtime_source_sha
        self.runtime_identity = runtime_identity
        self.host = host
        self.port = int(port)

    @classmethod
    def from_environment(cls) -> "ProviderRuntimeConfig":
        required = {
            "CIOS_BEARER_TOKEN": os.environ.get("CIOS_BEARER_TOKEN", ""),
            "CIOS_DB_PATH": os.environ.get("CIOS_DB_PATH", ""),
            "CIOS_AUDIT_PATH": os.environ.get("CIOS_AUDIT_PATH", ""),
            "CIOS_EXPECTED_SOURCE_SHA": os.environ.get("CIOS_EXPECTED_SOURCE_SHA", ""),
            "CIOS_RUNTIME_SOURCE_SHA": os.environ.get("CIOS_RUNTIME_SOURCE_SHA", ""),
            "CIOS_RUNTIME_IDENTITY": os.environ.get("CIOS_RUNTIME_IDENTITY", ""),
        }
        missing = sorted(name for name, value in required.items() if not value)
        if missing:
            raise RuntimeError(f"missing required provider-runtime configuration: {','.join(missing)}")
        return cls(
            bearer_token=required["CIOS_BEARER_TOKEN"],
            db_path=required["CIOS_DB_PATH"],
            audit_path=required["CIOS_AUDIT_PATH"],
            expected_source_sha=required["CIOS_EXPECTED_SOURCE_SHA"],
            runtime_source_sha=required["CIOS_RUNTIME_SOURCE_SHA"],
            runtime_identity=required["CIOS_RUNTIME_IDENTITY"],
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8080")),
        )


class ProviderRuntimeApplication(LocalRuntimeApplication):
    """Provider-hostable wrapper around the already-tested CIOS safe API surface."""

    def __init__(self, config: ProviderRuntimeConfig) -> None:
        self.config = config
        super().__init__(config.db_path, config.audit_path, config.bearer_token)

    def handle(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, dict[str, Any]]:
        status, payload = super().handle(method, path, headers, body)
        normalized = path.split("?", 1)[0]
        if status == 200 and normalized in {"/health", "/ready"}:
            payload = dict(payload)
            payload.update(
                {
                    "runtime_mode": "PROVIDER_CANDIDATE",
                    "runtime_source_sha": self.config.runtime_source_sha,
                    "declared_runtime_identity": self.config.runtime_identity,
                    "provider_identity_readback_verified": False,
                    "provider_deployment_verified": False,
                    "external_effects_enabled": False,
                    "truth_boundary": (
                        "This response proves bounded application runtime semantics only. "
                        "Provider identity, revision and deployment require independent provider-native readback."
                    ),
                }
            )
        return status, payload


class _ProviderHandler(BaseHTTPRequestHandler):
    server_version = "CIOSProviderCandidate/1.0-rc5"

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
