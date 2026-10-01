from __future__ import annotations
import json, urllib.parse, urllib.request
from dataclasses import dataclass
from typing import Any, Mapping
from .contract import API_BASE, CALLBACK_URI, READ_ENDPOINTS, TOKEN_URL
from .authority import ActionAuthority, validate_action

class OAuthProtocolError(RuntimeError):
    pass

@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scope: str | None
    token_type: str | None

def parse_callback_url(url: str, expected_state: str) -> str:
    p = urllib.parse.urlparse(url)
    cb = urllib.parse.urlparse(CALLBACK_URI)
    if (p.scheme, p.hostname, p.port, p.path) != (cb.scheme, cb.hostname, cb.port, cb.path):
        raise OAuthProtocolError("callback URI mismatch")
    q = urllib.parse.parse_qs(p.query)
    if q.get("state", [None])[0] != expected_state:
        raise OAuthProtocolError("state mismatch")
    if "error" in q:
        raise OAuthProtocolError(q["error"][0])
    code = q.get("code", [None])[0]
    if not code:
        raise OAuthProtocolError("authorization code missing")
    return code

def token_request_body(client_id: str, code: str, verifier: str) -> bytes:
    if not all([client_id, code, verifier]):
        raise ValueError("client_id, code and verifier required")
    return urllib.parse.urlencode({
        "code": code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": CALLBACK_URI,
        "code_verifier": verifier,
    }).encode("ascii")

def refresh_request_body(client_id: str, refresh_token: str) -> bytes:
    if not client_id or not refresh_token:
        raise ValueError("client_id and refresh_token required")
    return urllib.parse.urlencode({
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "client_id": client_id,
    }).encode("ascii")

def endpoint(name: str, *, user_id: str | None = None) -> str:
    path = READ_ENDPOINTS[name]
    if "{id}" in path:
        if not user_id:
            raise ValueError("user_id required")
        path = path.format(id=urllib.parse.quote(user_id, safe=""))
    return API_BASE + path

def assert_mutation_allowed(authority: ActionAuthority) -> None:
    validate_action(authority)
