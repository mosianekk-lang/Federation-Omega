from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    claim_key: str
    content: str
    source_ref: str
    observed_at: str
    verified: bool
    confidence: float
    priority: int = 50
    workstreams: tuple[str, ...] = ()
    missions: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    token_cost: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticMemory:
    """Truth-aware semantic memory with lineage, decay and bounded context assembly."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.records_file = self.root / "memory-records.json"
        self.events_file = self.root / "memory-events.jsonl"
        self.records: dict[str, dict[str, Any]] = {}
        self._load()

    def add(self, record: MemoryRecord) -> dict[str, Any]:
        if not 0 <= record.confidence <= 1:
            raise ValueError("confidence must be within [0,1]")
        if record.token_cost < 1:
            raise ValueError("token_cost must be positive")
        body = asdict(record)
        existing = self.records.get(record.memory_id)
        if existing and existing != body:
            raise ValueError("memory_id collision")
        self.records[record.memory_id] = body
        self._append("MEMORY_ADDED", body)
        self._persist()
        return body

    def supersession_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in self.records.values():
            for prior in row.get("supersedes", ()):
                result[prior] = row["memory_id"]
        return result

    def active_records(self) -> list[dict[str, Any]]:
        superseded = set(self.supersession_map())
        return [row for key, row in self.records.items() if key not in superseded]

    def contradiction_clusters(self) -> list[dict[str, Any]]:
        edges: set[tuple[str, str]] = set()
        for row in self.active_records():
            for other in row.get("contradicts", ()):
                if other in self.records and other != row["memory_id"]:
                    edges.add(tuple(sorted((row["memory_id"], other))))
        by_claim: dict[str, set[str]] = {}
        for left, right in edges:
            claim = self.records[left]["claim_key"]
            by_claim.setdefault(claim, set()).update((left, right))
        return [
            {"claim_key": claim, "memory_ids": sorted(ids), "status": "UNRESOLVED_CONTRADICTION"}
            for claim, ids in sorted(by_claim.items())
        ]

    @staticmethod
    def freshness(observed_at: str, now_epoch: int, half_life_seconds: int) -> float:
        point = int(datetime.fromisoformat(observed_at.replace("Z", "+00:00")).timestamp())
        age = max(0, now_epoch - point)
        return 0.5 ** (age / max(1, half_life_seconds))

    def score(self, row: dict[str, Any], *, query_terms: set[str], now_epoch: int, half_life_seconds: int) -> float:
        words = set(row["content"].lower().split()) | set(row["claim_key"].lower().split())
        relevance = len(words & query_terms) / max(1, len(query_terms))
        verified = 1.0 if row["verified"] else 0.35
        freshness = self.freshness(row["observed_at"], now_epoch, half_life_seconds)
        confidence = float(row["confidence"])
        priority = min(1.0, max(0.0, int(row["priority"]) / 100))
        contradiction_penalty = 0.55 if row.get("contradicts") else 1.0
        return round((0.35 * relevance + 0.25 * verified + 0.2 * confidence + 0.1 * freshness + 0.1 * priority) * contradiction_penalty, 6)

    def retrieve(
        self,
        query: str,
        *,
        now_epoch: int,
        token_budget: int,
        workstream_id: str | None = None,
        mission_id: str | None = None,
        half_life_seconds: int = 86400,
    ) -> dict[str, Any]:
        terms = {part for part in query.lower().split() if part}
        superseded = set(self.supersession_map())
        candidates = []
        for row in self.records.values():
            if row["memory_id"] in superseded:
                continue
            if workstream_id and workstream_id not in row.get("workstreams", ()):
                if not mission_id or mission_id not in row.get("missions", ()):
                    continue
            scored = dict(row)
            scored["retrieval_score"] = self.score(
                row, query_terms=terms, now_epoch=now_epoch, half_life_seconds=half_life_seconds
            )
            candidates.append(scored)
        candidates.sort(key=lambda item: (-item["retrieval_score"], item["token_cost"], item["memory_id"]))

        selected, used = [], 0
        for row in candidates:
            cost = int(row["token_cost"])
            if used + cost > token_budget:
                continue
            selected.append(row)
            used += cost

        contradictions = self.contradiction_clusters()
        return {
            "query": query,
            "selected": selected,
            "token_budget": token_budget,
            "tokens_used": used,
            "tokens_remaining": token_budget - used,
            "contradictions": contradictions,
            "superseded_excluded": sorted(superseded),
            "context_hash": digest(selected),
        }

    def rebuild_context(self, request: dict[str, Any]) -> dict[str, Any]:
        context = self.retrieve(**request)
        self._append("CONTEXT_REBUILT", {
            "query": request["query"],
            "context_hash": context["context_hash"],
            "selected_ids": [row["memory_id"] for row in context["selected"]],
            "tokens_used": context["tokens_used"],
        })
        return context

    def verify_lineage(self) -> bool:
        previous = "GENESIS"
        if not self.events_file.exists():
            return True
        for line in self.events_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event["previous_hash"] != previous:
                return False
            payload = {k: v for k, v in event.items() if k != "event_hash"}
            if digest(payload) != event["event_hash"]:
                return False
            previous = event["event_hash"]
        return True

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        rows = []
        if self.events_file.exists():
            rows = [json.loads(line) for line in self.events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        event = {
            "event_id": f"mem-evt-{len(rows)+1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
            "previous_hash": rows[-1]["event_hash"] if rows else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

    def _load(self) -> None:
        if self.records_file.exists():
            self.records = json.loads(self.records_file.read_text(encoding="utf-8"))

    def _persist(self) -> None:
        temp = self.records_file.with_suffix(".tmp")
        temp.write_text(json.dumps(self.records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.records_file)
