from __future__ import annotations
import base64, hashlib, secrets, urllib.parse
from dataclasses import dataclass
from .contract import AUTHORIZATION_URL, CALLBACK_URI, OAuthProfile

def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

@dataclass(frozen=True)
class PKCEPair:
    verifier: str
    challenge: str

def generate_pkce() -> PKCEPair:
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return PKCEPair(verifier=verifier, challenge=challenge)

def generate_state() -> str:
    return _b64url(secrets.token_bytes(32))

def build_authorization_url(client_id: str, profile: OAuthProfile, state: str, pkce: PKCEPair) -> str:
    if not client_id or not client_id.strip():
        raise ValueError("client_id required")
    if not state:
        raise ValueError("state required")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": CALLBACK_URI,
        "scope": " ".join(sorted(profile.scopes)),
        "state": state,
        "code_challenge": pkce.challenge,
        "code_challenge_method": "S256",
    }
    return AUTHORIZATION_URL + "?" + urllib.parse.urlencode(params)
