from __future__ import annotations

from pathlib import Path
from typing import Any

from authority_snapshot import (
    CommercialAuthoritySnapshot,
    CommercialAuthoritySnapshotValidator,
    digest,
)
from authority_snapshot_acceptance import AuthoritySnapshotAcceptanceLedger
from commercial_assurance import EvidenceReference, _OWNER_RESERVED_SERVICE_REQUESTS
from governed_commercial_assurance import (
    GovernedCommercialAssuranceControlPlane,
    LIVE_AUTHORITY_CLASS,
    utc_now,
)


LIVE_PROFILE = "LIVE_PROVIDER_AUTHORITY"

REQUIRED_SCOPE = {
    "owner_decision": ("owner_identity_verification", "decision_receipt_issue"),
    "payment_provider": ("settlement_readback", "receipt_verification"),
    "customer_market": ("customer_identity", "outcome_evidence"),
}


class AuthoritySnapshotCommercialControlPlane(GovernedCommercialAssuranceControlPlane):
    """Canonical commercial control plane with evidence-bound authority freshness.

    The v2 governed control plane removed caller-set approval shortcuts. This v5
    wrapper closes the remaining authority-use gap: live authority is admitted only
    through a hash-valid, scope-complete, non-expired snapshot, an older valid
    snapshot cannot be replayed, and every consequential use is bound to the exact
    latest durable acceptance entry.
    """

    def __init__(
        self,
        state_dir: str | Path,
        *,
        authority_snapshot: CommercialAuthoritySnapshot | dict[str, Any] | None = None,
        authority: dict[str, dict[str, Any]] | None = None,
        owner_receipts: dict[str, Any] | None = None,
        authority_profile: str = LIVE_PROFILE,
    ) -> None:
        self.authority_snapshot_validator = CommercialAuthoritySnapshotValidator(
            authority_snapshot
        )
        self.authority_snapshot_acceptance = AuthoritySnapshotAcceptanceLedger(
            Path(state_dir) / "authority_snapshot_acceptance"
        )
        self.raw_authority_input = dict(authority or {})
        if authority_profile == LIVE_PROFILE:
            governed_authority = self.authority_snapshot_validator.authority_view(
                now=utc_now()
            )
        else:
            governed_authority = self.raw_authority_input
        super().__init__(
            state_dir,
            authority=governed_authority,
            owner_receipts=owner_receipts,
            authority_profile=authority_profile,
        )

    def accept_authority_snapshot(self, *, now: str | None = None) -> dict[str, Any]:
        """Persist one monotonic provider-native authority-snapshot acceptance.

        The operation is internal and reversible only through state restoration. It
        does not perform a customer, payment, cloud, communication or contract action.
        """

        current = now or utc_now()
        return self.authority_snapshot_acceptance.accept(
            self.authority_snapshot_validator.snapshot,
            self.authority_snapshot_validator,
            required_scope=REQUIRED_SCOPE,
            now=current,
        )

    def authority_snapshot_readback(self, *, now: str | None = None) -> dict[str, Any]:
        current = now or utc_now()
        snapshot = self.authority_snapshot_validator.snapshot
        domains: dict[str, Any] = {}
        if snapshot is not None:
            for domain in sorted(snapshot.domains):
                decision = self.authority_snapshot_validator.validate_domain(
                    domain,
                    required_scope=REQUIRED_SCOPE.get(domain, ()),
                    now=current,
                )
                domains[domain] = {
                    "valid": decision.valid,
                    "reasons": list(decision.reasons),
                    "snapshot_id": decision.snapshot_id,
                    "snapshot_sha256": decision.snapshot_sha256,
                    "evidence_sha256": decision.evidence_sha256,
                }
        return {
            "canonical_class": self.__class__.__name__,
            "authority_profile": self.authority_profile,
            "snapshot_present": snapshot is not None,
            "snapshot_id": snapshot.snapshot_id if snapshot else None,
            "snapshot_sha256": snapshot.snapshot_sha256 if snapshot else None,
            "domains": domains,
            "acceptance": self.authority_snapshot_acceptance.readback(
                snapshot,
                self.authority_snapshot_validator,
                required_scope=REQUIRED_SCOPE,
                now=current,
            ),
            "raw_authority_input_grants_live_authority": False,
            "preview_validation_grants_live_authority": False,
            "consequential_use_requires_latest_acceptance": True,
            "truth_boundary": (
                "A raw authority dictionary or merely valid candidate snapshot cannot "
                "grant live commercial authority. Each consequential domain requires "
                "a fresh provider-native snapshot with exact scope, source-ledger "
                "integrity and hash-valid evidence, and the snapshot must match the "
                "latest durable acceptance entry exactly."
            ),
        }

    def governed_authority_readback(self) -> dict[str, Any]:
        result = super().governed_authority_readback()
        state = self._read_state()
        bindings: list[dict[str, Any]] = []
        for collection in (
            "service_requests",
            "quotes",
            "case_studies",
            "revenue_events",
        ):
            for object_id, item in sorted(state.get(collection, {}).items()):
                binding = item.get("authority_snapshot_binding")
                if binding:
                    bindings.append(
                        {
                            "collection": collection,
                            "object_id": object_id,
                            "binding_sha256": binding["binding_sha256"],
                            "snapshot_sha256": binding["snapshot_sha256"],
                            "acceptance_entry_sha256": binding[
                                "acceptance_entry_sha256"
                            ],
                        }
                    )
        result["authority_snapshot"] = self.authority_snapshot_readback()
        result["authority_action_bindings"] = {
            "count": len(bindings),
            "items": bindings,
            "latest_accepted_snapshot_required": True,
            "binding_integrity": "HASH_BOUND_TO_ACCEPTANCE_ENTRY",
        }
        result["canonical_class"] = self.__class__.__name__
        result["predecessor_class"] = "GovernedCommercialAssuranceControlPlane"
        return result

    def _snapshot_decision(
        self,
        domain: str,
        *,
        now: str,
        required_scope: tuple[str, ...] | None = None,
    ) -> Any:
        return self.authority_snapshot_validator.validate_domain(
            domain,
            required_scope=(
                required_scope
                if required_scope is not None
                else REQUIRED_SCOPE.get(domain, ())
            ),
            now=now,
        )

    def _require_snapshot_domain(
        self,
        domain: str,
        *,
        now: str,
        required_scope: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        if self.authority_profile != LIVE_PROFILE:
            return {}
        decision = self._snapshot_decision(
            domain,
            now=now,
            required_scope=required_scope,
        )
        if not decision.valid:
            raise PermissionError(
                "authority snapshot validation failed: "
                + ",".join(decision.reasons)
            )
        return self.accept_authority_snapshot(now=now)

    def _live_authority_verified(self, domain: str) -> bool:
        if self.authority_profile != LIVE_PROFILE:
            return super()._live_authority_verified(domain)
        current = utc_now()
        decision = self._snapshot_decision(domain, now=current)
        if not decision.valid:
            return False
        return self.authority_snapshot_acceptance.is_latest_accepted(
            self.authority_snapshot_validator.snapshot,
            self.authority_snapshot_validator,
            required_scope=REQUIRED_SCOPE,
            now=current,
        )

    def _latest_acceptance_binding(
        self,
        domains: tuple[str, ...],
        *,
        now: str,
    ) -> dict[str, Any]:
        snapshot = self.authority_snapshot_validator.snapshot
        entry = self.authority_snapshot_acceptance.latest_accepted(
            snapshot,
            self.authority_snapshot_validator,
            required_scope=REQUIRED_SCOPE,
            now=now,
        )
        assert snapshot is not None
        missing = sorted(set(domains) - set(snapshot.domains))
        if missing:
            raise PermissionError(
                "authority snapshot binding failed: AUTHORITY_DOMAINS_MISSING:"
                + ",".join(missing)
            )
        binding: dict[str, Any] = {
            "binding_state": "EXACT_LATEST_ACCEPTED_SNAPSHOT",
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_sha256": snapshot.snapshot_sha256,
            "acceptance_sequence": entry["sequence"],
            "acceptance_entry_sha256": entry["entry_sha256"],
            "domains": sorted(set(domains)),
            "domain_evidence_sha256": {
                domain: snapshot.domains[domain].evidence_sha256
                for domain in sorted(set(domains))
            },
            "bound_at": now,
        }
        binding["binding_sha256"] = digest(binding)
        return binding

    def _bind_state_object(
        self,
        *,
        stage: str,
        event: str,
        collection: str,
        object_id: str,
        domains: tuple[str, ...],
        now: str,
    ) -> dict[str, Any]:
        binding = self._latest_acceptance_binding(domains, now=now)
        state = self._read_state()
        try:
            stored = state[collection][object_id]
        except KeyError as exc:
            raise RuntimeError(
                f"authority snapshot binding target missing: {collection}/{object_id}"
            ) from exc
        stored["authority_snapshot_binding"] = binding
        self._write_state(state)
        self._ledger(stage, event, object_id, stored)
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
        current = now or utc_now()
        stored = super().submit_service_request(
            request_id,
            tenant_id,
            request_type,
            payload,
            requested_by,
            owner_decision_receipt_id=owner_decision_receipt_id,
            now=current,
        )
        if (
            self.authority_profile == LIVE_PROFILE
            and request_type in _OWNER_RESERVED_SERVICE_REQUESTS
        ):
            return self._bind_state_object(
                stage="C11",
                event="service.authority-snapshot-binding",
                collection="service_requests",
                object_id=request_id,
                domains=("owner_decision",),
                now=current,
            )
        return stored

    def approve_quote(
        self,
        quote_id: str,
        *,
        owner_decision_receipt_id: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        super().approve_quote(
            quote_id,
            owner_decision_receipt_id=owner_decision_receipt_id,
            now=current,
        )
        if self.authority_profile == LIVE_PROFILE:
            return self._bind_state_object(
                stage="C13",
                event="quote.authority-snapshot-binding",
                collection="quotes",
                object_id=quote_id,
                domains=("owner_decision",),
                now=current,
            )
        return self._read_state()["quotes"][quote_id]

    def _require_owner_decision(
        self,
        receipt_id: str | None,
        gate: str,
        evidence_id: str,
        content_sha256: str,
        *,
        now: str | None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        self._require_snapshot_domain("owner_decision", now=current)
        return super()._require_owner_decision(
            receipt_id,
            gate,
            evidence_id,
            content_sha256,
            now=current,
        )

    def admit_external_evidence(self, evidence: Any, *, now: str | None = None) -> dict[str, Any]:
        current = now or utc_now()
        gate_domain = {
            "payment_provider_revenue": "payment_provider",
            "external_case_study": "customer_market",
        }.get(evidence.gate)
        if gate_domain:
            self._require_snapshot_domain(gate_domain, now=current)
        return super().admit_external_evidence(evidence, now=current)

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
        current = utc_now()
        if external_evidence_id and self.authority_profile == LIVE_PROFILE:
            self._require_snapshot_domain("customer_market", now=current)
            self._require_snapshot_domain("owner_decision", now=current)
        stored = super().register_outcome_study(
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
        if (
            self.authority_profile == LIVE_PROFILE
            and stored.get("external_admission_verified") is True
        ):
            return self._bind_state_object(
                stage="C12",
                event="study.authority-snapshot-binding",
                collection="case_studies",
                object_id=study_id,
                domains=("customer_market", "owner_decision"),
                now=current,
            )
        return stored

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
        current = now or utc_now()
        self._require_snapshot_domain("payment_provider", now=current)
        self._require_snapshot_domain("owner_decision", now=current)
        stored = super().register_verified_revenue_event(
            event_id,
            contract_id,
            amount,
            currency,
            provider_evidence,
            now=current,
        )
        if (
            self.authority_profile == LIVE_PROFILE
            and stored.get("live_revenue_recognition") is True
        ):
            return self._bind_state_object(
                stage="C13",
                event="revenue.authority-snapshot-binding",
                collection="revenue_events",
                object_id=event_id,
                domains=("payment_provider", "owner_decision"),
                now=current,
            )
        return stored
