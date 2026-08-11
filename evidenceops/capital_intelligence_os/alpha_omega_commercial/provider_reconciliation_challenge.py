from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from authority_snapshot import digest, parse_utc
from governed_commercial_assurance import utc_now
from provider_dispatch_outbox import LIVE_PROVIDER_RECEIPT_CLASS, MOCK_PROVIDER_RECEIPT_CLASS
from provider_dispatch_outcome_reconciliation import (
    OUTCOME_COMPLETED,
    OUTCOME_NO_EFFECT,
    OutcomeReconciledProviderDispatchCommercialControlPlane,
    ReconciliationConformantMockProviderAdapter,
)

RECONCILIATION_CHALLENGE_CLASS = "LOCAL_PROVIDER_RECONCILIATION_CHALLENGE_V15"
MIN_CHALLENGE_TTL_SECONDS = 5
MAX_CHALLENGE_TTL_SECONDS = 900


class ChallengeBoundMockProviderAdapter(ReconciliationConformantMockProviderAdapter):
    """Mock lookup conformance bound to one durable reconciliation challenge."""

    @staticmethod
    def _verify_challenge(challenge: dict[str, Any]) -> dict[str, Any]:
        payload = dict(challenge)
        observed = payload.pop("event_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("provider reconciliation challenge hash invalid")
        if challenge.get("event_type") != "CHALLENGE_ISSUED":
            raise RuntimeError("provider reconciliation challenge is not issued")
        if challenge.get("challenge_class") != RECONCILIATION_CHALLENGE_CLASS:
            raise RuntimeError("unsupported provider reconciliation challenge class")
        return dict(challenge)

    def reconcile_with_challenge(
        self,
        envelope: dict[str, Any],
        challenge: dict[str, Any],
        *,
        outcome: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        verified = self._verify_challenge(challenge)
        expected = {
            "dispatch_id": envelope["dispatch_id"],
            "provider_domain": envelope["provider_domain"],
            "provider_idempotency_key": envelope["provider_idempotency_key"],
            "claim_reference": envelope["claim_reference"],
            "dispatch_attempt_reference": envelope["dispatch_attempt_reference"],
            "fencing_epoch": envelope["fencing_epoch"],
            "attempt_envelope_sha256": envelope["record_sha256"],
        }
        if any(verified.get(field) != value for field, value in expected.items()):
            raise RuntimeError("provider reconciliation challenge does not bind attempt")
        current = observed_at or verified["issued_at"]
        if parse_utc(current) < parse_utc(str(verified["issued_at"])):
            raise RuntimeError("provider reconciliation observation predates challenge")
        if parse_utc(current) >= parse_utc(str(verified["expires_at"])):
            raise RuntimeError("provider reconciliation challenge expired")
        evidence = super().reconcile(envelope, outcome=outcome)
        evidence.pop("reconciliation_sha256", None)
        evidence["observed_at"] = current
        evidence["reconciliation_challenge_reference"] = verified["challenge_reference"]
        evidence["reconciliation_challenge_event_sha256"] = verified["event_sha256"]
        evidence["reconciliation_challenge_issued_at"] = verified["issued_at"]
        evidence["reconciliation_challenge_expires_at"] = verified["expires_at"]
        evidence["reconciliation_sha256"] = digest(evidence)
        return evidence


class ChallengeBoundProviderDispatchCommercialControlPlane(
    OutcomeReconciledProviderDispatchCommercialControlPlane
):
    """V15 admits reconciliation only through a current one-time durable challenge."""

    CAPABILITY_REVISION = "AO-COMMERCIAL-PROVIDER-RECONCILIATION-CHALLENGE-V15"
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]

    @staticmethod
    def _verify_challenge_history(raw: Any, dispatch_id: str) -> list[dict[str, Any]]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise RuntimeError("provider reconciliation challenge history invalid")
        previous = None
        verified: list[dict[str, Any]] = []
        issued: set[str] = set()
        consumed: set[str] = set()
        for expected_sequence, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                raise RuntimeError("provider reconciliation challenge event invalid")
            event = dict(item)
            observed = event.pop("event_sha256", None)
            if observed != digest(event):
                raise RuntimeError("provider reconciliation challenge history hash invalid")
            if item.get("sequence") != expected_sequence:
                raise RuntimeError("provider reconciliation challenge sequence invalid")
            if item.get("previous_event_sha256") != previous:
                raise RuntimeError("provider reconciliation challenge chain invalid")
            if item.get("dispatch_id") != dispatch_id:
                raise RuntimeError("provider reconciliation challenge dispatch mismatch")
            kind = item.get("event_type")
            reference = str(item.get("challenge_reference", ""))
            if kind == "CHALLENGE_ISSUED":
                if item.get("challenge_class") != RECONCILIATION_CHALLENGE_CLASS:
                    raise RuntimeError("provider reconciliation challenge class invalid")
                if not reference or reference in issued:
                    raise RuntimeError("provider reconciliation challenge reference invalid")
                issued.add(reference)
            elif kind == "CHALLENGE_CONSUMED":
                if reference not in issued or reference in consumed:
                    raise RuntimeError("provider reconciliation challenge consumption invalid")
                consumed.add(reference)
            else:
                raise RuntimeError("unsupported provider reconciliation challenge event")
            previous = observed
            verified.append(dict(item))
        return verified

    @staticmethod
    def _append_challenge_event(
        events: list[dict[str, Any]],
        *,
        dispatch_id: str,
        event_type: str,
        event_at: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        event = {
            "sequence": len(events) + 1,
            "event_type": event_type,
            "event_at": event_at,
            "dispatch_id": dispatch_id,
            "previous_event_sha256": events[-1]["event_sha256"] if events else None,
            **details,
        }
        event["event_sha256"] = digest(event)
        events.append(event)
        return event

    @staticmethod
    def _active_challenge(
        events: list[dict[str, Any]], unknown: dict[str, Any], now: str
    ) -> dict[str, Any] | None:
        consumed = {
            str(event["challenge_reference"])
            for event in events
            if event.get("event_type") == "CHALLENGE_CONSUMED"
        }
        for issued in reversed(
            [event for event in events if event.get("event_type") == "CHALLENGE_ISSUED"]
        ):
            if issued.get("unresolved_event_sha256") != unknown.get("event_sha256"):
                continue
            if str(issued["challenge_reference"]) in consumed:
                continue
            if parse_utc(now) >= parse_utc(str(issued["expires_at"])):
                continue
            return dict(issued)
        return None

    def issue_provider_reconciliation_challenge(
        self,
        dispatch_id: str,
        *,
        ttl_seconds: int = 60,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not MIN_CHALLENGE_TTL_SECONDS <= ttl_seconds <= MAX_CHALLENGE_TTL_SECONDS:
            raise ValueError("provider reconciliation challenge ttl out of bounds")
        current = now or utc_now()
        expires = (
            parse_utc(current) + timedelta(seconds=ttl_seconds)
        ).isoformat().replace("+00:00", "Z")
        with self._action_coordination_locked():
            state = self._read_state()
            record = state.setdefault("provider_dispatches", {}).get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(record)
            claim_events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            unknown = self._unresolved(claim_events)
            if unknown is None:
                raise RuntimeError("provider dispatch has no unresolved outcome")
            histories = state.setdefault("provider_reconciliation_challenge_history", {})
            events = self._verify_challenge_history(histories.get(dispatch_id), dispatch_id)
            existing = self._active_challenge(events, unknown, current)
            if existing is not None:
                return existing
            reference = digest(
                {
                    "dispatch_id": dispatch_id,
                    "unresolved_event_sha256": unknown["event_sha256"],
                    "attempt_envelope_sha256": unknown["attempt_envelope_sha256"],
                    "issued_at": current,
                    "expires_at": expires,
                    "sequence": len(events) + 1,
                }
            )
            issued = self._append_challenge_event(
                events,
                dispatch_id=dispatch_id,
                event_type="CHALLENGE_ISSUED",
                event_at=current,
                details={
                    "challenge_class": RECONCILIATION_CHALLENGE_CLASS,
                    "challenge_reference": reference,
                    "issued_at": current,
                    "expires_at": expires,
                    "provider_domain": record["provider_domain"],
                    "provider_idempotency_key": record["provider_idempotency_key"],
                    "claim_reference": unknown["claim_reference"],
                    "dispatch_attempt_reference": unknown["dispatch_attempt_reference"],
                    "fencing_epoch": unknown["fencing_epoch"],
                    "attempt_envelope_sha256": unknown["attempt_envelope_sha256"],
                    "unresolved_event_sha256": unknown["event_sha256"],
                    "provider_native_reconciliation_authority": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
                },
            )
            histories[dispatch_id] = events
            self._write_state(state)
            self._ledger("C03", "provider_reconciliation.challenge_issued", dispatch_id, issued)
            return dict(issued)

    def _verified_challenge_for_evidence(
        self,
        state: dict[str, Any],
        dispatch_id: str,
        unknown: dict[str, Any],
        evidence: dict[str, Any],
        now: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        verified = self._verify_evidence(evidence)
        histories = state.setdefault("provider_reconciliation_challenge_history", {})
        events = self._verify_challenge_history(histories.get(dispatch_id), dispatch_id)
        active = self._active_challenge(events, unknown, now)
        if active is None:
            raise RuntimeError("current provider reconciliation challenge required")
        expected = {
            "reconciliation_challenge_reference": active["challenge_reference"],
            "reconciliation_challenge_event_sha256": active["event_sha256"],
            "reconciliation_challenge_issued_at": active["issued_at"],
            "reconciliation_challenge_expires_at": active["expires_at"],
        }
        if any(verified.get(field) != value for field, value in expected.items()):
            raise RuntimeError("provider reconciliation evidence challenge binding invalid")
        observed_at = str(verified.get("observed_at", ""))
        if not observed_at:
            raise RuntimeError("provider reconciliation evidence observation missing")
        if parse_utc(observed_at) < parse_utc(str(active["issued_at"])):
            raise RuntimeError("provider reconciliation evidence predates challenge")
        if parse_utc(observed_at) >= parse_utc(str(active["expires_at"])):
            raise RuntimeError("provider reconciliation evidence challenge expired")
        if parse_utc(observed_at) > parse_utc(now):
            raise RuntimeError("provider reconciliation evidence observation is in the future")
        return verified, events, active

    def resolve_provider_dispatch_outcome(
        self,
        dispatch_id: str,
        evidence: dict[str, Any],
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        with self._action_coordination_locked():
            state = self._read_state()
            dispatches = state.setdefault("provider_dispatches", {})
            record = dispatches.get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            claim_events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id),
                dispatch_id,
            )
            unknown = self._unresolved(claim_events)
            if unknown is None:
                raise RuntimeError("provider dispatch has no unresolved outcome")
            verified, challenge_events, challenge = self._verified_challenge_for_evidence(
                state, dispatch_id, unknown, evidence, current
            )
            claim = str(unknown["claim_reference"])
            started = self._event(claim_events, claim, "STARTED")
            submitted = self._event(claim_events, claim, "SUBMITTED")
            if started is None or submitted is None:
                raise RuntimeError("provider outcome lacks attempt evidence")
            expected = {
                "dispatch_id": dispatch_id,
                "provider_domain": record["provider_domain"],
                "operation": record["operation"],
                "provider_idempotency_key": record["provider_idempotency_key"],
                "dispatch_attempt_reference": unknown["dispatch_attempt_reference"],
                "claim_reference": unknown["claim_reference"],
                "fencing_epoch": unknown["fencing_epoch"],
                "provider_dispatch_record_sha256": started["prepared_dispatch_record_sha256"],
                "attempt_envelope_sha256": unknown["attempt_envelope_sha256"],
            }
            if any(verified.get(field) != value for field, value in expected.items()):
                raise RuntimeError("provider reconciliation does not bind the quarantined attempt")

            if verified["outcome"] == OUTCOME_NO_EFFECT:
                if verified.get("provider_effect_observed") is not False or verified.get("provider_receipt") is not None:
                    raise RuntimeError("no-effect reconciliation is contradictory")
                resolved = self._append_claim_event(
                    claim_events,
                    dispatch_id=dispatch_id,
                    event_type="OUTCOME_RESOLVED_NO_EFFECT",
                    event_at=current,
                    details={
                        "worker_id": unknown["worker_id"],
                        "claim_reference": claim,
                        "attempt": unknown["attempt"],
                        "fencing_epoch": unknown["fencing_epoch"],
                        "dispatch_attempt_reference": unknown["dispatch_attempt_reference"],
                        "outcome_reconciliation_sha256": verified["reconciliation_sha256"],
                        "reconciliation_challenge_reference": challenge["challenge_reference"],
                        "provider_effect_observed": False,
                    },
                )
                updated = self._with_state(record, "PREPARED_PROVIDER_PROOF_REQUIRED")
                dispatches[dispatch_id] = updated
            else:
                if verified.get("outcome") != OUTCOME_COMPLETED or verified.get("provider_effect_observed") is not True:
                    raise RuntimeError("completed reconciliation lacks observed effect")
                receipt = verified.get("provider_receipt")
                if not isinstance(receipt, dict):
                    raise RuntimeError("completed reconciliation lacks provider receipt")
                receipt_payload = dict(receipt)
                if receipt_payload.pop("provider_receipt_sha256", None) != digest(receipt_payload):
                    raise RuntimeError("reconciled provider receipt hash invalid")
                if receipt.get("receipt_class") == LIVE_PROVIDER_RECEIPT_CLASS:
                    raise RuntimeError("live reconciled receipt requires provider proof")
                if receipt.get("receipt_class") != MOCK_PROVIDER_RECEIPT_CLASS:
                    raise ValueError("unsupported reconciled provider receipt class")
                receipt_expected = {**expected, "attempt_start_event_sha256": started["event_sha256"]}
                if any(receipt.get(field) != value for field, value in receipt_expected.items()):
                    raise RuntimeError("reconciled receipt does not bind the quarantined attempt")
                updated = self._with_state(
                    record,
                    "MOCK_PROVIDER_CHALLENGE_RECONCILIATION_CONFORMANCE_VERIFIED_LIVE_PROVIDER_PROOF_REQUIRED",
                    receipt,
                )
                dispatches[dispatch_id] = updated
                resolved = self._append_claim_event(
                    claim_events,
                    dispatch_id=dispatch_id,
                    event_type="COMPLETED",
                    event_at=current,
                    details={
                        "worker_id": unknown["worker_id"],
                        "claim_reference": claim,
                        "attempt": unknown["attempt"],
                        "fencing_epoch": unknown["fencing_epoch"],
                        "dispatch_attempt_reference": unknown["dispatch_attempt_reference"],
                        "provider_receipt_sha256": receipt["provider_receipt_sha256"],
                        "completed_dispatch_record_sha256": updated["record_sha256"],
                        "outcome_reconciliation_sha256": verified["reconciliation_sha256"],
                        "reconciliation_challenge_reference": challenge["challenge_reference"],
                    },
                )

            consumed = self._append_challenge_event(
                challenge_events,
                dispatch_id=dispatch_id,
                event_type="CHALLENGE_CONSUMED",
                event_at=current,
                details={
                    "challenge_reference": challenge["challenge_reference"],
                    "unresolved_event_sha256": unknown["event_sha256"],
                    "resolution_event_sha256": resolved["event_sha256"],
                    "outcome_reconciliation_sha256": verified["reconciliation_sha256"],
                    "outcome": verified["outcome"],
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = claim_events
            state["provider_reconciliation_challenge_history"][dispatch_id] = challenge_events
            self._write_state(state)
            self._ledger("C06", "provider_reconciliation.challenge_consumed", dispatch_id, consumed)
            return {
                "outcome": verified["outcome"],
                "dispatch": dict(updated),
                "resolution_event": dict(resolved),
                "challenge_consumption_event": dict(consumed),
            }

    def _verify_provider_dispatch_attempt_state(self) -> bool:
        super()._verify_provider_dispatch_attempt_state()
        state = self._read_state()
        histories = state.get("provider_reconciliation_challenge_history", {})
        claim_histories = state.get("provider_dispatch_claim_history", {})
        for dispatch_id, raw in histories.items():
            events = self._verify_challenge_history(raw, dispatch_id)
            claims = self._verify_claim_history(claim_histories.get(dispatch_id), dispatch_id)
            claim_event_hashes = {event["event_sha256"] for event in claims}
            for event in events:
                if event.get("event_type") == "CHALLENGE_CONSUMED" and event.get("resolution_event_sha256") not in claim_event_hashes:
                    raise RuntimeError("provider reconciliation challenge resolution binding invalid")
        return True

    def provider_reconciliation_challenge_readback(self) -> dict[str, Any]:
        base = super().provider_dispatch_outcome_readback()
        with self._action_coordination_locked():
            self._verify_provider_dispatch_attempt_state()
            state = self._read_state()
            histories = state.get("provider_reconciliation_challenge_history", {})
            events = [event for history in histories.values() for event in history]
            return {
                **base,
                "capability_revision": self.CAPABILITY_REVISION,
                "stage_scope": list(self.STAGE_SCOPE),
                "challenges_issued": sum(event.get("event_type") == "CHALLENGE_ISSUED" for event in events),
                "challenges_consumed": sum(event.get("event_type") == "CHALLENGE_CONSUMED" for event in events),
                "challenge_history_hash_chain_verified": True,
                "challenge_attempt_binding_verified": True,
                "challenge_freshness_enforced": True,
                "challenge_single_use_enforced": True,
                "provider_native_reconciliation_authority": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
                "provider_native_reconciliation_proven": False,
                "external_mutation_performed": False,
                "live_provider_operation_proven": False,
            }
