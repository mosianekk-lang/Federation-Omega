"""Immutable in-memory inbox, outbox, and receipt stores."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import HeartbeatEnvelope, Receipt, digest
from .errors import ContractError, ReplayError


@dataclass(frozen=True, slots=True)
class Outbox:
    envelopes: tuple[HeartbeatEnvelope, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.envelopes, (tuple, list)):
            raise ContractError("OUTBOX_ENVELOPES_SEQUENCE_REQUIRED")
        snapshot = tuple(self.envelopes)
        if any(not isinstance(item, HeartbeatEnvelope) for item in snapshot):
            raise ContractError("OUTBOX_ENVELOPE_ITEM_REQUIRED")
        object.__setattr__(self, "envelopes", snapshot)

    def enqueue(self, envelope: HeartbeatEnvelope) -> "Outbox":
        same_key = [item for item in self.envelopes if item.idempotency_key == envelope.idempotency_key]
        if same_key:
            if same_key[0] == envelope:
                return self
            raise ReplayError("OUTBOX_IDEMPOTENCY_CONFLICT")
        if any(item.envelope_id == envelope.envelope_id for item in self.envelopes):
            raise ReplayError("OUTBOX_ENVELOPE_ID_CONFLICT")
        return Outbox(self.envelopes + (envelope,))


@dataclass(frozen=True, slots=True)
class Inbox:
    envelopes: tuple[HeartbeatEnvelope, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.envelopes, (tuple, list)):
            raise ContractError("INBOX_ENVELOPES_SEQUENCE_REQUIRED")
        snapshot = tuple(self.envelopes)
        if any(not isinstance(item, HeartbeatEnvelope) for item in snapshot):
            raise ContractError("INBOX_ENVELOPE_ITEM_REQUIRED")
        object.__setattr__(self, "envelopes", snapshot)

    def accept(self, envelope: HeartbeatEnvelope) -> "Inbox":
        same_id = [item for item in self.envelopes if item.envelope_id == envelope.envelope_id]
        if same_id:
            if same_id[0] == envelope:
                return self
            raise ReplayError("INBOX_ENVELOPE_CONFLICT")
        if any(
            item.idempotency_key == envelope.idempotency_key and item != envelope
            for item in self.envelopes
        ):
            raise ReplayError("INBOX_IDEMPOTENCY_CONFLICT")
        return Inbox(self.envelopes + (envelope,))


@dataclass(frozen=True, slots=True)
class ReceiptStore:
    receipts: tuple[Receipt, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.receipts, (tuple, list)):
            raise ContractError("RECEIPTS_SEQUENCE_REQUIRED")
        snapshot = tuple(self.receipts)
        if any(not isinstance(item, Receipt) for item in snapshot):
            raise ContractError("RECEIPT_ITEM_REQUIRED")
        object.__setattr__(self, "receipts", snapshot)

    def record(self, receipt: Receipt) -> "ReceiptStore":
        matches = [item for item in self.receipts if item.receipt_id == receipt.receipt_id]
        if matches:
            if matches[0] == receipt:
                return self
            raise ReplayError("RECEIPT_ID_CONFLICT")
        if any(
            item.envelope_id == receipt.envelope_id
            and item.accepting_node_id == receipt.accepting_node_id
            and item.semantic_hash != receipt.semantic_hash
            for item in self.receipts
        ):
            raise ReplayError("RECEIPT_SEMANTIC_CONFLICT")
        return ReceiptStore(self.receipts + (receipt,))

    @property
    def store_hash(self) -> str:
        return digest([item.signing_body() | {"signature": item.signature} for item in self.receipts])
