"""BCO-Prime append-only local flight recorder v3.

The recorder is deliberately local and provider-free.  It records supplied
mission events in a hash-chained JSONL ledger, verifies tamper evidence,
creates bounded checkpoints, and replays events into deterministic summaries.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "BCO_PRIME_FLIGHT_RECORDER_V3"
VERSION = "3.0.0"
MAX_LEDGER_BYTES = 16 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024
MAX_EVENTS = 100_000
FAILURE_TAXONOMY = (
    "NONE",
    "VALIDATION",
    "AUTHORITY",
    "DEPENDENCY",
    "TIMEOUT",
    "RATE_LIMIT",
    "TRANSPORT",
    "SCHEMA_DRIFT",
    "SEMANTIC_FALSE_SUCCESS",
    "INTEGRITY",
    "CANCELLED",
    "UNKNOWN",
)
EVENT_STATUSES = (
    "CREATED",
    "QUEUED",
    "PROCESSING",
    "CHECKPOINTED",
    "COMPLETED",
    "FAILED",
    "RETRIED",
    "CANCELLED",
    "QUARANTINED",
    "ARCHIVED",
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FORBIDDEN_EFFECT_KEYS = {
    "external_effect",
    "provider_effect_authorized",
    "authority_expansion",
    "manual_user_tasks",
    "manualusertasks",
}
_NORMALIZED_FORBIDDEN_EFFECT_KEYS = {
    re.sub(r"[^a-z0-9]", "", key.lower()) for key in _FORBIDDEN_EFFECT_KEYS
}


class FlightRecorderError(ValueError):
    """Raised when a ledger or event violates the recorder contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _normalize(value: Any, path: str = "$") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise FlightRecorderError(f"non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise FlightRecorderError(f"non-string key at {path}")
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized_key in _NORMALIZED_FORBIDDEN_EFFECT_KEYS and value[key] not in (None, False, 0, "", [], {}):
                raise FlightRecorderError(f"external effect rejected at {path}.{key}")
            result[key] = _normalize(value[key], f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_normalize(item, f"{path}[]") for item in value]
    raise FlightRecorderError(f"unsupported value at {path}: {type(value).__name__}")


def _identifier(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise FlightRecorderError(f"invalid {field}")
    return value


def _safe_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise FlightRecorderError("path must be non-empty and relative")
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise FlightRecorderError("path traversal rejected")
    return candidate


class FlightRecorder:
    """Append, verify, checkpoint and replay one bounded local ledger."""

    def __init__(self, root: Path, ledger_name: str = "flight_events_v3.jsonl") -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = _safe_path(self.root, ledger_name)
        self.lock_path = _safe_path(self.root, ledger_name + ".lock")

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        if self.ledger_path.is_symlink() or not self.ledger_path.is_file():
            raise FlightRecorderError("ledger must be a regular file")
        if self.ledger_path.stat().st_size > MAX_LEDGER_BYTES:
            raise FlightRecorderError("ledger size limit exceeded")
        events: list[dict[str, Any]] = []
        with self.ledger_path.open("rb") as handle:
            for index, raw in enumerate(handle, 1):
                if index > MAX_EVENTS:
                    raise FlightRecorderError("event count limit exceeded")
                if len(raw) > MAX_LINE_BYTES:
                    raise FlightRecorderError(f"line {index} exceeds size limit")
                try:
                    item = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise FlightRecorderError(f"invalid JSONL at line {index}") from exc
                if not isinstance(item, dict):
                    raise FlightRecorderError(f"non-object event at line {index}")
                events.append(item)
        return events

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        clean = _normalize(dict(event))
        lock_descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
            events = self._read_events()
            verification = verify_events(events)
            if not verification["valid"]:
                raise FlightRecorderError("existing ledger failed verification")
            event_id = _identifier(clean.get("event_id"), "event_id")
            if event_id in {item["event_id"] for item in events}:
                raise FlightRecorderError("duplicate event_id")
            mission_id = _identifier(clean.get("mission_id"), "mission_id")
            correlation_id = _identifier(clean.get("correlation_id"), "correlation_id")
            parent_id = _identifier(clean.get("parent_id"), "parent_id", optional=True)
            kind = _identifier(clean.get("kind"), "kind")
            status = str(clean.get("status", "")).upper()
            if status not in EVENT_STATUSES:
                raise FlightRecorderError("unknown status")
            failure = str(clean.get("failure_type", "NONE")).upper()
            if failure not in FAILURE_TAXONOMY:
                raise FlightRecorderError("unknown failure_type")
            started_ns = clean.get("started_ns")
            ended_ns = clean.get("ended_ns")
            if type(started_ns) is not int or type(ended_ns) is not int:
                raise FlightRecorderError("started_ns and ended_ns must be integers")
            if started_ns < 0 or ended_ns < started_ns:
                raise FlightRecorderError("invalid monotonic timing")
            payload = clean.get("payload", {})
            if not isinstance(payload, Mapping):
                raise FlightRecorderError("payload must be an object")
            record: dict[str, Any] = {
                "schema": SCHEMA,
                "version": VERSION,
                "sequence": len(events) + 1,
                "event_id": event_id,
                "mission_id": mission_id,
                "correlation_id": correlation_id,
                "parent_id": parent_id,
                "kind": kind,
                "status": status,
                "failure_type": failure,
                "started_ns": started_ns,
                "ended_ns": ended_ns,
                "latency_ms": round((ended_ns - started_ns) / 1_000_000, 6),
                "payload": _normalize(dict(payload), "$.payload"),
                "previous_hash": events[-1]["event_hash"] if events else "GENESIS",
            }
            record["event_hash"] = digest(record)
            encoded = (canonical_json(record) + "\n").encode("utf-8")
            if len(encoded) > MAX_LINE_BYTES:
                raise FlightRecorderError("event exceeds line size limit")
            current_size = self.ledger_path.stat().st_size if self.ledger_path.exists() else 0
            if current_size + len(encoded) > MAX_LEDGER_BYTES:
                raise FlightRecorderError("ledger size limit exceeded")
            descriptor = os.open(self.ledger_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                if os.write(descriptor, encoded) != len(encoded):
                    raise FlightRecorderError("partial ledger write")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            os.close(lock_descriptor)
        return record

    def verify(self) -> dict[str, Any]:
        result = verify_events(self._read_events())
        result["ledger"] = str(self.ledger_path)
        result["ledger_sha256"] = file_sha256(self.ledger_path) if self.ledger_path.exists() else hashlib.sha256(b"").hexdigest()
        return result

    def replay(self) -> dict[str, Any]:
        return replay_events(self._read_events())

    def checkpoint(self, relative_path: str = "flight_checkpoint_v3.json") -> dict[str, Any]:
        target = _safe_path(self.root, relative_path)
        verification = self.verify()
        if not verification["valid"]:
            raise FlightRecorderError("cannot checkpoint invalid ledger")
        events = self._read_events()
        checkpoint = {
            "schema": "BCO_PRIME_FLIGHT_CHECKPOINT_V3",
            "sequence": len(events),
            "last_event_hash": events[-1]["event_hash"] if events else "GENESIS",
            "ledger_sha256": verification["ledger_sha256"],
            "event_count": len(events),
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        checkpoint["checkpoint_sha256"] = digest(checkpoint)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(canonical_json(checkpoint) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        return checkpoint


def verify_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    previous = "GENESIS"
    seen: set[str] = set()
    for index, raw in enumerate(events, 1):
        event = dict(raw)
        if event.get("sequence") != index:
            failures.append(f"SEQUENCE_GAP:{index}")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or event_id in seen:
            failures.append(f"EVENT_ID_INVALID_OR_DUPLICATE:{index}")
        else:
            seen.add(event_id)
        if event.get("previous_hash") != previous:
            failures.append(f"PREVIOUS_HASH_MISMATCH:{index}")
        claimed = event.pop("event_hash", None)
        observed = digest(event)
        if claimed != observed:
            failures.append(f"EVENT_HASH_MISMATCH:{index}")
        previous = str(claimed)
    return {
        "schema": "BCO_PRIME_FLIGHT_VERIFICATION_V3",
        "valid": not failures,
        "event_count": len(events),
        "last_event_hash": previous,
        "failures": failures,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }


def replay_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    verification = verify_events(events)
    if not verification["valid"]:
        raise FlightRecorderError("replay rejected: ledger verification failed")
    ids = {str(item["event_id"]) for item in events}
    drift: list[str] = []
    status_counts: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    mission_counts: dict[str, int] = {}
    total_latency = 0.0
    for item in events:
        parent = item.get("parent_id")
        if parent is not None and parent not in ids:
            drift.append(f"MISSING_PARENT:{item['event_id']}:{parent}")
        status = str(item.get("status"))
        failure = str(item.get("failure_type"))
        mission = str(item.get("mission_id"))
        status_counts[status] = status_counts.get(status, 0) + 1
        failure_counts[failure] = failure_counts.get(failure, 0) + 1
        mission_counts[mission] = mission_counts.get(mission, 0) + 1
        total_latency += float(item.get("latency_ms", 0))
    result = {
        "schema": "BCO_PRIME_FLIGHT_REPLAY_V3",
        "verification": verification,
        "status_counts": dict(sorted(status_counts.items())),
        "failure_counts": dict(sorted(failure_counts.items())),
        "mission_counts": dict(sorted(mission_counts.items())),
        "total_latency_ms": round(total_latency, 6),
        "drift": sorted(drift),
        "drift_state": "DRIFT_DETECTED" if drift else "NO_DRIFT_DETECTED",
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["replay_sha256"] = digest(result)
    return result


def manifest() -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "failure_taxonomy": list(FAILURE_TAXONOMY),
        "event_statuses": list(EVENT_STATUSES),
        "append_only": True,
        "hash_chained": True,
        "provider_effect_authorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["manifest_sha256"] = digest(result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=SCHEMA)
    parser.add_argument("--root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    append = sub.add_parser("append")
    append.add_argument("--event-json", required=True)
    sub.add_parser("verify")
    sub.add_parser("replay")
    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--path", default="flight_checkpoint_v3.json")
    sub.add_parser("manifest")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    recorder = FlightRecorder(Path(args.root))
    if args.command == "append":
        output = recorder.append(json.loads(args.event_json))
    elif args.command == "verify":
        output = recorder.verify()
    elif args.command == "replay":
        output = recorder.replay()
    elif args.command == "checkpoint":
        output = recorder.checkpoint(args.path)
    else:
        output = manifest()
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FAILURE_TAXONOMY",
    "FlightRecorder",
    "FlightRecorderError",
    "manifest",
    "replay_events",
    "verify_events",
]
