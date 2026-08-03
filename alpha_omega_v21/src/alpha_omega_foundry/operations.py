from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import datetime
import hashlib
import json


@dataclass
class OperationsFabric:
    workspace: Path
    heartbeat_file: Path = field(init=False)
    learning_file: Path = field(init=False)

    def __post_init__(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.heartbeat_file = self.workspace / "heartbeat.jsonl"
        self.learning_file = self.workspace / "learning_ledger.jsonl"

    def heartbeat(self, system_id: str, state: str = "HEALTHY") -> dict:
        row = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "system_id": system_id,
            "state": state,
        }
        with self.heartbeat_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        return row

    def detect_drift(self, expected: dict, actual: dict) -> dict:
        missing = sorted(set(expected) - set(actual))
        changed = sorted(key for key in expected.keys() & actual.keys() if expected[key] != actual[key])
        unexpected = sorted(set(actual) - set(expected))
        return {
            "drift": bool(missing or changed or unexpected),
            "missing": missing,
            "changed": changed,
            "unexpected": unexpected,
        }

    def classify_failure(self, error: str) -> dict:
        text = error.lower()
        if any(token in text for token in ("permission", "unauthor", "forbidden")):
            category = "AUTHORITY"
        elif any(token in text for token in ("timeout", "temporar", "rate limit")):
            category = "TRANSIENT"
        elif any(token in text for token in ("schema", "invalid", "validation")):
            category = "CONTRACT"
        elif any(token in text for token in ("checksum", "hash", "corrupt")):
            category = "INTEGRITY"
        else:
            category = "UNKNOWN"
        return {"category": category, "retryable": category == "TRANSIENT"}

    def choose_repair(self, failure: dict) -> dict:
        mapping = {
            "TRANSIENT": "RETRY_WITH_BACKOFF",
            "AUTHORITY": "HALT_AND_RECORD_AUTHORITY_REQUIRED",
            "CONTRACT": "FORWARD_FIX_AND_RETEST",
            "INTEGRITY": "ROLLBACK_AND_REBUILD",
            "UNKNOWN": "QUARANTINE_AND_DIAGNOSE",
        }
        category = failure["category"]
        return {
            "action": mapping[category],
            "automatic": category in {"TRANSIENT", "CONTRACT", "INTEGRITY"},
        }

    def learn(self, event: dict, outcome: dict) -> dict:
        row = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "event": event,
            "outcome": outcome,
        }
        row["lesson_id"] = "LRN-" + hashlib.sha256(
            json.dumps(row, sort_keys=True).encode()
        ).hexdigest()[:12]
        with self.learning_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        return row

    def retirement_decision(self, metrics: dict) -> dict:
        triggers = []
        if metrics.get("value_score", 1) < 0.3:
            triggers.append("LOW_VALUE")
        if metrics.get("failure_rate", 0) > 0.25:
            triggers.append("HIGH_FAILURE_RATE")
        if metrics.get("replacement_ready", False):
            triggers.append("SUCCESSOR_READY")
        return {
            "retire": len(triggers) >= 2,
            "triggers": triggers,
            "requires_archive": True,
            "requires_rollback_pointer": True,
        }
