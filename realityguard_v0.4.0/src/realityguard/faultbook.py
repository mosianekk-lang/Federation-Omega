from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


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
    previous = "GENESIS"
    seen: set[str] = set()
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


class FaultBookManager:
    def __init__(self, registry_path: str | Path):
        self.path = Path(registry_path)

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "manager": "RealityGuard", "faults": [], "registry_sha256": ""}

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("UNSUPPORTED_FAULT_REGISTRY_SCHEMA")
        claimed = data.get("registry_sha256", "")
        unsigned = dict(data)
        unsigned["registry_sha256"] = ""
        if claimed != _sha(_canonical(unsigned)):
            raise ValueError("FAULT_REGISTRY_HASH_MISMATCH")
        return data

    def _write(self, data: dict[str, Any]) -> dict[str, Any]:
        data = dict(data)
        data["faults"] = sorted(data["faults"], key=lambda item: item["fault_id"])
        data["registry_sha256"] = ""
        data["registry_sha256"] = _sha(_canonical(data))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return data

    def register(self, record: FaultRecord) -> dict[str, Any]:
        if record.status not in ACTIVE_STATES | TERMINAL_STATES:
            raise ValueError("INVALID_FAULT_STATUS")
        if record.status in TERMINAL_STATES and record.open_requirements:
            raise ValueError("FALSE_FAULT_CLOSURE")
        data = self.load()
        by_id = {item["fault_id"]: item for item in data["faults"]}
        prior = by_id.get(record.fault_id)
        candidate = record.to_dict()
        if prior:
            if prior["source_sha256"] == candidate["source_sha256"]:
                return {"decision": "DEDUPLICATED", "record": prior, "registry": data}
            if candidate["event_count"] < prior["event_count"]:
                raise ValueError("FAULT_HISTORY_REGRESSION")
            if candidate["event_count"] == prior["event_count"] and candidate["chain_head"] != prior["chain_head"]:
                raise ValueError("FAULT_BRANCH_MERGE_REQUIRED")
        by_id[record.fault_id] = candidate
        data["faults"] = list(by_id.values())
        written = self._write(data)
        return {"decision": "UPDATED" if prior else "REGISTERED", "record": candidate, "registry": written}

    def register_jsonl(self, ledger_path: str | Path, **metadata: Any) -> dict[str, Any]:
        path = Path(ledger_path)
        raw = path.read_bytes()
        count, head = verify_jsonl_chain(raw.decode("utf-8").splitlines())
        record = FaultRecord(event_count=count, chain_head=head, source_sha256=_sha(raw), source_ref=str(path), **metadata)
        return self.register(record)

    def query(self, *, status: str | None = None, scope: str | None = None, fault_class: str | None = None) -> list[dict[str, Any]]:
        faults = self.load()["faults"]
        return [item for item in faults if (status is None or item["status"] == status) and (scope is None or item["scope"] == scope) and (fault_class is None or fault_class in item["fault_classes"])]

    def state(self) -> dict[str, Any]:
        data = self.load()
        active = [item for item in data["faults"] if item["status"] in ACTIVE_STATES]
        return {"manager": "RealityGuard", "schema_version": SCHEMA_VERSION, "registered_fault_books": len(data["faults"]), "active_fault_books": len(active), "registry_sha256": data["registry_sha256"], "provider_binding": "ADAPTER_REQUIRED"}
