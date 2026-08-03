from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from live_provider_expansion import contains_secret_material, digest, parse_utc, valid_sha256


ALLOWED_BLOCK_REASONS = {
    "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
    "PROVIDER_BLOCKED_WIF_INVALID_TARGET",
    "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
}


@dataclass(frozen=True)
class ProviderBlockEvidence:
    block_id: str
    provider: str
    reason: str
    provider_native: bool
    observed_at: str
    locator: str
    attempted_scope: tuple[str, ...]
    mutation_performed: bool
    content_sha256: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderBlockLedger:
    """Append-only proof that a provider route is blocked before mutation."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.root / "provider-block-ledger.jsonl"
        self.state_file = self.root / "provider-block-state.json"
        self.decisions: dict[str, dict[str, Any]] = {}
        self.by_provider: dict[str, list[str]] = {}
        self._replay()

    def record(self, evidence: ProviderBlockEvidence, *, now: str) -> dict[str, Any]:
        evidence_hash = digest(asdict(evidence))
        existing = self.decisions.get(evidence.block_id)
        if existing:
            if existing["evidence_hash"] == evidence_hash:
                return existing
            conflict = {
                "block_id": evidence.block_id,
                "provider": evidence.provider,
                "status": "REJECTED",
                "admitted": False,
                "reasons": ["BLOCK_ID_CONFLICT"],
                "evidence_hash": evidence_hash,
            }
            self._append("PROVIDER_BLOCK_CONFLICT", conflict)
            return conflict

        reasons: list[str] = []
        if evidence.provider != "google_cloud_run":
            reasons.append("UNSUPPORTED_BLOCK_PROVIDER")
        if evidence.reason not in ALLOWED_BLOCK_REASONS:
            reasons.append("UNRECOGNISED_BLOCK_REASON")
        if not evidence.provider_native:
            reasons.append("NON_PROVIDER_NATIVE_FAILURE")
        if not evidence.block_id.strip() or not evidence.locator.strip():
            reasons.append("MISSING_ID_OR_LOCATOR")
        if not evidence.attempted_scope:
            reasons.append("MISSING_ATTEMPTED_SCOPE")
        if evidence.mutation_performed:
            reasons.append("MUTATION_OCCURRED_BEFORE_BLOCK")
        if not valid_sha256(evidence.content_sha256):
            reasons.append("INVALID_CONTENT_SHA256")
        if contains_secret_material(asdict(evidence)):
            reasons.append("SECRET_MATERIAL_FORBIDDEN")
        try:
            observed = parse_utc(evidence.observed_at)
            current = parse_utc(now)
            age = (current - observed).total_seconds()
            if age < 0:
                reasons.append("OBSERVATION_FROM_FUTURE")
            if age > 21600:
                reasons.append("BLOCK_EVIDENCE_STALE")
        except (TypeError, ValueError):
            reasons.append("INVALID_TIMESTAMP")

        admitted = not reasons
        decision = {
            "block_id": evidence.block_id,
            "provider": evidence.provider,
            "reason": evidence.reason,
            "status": "ADMITTED" if admitted else "REJECTED",
            "admitted": admitted,
            "reasons": sorted(set(reasons)),
            "evidence_hash": evidence_hash,
            "observed_at": evidence.observed_at,
            "locator": evidence.locator,
            "attempted_scope": sorted(evidence.attempted_scope),
            "mutation_performed": evidence.mutation_performed,
            "content_sha256": evidence.content_sha256,
            "metadata": evidence.metadata,
        }
        self._append("PROVIDER_BLOCK_EVALUATED", decision)
        return decision

    def latest(self, provider: str, *, now: str) -> dict[str, Any] | None:
        rows = [
            self.decisions[item]
            for item in self.by_provider.get(provider, [])
            if self.decisions[item].get("admitted")
        ]
        if not rows:
            return None
        latest = max(rows, key=lambda row: parse_utc(row["observed_at"]))
        age = (parse_utc(now) - parse_utc(latest["observed_at"])).total_seconds()
        result = dict(latest)
        result["age_seconds"] = age
        result["fresh"] = 0 <= age <= 21600
        result["projected_state"] = latest["reason"] if result["fresh"] else "STALE_REVALIDATION_REQUIRED"
        return result

    def verify_ledger(self) -> bool:
        previous = "GENESIS"
        for event in self._events():
            if event.get("previous_hash") != previous:
                return False
            payload = {key: value for key, value in event.items() if key != "event_hash"}
            if digest(payload) != event.get("event_hash"):
                return False
            previous = event["event_hash"]
        return True

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        events = self._events()
        event = {
            "event_id": f"provider-block-{len(events) + 1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "previous_hash": events[-1]["event_hash"] if events else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.ledger_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        self._apply(event)
        self._persist()

    def _events(self) -> list[dict[str, Any]]:
        if not self.ledger_file.exists():
            return []
        return [json.loads(line) for line in self.ledger_file.read_text(encoding="utf-8").splitlines() if line]

    def _apply(self, event: dict[str, Any]) -> None:
        if event["event_type"] != "PROVIDER_BLOCK_EVALUATED":
            return
        payload = event["payload"]
        self.decisions[payload["block_id"]] = payload
        ids = self.by_provider.setdefault(payload["provider"], [])
        if payload["block_id"] not in ids:
            ids.append(payload["block_id"])

    def _persist(self) -> None:
        events = self._events()
        state = {
            "decisions": self.decisions,
            "by_provider": self.by_provider,
            "ledger_head": events[-1]["event_hash"] if events else "GENESIS",
            "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        state["state_sha256"] = digest(state)
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _replay(self) -> None:
        for event in self._events():
            self._apply(event)
