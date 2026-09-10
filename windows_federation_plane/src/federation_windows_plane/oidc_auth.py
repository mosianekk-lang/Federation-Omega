from __future__ import annotations

import asyncio
import time
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken


class OIDCTokenVerifier:
    """Strict JWT verifier for an external OAuth 2.1/OIDC authorization server."""

    def __init__(self, *, issuer: str, audience: str, jwks_url: str) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience.rstrip("/")
        self._jwks = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def _verify(self, token: str) -> AccessToken | None:
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            )
            expires = int(claims["exp"])
            if expires <= int(time.time()):
                return None
            raw_scopes = claims.get("scope", claims.get("scp", ""))
            if isinstance(raw_scopes, str):
                scopes = [item for item in raw_scopes.split() if item]
            elif isinstance(raw_scopes, list):
                scopes = [str(item) for item in raw_scopes]
            else:
                scopes = []
            client_id = str(claims.get("client_id") or claims.get("azp") or "")
            if not client_id:
                return None
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=expires,
                resource=self.audience,
                subject=str(claims["sub"]),
                claims=claims,
            )
        except (jwt.PyJWTError, ValueError, KeyError):
            return None

    async def verify_token(self, token: str) -> AccessToken | None:
        return await asyncio.to_thread(self._verify, token)
