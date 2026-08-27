from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import hashlib
import hmac


@dataclass(frozen=True)
class RuntimePrincipal:
    tenant_id: str
    user_id: str
    roles: tuple[str, ...] = ("operator",)


class RuntimePolicy:
    SAFE_ROUTES = {
        ("GET", "/health"),
        ("GET", "/ready"),
        ("GET", "/v1/verify"),
        ("POST", "/v1/events"),
        ("POST", "/v1/documents"),
        ("POST", "/v1/search"),
        ("GET", "/v1/diligence"),
        ("GET", "/v1/workspace"),
    }
    FORBIDDEN_PREFIXES = (
        "/orders",
        "/trade",
        "/transfer",
        "/withdraw",
        "/payments",
        "/sign",
        "/regulatory-file",
    )
    ALLOWED_RUNTIME_ROLES = frozenset(
        {
            "operator",
            "deal_member",
            "admin",
            "clean_team",
            "restricted_access",
            "legal_privileged",
        }
    )

    def __init__(
        self,
        bearer_token: str,
        runtime_roles: Iterable[str] = ("operator", "deal_member"),
        *,
        safe_routes: Iterable[tuple[str, str]] | None = None,
        fixed_tenant_id: str | None = None,
        fixed_user_id: str | None = None,
    ) -> None:
        if len(bearer_token) < 24:
            raise ValueError("local canary bearer token must be at least 24 characters")
        roles = tuple(dict.fromkeys(str(role).strip() for role in runtime_roles if str(role).strip()))
        if not roles:
            raise ValueError("at least one runtime role is required")
        unknown = sorted(set(roles) - self.ALLOWED_RUNTIME_ROLES)
        if unknown:
            raise ValueError(f"unsupported runtime roles: {','.join(unknown)}")
        self._token_hash = hashlib.sha256(bearer_token.encode()).digest()
        self._runtime_roles = roles
        self._safe_routes = frozenset(
            (str(method).upper(), str(path))
            for method, path in (safe_routes if safe_routes is not None else self.SAFE_ROUTES)
        )
        if (fixed_tenant_id is None) != (fixed_user_id is None):
            raise ValueError("fixed tenant and user identity must be configured together")
        if fixed_tenant_id is not None and (
            not fixed_tenant_id.strip() or not fixed_user_id or not fixed_user_id.strip()
        ):
            raise ValueError("fixed tenant and user identity must be non-empty")
        self._fixed_tenant_id = fixed_tenant_id
        self._fixed_user_id = fixed_user_id

    def authenticate(
        self,
        authorization: str | None,
        tenant_id: str | None,
        user_id: str | None,
    ) -> RuntimePrincipal:
        if not authorization or not authorization.startswith("Bearer "):
            raise PermissionError("AUTH_REQUIRED")
        supplied = hashlib.sha256(authorization[7:].encode()).digest()
        if not hmac.compare_digest(supplied, self._token_hash):
            raise PermissionError("AUTH_INVALID")
        if self._fixed_tenant_id is not None:
            if tenant_id and tenant_id != self._fixed_tenant_id:
                raise PermissionError("CALLER_TENANT_OVERRIDE_DENIED")
            if user_id and user_id != self._fixed_user_id:
                raise PermissionError("CALLER_USER_OVERRIDE_DENIED")
            return RuntimePrincipal(
                self._fixed_tenant_id,
                self._fixed_user_id or "",
                self._runtime_roles,
            )
        if not tenant_id or not user_id:
            raise PermissionError("TENANT_AND_USER_REQUIRED")
        return RuntimePrincipal(tenant_id, user_id, self._runtime_roles)

    def authorize(self, method: str, path: str) -> None:
        normalized = path.split("?", 1)[0]
        if any(normalized.startswith(prefix) for prefix in self.FORBIDDEN_PREFIXES):
            raise PermissionError("CONSEQUENTIAL_ROUTE_NOT_EXPOSED")
        if (method.upper(), normalized) not in self._safe_routes:
            raise PermissionError("ROUTE_DEFAULT_DENY")
