from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from .behavioral_convergence import (
    BehavioralConvergenceEngine,
    BehavioralOrigin,
    BehavioralProofReceipt,
    BehavioralEvidenceKind,
)
from .models import FederationEvent


BINDING_SCHEMA = "failure-win.behavioral-binding.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class BehavioralStoreConflict(ValueError):
    """Raised when a durable record id is reused with different content."""


class BehavioralRecordStore(Protocol):
    """Append-only persistence contract for behavioral events and proof receipts."""

    @property
    def kind(self) -> str: ...

    def append(self, record: dict[str, Any]) -> bool: ...

    def records(self) -> tuple[dict[str, Any], ...]: ...


class InMemoryBehavioralRecordStore:
    """Deterministic store for tests and explicitly non-durable runtimes."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []
        self._hashes: dict[str, str] = {}

    @property
    def kind(self) -> str:
        return "IN_MEMORY_NON_DURABLE"

    def append(self, record: dict[str, Any]) -> bool:
        record_id = str(record["record_id"])
        payload_hash = str(record["payload_sha256"])
        prior = self._hashes.get(record_id)
        if prior is not None:
            if prior != payload_hash:
                raise BehavioralStoreConflict(f"STORE_RECORD_CONFLICT:{record_id}")
            return False
        self._records.append(json.loads(_canonical_json(record)))
        self._hashes[record_id] = payload_hash
        return True

    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(_canonical_json(item)) for item in self._records)


class JsonlBehavioralRecordStore:
    """Restart-safe local append-only store with fsync and payload-hash validation.

    This is a provider-neutral runtime primitive. A remote/provider store remains a
    separate adapter and authority gate; this class does not create network effects.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[dict[str, Any]] = []
        self._hashes: dict[str, str] = {}
        if self.path.exists():
            for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                self._validate_record(record, line_number=line_number)
                record_id = str(record["record_id"])
                payload_hash = str(record["payload_sha256"])
                prior = self._hashes.get(record_id)
                if prior is not None and prior != payload_hash:
                    raise BehavioralStoreConflict(f"STORE_RECORD_CONFLICT:{record_id}")
                if prior is None:
                    self._records.append(record)
                    self._hashes[record_id] = payload_hash

    @property
    def kind(self) -> str:
        return "JSONL_LOCAL_DURABLE"

    @staticmethod
    def _validate_record(record: dict[str, Any], *, line_number: int = 0) -> None:
        if record.get("schema") != BINDING_SCHEMA:
            raise ValueError(f"BEHAVIOR_STORE_SCHEMA_MISMATCH:{line_number}")
        payload = record.get("payload")
        expected = _sha256(payload)
        if record.get("payload_sha256") != expected:
            raise ValueError(f"BEHAVIOR_STORE_PAYLOAD_HASH_MISMATCH:{line_number}")
        if not str(record.get("record_id", "")).strip():
            raise ValueError(f"BEHAVIOR_STORE_RECORD_ID_MISSING:{line_number}")

    def append(self, record: dict[str, Any]) -> bool:
        self._validate_record(record)
        record_id = str(record["record_id"])
        payload_hash = str(record["payload_sha256"])
        prior = self._hashes.get(record_id)
        if prior is not None:
            if prior != payload_hash:
                raise BehavioralStoreConflict(f"STORE_RECORD_CONFLICT:{record_id}")
            return False
        rendered = _canonical_json(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._records.append(json.loads(rendered))
        self._hashes[record_id] = payload_hash
        return True

    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(_canonical_json(item)) for item in self._records)


