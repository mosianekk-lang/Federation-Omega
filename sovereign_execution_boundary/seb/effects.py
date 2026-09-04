from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from typing import Any, Callable


class EffectRejected(RuntimeError):
    pass


@dataclass(frozen=True)
class EffectReceipt:
    effect_id: str
    idempotency_key: str
    committed: bool
    readback: Any


class EffectBroker:
    """Fenced, idempotent two-phase effect broker."""

    def __init__(self, external_effects_enabled: bool = False):
        self.external_effects_enabled = external_effects_enabled
        self._receipts: dict[str, EffectReceipt] = {}
        self._lock = RLock()

    @staticmethod
    def key(mission_id: str, action: str, payload: dict[str, Any]) -> str:
        body = json.dumps([mission_id, action, payload], sort_keys=True, separators=(",", ":"))
        return sha256(body.encode()).hexdigest()

    def execute(self, *, mission_id: str, action: str, payload: dict[str, Any],
                operation: Callable[[], Any], verify: Callable[[Any], bool],
                external: bool = True) -> EffectReceipt:
        key = self.key(mission_id, action, payload)
        with self._lock:
            if key in self._receipts:
                return self._receipts[key]
            if external and not self.external_effects_enabled:
                raise EffectRejected("external effects disabled")
            result = operation()
            if not verify(result):
                raise EffectRejected("semantic readback failed")
            receipt = EffectReceipt(key[:16], key, True, result)
            self._receipts[key] = receipt
            return receipt

