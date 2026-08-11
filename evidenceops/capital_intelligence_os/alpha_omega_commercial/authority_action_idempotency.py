from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterator

from authority_action_coordination import (
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from commercial_assurance import EvidenceReference, _OWNER_RESERVED_SERVICE_REQUESTS
from governed_commercial_assurance import utc_now


class IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane
):
    """V10 managed-service control plane with crash-safe exact-request replay.

    V9 serializes provider-process startup, recovery, actions and readback. A
    caller retry after an uncertain response could still execute a completed
    owner-reserved action a second time. V10 binds a canonical request intent to
    the same state object and atomic transaction that records the action. Exact
    retries return the committed record without consuming authority again;
    conflicting reuse of the same object identity fails closed.
    """

    CAPABILITY_REVISION = "AO-COMMERCIAL-AUTHORITY-ACTION-IDEMPOTENCY-V10"
    _ACTION_COLLECTIONS = {
        "service_request": "service_requests",
        "quote_approval": "quotes",
        "outcome_study": "case_studies",
        "revenue_event": "revenue_events",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._idempotency_local = threading.local()
        super().__init__(*args, **kwargs)
        self._verify_idempotency_state()

    @staticmethod
    def _evidence_reference_payload(item: EvidenceReference) -> dict[str, Any]:
        return {
            "reference_id": item.reference_id,
            "provider": item.provider,
            "locator": item.locator,
            "sha256": item.sha256,
            "observed_at": item.observed_at,
            "evidence_class": item.evidence_class,
        }

    @staticmethod
    def _provider_evidence_payload(evidence: Any) -> dict[str, Any]:
        return {
            "evidence_id": getattr(evidence, "evidence_id", None),
            "gate": getattr(evidence, "gate", None),
            "provider": getattr(evidence, "provider", None),
            "locator": getattr(evidence, "locator", None),
            "observed_at": getattr(evidence, "observed_at", None),
            "content_sha256": getattr(evidence, "content_sha256", None),
            "owner_decision_receipt_id": getattr(
                evidence, "owner_decision_receipt_id", None
            ),
            "claims": getattr(evidence, "claims", None),
        }

    @staticmethod
    def _intent_sha256(
        *, action: str, object_id: str, subject: dict[str, Any]
    ) -> str:
        return digest(
            {
                "action": action,
                "object_id": object_id,
                "subject": subject,
            }
        )

    @contextmanager
    def _active_idempotency_intent(
        self,
        *,
        action: str,
        object_id: str,
        intent_sha256: str,
    ) -> Iterator[None]:
        if getattr(self._idempotency_local, "intent", None) is not None:
            raise RuntimeError("nested authority action idempotency intents are not allowed")
        self._idempotency_local.intent = {
            "action": action,
            "object_id": object_id,
            "intent_sha256": intent_sha256,
        }
        try:
            yield
        finally:
            self._idempotency_local.intent = None

    def _verify_idempotency_seal(
        self,
        record: dict[str, Any],
        *,
        expected_action: str | None = None,
        expected_object_id: str | None = None,
        expected_intent_sha256: str | None = None,
    ) -> dict[str, Any] | None:
        seal = record.get("authority_action_idempotency")
        commit = record.get("authority_action_commit")
        if seal is None:
            if commit is not None:
                raise RuntimeError(
                    "committed authority action lacks an idempotency seal"
                )
            return None
        if not isinstance(seal, dict):
            raise RuntimeError("authority action idempotency seal invalid")
        payload = dict(seal)
        observed = payload.pop("seal_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("authority action idempotency seal hash invalid")
        if seal.get("state") != "EXACT_REPLAY_SAFE":
            raise RuntimeError("authority action idempotency state invalid")
        if commit is None:
            raise RuntimeError("idempotency seal lacks committed authority action")
        if seal.get("transaction_id") != commit.get("transaction_id"):
            raise RuntimeError("idempotency seal transaction binding invalid")
        if expected_action is not None and seal.get("action") != expected_action:
            raise ValueError("idempotency object identity already used by another action")
        if expected_object_id is not None and seal.get("object_id") != expected_object_id:
            raise RuntimeError("idempotency seal object binding invalid")
        if (
            expected_intent_sha256 is not None
            and seal.get("intent_sha256") != expected_intent_sha256
        ):
            raise ValueError("idempotency conflict: object identity reused with new intent")
        return dict(seal)

    def _existing_idempotent_result(
        self,
        *,
        action: str,
        object_id: str,
        intent_sha256: str,
    ) -> dict[str, Any] | None:
        collection = self._ACTION_COLLECTIONS[action]
        record = self._read_state().get(collection, {}).get(object_id)
        if record is None:
            return None
        seal = self._verify_idempotency_seal(
            record,
            expected_action=action,
            expected_object_id=object_id,
            expected_intent_sha256=intent_sha256,
        )
        if seal is None:
            return None
        return dict(record)

    def _seal_state_object(
        self,
        *,
        stage: str,
        event: str,
        collection: str,
        object_id: str,
        transaction: dict[str, Any],
    ) -> dict[str, Any]:
        stored = super()._seal_state_object(
            stage=stage,
            event=event,
            collection=collection,
            object_id=object_id,
            transaction=transaction,
        )
        intent = getattr(self._idempotency_local, "intent", None)
        if intent is None:
            raise RuntimeError("authority action idempotency intent missing")
        expected_collection = self._ACTION_COLLECTIONS.get(intent["action"])
        if expected_collection != collection or intent["object_id"] != object_id:
            raise RuntimeError("authority action idempotency intent binding invalid")
        seal = {
            "state": "EXACT_REPLAY_SAFE",
            "action": intent["action"],
            "object_id": object_id,
            "intent_sha256": intent["intent_sha256"],
            "transaction_id": transaction["transaction_id"],
            "snapshot_sha256": transaction["snapshot_sha256"],
            "acceptance_entry_sha256": transaction["acceptance_entry_sha256"],
        }
        seal["seal_sha256"] = digest(seal)
        state = self._read_state()
        state[collection][object_id]["authority_action_idempotency"] = seal
        self._write_state(state)
        stored = state[collection][object_id]
        self._ledger(stage, event + ".idempotency", object_id, stored)
        return stored

    def submit_service_request(
        self,
        request_id: str,
        tenant_id: str,
        request_type: str,
        payload: dict[str, Any],
        requested_by: str,
        *,
        owner_decision_receipt_id: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if (
            self.authority_profile != "LIVE_PROVIDER_AUTHORITY"
            or request_type not in _OWNER_RESERVED_SERVICE_REQUESTS
        ):
            return super().submit_service_request(
                request_id,
                tenant_id,
                request_type,
                payload,
                requested_by,
                owner_decision_receipt_id=owner_decision_receipt_id,
                now=now,
            )
        current = now or utc_now()
        subject = {
            "tenant_id": tenant_id,
            "request_type": request_type,
            "payload": payload,
            "requested_by": requested_by,
            "owner_decision_receipt_id": owner_decision_receipt_id,
        }
        intent_sha = self._intent_sha256(
            action="service_request", object_id=request_id, subject=subject
        )
        with self._action_coordination_locked():
            existing = self._existing_idempotent_result(
                action="service_request",
                object_id=request_id,
                intent_sha256=intent_sha,
            )
            if existing is not None:
                return existing
            with self._active_idempotency_intent(
                action="service_request",
                object_id=request_id,
                intent_sha256=intent_sha,
            ):
                return super().submit_service_request(
                    request_id,
                    tenant_id,
                    request_type,
                    payload,
                    requested_by,
                    owner_decision_receipt_id=owner_decision_receipt_id,
                    now=current,
                )

    def approve_quote(
        self,
        quote_id: str,
        *,
        owner_decision_receipt_id: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if self.authority_profile != "LIVE_PROVIDER_AUTHORITY":
            return super().approve_quote(
                quote_id,
                owner_decision_receipt_id=owner_decision_receipt_id,
                now=now,
            )
        current = now or utc_now()
        subject = {
            "quote": self.quote_authority_subject(quote_id)["subject"],
            "owner_decision_receipt_id": owner_decision_receipt_id,
        }
        intent_sha = self._intent_sha256(
            action="quote_approval", object_id=quote_id, subject=subject
        )
        with self._action_coordination_locked():
            existing = self._existing_idempotent_result(
                action="quote_approval",
                object_id=quote_id,
                intent_sha256=intent_sha,
            )
            if existing is not None:
                return existing
            with self._active_idempotency_intent(
                action="quote_approval",
                object_id=quote_id,
                intent_sha256=intent_sha,
            ):
                return super().approve_quote(
                    quote_id,
                    owner_decision_receipt_id=owner_decision_receipt_id,
                    now=current,
                )

    def register_outcome_study(
        self,
        study_id: str,
        tenant_id: str,
        metric: str,
        baseline: float,
        outcome: float,
        unit: str,
        lower_is_better: bool,
        evidence: list[EvidenceReference],
        *,
        external_evidence_id: str | None = None,
    ) -> dict[str, Any]:
        if (
            self.authority_profile != "LIVE_PROVIDER_AUTHORITY"
            or not external_evidence_id
        ):
            return super().register_outcome_study(
                study_id,
                tenant_id,
                metric,
                baseline,
                outcome,
                unit,
                lower_is_better,
                evidence,
                external_evidence_id=external_evidence_id,
            )
        subject = {
            "tenant_id": tenant_id,
            "metric": metric,
            "baseline": baseline,
            "outcome": outcome,
            "unit": unit,
            "lower_is_better": lower_is_better,
            "evidence": [self._evidence_reference_payload(item) for item in evidence],
            "external_evidence_id": external_evidence_id,
        }
        intent_sha = self._intent_sha256(
            action="outcome_study", object_id=study_id, subject=subject
        )
        with self._action_coordination_locked():
            existing = self._existing_idempotent_result(
                action="outcome_study",
                object_id=study_id,
                intent_sha256=intent_sha,
            )
            if existing is not None:
                return existing
            with self._active_idempotency_intent(
                action="outcome_study",
                object_id=study_id,
                intent_sha256=intent_sha,
            ):
                return super().register_outcome_study(
                    study_id,
                    tenant_id,
                    metric,
                    baseline,
                    outcome,
                    unit,
                    lower_is_better,
                    evidence,
                    external_evidence_id=external_evidence_id,
                )

    def register_verified_revenue_event(
        self,
        event_id: str,
        contract_id: str,
        amount: float,
        currency: str,
        provider_evidence: Any,
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        if self.authority_profile != "LIVE_PROVIDER_AUTHORITY":
            return super().register_verified_revenue_event(
                event_id,
                contract_id,
                amount,
                currency,
                provider_evidence,
                now=now,
            )
        current = now or utc_now()
        subject = {
            "contract_id": contract_id,
            "amount": round(float(amount), 2),
            "currency": currency,
            "provider_evidence": self._provider_evidence_payload(provider_evidence),
        }
        intent_sha = self._intent_sha256(
            action="revenue_event", object_id=event_id, subject=subject
        )
        with self._action_coordination_locked():
            existing = self._existing_idempotent_result(
                action="revenue_event",
                object_id=event_id,
                intent_sha256=intent_sha,
            )
            if existing is not None:
                return existing
            with self._active_idempotency_intent(
                action="revenue_event",
                object_id=event_id,
                intent_sha256=intent_sha,
            ):
                return super().register_verified_revenue_event(
                    event_id,
                    contract_id,
                    amount,
                    currency,
                    provider_evidence,
                    now=current,
                )

    def _verify_idempotency_state(self) -> bool:
        state = self._read_state()
        for action, collection in self._ACTION_COLLECTIONS.items():
            for object_id, record in state.get(collection, {}).items():
                seal = record.get("authority_action_idempotency")
                if seal is not None:
                    self._verify_idempotency_seal(
                        record,
                        expected_action=action,
                        expected_object_id=object_id,
                    )
        return True

    def authority_action_idempotency_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            self._verify_idempotency_state()
            state = self._read_state()
            sealed = {
                action: sum(
                    1
                    for record in state.get(collection, {}).values()
                    if record.get("authority_action_idempotency") is not None
                )
                for action, collection in self._ACTION_COLLECTIONS.items()
            }
            return {
                "capability_revision": self.CAPABILITY_REVISION,
                "integrity": "VERIFIED",
                "exact_retry_returns_committed_record": True,
                "retry_consumes_owner_authority_again": False,
                "conflicting_object_identity_reuse_rejected": True,
                "idempotency_seal_committed_in_atomic_transaction": True,
                "restart_safe": True,
                "sealed_objects": sealed,
            }

    def governed_authority_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().governed_authority_readback()
            result["canonical_class"] = self.__class__.__name__
            result["predecessor_class"] = (
                "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane"
            )
            result["authority_action_idempotency"] = (
                self.authority_action_idempotency_readback()
            )
            return result