class BehavioralConvergenceBinding:
    """Bind Federation events to empirical Failure-Win v2 with replayable state."""

    def __init__(
        self,
        engine: BehavioralConvergenceEngine,
        *,
        store: BehavioralRecordStore | None = None,
        replay: bool = True,
    ) -> None:
        self.engine = engine
        self.store: BehavioralRecordStore = store or InMemoryBehavioralRecordStore()
        self.replayed_records = 0
        if replay:
            self.replayed_records = self.replay()

    @staticmethod
    def _record(record_id: str, record_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": BINDING_SCHEMA,
            "record_id": record_id,
            "record_type": record_type,
            "payload_sha256": _sha256(payload),
            "payload": payload,
        }

    @staticmethod
    def _event_payload(event: FederationEvent) -> dict[str, Any]:
        return {
            "event": asdict(event),
            "origin": str(event.payload.get("behavioral_origin", "UNKNOWN")).upper(),
        }

    @staticmethod
    def _event_from_payload(payload: dict[str, Any]) -> tuple[FederationEvent, str]:
        raw = dict(payload["event"])
        raw["affected_state_keys"] = tuple(raw.get("affected_state_keys", ()) or ())
        raw["affected_mission_nodes"] = tuple(raw.get("affected_mission_nodes", ()) or ())
        event = FederationEvent(**raw)
        return event, str(payload.get("origin", "UNKNOWN"))

    @staticmethod
    def _proof_payload(fingerprint: str, receipt: BehavioralProofReceipt) -> dict[str, Any]:
        return {
            "fingerprint": fingerprint,
            "receipt": {
                **asdict(receipt),
                "kind": receipt.kind.value,
                "origin": receipt.origin.value,
            },
        }

    @staticmethod
    def _proof_from_payload(payload: dict[str, Any]) -> tuple[str, BehavioralProofReceipt]:
        raw = dict(payload["receipt"])
        raw["kind"] = BehavioralEvidenceKind(str(raw["kind"]))
        raw["origin"] = BehavioralOrigin(str(raw["origin"]))
        raw["proof_refs"] = tuple(raw.get("proof_refs", ()) or ())
        return str(payload["fingerprint"]), BehavioralProofReceipt(**raw)

    def replay(self) -> int:
        if self.engine.ledger_head != "GENESIS":
            raise ValueError("BEHAVIOR_REPLAY_REQUIRES_EMPTY_ENGINE")
        count = 0
        for raw in self.store.records():
            if raw.get("schema") != BINDING_SCHEMA:
                raise ValueError("BEHAVIOR_STORE_SCHEMA_MISMATCH")
            if raw.get("payload_sha256") != _sha256(raw.get("payload")):
                raise ValueError("BEHAVIOR_STORE_PAYLOAD_HASH_MISMATCH")
            record_type = str(raw.get("record_type", ""))
            if record_type == "FEDERATION_EVENT":
                event, origin = self._event_from_payload(raw["payload"])
                self.engine.observe_federation_event(event, origin=origin)
            elif record_type == "PROOF_RECEIPT":
                fingerprint, receipt = self._proof_from_payload(raw["payload"])
                self.engine.record_proof(fingerprint, receipt)
            else:
                raise ValueError(f"UNKNOWN_BEHAVIOR_STORE_RECORD_TYPE:{record_type}")
            count += 1
        return count

    def handle_event(self, event: FederationEvent) -> dict[str, Any]:
        result = self.engine.observe_federation_event(event)
        record = self._record(event.event_id, "FEDERATION_EVENT", self._event_payload(event))
        stored = self.store.append(record)
        payload = result.to_dict()
        payload["persistence"] = {
            "store_kind": self.store.kind,
            "record_stored": stored,
            "record_id": event.event_id,
            "payload_sha256": record["payload_sha256"],
            "replayed_records": self.replayed_records,
        }
        return payload

    def record_proof(self, fingerprint: str, receipt: BehavioralProofReceipt) -> dict[str, Any]:
        result = self.engine.record_proof(fingerprint, receipt)
        record = self._record(receipt.event_id, "PROOF_RECEIPT", self._proof_payload(fingerprint, receipt))
        stored = self.store.append(record)
        payload = result.to_dict()
        payload["persistence"] = {
            "store_kind": self.store.kind,
            "record_stored": stored,
            "record_id": receipt.event_id,
            "payload_sha256": record["payload_sha256"],
            "replayed_records": self.replayed_records,
        }
        return payload
