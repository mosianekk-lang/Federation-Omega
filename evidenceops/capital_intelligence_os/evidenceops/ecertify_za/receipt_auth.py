from __future__ import annotations
import hashlib,hmac,json,time
from dataclasses import dataclass
from datetime import datetime,timezone
from .replay import ReplayGuard,SQLiteReplayGuard

@dataclass(frozen=True)
class ReceiptEnvelope:
    provider:str
    payload:dict
    signature_hex:str
    key_id:str

@dataclass(frozen=True)
class AuthenticatedReceipt:
    provider:str
    payload:dict
    key_id:str
    payload_sha256:str

# Backward-compatible local reference alias. Production must inject a distributed ReplayGuard.
ReplayStore=SQLiteReplayGuard

class HMACReceiptAuthenticator:
    """Reference signed-receipt authenticator.

    Provider adapters may use provider-native JWS/mTLS. The replay guard is injected
    so production can bind an atomic distributed implementation without changing
    identity policy.
    """
    def __init__(self,provider_secrets:dict[str,bytes],allowed_key_ids:dict[str,set[str]]|None=None,max_age_seconds:int=300,replay_store:ReplayGuard|None=None):
        self.provider_secrets=dict(provider_secrets);self.allowed_key_ids=allowed_key_ids or {};self.max_age_seconds=max_age_seconds;self.replay_store=replay_store or SQLiteReplayGuard()
    @staticmethod
    def canonical_payload(payload:dict)->bytes:return json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    @staticmethod
    def _parse_epoch(value:str)->int:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    def verify(self,envelope:ReceiptEnvelope,now:int|None=None)->AuthenticatedReceipt:
        if envelope.provider not in self.provider_secrets:raise ValueError("PROVIDER_NOT_ALLOWLISTED")
        allowed=self.allowed_key_ids.get(envelope.provider)
        if allowed is not None and envelope.key_id not in allowed:raise ValueError("KEY_ID_NOT_ALLOWED")
        payload=self.canonical_payload(envelope.payload)
        expected=hmac.new(self.provider_secrets[envelope.provider],payload,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,envelope.signature_hex.lower()):raise ValueError("SIGNATURE_INVALID")
        tx=str(envelope.payload.get("transaction_id","")).strip();issued=str(envelope.payload.get("issued_at","")).strip()
        if not tx or not issued:raise ValueError("RECEIPT_REQUIRED_FIELDS_MISSING")
        current=int(time.time()) if now is None else int(now);issued_epoch=self._parse_epoch(issued)
        if issued_epoch>current+60:raise ValueError("RECEIPT_ISSUED_IN_FUTURE")
        if current-issued_epoch>self.max_age_seconds:raise ValueError("RECEIPT_EXPIRED")
        if not self.replay_store.claim(envelope.provider,tx):raise ValueError("RECEIPT_REPLAY_DETECTED")
        return AuthenticatedReceipt(envelope.provider,dict(envelope.payload),envelope.key_id,hashlib.sha256(payload).hexdigest())
