from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .engine import HeartbeatError, SAFE_ID, sha256_value

CONTRACT_SCHEMA = "EVIDENCEOPS-LIVE-BIBLE-CAPTURE-CONTRACT-2"
EVENT_SCHEMA = "EVIDENCEOPS-LIVE-BIBLE-EVENT-2"
STATE_SCHEMA = "EVIDENCEOPS-LIVE-BIBLE-CAPTURE-STATE-2"
DELTA_SCHEMA = "EVIDENCEOPS-LIVE-BIBLE-DELTA-2"
RECEIPT_SCHEMA = "EVIDENCEOPS-LIVE-BIBLE-RECONCILIATION-RECEIPT-2"

PRIVACY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
CAPTURE_MODES = {"ACTIVE_TURN", "SCHEDULED_RECONCILIATION", "PROVIDER_EVENT", "RECOVERY_REPLAY"}
SOURCE_KINDS = {
    "CHATGPT_ACTIVE_TURN",
    "GITHUB_REPOSITORY",
    "GOOGLE_DRIVE",
    "GMAIL",
    "PROVIDER_FEED",
    "LOCAL_RUNTIME",
}
HEX_64 = re.compile(r"^[a-f0-9]{64}$")


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HeartbeatError("invalid Live Bible timestamp") from exc
    if parsed.tzinfo is None:
        raise HeartbeatError("Live Bible timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class SourceAdapter:
    source_id: str
    kind: str
    allowed_modes: tuple[str, ...]
    supports_between_turn: bool
    provider_receipt_required: bool
    privacy_ceiling: str
    materiality_threshold: float
    master_promotion_allowed: bool


class LiveBibleCaptureFabric:
    """Fail-closed capture, reconciliation, deduplication and promotion planning."""

    def __init__(self, contract: dict[str, Any]):
        self.contract = contract
        self.sources = self._validate_contract(contract)

    @staticmethod
    def _validate_contract(contract: dict[str, Any]) -> dict[str, SourceAdapter]:
        if contract.get("schema") != CONTRACT_SCHEMA:
            raise HeartbeatError("unsupported Live Bible capture contract")
        if not SAFE_ID.fullmatch(str(contract.get("node_id", ""))):
            raise HeartbeatError("invalid Live Bible node_id")
        if contract.get("privacy_tier") not in PRIVACY_RANK:
            raise HeartbeatError("invalid Live Bible privacy tier")
        if contract.get("capture_version") != 2:
            raise HeartbeatError("capture_version must be 2")
        if not isinstance(contract.get("max_seen_fingerprints"), int) or not 128 <= contract["max_seen_fingerprints"] <= 100000:
            raise HeartbeatError("max_seen_fingerprints must be between 128 and 100000")
        source_rows = contract.get("sources")
        if not isinstance(source_rows, list) or not source_rows:
            raise HeartbeatError("at least one capture source is required")
        sources: dict[str, SourceAdapter] = {}
        for row in source_rows:
            source_id = str(row.get("source_id", ""))
            if not SAFE_ID.fullmatch(source_id) or source_id in sources:
                raise HeartbeatError("source_id is invalid or duplicated")
            kind = row.get("kind")
            if kind not in SOURCE_KINDS:
                raise HeartbeatError(f"unsupported source kind for {source_id}")
            modes = row.get("allowed_modes")
            if not isinstance(modes, list) or not modes or any(mode not in CAPTURE_MODES for mode in modes):
                raise HeartbeatError(f"invalid capture modes for {source_id}")
            ceiling = row.get("privacy_ceiling")
            if ceiling not in PRIVACY_RANK:
                raise HeartbeatError(f"invalid privacy ceiling for {source_id}")
            threshold = row.get("materiality_threshold", 0.5)
            if not isinstance(threshold, (int, float)) or not 0 <= float(threshold) <= 1:
                raise HeartbeatError(f"invalid materiality threshold for {source_id}")
            sources[source_id] = SourceAdapter(
                source_id=source_id,
                kind=kind,
                allowed_modes=tuple(sorted(set(modes))),
                supports_between_turn=bool(row.get("supports_between_turn")),
                provider_receipt_required=bool(row.get("provider_receipt_required")),
                privacy_ceiling=ceiling,
                materiality_threshold=float(threshold),
                master_promotion_allowed=bool(row.get("master_promotion_allowed")),
            )
        return sources

    @staticmethod
    def empty_state(node_id: str) -> dict[str, Any]:
        body = {
            "schema": STATE_SCHEMA,
            "node_id": node_id,
            "capture_version": 2,
            "source_cursors": {},
            "seen_fingerprints": [],
            "last_receipt_sha256": None,
            "last_reconciled_at": None,
            "accepted_event_count": 0,
            "held_event_count": 0,
            "conflict_count": 0,
        }
        return {**body, "state_sha256": sha256_value(body)}

    @staticmethod
    def verify_state(state: dict[str, Any], expected_node_id: str | None = None) -> None:
        if state.get("schema") != STATE_SCHEMA or state.get("capture_version") != 2:
            raise HeartbeatError("unsupported Live Bible capture state")
        if expected_node_id and state.get("node_id") != expected_node_id:
            raise HeartbeatError("Live Bible state belongs to a different node")
        body = {key: value for key, value in state.items() if key != "state_sha256"}
        if state.get("state_sha256") != sha256_value(body):
            raise HeartbeatError("Live Bible capture state hash mismatch")
        if not isinstance(state.get("source_cursors"), dict):
            raise HeartbeatError("source_cursors must be an object")
        fingerprints = state.get("seen_fingerprints")
        if not isinstance(fingerprints, list) or any(not HEX_64.fullmatch(str(value)) for value in fingerprints):
            raise HeartbeatError("seen_fingerprints contains an invalid value")

    def make_event(
        self,
        *,
        source_id: str,
        source_event_id: str,
        capture_mode: str,
        occurred_at: str,
        observed_at: str,
        event_type: str,
        summary: str,
        content_fingerprint: str,
        source_cursor: str,
        privacy_tier: str,
        materiality: float,
        provider_receipt_ref: str | None = None,
        case_wall: str | None = None,
        workstream_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "schema": EVENT_SCHEMA,
            "node_id": self.contract["node_id"],
            "source_id": source_id,
            "source_event_id": source_event_id,
            "capture_mode": capture_mode,
            "occurred_at": occurred_at,
            "observed_at": observed_at,
            "event_type": event_type,
            "summary": summary,
            "content_fingerprint": content_fingerprint,
            "source_cursor": source_cursor,
            "privacy_tier": privacy_tier,
            "materiality": materiality,
            "provider_receipt_ref": provider_receipt_ref,
            "case_wall": case_wall,
            "workstream_id": workstream_id,
            "raw_content_included": False,
            "credentials_included": False,
        }
        self.verify_event(event)
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        return {**event, "event_sha256": sha256_value(body)}

    def verify_event(self, event: dict[str, Any]) -> None:
        if event.get("schema") != EVENT_SCHEMA:
            raise HeartbeatError("unsupported Live Bible event")
        if event.get("node_id") != self.contract["node_id"]:
            raise HeartbeatError("Live Bible event belongs to a different node")
        source_id = str(event.get("source_id", ""))
        source = self.sources.get(source_id)
        if source is None:
            raise HeartbeatError("unregistered Live Bible source")
        if not SAFE_ID.fullmatch(str(event.get("source_event_id", ""))):
            raise HeartbeatError("invalid source_event_id")
        mode = event.get("capture_mode")
        if mode not in source.allowed_modes:
            raise HeartbeatError("capture mode is not allowed for source")
        if event.get("privacy_tier") not in PRIVACY_RANK:
            raise HeartbeatError("invalid event privacy tier")
        if PRIVACY_RANK[event["privacy_tier"]] > PRIVACY_RANK[source.privacy_ceiling]:
            raise HeartbeatError("event exceeds source privacy ceiling")
        materiality = event.get("materiality")
        if not isinstance(materiality, (int, float)) or not 0 <= float(materiality) <= 1:
            raise HeartbeatError("event materiality must be between zero and one")
        summary = event.get("summary")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
            raise HeartbeatError("event summary is missing or too long")
        if not HEX_64.fullmatch(str(event.get("content_fingerprint", ""))):
            raise HeartbeatError("invalid event content fingerprint")
        if not isinstance(event.get("source_cursor"), str) or not event["source_cursor"]:
            raise HeartbeatError("event source_cursor is required")
        if event.get("raw_content_included") or event.get("credentials_included"):
            raise HeartbeatError("raw content or credentials are prohibited in capture events")
        parse_time(event.get("occurred_at"))
        parse_time(event.get("observed_at"))
        if "event_sha256" in event:
            body = {key: value for key, value in event.items() if key != "event_sha256"}
            if event["event_sha256"] != sha256_value(body):
                raise HeartbeatError("Live Bible event hash mismatch")

    def _evaluate_event(
        self,
        event: dict[str, Any],
        source: SourceAdapter,
        seen: set[str],
        cursors: dict[str, Any],
        observed: datetime,
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []
        fingerprint = event["content_fingerprint"]
        if fingerprint in seen:
            return "DUPLICATE", ["CONTENT_FINGERPRINT_ALREADY_CAPTURED"]
        mode = event["capture_mode"]
        if mode != "ACTIVE_TURN" and not source.supports_between_turn:
            reasons.append("BETWEEN_TURN_SOURCE_NOT_AVAILABLE")
        if mode != "ACTIVE_TURN" and source.provider_receipt_required and not event.get("provider_receipt_ref"):
            reasons.append("PROVIDER_RECEIPT_REQUIRED")
        if float(event["materiality"]) < source.materiality_threshold:
            reasons.append("BELOW_MATERIALITY_THRESHOLD")
        if parse_time(event["observed_at"]) > observed:
            reasons.append("EVENT_OBSERVED_IN_FUTURE")
        prior = cursors.get(source.source_id)
        if prior and prior.get("cursor") == event["source_cursor"] and prior.get("fingerprint") != fingerprint:
            reasons.append("CURSOR_CONTENT_CONFLICT")
        if reasons:
            if "CURSOR_CONTENT_CONFLICT" in reasons:
                return "CONFLICT", reasons
            return "HELD", reasons
        return "ACCEPT", []

    def reconcile(
        self,
        events: Iterable[dict[str, Any]],
        *,
        previous_state: dict[str, Any] | None,
        observed_at: str,
    ) -> dict[str, Any]:
        observed = parse_time(observed_at)
        state = previous_state or self.empty_state(self.contract["node_id"])
        self.verify_state(state, self.contract["node_id"])
        seen = set(state["seen_fingerprints"])
        cursors = dict(state["source_cursors"])
        accepted: list[dict[str, Any]] = []
        held: list[dict[str, Any]] = []
        duplicates: list[str] = []
        conflicts: list[dict[str, Any]] = []

        ordered = sorted(
            list(events),
            key=lambda event: (parse_time(event.get("observed_at")).isoformat(), str(event.get("source_id")), str(event.get("source_event_id"))),
        )
        for event in ordered:
            self.verify_event(event)
            source = self.sources[event["source_id"]]
            decision, reasons = self._evaluate_event(event, source, seen, cursors, observed)
            if decision == "DUPLICATE":
                duplicates.append(event["event_sha256"])
                continue
            if decision in {"HELD", "CONFLICT"}:
                row = {
                    "event_sha256": event["event_sha256"],
                    "source_id": event["source_id"],
                    "source_event_id": event["source_event_id"],
                    "decision": decision,
                    "reasons": reasons,
                }
                (conflicts if decision == "CONFLICT" else held).append(row)
                continue

            promotion_eligible = (
                source.master_promotion_allowed
                and PRIVACY_RANK[event["privacy_tier"]] <= PRIVACY_RANK["P1"]
                and float(event["materiality"]) >= max(0.75, source.materiality_threshold)
            )
            delta_body = {
                "schema": DELTA_SCHEMA,
                "node_id": self.contract["node_id"],
                "source_id": event["source_id"],
                "source_event_id": event["source_event_id"],
                "event_sha256": event["event_sha256"],
                "captured_at": observed.isoformat(),
                "event_type": event["event_type"],
                "summary": event["summary"],
                "privacy_tier": event["privacy_tier"],
                "case_wall": event.get("case_wall"),
                "workstream_id": event.get("workstream_id"),
                "content_fingerprint": event["content_fingerprint"],
                "source_cursor": event["source_cursor"],
                "provider_receipt_ref": event.get("provider_receipt_ref"),
                "local_capture_required": True,
                "master_promotion_eligible": promotion_eligible,
                "external_effect_authority": False,
            }
            delta = {**delta_body, "delta_sha256": sha256_value(delta_body)}
            accepted.append(delta)
            seen.add(event["content_fingerprint"])
            cursors[event["source_id"]] = {
                "cursor": event["source_cursor"],
                "fingerprint": event["content_fingerprint"],
                "observed_at": event["observed_at"],
                "provider_receipt_ref": event.get("provider_receipt_ref"),
            }

        capture_state = "NO_MATERIAL_CHANGE"
        if conflicts:
            capture_state = "CONFLICT_HELD"
        elif held:
            capture_state = "HELD_SOURCE_OR_POLICY"
        elif accepted:
            capture_state = "CAPTURED_MATERIAL_DELTA"

        trimmed_seen = sorted(seen)[-self.contract["max_seen_fingerprints"] :]
        state_body = {
            "schema": STATE_SCHEMA,
            "node_id": self.contract["node_id"],
            "capture_version": 2,
            "source_cursors": cursors,
            "seen_fingerprints": trimmed_seen,
            "last_receipt_sha256": None,
            "last_reconciled_at": observed.isoformat(),
            "accepted_event_count": int(state.get("accepted_event_count", 0)) + len(accepted),
            "held_event_count": int(state.get("held_event_count", 0)) + len(held),
            "conflict_count": int(state.get("conflict_count", 0)) + len(conflicts),
        }
        provisional_state = {**state_body, "state_sha256": sha256_value(state_body)}
        receipt_body = {
            "schema": RECEIPT_SCHEMA,
            "node_id": self.contract["node_id"],
            "observed_at": observed.isoformat(),
            "capture_state": capture_state,
            "accepted_delta_refs": [item["delta_sha256"] for item in accepted],
            "held_events": held,
            "conflicts": conflicts,
            "duplicate_event_refs": duplicates,
            "source_cursor_digest": sha256_value(cursors),
            "previous_state_sha256": state["state_sha256"],
            "provisional_state_sha256": provisional_state["state_sha256"],
            "external_effects": 0,
            "invisible_chat_capture_claimed": False,
            "truth_boundary": (
                "Active-turn chat text is captured only during an authorised turn. "
                "Between-turn capture requires a registered provider source, a current cursor, "
                "a provider receipt when configured, and target readback."
            ),
        }
        receipt = {**receipt_body, "receipt_sha256": sha256_value(receipt_body)}
        final_state_body = {
            **state_body,
            "last_receipt_sha256": receipt["receipt_sha256"],
        }
        final_state = {**final_state_body, "state_sha256": sha256_value(final_state_body)}
        return {
            "schema": "EVIDENCEOPS-LIVE-BIBLE-RECONCILIATION-RESULT-2",
            "accepted_deltas": accepted,
            "held_events": held,
            "conflicts": conflicts,
            "duplicate_event_refs": duplicates,
            "state": final_state,
            "receipt": receipt,
        }

    @staticmethod
    def verify_receipt(receipt: dict[str, Any]) -> None:
        if receipt.get("schema") != RECEIPT_SCHEMA:
            raise HeartbeatError("unsupported Live Bible receipt")
        body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if receipt.get("receipt_sha256") != sha256_value(body):
            raise HeartbeatError("Live Bible receipt hash mismatch")
        if receipt.get("external_effects") != 0:
            raise HeartbeatError("Live Bible receipt reports an external effect")
        if receipt.get("invisible_chat_capture_claimed"):
            raise HeartbeatError("invisible chat capture claims are prohibited")
