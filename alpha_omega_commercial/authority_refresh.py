from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OPERATIONAL_STATES = {"FRESH_VERIFIED", "FRESH_VERIFIED_READBACK"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class AuthorityObservation:
    observation_id: str
    domain: str
    provider: str
    subject: str
    locator: str
    observed_at: str
    captured_at: str
    state: str
    scope: tuple[str, ...]
    content_sha256: str
    provider_native: bool
    evidence: dict[str, Any] = field(default_factory=dict)


class ProviderAuthorityFreshnessLedger:
    """Hash-linked, fail-closed provider-authority freshness reconciliation."""

    def __init__(self, root: str | Path, policies: dict[str, dict[str, Any]]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.root / "provider-authority-ledger.jsonl"
        self.state_file = self.root / "provider-authority-state.json"
        self.policies = policies
        self.decisions: dict[str, dict[str, Any]] = {}
        self.admitted_by_domain: dict[str, list[str]] = {domain: [] for domain in policies}
        self._replay()

    def admit(self, observation: AuthorityObservation, *, now: str | None = None) -> dict[str, Any]:
        observation_hash = digest(asdict(observation))
        existing = self.decisions.get(observation.observation_id)
        if existing:
            if existing["observation_hash"] == observation_hash:
                return existing
            conflict = {
                "observation_id": observation.observation_id,
                "domain": observation.domain,
                "status": "REJECTED",
                "reasons": ["OBSERVATION_ID_CONFLICT"],
                "observation_hash": observation_hash,
                "admitted": False,
            }
            self._append("AUTHORITY_OBSERVATION_CONFLICT", conflict)
            return conflict

        reasons: list[str] = []
        policy = self.policies.get(observation.domain)
        if not policy:
            reasons.append("UNKNOWN_AUTHORITY_DOMAIN")
        if not observation.observation_id.strip():
            reasons.append("MISSING_OBSERVATION_ID")
        if not observation.provider.strip() or not observation.locator.strip():
            reasons.append("MISSING_PROVIDER_LOCATOR")
        if not observation.provider_native:
            reasons.append("NON_PROVIDER_NATIVE_OBSERVATION")
        if not valid_sha256(observation.content_sha256):
            reasons.append("INVALID_CONTENT_SHA256")

        if policy:
            if observation.subject != policy["subject"]:
                reasons.append("SUBJECT_MISMATCH")
            if observation.state not in set(policy["allowed_states"]):
                reasons.append("STATE_NOT_ALLOWED")
            missing_scope = sorted(set(policy["required_scope"]) - set(observation.scope))
            if missing_scope:
                reasons.append("MISSING_REQUIRED_SCOPE:" + ",".join(missing_scope))
            try:
                observed = parse_utc(observation.observed_at)
                captured = parse_utc(observation.captured_at)
                current = parse_utc(now or utc_now())
                if observed > captured:
                    reasons.append("OBSERVED_AFTER_CAPTURE")
                if captured > current:
                    reasons.append("CAPTURE_FROM_FUTURE")
                age_seconds = (current - observed).total_seconds()
                if age_seconds < 0:
                    reasons.append("OBSERVATION_FROM_FUTURE")
                if age_seconds > int(policy["max_age_seconds"]):
                    reasons.append("AUTHORITY_OBSERVATION_STALE")
            except (TypeError, ValueError):
                reasons.append("INVALID_TIMESTAMP")

        admitted = not reasons
        decision = {
            "observation_id": observation.observation_id,
            "domain": observation.domain,
            "state": observation.state,
            "status": "ADMITTED" if admitted else "REJECTED",
            "reasons": sorted(set(reasons)),
            "observation_hash": observation_hash,
            "admitted": admitted,
            "provider": observation.provider,
            "subject": observation.subject,
            "locator": observation.locator,
            "observed_at": observation.observed_at,
            "captured_at": observation.captured_at,
            "scope": sorted(observation.scope),
            "content_sha256": observation.content_sha256,
            "evidence": observation.evidence,
        }
        self._append("AUTHORITY_OBSERVATION_EVALUATED", decision)
        return decision

    def project(self, base_authority: dict[str, str], *, now: str) -> dict[str, Any]:
        current = parse_utc(now)
        states = dict(base_authority)
        evidence: dict[str, dict[str, Any]] = {}
        for domain, ids in self.admitted_by_domain.items():
            candidates = [self.decisions[obs_id] for obs_id in ids]
            if not candidates:
                continue
            latest = max(candidates, key=lambda row: parse_utc(row["observed_at"]))
            policy = self.policies[domain]
            age_seconds = (current - parse_utc(latest["observed_at"])).total_seconds()
            fresh = 0 <= age_seconds <= int(policy["max_age_seconds"])
            states[domain] = latest["state"] if fresh else "STALE_REVALIDATION_REQUIRED"
            evidence[domain] = {
                "observation_id": latest["observation_id"],
                "provider": latest["provider"],
                "subject": latest["subject"],
                "locator": latest["locator"],
                "observed_at": latest["observed_at"],
                "captured_at": latest["captured_at"],
                "content_sha256": latest["content_sha256"],
                "age_seconds": age_seconds,
                "fresh": fresh,
                "evidence": latest["evidence"],
            }
        result = {
            "states": states,
            "evidence": evidence,
            "fresh_operational_domains": sorted(
                domain for domain, state in states.items() if state in OPERATIONAL_STATES
            ),
            "blocked_or_unverified_domains": sorted(
                domain for domain, state in states.items() if state not in OPERATIONAL_STATES
            ),
            "external_gate_effect": "UNCHANGED",
            "owner_authority_effect": "UNCHANGED",
            "ledger_integrity": self.verify_ledger(),
            "projected_at": now,
        }
        result["projection_sha256"] = digest(result)
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
            "event_id": f"authority-refresh-{len(events) + 1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
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
        if event["event_type"] != "AUTHORITY_OBSERVATION_EVALUATED":
            return
        decision = event["payload"]
        self.decisions[decision["observation_id"]] = decision
        if decision.get("admitted"):
            ids = self.admitted_by_domain.setdefault(decision["domain"], [])
            if decision["observation_id"] not in ids:
                ids.append(decision["observation_id"])

    def _replay(self) -> None:
        for event in self._events():
            self._apply(event)
        self._persist()

    def _persist(self) -> None:
        events = self._events()
        state = {
            "decisions": self.decisions,
            "admitted_by_domain": self.admitted_by_domain,
            "ledger_head": events[-1]["event_hash"] if events else "GENESIS",
        }
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
