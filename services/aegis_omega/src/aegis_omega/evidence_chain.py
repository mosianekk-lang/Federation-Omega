from __future__ import annotations

import hashlib
import json
from typing import Sequence

from .schemas import SealedEvent


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compile_evidence_chain(events: Sequence[SealedEvent]) -> list[dict]:
    chain: list[dict] = []
    previous = "GENESIS"
    for seq, sealed in enumerate(events, start=1):
        body = {
            "seq": seq,
            "event_id": sealed.event.event_id,
            "event_digest_sha256": sealed.digest_sha256,
            "signature_hmac_sha256": sealed.signature_hmac_sha256,
            "provenance_key_id": sealed.provenance_key_id,
            "previous_hash": previous,
        }
        entry_hash = _hash(body)
        chain.append({**body, "entry_hash": entry_hash})
        previous = entry_hash
    return chain


def verify_evidence_chain(events: Sequence[SealedEvent], chain: Sequence[dict]) -> bool:
    if len(events) != len(chain):
        return False
    expected = compile_evidence_chain(events)
    return expected == list(chain)
