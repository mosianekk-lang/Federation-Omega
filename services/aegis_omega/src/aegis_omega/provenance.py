from __future__ import annotations
from datetime import datetime, timezone
import hashlib, hmac, json
from .schemas import SecurityEvent, SealedEvent


def canonical_json(event: SecurityEvent) -> bytes:
    payload = event.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seal_event(event: SecurityEvent, secret: str, key_id: str = "default") -> SealedEvent:
    raw = canonical_json(event)
    digest = hashlib.sha256(raw).hexdigest()
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return SealedEvent(event=event,digest_sha256=digest,signature_hmac_sha256=signature,provenance_key_id=key_id,normalized_at=datetime.now(timezone.utc))


def verify_event(sealed: SealedEvent, secret: str) -> bool:
    raw = canonical_json(sealed.event)
    digest_ok = hmac.compare_digest(hashlib.sha256(raw).hexdigest(), sealed.digest_sha256)
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return digest_ok and hmac.compare_digest(sig, sealed.signature_hmac_sha256)


def verify_event_with_keyring(sealed: SealedEvent, keyring: dict[str, str]) -> bool:
    secret = keyring.get(sealed.provenance_key_id)
    return bool(secret) and verify_event(sealed, secret)
