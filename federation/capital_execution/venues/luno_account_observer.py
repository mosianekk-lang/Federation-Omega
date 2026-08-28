from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import base64
import json
import re


SecretResolver = Callable[[str], tuple[str, str]]
AuthenticatedTransport = Callable[[str, Mapping[str, Any], str, str], Mapping[str, Any]]


@dataclass(frozen=True)
class LunoCredentialReference:
    reference: str
    expected_permissions: tuple[str, ...] = (
        "Perm_R_Balance",
        "Perm_R_Transactions",
        "Perm_R_Orders",
    )

    def validate(self) -> None:
        reference = self.reference.strip()
        if not reference or reference != self.reference or "=" in reference or any(ch.isspace() for ch in reference):
            raise ValueError("credential reference must be symbolic and value-free")
        scheme, separator, locator = reference.partition("://")
        if not separator or not scheme or not locator:
            raise ValueError("credential reference must use a symbolic URI scheme")
        if scheme not in {"secret", "gcp-secret", "env", "runtime-ref"}:
            raise ValueError("credential reference scheme is not allowlisted")
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
    TRANSACTION_PATH = re.compile(r"^/api/1/accounts/[0-9]+/transactions$")

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

    @classmethod
    def _path_allowed(cls, path: str) -> bool:
        return path in cls.READ_PATHS or bool(cls.TRANSACTION_PATH.fullmatch(path))

    def _credentials(self) -> tuple[str, str]:
        key_id, material = self._secret_resolver(self.credential.reference)
        if not key_id or not material:
            raise PermissionError("LUNO_OBSERVER_CREDENTIAL_UNRESOLVED")
        return key_id, material

    def _https_get(self, path: str, params: Mapping[str, Any], key_id: str, material: str) -> Mapping[str, Any]:
        if not self._path_allowed(path):
            raise PermissionError("LUNO_OBSERVER_PATH_NOT_ALLOWLISTED")
        query = urlencode([(k, v) for k, v in params.items() if v is not None], doseq=True)
        url = f"{self.API_BASE}{path}" + (f"?{query}" if query else "")
        token = base64.b64encode(f"{key_id}:{material}".encode("utf-8")).decode("ascii")
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {token}",
                "User-Agent": "Federation-Luno-Observer/1.2",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Luno response must be an object")
        return payload

    def _get(self, path: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        if not self._path_allowed(path):
            raise PermissionError("LUNO_OBSERVER_PATH_NOT_ALLOWLISTED")
        key_id, material = self._credentials()
        try:
            return self._transport(path, params, key_id, material)
        finally:
            key_id = ""
            material = ""

    def balances(self, *, assets: tuple[str, ...] = ()) -> Mapping[str, Any]:
        return self._get("/api/1/balance", {"assets": list(assets) if assets else None})

    def list_orders(self, *, pair: str | None = None, state: str | None = None, limit: int = 100) -> Mapping[str, Any]:
        if state not in {None, "PENDING", "COMPLETE"}:
            raise ValueError("state must be PENDING, COMPLETE or None")
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return self._get("/api/1/listorders", {"pair": pair, "state": state, "limit": int(limit)})

    def fee_info(self, pair: str) -> Mapping[str, Any]:
        if not pair or not pair.isalnum():
            raise ValueError("pair must be alphanumeric")
        return self._get("/api/1/fee_info", {"pair": pair})

    def account_transactions(self, account_id: int, *, min_row: int = -100, max_row: int = 0) -> Mapping[str, Any]:
        account_id = int(account_id)
        if account_id <= 0:
            raise ValueError("account_id must be positive")
        if min_row >= max_row:
            raise ValueError("min_row must be less than max_row")
        if max_row - min_row > 1000:
            raise ValueError("transaction window cannot exceed 1000 rows")
        return self._get(
            f"/api/1/accounts/{account_id}/transactions",
            {"min_row": int(min_row), "max_row": int(max_row)},
        )

    def create_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_ORDER_AUTHORITY")

    def cancel_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_ORDER_AUTHORITY")

    def convert(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_CONVERSION_AUTHORITY")

    def send(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_SEND_AUTHORITY")

    def withdraw(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_WITHDRAWAL_AUTHORITY")

    def transfer(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("LUNO_OBSERVER_HAS_NO_TRANSFER_AUTHORITY")
