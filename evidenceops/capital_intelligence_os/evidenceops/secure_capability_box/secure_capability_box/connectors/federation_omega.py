from __future__ import annotations

from typing import Any, Protocol

from ..audit import redact
from ..errors import ConnectorFailure, InvalidRequest


class HttpTransport(Protocol):
    def request(self, method: str, url: str, **kwargs): ...


class FederationOmegaConnector:
    """Fail-closed adapter for the allowlisted Federation Omega operator."""

    name = "federation-omega"

    def __init__(self, base_url: str, *, transport: HttpTransport | None = None, timeout_seconds: float = 15.0) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("Federation Omega requires an HTTPS base URL")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        if transport is None:
            try:
                import httpx
            except ImportError as exc:
                raise RuntimeError("httpx is required for Federation Omega") from exc
            transport = httpx.Client(timeout=timeout_seconds, follow_redirects=False)
        self._transport = transport

    def public_health(self) -> dict[str, Any]:
        return self._request("GET", "/health", credential=None, body=None)

    def execute(
        self,
        *,
        action: str,
        credential: memoryview,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        if not action or not isinstance(payload, dict):
            raise InvalidRequest("operator action and object payload are required")
        body = {"action": action, "payload": payload, "correlation_id": correlation_id}
        result = self._request("POST", "/execute", credential=credential, body=body)
        returned_action = result.get("action")
        if returned_action is not None and returned_action != action:
            raise ConnectorFailure("operator response action mismatch")
        state = result.get("state") or result.get("status")
        if result.get("ok") is not True and state not in {"OK", "READY", "COMPLETED", "SUCCESS"}:
            raise ConnectorFailure("operator response did not prove success")
        return redact(result)

    def readiness(self) -> dict[str, object]:
        return {"state": "CONFIGURED", "production_ready": True, "transport": "HTTPS"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        credential: memoryview | None,
        body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        headers: dict[str, Any] = {"accept": "application/json"}
        if credential is not None:
            headers["x-fo-admin-token"] = bytes(credential)
        try:
            response = self._transport.request(
                method,
                self.base_url + path,
                headers=headers,
                json=body,
                timeout=self.timeout_seconds,
            )
            if int(response.status_code) < 200 or int(response.status_code) >= 300:
                raise ConnectorFailure("operator request failed")
            value = response.json()
            if not isinstance(value, dict):
                raise ConnectorFailure("operator response must be an object")
            return value
        except ConnectorFailure:
            raise
        except Exception as exc:
            raise ConnectorFailure("operator transport failed") from exc
        finally:
            headers.pop("x-fo-admin-token", None)
