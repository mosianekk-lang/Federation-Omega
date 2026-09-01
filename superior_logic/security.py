from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class AuthMode(str, Enum):
    DENY_MUTATIONS = "deny_mutations"
    HMAC = "hmac"
    TRUSTED_PROXY = "trusted_proxy"


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    roles: frozenset[str]
    audience: str
    expires_at: int | None = None

    @property
    def can_mutate(self) -> bool:
        return bool(self.roles.intersection({"operator", "admin", "owner"}))


@dataclass(frozen=True)
class SlosAuthPolicy:
    mode: AuthMode = AuthMode.DENY_MUTATIONS
    audience: str = "superior-logic"
    require_read_auth: bool = False
    trusted_proxy_enabled: bool = False
    max_hmac_ttl_seconds: int = 300
    hmac_secret: str = ""

    @classmethod
    def from_env(cls) -> "SlosAuthPolicy":
        raw_mode = os.getenv("SUPERIOR_LOGIC_AUTH_MODE", AuthMode.DENY_MUTATIONS.value).strip().lower()
        try:
            mode = AuthMode(raw_mode)
        except ValueError as exc:
            raise RuntimeError(f"unsupported SUPERIOR_LOGIC_AUTH_MODE: {raw_mode!r}") from exc
        audience = os.getenv("SUPERIOR_LOGIC_AUTH_AUDIENCE", "superior-logic").strip() or "superior-logic"
        require_read_auth = os.getenv("SUPERIOR_LOGIC_REQUIRE_READ_AUTH", "0").strip().lower() in {"1", "true", "yes"}
        trusted_proxy = os.getenv("SUPERIOR_LOGIC_TRUSTED_PROXY", "0").strip().lower() in {"1", "true", "yes"}
        ttl = int(os.getenv("SUPERIOR_LOGIC_HMAC_MAX_TTL_SECONDS", "300"))
        if ttl < 30 or ttl > 3600:
            raise RuntimeError("SUPERIOR_LOGIC_HMAC_MAX_TTL_SECONDS must be between 30 and 3600")
        secret = os.getenv("SUPERIOR_LOGIC_HMAC_SECRET", "")
        if mode is AuthMode.HMAC and len(secret.encode("utf-8")) < 32:
            raise RuntimeError("HMAC auth requires SUPERIOR_LOGIC_HMAC_SECRET of at least 32 bytes")
        if mode is AuthMode.TRUSTED_PROXY and not trusted_proxy:
            raise RuntimeError("trusted_proxy auth requires SUPERIOR_LOGIC_TRUSTED_PROXY=1")
        return cls(
            mode=mode,
            audience=audience,
            require_read_auth=require_read_auth,
            trusted_proxy_enabled=trusted_proxy,
            max_hmac_ttl_seconds=ttl,
            hmac_secret=secret,
        )


def _canonical_roles(values: Iterable[str]) -> frozenset[str]:
    return frozenset(item.strip().lower() for item in values if item and item.strip())


def _signature_payload(*, method: str, path: str, subject: str, roles: str, expires_at: int, audience: str, nonce: str) -> bytes:
    return "\n".join(
        [method.upper(), path, subject, roles, str(expires_at), audience, nonce]
    ).encode("utf-8")


def sign_hmac_assertion(
    *,
    secret: str,
    method: str,
    path: str,
    subject: str,
    roles: Iterable[str],
    expires_at: int,
    audience: str,
    nonce: str,
) -> str:
    canonical_roles = ",".join(sorted(_canonical_roles(roles)))
    return hmac.new(
        secret.encode("utf-8"),
        _signature_payload(
            method=method,
            path=path,
            subject=subject,
            roles=canonical_roles,
            expires_at=expires_at,
            audience=audience,
            nonce=nonce,
        ),
        hashlib.sha256,
    ).hexdigest()


def _authenticate_hmac(request: Request, policy: SlosAuthPolicy, now: int) -> AuthPrincipal | None:
    subject = request.headers.get("x-slos-principal", "").strip()
    roles_raw = request.headers.get("x-slos-roles", "").strip()
    audience = request.headers.get("x-slos-audience", "").strip()
    expires_raw = request.headers.get("x-slos-expires", "").strip()
    nonce = request.headers.get("x-slos-nonce", "").strip()
    signature = request.headers.get("x-slos-signature", "").strip().lower()
    if not all((subject, roles_raw, audience, expires_raw, nonce, signature)):
        return None
    if audience != policy.audience:
        return None
    try:
        expires_at = int(expires_raw)
    except ValueError:
        return None
    if expires_at <= now or expires_at - now > policy.max_hmac_ttl_seconds:
        return None
    roles = _canonical_roles(roles_raw.split(","))
    canonical_roles = ",".join(sorted(roles))
    expected = hmac.new(
        policy.hmac_secret.encode("utf-8"),
        _signature_payload(
            method=request.method,
            path=request.url.path,
            subject=subject,
            roles=canonical_roles,
            expires_at=expires_at,
            audience=audience,
            nonce=nonce,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return AuthPrincipal(subject=subject, roles=roles, audience=audience, expires_at=expires_at)


def _authenticate_trusted_proxy(request: Request, policy: SlosAuthPolicy) -> AuthPrincipal | None:
    if not policy.trusted_proxy_enabled:
        return None
    subject = request.headers.get("x-slos-principal", "").strip()
    roles = _canonical_roles(request.headers.get("x-slos-roles", "").split(","))
    audience = request.headers.get("x-slos-audience", "").strip()
    verified = request.headers.get("x-slos-proxy-verified", "").strip().lower() == "true"
    if not subject or audience != policy.audience or not verified:
        return None
    return AuthPrincipal(subject=subject, roles=roles, audience=audience)


class SlosSecurityMiddleware(BaseHTTPMiddleware):
    """Fail-closed application boundary for the legacy Superior Logic API.

    Production deployments are expected to use provider-native ingress/IAM and
    trusted_proxy mode. HMAC mode exists for bounded local/private integrations.
    The default mode permits public health/read traffic but denies every state-
    changing HTTP method, preventing accidental unauthenticated deployment.
    """

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app, *, policy: SlosAuthPolicy | None = None):
        super().__init__(app)
        self.policy = policy or SlosAuthPolicy.from_env()

    async def dispatch(self, request: Request, call_next):
        now = int(time.time())
        safe_method = request.method.upper() in self.SAFE_METHODS
        authentication_required = (not safe_method) or self.policy.require_read_auth

        principal: AuthPrincipal | None = None
        if self.policy.mode is AuthMode.HMAC:
            principal = _authenticate_hmac(request, self.policy, now)
        elif self.policy.mode is AuthMode.TRUSTED_PROXY:
            principal = _authenticate_trusted_proxy(request, self.policy)

        if authentication_required:
            if self.policy.mode is AuthMode.DENY_MUTATIONS:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Superior Logic mutation API is fail-closed until application authentication is configured.",
                        "auth_mode": self.policy.mode.value,
                    },
                )
            if principal is None:
                return JSONResponse(status_code=401, content={"detail": "Missing or invalid Superior Logic authentication."})
            if not safe_method and not principal.can_mutate:
                return JSONResponse(status_code=403, content={"detail": "Authenticated principal lacks mutation authority."})

        request.state.slos_principal = principal
        response = await call_next(request)
        response.headers["X-SLOS-Auth-Mode"] = self.policy.mode.value
        response.headers["X-SLOS-Mutation-Auth"] = "enforced"
        return response


__all__ = [
    "AuthMode",
    "AuthPrincipal",
    "SlosAuthPolicy",
    "SlosSecurityMiddleware",
    "sign_hmac_assertion",
]
