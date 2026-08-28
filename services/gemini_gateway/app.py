"""Private Cloud Run Gemini execution gateway using service-account ADC.

Security properties:
- No API key or service-account key is accepted.
- OAuth tokens come only from the Google metadata server.
- The canonical project is fail-closed.
- Provider proof requires an exact semantic nonce plus Vertex response identity.
- OAuth tokens are never returned or logged.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import VERSION

CANONICAL_PROJECT_ID = "sov-hybrid-suite"
CANONICAL_PROJECT_NUMBER = "257649435135"
DEFAULT_LOCATION = "global"
DEFAULT_MODEL = "gemini-2.5-flash"
METADATA_ROOT = "http://metadata.google.internal/computeMetadata/v1"
MAX_BODY_BYTES = 256_000
MAX_PROMPT_CHARS = 80_000
HANDSHAKE_PREFIX = "HANDSHAKE_RECEIPT:"
USER_AGENT = f"sovara-gemini-gateway/{VERSION}"


class GatewayError(RuntimeError):
    """Fail-closed gateway error with a stable machine-readable code."""

    def __init__(self, code: str, detail: str = "", *, http_status: int = 500) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code
        self.http_status = http_status


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value: Any) -> str:
    if not isinstance(value, str):
        value = canonical_json(value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _urlopen_json(request: Request, *, timeout: float = 15.0) -> tuple[int, dict[str, Any]]:
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status = int(getattr(response, "status", response.getcode()))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:4000]}
        raise GatewayError(
            "UPSTREAM_HTTP_ERROR",
            f"HTTP {exc.code}: {canonical_json(payload)}",
            http_status=502,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise GatewayError("UPSTREAM_TRANSPORT_ERROR", str(exc), http_status=502) from exc

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise GatewayError("UPSTREAM_NON_JSON_RESPONSE", raw[:4000], http_status=502) from exc
    if not isinstance(parsed, dict):
        raise GatewayError("UPSTREAM_JSON_OBJECT_REQUIRED", http_status=502)
    return status, parsed


class MetadataIdentity:
    """Read Cloud Run service identity from the metadata server."""

    def __init__(
        self,
        *,
        metadata_root: str = METADATA_ROOT,
        fetch_json: Callable[[Request], tuple[int, dict[str, Any]]] | None = None,
    ) -> None:
        self.metadata_root = metadata_root.rstrip("/")
        self._fetch_json = fetch_json or (lambda req: _urlopen_json(req, timeout=5.0))

    def _request(self, path: str) -> dict[str, Any]:
        request = Request(
            f"{self.metadata_root}/{path.lstrip('/')}",
            headers={"Metadata-Flavor": "Google", "User-Agent": USER_AGENT},
            method="GET",
        )
        status, payload = self._fetch_json(request)
        if not 200 <= status < 300:
            raise GatewayError("METADATA_HTTP_ERROR", f"HTTP {status}", http_status=503)
        return payload

    def _request_text(self, path: str) -> str:
        request = Request(
            f"{self.metadata_root}/{path.lstrip('/')}",
            headers={"Metadata-Flavor": "Google", "User-Agent": USER_AGENT},
            method="GET",
        )
        try:
            with urlopen(request, timeout=5.0) as response:
                text = response.read().decode("utf-8").strip()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise GatewayError("METADATA_TRANSPORT_ERROR", str(exc), http_status=503) from exc
        if not text:
            raise GatewayError("METADATA_EMPTY_VALUE", path, http_status=503)
        return text

    def project_id(self) -> str:
        return self._request_text("project/project-id")

    def service_account_email(self) -> str:
        return self._request_text("instance/service-accounts/default/email")

    def access_token(self) -> str:
        payload = self._request("instance/service-accounts/default/token")
        token = str(payload.get("access_token") or "")
        token_type = str(payload.get("token_type") or "").lower()
        expires_in = int(payload.get("expires_in") or 0)
        if not token or token_type != "bearer" or expires_in <= 0:
            raise GatewayError("METADATA_TOKEN_INVALID", http_status=503)
        return token

    def snapshot(self) -> dict[str, Any]:
        project = self.project_id()
        service_account = self.service_account_email()
        expected_service_account = os.getenv("EXPECTED_RUNTIME_SERVICE_ACCOUNT", "").strip()
        if project != CANONICAL_PROJECT_ID:
            raise GatewayError(
                "CANONICAL_PROJECT_MISMATCH",
                f"expected={CANONICAL_PROJECT_ID} observed={project}",
                http_status=503,
            )
        if expected_service_account and service_account != expected_service_account:
            raise GatewayError(
                "RUNTIME_IDENTITY_MISMATCH",
                f"expected={expected_service_account} observed={service_account}",
                http_status=503,
            )
        return {
            "project_id": project,
            "project_number": CANONICAL_PROJECT_NUMBER,
            "service_account": service_account,
            "authority_mode": "CLOUD_RUN_SERVICE_ACCOUNT_ADC",
        }


class VertexGeminiClient:
    """Minimal Vertex AI Gemini REST client authenticated with metadata ADC."""

    def __init__(
        self,
        identity: MetadataIdentity,
        *,
        location: str | None = None,
        model: str | None = None,
        fetch_json: Callable[[Request], tuple[int, dict[str, Any]]] | None = None,
    ) -> None:
        self.identity = identity
        self.location = (location or os.getenv("GOOGLE_CLOUD_LOCATION") or DEFAULT_LOCATION).strip()
        self.model = (model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL).strip()
        self._fetch_json = fetch_json or (lambda req: _urlopen_json(req, timeout=60.0))
        if self.location != "global":
            raise GatewayError(
                "NON_CANONICAL_VERTEX_LOCATION",
                "This gateway is pinned to the Vertex AI global endpoint.",
                http_status=503,
            )
        if not self.model or "/" in self.model or ":" in self.model:
            raise GatewayError("INVALID_MODEL_ID", self.model, http_status=503)

    @property
    def endpoint(self) -> str:
        return (
            "https://aiplatform.googleapis.com/v1/"
            f"projects/{CANONICAL_PROJECT_ID}/locations/{self.location}/"
            f"publishers/google/models/{self.model}:generateContent"
        )

    def generate(
        self,
        *,
        prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
    ) -> dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise GatewayError("PROMPT_REQUIRED", http_status=400)
        if len(prompt) > MAX_PROMPT_CHARS:
            raise GatewayError("PROMPT_TOO_LARGE", http_status=413)
        if not 0 <= float(temperature) <= 2:
            raise GatewayError("INVALID_TEMPERATURE", http_status=400)
        if not 1 <= int(max_output_tokens) <= 4096:
            raise GatewayError("INVALID_MAX_OUTPUT_TOKENS", http_status=400)

        identity = self.identity.snapshot()
        token = self.identity.access_token()
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": int(max_output_tokens),
            },
        }
        request_sha = sha256(body)
        request = Request(
            self.endpoint,
            data=canonical_json(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        started = time.monotonic()
        status, payload = self._fetch_json(request)
        latency_ms = int((time.monotonic() - started) * 1000)
        if not 200 <= status < 300:
            raise GatewayError("VERTEX_HTTP_ERROR", f"HTTP {status}", http_status=502)

        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise GatewayError("VERTEX_CANDIDATE_MISSING", canonical_json(payload), http_status=502)
        candidate = candidates[0] if isinstance(candidates[0], dict) else {}
        content = candidate.get("content") if isinstance(candidate, dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text = "".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and part.get("text") is not None
        ).strip()

        response_id = str(payload.get("responseId") or "")
        model_version = str(payload.get("modelVersion") or "")
        finish_reason = str(candidate.get("finishReason") or "")
        usage = payload.get("usageMetadata")
        if not response_id or not model_version or not finish_reason or not isinstance(usage, dict):
            raise GatewayError(
                "VERTEX_PROVIDER_IDENTITY_INCOMPLETE",
                canonical_json({
                    "responseId": bool(response_id),
                    "modelVersion": bool(model_version),
                    "finishReason": bool(finish_reason),
                    "usageMetadata": isinstance(usage, dict),
                }),
                http_status=502,
            )

        return {
            "provider": "GOOGLE_VERTEX_AI_GEMINI",
            "provider_request_id": response_id,
            "model_identity": model_version,
            "configured_model": self.model,
            "finish_state": finish_reason,
            "usage": usage,
            "latency_ms": latency_ms,
            "provider_identity": identity,
            "request_sha256": request_sha,
            "response_sha256": sha256(payload),
            "text": text,
        }


class Gateway:
    def __init__(
        self,
        *,
        identity: MetadataIdentity | None = None,
        client: VertexGeminiClient | None = None,
    ) -> None:
        self.identity = identity or MetadataIdentity()
        self.client = client or VertexGeminiClient(self.identity)

    def health(self) -> dict[str, Any]:
        return {
            "status": "HEALTHY",
            "service": "SOVARA_GEMINI_GATEWAY",
            "version": VERSION,
            "canonical_project_id": CANONICAL_PROJECT_ID,
            "canonical_project_number": CANONICAL_PROJECT_NUMBER,
            "location": self.client.location,
            "configured_model": self.client.model,
            "provider_execution_verified": False,
            "checked_at_unix_ms": int(time.time() * 1000),
        }

    def ready(self) -> dict[str, Any]:
        identity = self.identity.snapshot()
        return {
            "status": "READY_IDENTITY_VERIFIED",
            "service": "SOVARA_GEMINI_GATEWAY",
            "version": VERSION,
            "provider_identity": identity,
            "location": self.client.location,
            "configured_model": self.client.model,
            "provider_execution_verified": False,
            "checked_at_unix_ms": int(time.time() * 1000),
        }

    def handshake(self, body: Mapping[str, Any]) -> dict[str, Any]:
        nonce = str(body.get("semantic_nonce") or "").strip()
        if not nonce or len(nonce) > 256:
            raise GatewayError("SEMANTIC_NONCE_REQUIRED", http_status=400)
        if any(ch.isspace() for ch in nonce):
            raise GatewayError("SEMANTIC_NONCE_INVALID", http_status=400)

        expected = f"{HANDSHAKE_PREFIX}{nonce}"
        prompt = (
            "This is a bounded provider identity canary. "
            "Return exactly the following token and no other text:\n"
            f"{expected}"
        )
        provider = self.client.generate(
            prompt=prompt,
            temperature=0.0,
            max_output_tokens=128,
        )
        observed = str(provider.get("text") or "").strip()
        semantic_verified = observed == expected
        if not semantic_verified:
            raise GatewayError(
                "SEMANTIC_NONCE_MISMATCH",
                f"expected_sha256={sha256(expected)} observed_sha256={sha256(observed)}",
                http_status=502,
            )

        receipt_core = {
            "schema": "SOVARA_GEMINI_HANDSHAKE_RECEIPT_V1",
            "status": "VERIFIED",
            "provider": provider["provider"],
            "provider_request_id": provider["provider_request_id"],
            "model_identity": provider["model_identity"],
            "configured_model": provider["configured_model"],
            "semantic_nonce": nonce,
            "semantic_nonce_sha256": sha256(nonce),
            "semantic_verified": True,
            "finish_state": provider["finish_state"],
            "usage": provider["usage"],
            "latency_ms": provider["latency_ms"],
            "provider_identity": provider["provider_identity"],
            "request_sha256": provider["request_sha256"],
            "response_sha256": provider["response_sha256"],
        }
        return {**receipt_core, "receipt_sha256": sha256(receipt_core)}

    def generate(self, body: Mapping[str, Any]) -> dict[str, Any]:
        prompt = str(body.get("prompt") or "")
        result = self.client.generate(
            prompt=prompt,
            temperature=float(body.get("temperature", 0.0)),
            max_output_tokens=int(body.get("max_output_tokens", 512)),
        )
        receipt_core = {
            key: value
            for key, value in result.items()
            if key != "text"
        }
        return {
            "status": "DONE",
            "text": result["text"],
            "receipt": {
                **receipt_core,
                "receipt_sha256": sha256(receipt_core),
            },
        }


class Handler(BaseHTTPRequestHandler):
    server_version = f"SovaraGeminiGateway/{VERSION}"
    gateway: Gateway

    def _reply(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise GatewayError("INVALID_CONTENT_LENGTH", http_status=400) from exc
        if length < 1:
            raise GatewayError("BODY_REQUIRED", http_status=400)
        if length > MAX_BODY_BYTES:
            raise GatewayError("BODY_TOO_LARGE", http_status=413)
        try:
            parsed = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise GatewayError("INVALID_JSON", str(exc), http_status=400) from exc
        if not isinstance(parsed, dict):
            raise GatewayError("JSON_OBJECT_REQUIRED", http_status=400)
        return parsed

    def do_GET(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/health":
                self._reply(200, self.gateway.health())
            elif path == "/ready":
                self._reply(200, self.gateway.ready())
            else:
                self._reply(404, {"status": "FAILED", "code": "NOT_FOUND"})
        except GatewayError as exc:
            self._reply(exc.http_status, {"status": "FAILED", "code": exc.code, "detail": exc.detail})

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            body = self._body()
            if path == "/v1/handshake":
                self._reply(200, self.gateway.handshake(body))
            elif path == "/v1/generate":
                self._reply(200, self.gateway.generate(body))
            else:
                self._reply(404, {"status": "FAILED", "code": "NOT_FOUND"})
        except GatewayError as exc:
            self._reply(exc.http_status, {"status": "FAILED", "code": exc.code, "detail": exc.detail})
        except (TypeError, ValueError) as exc:
            self._reply(400, {"status": "FAILED", "code": "INVALID_ARGUMENT", "detail": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def run() -> None:
    project_env = (os.getenv("GOOGLE_CLOUD_PROJECT") or CANONICAL_PROJECT_ID).strip()
    if project_env != CANONICAL_PROJECT_ID:
        raise SystemExit(
            f"CANONICAL_PROJECT_MISMATCH expected={CANONICAL_PROJECT_ID} observed={project_env}"
        )
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    Handler.gateway = Gateway()
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    run()
