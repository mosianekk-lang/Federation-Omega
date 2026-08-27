from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import base64
import json


SecretResolver = Callable[[str], tuple[str, str]]
AuthenticatedTransport = Callable[[str, Mapping[str, Any], str, str], Mapping[str, Any]]


@dataclass(frozen=True)
class LunoCredentialReference:
    reference: str
    expected_permissions: tuple[str, ...] = ("Perm_R_Balance", "Perm_R_Orders")

    def validate(self) -> None:
        if not self.reference or any(token in self.reference.lower() for token in ("secret=", "api_secret", "password=")):
            raise ValueError("credential reference must be symbolic and value-free")
        allowed = {"Perm_R_Balance", "Perm_R_Transactions", "Perm_R_Orders"}
        if not set(self.expected_permissions).issubset(allowed):
            raise PermissionError("LUNO_OBSERVER_WRITE_PERMISSION_NOT_ALLOWED")


class LunoReadOnlyAccountObserver:
    """Authenticated Luno observer with a GET-only allowlist and no credential persistence."""

    API_BASE = "https://api.luno.com"
    READ_PATHS = {
        "/api/1/balance",
        "/api/1/listorders",
        "/api/1/fee_info",
    }

    def __init__(
        self,
        credential: LunoCredentialReference,
        secret_resolver: SecretResolver,
        transport: AuthenticatedTransport | None = None,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        credential.validate()
        self.credential = credential
        self._secret_resolver = secret_resolver
        self._transport = transport or self._https_get
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def _credentials(self) -> tuple[str, str]:
        key_id, secret = self._secret_resolver(self.credential.reference)
        if not key_id or not secret:
            raise PermissionError("LUNO_OBSERVER_CREDENTIAL_UNRESOLVED")
        return key_id, secret

    def _https_get(self, path: str, params: Mapping[str, Any], key_id: str, secret: str) -> Mapping[str, Any]:
        if path not in self.READ_PATHS:
            raise PermissionError("LUNO_OBSERVER_PATH_NOT_ALLOWLISTED")
        query = urlencode([(k, v) for k, v in params.items() if v is not None], doseq=True)
        url = f"{self.API_BASE}{path}" + (f"?{query}" if query else "")
        token = base64.b64encode(f"{key_id}:{secret}".encode("utf-8")).decode("ascii")
        request = Request(url, method="GET", headers={"Accept": "application/json", "Authorization": f"Basic {token}", "User-Agent": "Federation-Capital-Observer/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Luno response must be an object")
        return payload

    def _get(self, path: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        if path not in self.READ_PATHS:
            raise PermissionError("LUNO_OBSERVER_PATH_NOT_ALLOWLISTED")
        key_id, secret = self._credentials()
        try:
            return self._transport(path, params, key_id, secret)
        finally:
            key_id = ""
            secret = ""

    def balances(self, *, assets: tuple[str, ...] = ()) -> Mapping[str, Any]:
        return self._get("/api/1/balance", {"assets": list(assets) if assets else None})

    def list_orders(self, *, pair: str | None = None, state: str | None = None, limit: int = 100) -> Mapping[str, Any]:
        if state not in {None, "PENDING", "COMPLETE"}:
            raise ValueError("state must be PENDING, COMPLETE or None")
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return self._get("/api/1/listorders", {"pair": pair, "state": state, "limit": int(limit)})

    def fee_info(self, pair: str) -> Mapping[str, Any]:
        return self._get("/api/1/fee_info", {"pair": pair})

    def create_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_ORDER_AUTHORITY")

    def withdraw(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_WITHDRAWAL_AUTHORITY")

    def transfer(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_TRANSFER_AUTHORITY")
