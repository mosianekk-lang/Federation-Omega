"""Compatibility adapter for the canonical RealityGuard fault-book manager.

The central implementation lives in :mod:`realityguard.faultbooks`.  This
module preserves the earlier FaultBookManager/FaultRecord API admitted on the
Federation main branch without creating a second registry engine.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .faultbooks import FaultbookManager, sha256_file


SCHEMA_VERSION = "realityguard.fault-manager.v1"
ACTIVE_STATES = {"OPEN", "SYSTEMIC_OPEN", "PARTIAL_CHECKPOINTED", "BLOCKED_WITH_ROUTE"}
TERMINAL_STATES = {"PROVEN_CLOSED", "SUPERSEDED"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class FaultRecord:
    fault_id: str
    title: str
    scope: str
    status: str
    source_kind: str
    source_ref: str
    source_sha256: str
    event_count: int
    chain_head: str
    owner_authority: str
    truth_state: str
    lifecycle_state: str
    registered_at: str
    fault_classes: tuple[str, ...] = ()
    open_requirements: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("fault_classes", "open_requirements", "supersedes"):
            value[key] = list(value[key])
        return value


def verify_jsonl_chain(lines: Iterable[str]) -> tuple[int, str]:
    events = [json.loads(line) for line in lines if line.strip()]
    if not events:
        raise ValueError("EMPTY_FAULT_LEDGER")
    previous, seen = "GENESIS", set()
    for event in events:
        event_id = str(event.get("event_id", ""))
        if not event_id or event_id in seen:
            raise ValueError("INVALID_OR_DUPLICATE_EVENT_ID")
        seen.add(event_id)
        if event.get("prev_hash") != previous:
            raise ValueError(f"CHAIN_PARENT_MISMATCH:{event_id}")
        payload = {key: value for key, value in event.items() if key not in {"prev_hash", "event_hash"}}
        expected = _sha(previous + "\n" + _canonical(payload))
        if event.get("event_hash") != expected:
            raise ValueError(f"CHAIN_HASH_MISMATCH:{event_id}")
        previous = expected
    return len(events), previous


class FaultBookManager(FaultbookManager):
    """Backward-compatible API backed by the one central manager registry."""

    def register(self, record: FaultRecord) -> dict[str, Any]:
        if record.status not in ACTIVE_STATES | TERMINAL_STATES:
            raise ValueError("INVALID_FAULT_STATUS")
        if record.status in TERMINAL_STATES and record.open_requirements:
            raise ValueError("FALSE_FAULT_CLOSURE")
        data = self._read()
        records = data.setdefault("records", [])
        by_id = {item["fault_id"]: item for item in records}
        prior, candidate = by_id.get(record.fault_id), record.to_dict()
        if prior:
            if prior["source_sha256"] == candidate["source_sha256"]:
                return {"decision": "DEDUPLICATED", "record": prior, "registry": data}
            if candidate["event_count"] < prior["event_count"]:
                raise ValueError("FAULT_HISTORY_REGRESSION")
            if candidate["event_count"] == prior["event_count"] and candidate["chain_head"] != prior["chain_head"]:
                raise ValueError("FAULT_BRANCH_MERGE_REQUIRED")
        by_id[record.fault_id] = candidate
        data["records"] = sorted(by_id.values(), key=lambda item: item["fault_id"])
        self._atomic_write(data)
        return {"decision": "UPDATED" if prior else "REGISTERED", "record": candidate, "registry": data}

    def register_jsonl(self, ledger_path: str | Path, **metadata: Any) -> dict[str, Any]:
        path = Path(ledger_path)
        raw = path.read_bytes()
        count, head = verify_jsonl_chain(raw.decode("utf-8").splitlines())
        return self.register(FaultRecord(event_count=count, chain_head=head, source_sha256=sha256_file(path), source_ref=str(path), **metadata))

    def query(self, *, status: str | None = None, scope: str | None = None, fault_class: str | None = None) -> list[dict[str, Any]]:
        records = self._read().get("records", [])
        return [item for item in records if (status is None or item["status"] == status) and
                (scope is None or item["scope"] == scope) and
                (fault_class is None or fault_class in item["fault_classes"])]

    def state(self) -> dict[str, Any]:
        records = self._read().get("records", [])
        active = [item for item in records if item["status"] in ACTIVE_STATES]
        return {"manager": "RealityGuard", "schema_version": self.schema_version,
                "registered_fault_books": len(records), "active_fault_books": len(active),
                "provider_binding": "ADAPTER_REQUIRED"}

