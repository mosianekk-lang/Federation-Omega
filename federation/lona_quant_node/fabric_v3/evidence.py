"""Hash-chained evidence receipts for the Quant Evidence Fabric v3."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping


@dataclass(frozen=True)
class EvidenceReceipt:
    experiment_id: str
    event_type: str
    payload: Mapping[str, Any]
    previous_hash: str = "GENESIS"

    def canonical_payload(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def receipt_hash(self) -> str:
        return hashlib.sha256(self.canonical_payload().encode("utf-8")).hexdigest()


def verify_chain(receipts: list[EvidenceReceipt]) -> bool:
    expected = "GENESIS"
    for receipt in receipts:
        if receipt.previous_hash != expected:
            return False
        expected = receipt.receipt_hash()
    return True
