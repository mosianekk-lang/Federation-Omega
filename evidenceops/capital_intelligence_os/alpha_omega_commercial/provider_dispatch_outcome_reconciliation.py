from __future__ import annotations

from copy import deepcopy
from typing import Any

from authority_snapshot import digest, parse_utc
from governed_commercial_assurance import utc_now
from provider_dispatch_fencing import (
    FencedConformantMockProviderAdapter,
    FencedProviderDispatchCommercialControlPlane,
)
from provider_dispatch_outbox import LIVE_PROVIDER_RECEIPT_CLASS, MOCK_PROVIDER_RECEIPT_CLASS

MOCK_PROVIDER_RECONCILIATION_CLASS = "MOCK_PROVIDER_RECONCILIATION_CONFORMANCE"
LIVE_PROVIDER_RECONCILIATION_CLASS = "LIVE_PROVIDER_NATIVE_RECONCILIATION"
OUTCOME_NO_EFFECT = "NO_EFFECT"
OUTCOME_COMPLETED = "COMPLETED"


class ReconciliationConformantMockProviderAdapter(FencedConformantMockProviderAdapter):
    """Deterministic lookup conformance; never performs an external mutation."""

    def reconcile(self, envelope: dict[str, Any], *, outcome: str) -> dict[str, Any]:
        observed = envelope.get("record_sha256")
        payload = dict(envelope)
        payload.pop("record_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("provider dispatch attempt envelope hash invalid")
        if envelope.get("provider_domain") != self.provider_domain:
            raise ValueError("provider dispatch domain mismatch")
        if outcome not in {OUTCOME_NO_EFFECT, OUTCOME_COMPLETED}:
            raise ValueError("unsupported provider reconciliation outcome")
        key = str(envelope["provider_idempotency_key"])
        existing = self._receipts.get((key, int(envelope["fencing_epoch"])))
        if outcome == OUTCOME_COMPLETED and existing is None:
            raise RuntimeError("mock provider has no completed attempt to reconcile")
        if outcome == OUTCOME_NO_EFFECT and existing is not None:
            raise RuntimeError("mock provider already has a completed attempt")
        evidence = {
            "reconciliation_class": MOCK_PROVIDER_RECONCILIATION_CLASS,
            "outcome": outcome,
            "dispatch_id": envelope["dispatch_id"],
            "provider_domain": envelope["provider_domain"],
            "operation": envelope["operation"],
            "provider_idempotency_key": key,
            "dispatch_attempt_reference": envelope["dispatch_attempt_reference"],
            "claim_reference": envelope["claim_reference"],
            "fencing_epoch": envelope["fencing_epoch"],
            "provider_dispatch_record_sha256": envelope["provider_dispatch_record_sha256"],
            "attempt_envelope_sha256": observed,
            "attempt_start_event_sha256": envelope["attempt_start_event_sha256"],
            "provider_effect_observed": outcome == OUTCOME_COMPLETED,
            "provider_receipt": deepcopy(existing),
            "observed_at": envelope["attempt_started_at"],
            "external_mutation_performed": False,
            "live_provider_operation_proven": False,
            "provider_native_reconciliation_proven": False,
        }
        evidence["reconciliation_sha256"] = digest(evidence)
        return evidence


class OutcomeReconciledProviderDispatchCommercialControlPlane(
    FencedProviderDispatchCommercialControlPlane
):
    """V14 quarantines uncertain submitted attempts until exact lookup evidence."""

    CAPABILITY_REVISION = "AO-COMMERCIAL-PROVIDER-DISPATCH-OUTCOME-RECONCILIATION-V14"
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]
    TERMINAL_EVENT_TYPES = (
        FencedProviderDispatchCommercialControlPlane.TERMINAL_EVENT_TYPES
        | {"OUTCOME_UNKNOWN"}
    )

    @classmethod
    def _latest_claim(cls, events: list[dict[str, Any]]) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.get("event_type") != "CLAIMED":
                continue
            later = events[event["sequence"] :]
            if any(
                item.get("claim_reference") == event.get("claim_reference")
                and item.get("event_type") in cls.TERMINAL_EVENT_TYPES
                for item in later
            ):
                continue
            active = dict(event)
            renewals = [
                item for item in later
                if item.get("claim_reference") == event.get("claim_reference")
                and item.get("event_type") == "RENEWED"
            ]
            if renewals:
                active["lease_expires_at"] = renewals[-1]["lease_expires_at"]
            return active
        return None

    @staticmethod
    def _event(events: list[dict[str, Any]], claim: str, kind: str) -> dict[str, Any] | None:
        return next((e for e in events if e.get("claim_reference") == claim and e.get("event_type") == kind), None)

    @staticmethod
    def _unresolved(events: list[dict[str, Any]]) -> dict[str, Any] | None:
        for unknown in reversed([e for e in events if e.get("event_type") == "OUTCOME_UNKNOWN"]):
            later = events[unknown["sequence"] :]
            resolved = any(
                e.get("claim_reference") == unknown.get("claim_reference")
                and e.get("dispatch_attempt_reference") == unknown.get("dispatch_attempt_reference")
                and (
                    e.get("event_type") == "OUTCOME_RESOLVED_NO_EFFECT"
                    or (e.get("event_type") == "COMPLETED" and e.get("outcome_reconciliation_sha256"))
                )
                for e in later
            )
            if not resolved:
                return unknown
        return None

    @staticmethod
    def _with_state(record: dict[str, Any], state: str, receipt: dict[str, Any] | None = None) -> dict[str, Any]:
        updated = dict(record)
        updated.pop("record_sha256", None)
        updated["state"] = state
        if receipt is not None:
            updated["provider_receipt"] = deepcopy(receipt)
        updated["record_sha256"] = digest(updated)
        return updated

    def record_provider_dispatch_submission(
        self, dispatch_id: str, *, claim_token: str, now: str | None = None
    ) -> dict[str, Any]:
        current = now or utc_now()
        with self._action_coordination_locked():
            state = self._read_state()
            record = state.setdefault("provider_dispatches", {}).get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            self._verify_dispatch_record(record)
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id), dispatch_id
            )
            active = self._latest_claim(events)
            if active is None or active.get("claim_reference") != claim_token:
                raise RuntimeError("provider dispatch claim token is not current")
            if parse_utc(current) >= parse_utc(str(active["lease_expires_at"])):
                raise RuntimeError("provider dispatch claim lease expired")
            started = self._event(events, claim_token, "STARTED")
            if started is None:
                raise RuntimeError("provider dispatch attempt has not been started")
            existing = self._event(events, claim_token, "SUBMITTED")
            if existing is not None:
                return dict(existing)
            envelope = self.provider_dispatch_attempt_envelope(dispatch_id, claim_token=claim_token, now=current)
            submitted = self._append_claim_event(
                events, dispatch_id=dispatch_id, event_type="SUBMITTED", event_at=current,
                details={
                    "worker_id": active["worker_id"],
                    "claim_reference": claim_token,
                    "attempt": active["attempt"],
                    "fencing_epoch": started["fencing_epoch"],
                    "dispatch_attempt_reference": started["dispatch_attempt_reference"],
                    "provider_idempotency_key": record["provider_idempotency_key"],
                    "attempt_envelope_sha256": envelope["record_sha256"],
                    "submission_reference": digest({
                        "dispatch_id": dispatch_id,
                        "claim_reference": claim_token,
                        "attempt_envelope_sha256": envelope["record_sha256"],
                        "submitted_at": current,
                    }),
                    "lease_expires_at": active["lease_expires_at"],
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            self._ledger("C07", "provider_dispatch.submitted", dispatch_id, submitted)
            return dict(submitted)

    def _quarantine_locked(
        self, state: dict[str, Any], dispatch_id: str, events: list[dict[str, Any]],
        active: dict[str, Any], *, reason_class: str, event_at: str
    ) -> dict[str, Any]:
        claim = str(active["claim_reference"])
        submitted = self._event(events, claim, "SUBMITTED")
        if submitted is None:
            raise RuntimeError("provider dispatch attempt was not submitted")
        existing = self._event(events, claim, "OUTCOME_UNKNOWN")
        if existing is not None:
            return dict(existing)
        unknown = self._append_claim_event(
            events, dispatch_id=dispatch_id, event_type="OUTCOME_UNKNOWN", event_at=event_at,
            details={
                "worker_id": active["worker_id"],
                "claim_reference": claim,
                "attempt": active["attempt"],
                "fencing_epoch": submitted["fencing_epoch"],
                "dispatch_attempt_reference": submitted["dispatch_attempt_reference"],
                "submission_event_sha256": submitted["event_sha256"],
                "attempt_envelope_sha256": submitted["attempt_envelope_sha256"],
                "reason_class": reason_class,
                "reconciliation_required": True,
            },
        )
        state["provider_dispatches"][dispatch_id] = self._with_state(
            state["provider_dispatches"][dispatch_id],
            "PROVIDER_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED",
        )
        state["provider_dispatch_claim_history"][dispatch_id] = events
        self._write_state(state)
        self._ledger("C06", "provider_dispatch.outcome_quarantined", dispatch_id, unknown)
        return dict(unknown)

    def claim_provider_dispatch(
        self, dispatch_id: str, *, worker_id: str, lease_seconds: int = 60,
        now: str | None = None
    ) -> dict[str, Any]:
        current = now or utc_now()
        with self._action_coordination_locked():
            state = self._read_state()
            record = state.setdefault("provider_dispatches", {}).get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id), dispatch_id
            )
            if self._unresolved(events) is not None:
                raise RuntimeError("provider dispatch outcome unknown; reconciliation required")
            active = self._latest_claim(events)
            if active is not None and parse_utc(current) >= parse_utc(str(active["lease_expires_at"])):
                if self._event(events, str(active["claim_reference"]), "SUBMITTED") is not None:
                    self._quarantine_locked(
                        state, dispatch_id, events, active,
                        reason_class="LEASE_EXPIRED_AFTER_SUBMISSION", event_at=current,
                    )
                    raise RuntimeError("provider dispatch outcome unknown; reconciliation required")
            return super().claim_provider_dispatch(
                dispatch_id, worker_id=worker_id, lease_seconds=lease_seconds, now=current
            )

    def record_provider_dispatch_attempt_failure(
        self, dispatch_id: str, *, claim_token: str, error_class: str,
        retryable: bool, now: str | None = None
    ) -> dict[str, Any]:
        with self._action_coordination_locked():
            state = self._read_state()
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id), dispatch_id
            )
            if self._event(events, claim_token, "SUBMITTED") is not None:
                raise RuntimeError("submitted provider attempt requires outcome reconciliation")
            return super().record_provider_dispatch_attempt_failure(
                dispatch_id, claim_token=claim_token, error_class=error_class,
                retryable=retryable, now=now
            )

    @staticmethod
    def _verify_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        payload = dict(evidence)
        observed = payload.pop("reconciliation_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("provider reconciliation evidence hash invalid")
        if evidence.get("reconciliation_class") == LIVE_PROVIDER_RECONCILIATION_CLASS:
            raise RuntimeError("live provider reconciliation requires fresh provider proof")
        if evidence.get("reconciliation_class") != MOCK_PROVIDER_RECONCILIATION_CLASS:
            raise ValueError("unsupported provider reconciliation class")
        if evidence.get("external_mutation_performed") is not False:
            raise RuntimeError("mock reconciliation claimed external mutation")
        if evidence.get("live_provider_operation_proven") is not False:
            raise RuntimeError("mock reconciliation claimed live operation")
        return dict(evidence)

    def resolve_provider_dispatch_outcome(
        self, dispatch_id: str, evidence: dict[str, Any], *, now: str | None = None
    ) -> dict[str, Any]:
        current = now or utc_now()
        verified = self._verify_evidence(evidence)
        with self._action_coordination_locked():
            state = self._read_state()
            dispatches = state.setdefault("provider_dispatches", {})
            record = dispatches.get(dispatch_id)
            if record is None:
                raise KeyError("provider dispatch not found")
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id), dispatch_id
            )
            unknown = self._unresolved(events)
            if unknown is None:
                raise RuntimeError("provider dispatch has no unresolved outcome")
            claim = str(unknown["claim_reference"])
            started = self._event(events, claim, "STARTED")
            submitted = self._event(events, claim, "SUBMITTED")
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
                    events, dispatch_id=dispatch_id, event_type="OUTCOME_RESOLVED_NO_EFFECT", event_at=current,
                    details={
                        "worker_id": unknown["worker_id"],
                        "claim_reference": claim,
                        "attempt": unknown["attempt"],
                        "fencing_epoch": unknown["fencing_epoch"],
                        "dispatch_attempt_reference": unknown["dispatch_attempt_reference"],
                        "outcome_reconciliation_sha256": verified["reconciliation_sha256"],
                        "provider_effect_observed": False,
                    },
                )
                dispatches[dispatch_id] = self._with_state(record, "PREPARED_PROVIDER_PROOF_REQUIRED")
                state["provider_dispatch_claim_history"][dispatch_id] = events
                self._write_state(state)
                return {"outcome": OUTCOME_NO_EFFECT, "dispatch": dict(dispatches[dispatch_id]), "resolution_event": dict(resolved)}
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
                "MOCK_PROVIDER_FENCING_CONFORMANCE_VERIFIED_LIVE_PROVIDER_PROOF_REQUIRED",
                receipt,
            )
            dispatches[dispatch_id] = updated
            completed = self._append_claim_event(
                events, dispatch_id=dispatch_id, event_type="COMPLETED", event_at=current,
                details={
                    "worker_id": unknown["worker_id"],
                    "claim_reference": claim,
                    "attempt": unknown["attempt"],
                    "fencing_epoch": unknown["fencing_epoch"],
                    "dispatch_attempt_reference": unknown["dispatch_attempt_reference"],
                    "provider_receipt_sha256": receipt["provider_receipt_sha256"],
                    "completed_dispatch_record_sha256": updated["record_sha256"],
                    "outcome_reconciliation_sha256": verified["reconciliation_sha256"],
                },
            )
            state["provider_dispatch_claim_history"][dispatch_id] = events
            self._write_state(state)
            return {"outcome": OUTCOME_COMPLETED, "dispatch": dict(updated), "resolution_event": dict(completed)}

    def admit_provider_dispatch_receipt(
        self, dispatch_id: str, receipt: dict[str, Any], *, claim_token: str | None = None,
        now: str | None = None
    ) -> dict[str, Any]:
        with self._action_coordination_locked():
            state = self._read_state()
            events = self._verify_claim_history(
                state.setdefault("provider_dispatch_claim_history", {}).get(dispatch_id), dispatch_id
            )
            if self._unresolved(events) is not None:
                raise RuntimeError("unknown provider outcome requires reconciliation evidence")
            return super().admit_provider_dispatch_receipt(
                dispatch_id, receipt, claim_token=claim_token, now=now
            )

    def _verify_provider_dispatch_attempt_state(self) -> bool:
        super()._verify_provider_dispatch_attempt_state()
        state = self._read_state()
        for dispatch_id, raw in state.get("provider_dispatch_claim_history", {}).items():
            events = self._verify_claim_history(raw, dispatch_id)
            unresolved = self._unresolved(events)
            for claim in [e for e in events if e.get("event_type") == "CLAIMED"]:
                ref = str(claim["claim_reference"])
                started = self._event(events, ref, "STARTED")
                submitted = self._event(events, ref, "SUBMITTED")
                unknown = self._event(events, ref, "OUTCOME_UNKNOWN")
                if submitted and (not started or submitted["dispatch_attempt_reference"] != started["dispatch_attempt_reference"]):
                    raise RuntimeError("provider submission binding invalid")
                if unknown and (not submitted or unknown["submission_event_sha256"] != submitted["event_sha256"]):
                    raise RuntimeError("provider outcome submission chain invalid")
            record = state.get("provider_dispatches", {}).get(dispatch_id, {})
            if unresolved is not None and record.get("state") != "PROVIDER_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED":
                raise RuntimeError("unresolved provider outcome state invalid")
        return True

    def provider_dispatch_outcome_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            self._verify_provider_dispatch_attempt_state()
            histories = self._read_state().get("provider_dispatch_claim_history", {})
            events = [event for history in histories.values() for event in history]
            return {
                "capability_revision": self.CAPABILITY_REVISION,
                "integrity": "VERIFIED",
                "stage_scope": list(self.STAGE_SCOPE),
                "submitted_attempts": sum(e.get("event_type") == "SUBMITTED" for e in events),
                "quarantined_outcomes": sum(e.get("event_type") == "OUTCOME_UNKNOWN" for e in events),
                "unresolved_outcomes": sum(self._unresolved(h) is not None for h in histories.values()),
                "resolved_no_effect": sum(e.get("event_type") == "OUTCOME_RESOLVED_NO_EFFECT" for e in events),
                "resolved_completed": sum(e.get("event_type") == "COMPLETED" and bool(e.get("outcome_reconciliation_sha256")) for e in events),
                "submission_boundary_is_durable": True,
                "expired_submitted_attempt_is_quarantined": True,
                "unresolved_outcome_blocks_takeover": True,
                "no_effect_resolution_releases_retry": True,
                "completed_resolution_admits_original_receipt": True,
                "mock_reconciliation_conformance": True,
                "provider_native_reconciliation_proven": False,
                "external_mutation_performed": False,
                "live_provider_operation_proven": False,
                "distributed_provider_exactly_once_proven": False,
            }

    def governed_authority_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().governed_authority_readback()
            result["canonical_class"] = self.__class__.__name__
            result["predecessor_class"] = "FencedProviderDispatchCommercialControlPlane"
            result["provider_dispatch_outcome_reconciliation"] = self.provider_dispatch_outcome_readback()
            return result
