from __future__ import annotations
from datetime import timezone
import hashlib
import json
from typing import Any
from .schemas import SecurityEvent

# Content-like keys are deliberately excluded from the default defensive telemetry plane.
_CONTENT_KEYS = {
    "message", "message_body", "email_body", "photo", "image", "audio", "video",
    "password", "credential", "token", "cookie", "session_cookie", "private_key",
    "contact_list", "sms_body", "call_audio", "clipboard",
}
MAX_NORMALIZED_ATTRIBUTES_BYTES = 32768


def _safe_value(key: str, value: Any) -> Any:
    if key.lower() in _CONTENT_KEYS:
        return "[minimized]"
    if isinstance(value, str) and len(value) > 512:
        return value[:512] + "…"
    if isinstance(value, dict):
        return {str(k): _safe_value(str(k), v) for k, v in list(value.items())[:64]}
    if isinstance(value, list):
        return [_safe_value(key, v) for v in value[:100]]
    return value


def normalize_event(event: SecurityEvent) -> SecurityEvent:
    if not event.consent:
        raise ValueError("AEGIS accepts only authorized/consensual defensive telemetry")
    safe_attrs = {str(k): _safe_value(str(k), v) for k, v in event.attributes.items()}
    encoded = json.dumps(safe_attrs, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_NORMALIZED_ATTRIBUTES_BYTES:
        raise ValueError("AEGIS normalized attributes exceed 32 KiB safety bound")
    return event.model_copy(update={
        "attributes": safe_attrs,
        "timestamp": event.timestamp.astimezone(timezone.utc),
        "source": event.source.strip().lower(),
    })


def stable_subject_ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
