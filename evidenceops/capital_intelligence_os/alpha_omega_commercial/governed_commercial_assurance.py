from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from commercial_assurance import (
    CommercialAssuranceControlPlane,
    EvidenceReference,
    _OWNER_RESERVED_SERVICE_REQUESTS,
    digest,
    utc_now,
)
from external_evidence import (
    EvidenceEnvelope,
    ExternalEvidenceAdmissionController,
)
from owner_authority import OwnerAuthorityValidator, OwnerDecisionReceipt


LIVE_AUTHORITY_CLASS = "LIVE_PROVIDER_NATIVE"
MOCK_AUTHORITY_CLASS = "MOCK_PROVIDER_CONFORMANCE"

SERVICE_REQUEST_GATE = "consequential_service_request"
QUOTE_PRESENTATION_GATE = "external_quote_presentation"
PAYMENT_REVENUE_GATE = "payment_provider_revenue"


class GovernedCommercialAssuranceControlPlane(CommercialAssuranceControlPlane):
    """Canonical C10-C15 control plane with provider-backed owner authority.

    The legacy reference class remains available for regression compatibility, but
    this class is the only canonical public entry point for owner-reserved actions.
    Public callers cannot supply approval booleans or arbitrary approval strings.
    """

    def __init__(
        self,
        state_dir: str | Path,
        *,
        authority: dict[str, dict[str, Any]] | None = None,
        owner_receipts: dict[str, OwnerDecisionReceipt] | None = None,
        authority_profile: str = "LIVE_PROVIDER_AUTHORITY",
    ) -> None:
        super().__init__(state_dir)
        self.authority = dict(authority or {})
        self.authority_profile = authority_profile
        self.owner_receipts = dict(owner_receipts or {})
        self.owner_validator = OwnerAuthorityValidator(self.owner_receipts)
        self.governance_state_file = self.state_dir / "governed_authority_state.json"
        self.governance_ledger_file = self.state_dir / "governed_authority_ledger.jsonl"
        self.external_controller = ExternalEvidenceAdmissionController(
            self.state_dir / "governed_external_evidence",
            self.authority,
            owner_receipts=self.owner_receipts,
        )
        if self.governance_state_file.exists():
            current = self._read_governance_state()
            if current.get("authority_profile") != authority_profile:
                raise ValueError("authority profile does not match persisted governed state")
        self._rebuild_governance_state()

    @staticmethod
    def canonical_public_signatures() -> dict[str, str]:
        methods = (
            "submit_service_request",
            "approve_quote",
            "register_outcome_study",
            "register_verified_revenue_event",
        )
        return {
            name: str(inspect.signature(getattr(GovernedCommercialAssuranceControlPlane, name)))
            for name in methods
        }

    def service_request_authority_subject(
        self,
        request_id: str,
        tenant_id: str,
        request_type: str,
        payload: dict[str, Any],
        requested_by: str,
    ) -> dict[str, Any]:
        subject = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "request_type": request_type,
            "payload": payload,
            "requested_by": requested_by,
            "external_effects_allowed": False,
        }
        return {
            "gate": SERVICE_REQUEST_GATE,
            "evidence_id": f"service-request:{request_id}",
            "content_sha256": digest(subject),
            "subject": subject,
        }

    def quote_authority_subject(self, quote_id: str) -> dict[str, Any]:
        quote = self._read_state()["quotes"][quote_id]
        subject = {
            "quote_id": quote_id,
            "lead_id": quote["lead_id"],
            "offer_id": quote["offer_id"],
            "currency": quote["currency"],
            "amount": quote["amount"],
            "term_months": quote["term_months"],
            "action": "APPROVE_FOR_EXTERNAL_PRESENTATION_NOT_SEND",
            "financial_commitment": False,
        }
        return {
            "gate": QUOTE_PRESENTATION_GATE,
            "evidence_id": f"quote-presentation:{quote_id}",
            "content_sha256": digest(subject),
            "subject": subject,
        }

    def revenue_authority_subject(
        self,
        event_id: str,
        contract_id: str,
        amount: float,
        currency: str,
        provider_evidence: EvidenceEnvelope,
    ) -> dict[str, Any]:
        subject = {
            "event_id": event_id,
            "contract_id": contract_id,
            "amount": round(float(amount), 2),
            "currency": currency,
            "payment_evidence_id": provider_evidence.evidence_id,
            "payment_content_sha256": provider_evidence.content_sha256,
            "provider": provider_evidence.provider,
            "locator": provider_evidence.locator,
        }
        return {
            "gate": PAYMENT_REVENUE_GATE,
            "evidence_id": provider_evidence.evidence_id,
            "content_sha256": provider_evidence.content_sha256,
            "subject_sha256": digest(subject),
            "subject": subject,
        }

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
        reserved = request_type in _OWNER_RESERVED_SERVICE_REQUESTS
        if not reserved:
            return super().submit_service_request(
                request_id,
                tenant_id,
                request_type,
                payload,
                requested_by,
                False,
            )

        subject = self.service_request_authority_subject(
            request_id,
            tenant_id,
            request_type,
            payload,
            requested_by,
        )
        validation = self._require_owner_decision(
            owner_decision_receipt_id,
            subject["gate"],
            subject["evidence_id"],
            subject["content_sha256"],
            now=now,
        )
        super().submit_service_request(
            request_id,
            tenant_id,
            request_type,
            payload,
            requested_by,
            True,
        )
        state = self._read_state()
        stored = state["service_requests"][request_id]
        stored.update(
            {
                "owner_decision_receipt_id": owner_decision_receipt_id,
                "owner_decision_receipt_sha256": validation["receipt_sha256"],
                "authority_profile": self.authority_profile,
                "external_effects_allowed": False,
                "status": "ACCEPTED_REFERENCE_EXECUTION_PENDING",
            }
        )
        self._write_state(state)
        self._record_approval(
            owner_decision_receipt_id,
            subject["evidence_id"],
            subject["gate"],
            validation["receipt_sha256"],
        )
        self._ledger("C11", "service.owner-authority", request_id, stored)
        return stored

    def approve_quote(
        self,
        quote_id: str,
        *,
        owner_decision_receipt_id: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        subject = self.quote_authority_subject(quote_id)
        validation = self._require_owner_decision(
            owner_decision_receipt_id,
            subject["gate"],
            subject["evidence_id"],
            subject["content_sha256"],
            now=now,
        )
        super().approve_quote(
            quote_id,
            f"owner-decision-receipt:{owner_decision_receipt_id}",
        )
        state = self._read_state()
        stored = state["quotes"][quote_id]
        stored.update(
            {
                "owner_decision_receipt_id": owner_decision_receipt_id,
                "owner_decision_receipt_sha256": validation["receipt_sha256"],
                "authority_profile": self.authority_profile,
                "external_send_performed": False,
                "financial_commitment": False,
            }
        )
        self._write_state(state)
        self._record_approval(
            owner_decision_receipt_id,
            subject["evidence_id"],
            subject["gate"],
            validation["receipt_sha256"],
        )
        self._ledger("C13", "quote.owner-authority", quote_id, stored)
        return stored

    def admit_external_evidence(
        self,
        evidence: EvidenceEnvelope,
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate external evidence through the canonical fail-closed controller."""
        return self.external_controller.admit(evidence, now=now)

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
        external_admitted = False
        if external_evidence_id:
            decision = self.external_controller.decisions.get(external_evidence_id)
            external_admitted = bool(
                decision
                and decision.get("admitted")
                and decision.get("gate") == "external_case_study"
                and self._live_authority_verified("customer_market")
                and self._live_authority_verified("owner_decision")
            )
        evidence_origin = (
            "EXTERNAL_CUSTOMER_VERIFIED"
            if external_admitted
            else "REFERENCE_PROVIDER_SYNTHETIC"
        )
        safe_evidence = evidence
        if not external_admitted:
            safe_evidence = [
                EvidenceReference(
                    reference_id=item.reference_id,
                    provider=item.provider,
                    locator=item.locator,
                    sha256=item.sha256,
                    observed_at=item.observed_at,
                    evidence_class="REFERENCE_PROVIDER",
                )
                for item in evidence
            ]
        super().register_outcome_study(
            study_id,
            tenant_id,
            metric,
            baseline,
            outcome,
            unit,
            lower_is_better,
            safe_evidence,
            evidence_origin,
        )
        state = self._read_state()
        stored = state["case_studies"][study_id]
        stored.update(
            {
                "external_evidence_id": external_evidence_id,
                "external_admission_verified": external_admitted,
                "authority_profile": self.authority_profile,
            }
        )
        if not external_admitted:
            stored["status"] = "MARKET_PROOF_REQUIRED"
        self._write_state(state)
        self._ledger("C12", "study.governed-admission", study_id, stored)
        return stored

    def register_verified_revenue_event(
        self,
        event_id: str,
        contract_id: str,
        amount: float,
        currency: str,
        provider_evidence: EvidenceEnvelope,
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        if provider_evidence.gate != PAYMENT_REVENUE_GATE:
            raise ValueError("provider evidence must target payment_provider_revenue")
        if provider_evidence.claims.get("contract_id") != contract_id:
            raise ValueError("payment evidence contract_id mismatch")
        if provider_evidence.claims.get("currency") != currency:
            raise ValueError("payment evidence currency mismatch")
        try:
            claimed_amount = round(float(provider_evidence.claims.get("amount")), 2)
        except (TypeError, ValueError) as exc:
            raise ValueError("payment evidence amount is invalid") from exc
        if claimed_amount != round(float(amount), 2):
            raise ValueError("payment evidence amount mismatch")
        if provider_evidence.claims.get("settled") is not True:
            raise ValueError("payment evidence must prove settlement")

        governance = self._read_governance_state()
        receipt_id = provider_evidence.owner_decision_receipt_id
        if receipt_id and receipt_id in governance["consumed_owner_receipts"]:
            existing = governance["consumed_owner_receipts"][receipt_id]
            if existing != provider_evidence.evidence_id:
                raise PermissionError("owner decision receipt already consumed")

        decision = self.external_controller.admit(provider_evidence, now=now)
        if not decision.get("admitted"):
            raise PermissionError(
                "payment evidence admission failed: " + ",".join(decision.get("reasons", []))
            )

        is_live = (
            self.authority_profile == "LIVE_PROVIDER_AUTHORITY"
            and self._live_authority_verified("payment_provider")
            and self._live_authority_verified("owner_decision")
        )
        provider_receipt = EvidenceReference(
            reference_id=provider_evidence.evidence_id,
            provider=provider_evidence.provider,
            locator=provider_evidence.locator,
            sha256=provider_evidence.content_sha256,
            observed_at=provider_evidence.observed_at,
            evidence_class="PAYMENT_PROVIDER_VERIFIED",
        )
        super().register_verified_revenue_event(
            event_id,
            contract_id,
            amount,
            currency,
            provider_receipt,
            True,
        )
        state = self._read_state()
        stored = state["revenue_events"][event_id]
        stored.update(
            {
                "external_evidence_admission": decision,
                "owner_decision_receipt_id": receipt_id,
                "authority_profile": self.authority_profile,
                "live_revenue_recognition": is_live,
                "status": (
                    "PAYMENT_PROVIDER_VERIFIED_OWNER_RECEIPT_VERIFIED"
                    if is_live
                    else "MOCK_PAYMENT_PROVIDER_CONFORMANCE_ONLY"
                ),
            }
        )
        self._write_state(state)
        if receipt_id:
            receipt_sha = decision.get("owner_decision_receipt_sha256")
            self._record_approval(
                receipt_id,
                provider_evidence.evidence_id,
                PAYMENT_REVENUE_GATE,
                receipt_sha,
            )
        self._ledger("C13", "revenue.governed-admission", event_id, stored)
        return stored

    def governed_revenue_dashboard(self) -> dict[str, Any]:
        state = self._read_state()
        live = [
            item
            for item in state["revenue_events"].values()
            if item.get("live_revenue_recognition") is True
            and item.get("status") == "PAYMENT_PROVIDER_VERIFIED_OWNER_RECEIPT_VERIFIED"
        ]
        mock = [
            item
            for item in state["revenue_events"].values()
            if item.get("status") == "MOCK_PAYMENT_PROVIDER_CONFORMANCE_ONLY"
        ]
        by_currency: dict[str, float] = {}
        for event in live:
            currency = event["currency"]
            by_currency[currency] = round(
                by_currency.get(currency, 0.0) + float(event["amount"]),
                2,
            )
        return {
            "live_verified_revenue_events": len(live),
            "live_verified_revenue_by_currency": by_currency,
            "mock_provider_conformance_events": len(mock),
            "authority_profile": self.authority_profile,
            "truth_boundary": (
                "Mock-provider conformance is never counted as revenue. Live revenue "
                "requires fresh live payment-provider authority and a provider-backed "
                "owner decision receipt."
            ),
        }

    def governed_authority_readback(self) -> dict[str, Any]:
        state = self._read_governance_state()
        signatures = self.canonical_public_signatures()
        forbidden = ("owner_confirmed", "owner_approved", "owner_approval_reference")
        return {
            "canonical_class": self.__class__.__name__,
            "legacy_class": "REFERENCE_ONLY_NOT_CANONICAL",
            "authority_profile": self.authority_profile,
            "public_signatures": signatures,
            "caller_set_approval_parameters_absent": all(
                token not in signature
                for signature in signatures.values()
                for token in forbidden
            ),
            "consumed_owner_receipts": dict(
                sorted(state["consumed_owner_receipts"].items())
            ),
            "approval_count": len(state["approved_objects"]),
            "authority_ledger_integrity": self.verify_governance_ledger(),
            "external_evidence_ledger_integrity": self.external_controller.verify_ledger(),
            "revenue": self.governed_revenue_dashboard(),
        }

    def verify_governance_ledger(self) -> bool:
        previous = "GENESIS"
        for event in self._read_jsonl(self.governance_ledger_file):
            if event.get("previous_hash") != previous:
                return False
            payload = {key: value for key, value in event.items() if key != "event_hash"}
            if digest(payload) != event.get("event_hash"):
                return False
            previous = event["event_hash"]
        return True

    def _require_owner_decision(
        self,
        receipt_id: str | None,
        gate: str,
        evidence_id: str,
        content_sha256: str,
        *,
        now: str | None,
    ) -> dict[str, Any]:
        state = self._read_governance_state()
        validation = self.owner_validator.validate(
            receipt_id=receipt_id,
            gate=gate,
            evidence_id=evidence_id,
            evidence_content_sha256=content_sha256,
            authority=self.authority,
            now=now or utc_now(),
            consumed_by=state["consumed_owner_receipts"],
        )
        reasons = list(validation.reasons)
        if (
            self.authority_profile == "LIVE_PROVIDER_AUTHORITY"
            and not self._live_authority_verified("owner_decision")
        ):
            reasons.append("LIVE_OWNER_DECISION_AUTHORITY_NOT_VERIFIED")
        if reasons:
            raise PermissionError("owner authority validation failed: " + ",".join(sorted(set(reasons))))
        return {
            "receipt_id": validation.receipt_id,
            "receipt_sha256": validation.receipt_sha256,
        }

    def _record_approval(
        self,
        receipt_id: str | None,
        evidence_id: str,
        gate: str,
        receipt_sha256: str | None,
    ) -> None:
        if not receipt_id:
            raise PermissionError("owner decision receipt is required")
        state = self._read_governance_state()
        existing = state["consumed_owner_receipts"].get(receipt_id)
        if existing is not None and existing != evidence_id:
            raise PermissionError("owner decision receipt already consumed")
        if existing == evidence_id:
            return
        self._append_governance_event(
            "OWNER_DECISION_CONSUMED",
            {
                "receipt_id": receipt_id,
                "evidence_id": evidence_id,
                "gate": gate,
                "receipt_sha256": receipt_sha256,
                "authority_profile": self.authority_profile,
            },
        )
        self._rebuild_governance_state()

    def _live_authority_verified(self, domain: str) -> bool:
        item = self.authority.get(domain, {})
        return (
            item.get("state") == "FRESH_VERIFIED"
            and item.get("authority_class") == LIVE_AUTHORITY_CLASS
        )

    def _append_governance_event(self, event_type: str, payload: dict[str, Any]) -> None:
        events = self._read_jsonl(self.governance_ledger_file)
        event = {
            "event_id": f"governed-authority-{len(events) + 1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
            "previous_hash": events[-1]["event_hash"] if events else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.governance_ledger_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _rebuild_governance_state(self) -> None:
        state = {
            "authority_profile": self.authority_profile,
            "consumed_owner_receipts": {},
            "approved_objects": {},
            "ledger_head": "GENESIS",
        }
        events = self._read_jsonl(self.governance_ledger_file)
        previous = "GENESIS"
        for event in events:
            if event.get("previous_hash") != previous:
                raise RuntimeError("governed authority ledger chain is invalid")
            payload_without_hash = {
                key: value for key, value in event.items() if key != "event_hash"
            }
            if digest(payload_without_hash) != event.get("event_hash"):
                raise RuntimeError("governed authority ledger hash is invalid")
            previous = event["event_hash"]
            if event.get("event_type") == "OWNER_DECISION_CONSUMED":
                payload = event["payload"]
                receipt_id = payload["receipt_id"]
                evidence_id = payload["evidence_id"]
                existing = state["consumed_owner_receipts"].get(receipt_id)
                if existing is not None and existing != evidence_id:
                    raise RuntimeError("owner receipt ledger contains conflicting consumption")
                state["consumed_owner_receipts"][receipt_id] = evidence_id
                state["approved_objects"][evidence_id] = {
                    "gate": payload["gate"],
                    "receipt_id": receipt_id,
                    "receipt_sha256": payload.get("receipt_sha256"),
                    "recorded_at": event["recorded_at"],
                }
        state["ledger_head"] = previous
        self._write_governance_state(state)

    def _read_governance_state(self) -> dict[str, Any]:
        return json.loads(self.governance_state_file.read_text(encoding="utf-8"))

    def _write_governance_state(self, value: dict[str, Any]) -> None:
        temporary = self.governance_state_file.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.governance_state_file)
