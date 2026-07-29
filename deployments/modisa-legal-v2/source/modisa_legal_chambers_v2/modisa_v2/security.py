from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from .config import Settings, get_settings
from .schemas import AuthPrincipal


SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(password|passwd|api[_ -]?key|secret|token)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


@dataclass
class AccessRequirement:
    roles: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()


class AuthService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def decode(self, token: str) -> AuthPrincipal:
        if not self.settings.jwt_secret:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        try:
            payload = jwt.decode(token, self.settings.jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        return AuthPrincipal(
            subject=str(payload.get("sub", "")),
            roles=list(payload.get("roles", [])),
            matter_ids=list(payload.get("matter_ids", [])),
            scopes=list(payload.get("scopes", [])),
        )

    def principal_from_header(self, authorization: str | None) -> AuthPrincipal:
        if self.settings.auth_disabled_dev:
            return AuthPrincipal(
                subject="dev-owner",
                roles=["OWNER", "COUNSEL", "AUDITOR"],
                matter_ids=["*"],
                scopes=["*"],
            )
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
        return self.decode(authorization.removeprefix("Bearer ").strip())

    @staticmethod
    def enforce(
        principal: AuthPrincipal,
        requirement: AccessRequirement,
        matter_id: str | None = None,
    ) -> None:
        if requirement.roles and not requirement.roles.intersection(principal.roles):
            raise HTTPException(status_code=403, detail="Role not authorised")
        if requirement.scopes and "*" not in principal.scopes and not requirement.scopes.issubset(principal.scopes):
            raise HTTPException(status_code=403, detail="Scope not authorised")
        if matter_id and "*" not in principal.matter_ids and matter_id not in principal.matter_ids:
            raise HTTPException(status_code=403, detail="Matter access denied")


async def current_principal(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthPrincipal:
    return AuthService(settings).principal_from_header(authorization)


class SlidingWindowRateLimiter:
    """Local-process limiter. Production should replace this with Redis or gateway controls."""

    def __init__(self, limit: int = 120, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        queue = self._events[key]
        while queue and queue[0] < now - self.window_seconds:
            queue.popleft()
        if len(queue) >= self.limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        queue.append(now)
