from __future__ import annotations

from pathlib import Path
from typing import Any

from authority_snapshot import (
    CommercialAuthoritySnapshot,
    CommercialAuthoritySnapshotValidator,
)
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

    The v2 governed control plane removed caller-set approval shortcuts. This v3
    wrapper closes the remaining raw-authority-state gap: live authority is admitted
    only through a hash-valid, scope-complete, non-expired authority snapshot.
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
            "raw_authority_input_grants_live_authority": False,
            "truth_boundary": (
                "A raw authority dictionary cannot grant live commercial authority. "
                "Each consequential domain requires a fresh provider-native authority "
                "snapshot with exact scope, source-ledger integrity and hash-valid evidence."
            ),
        }

    def governed_authority_readback(self) -> dict[str, Any]:
        result = super().governed_authority_readback()
        result["authority_snapshot"] = self.authority_snapshot_readback()
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
    ) -> None:
        if self.authority_profile != LIVE_PROFILE:
            return
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

    def _live_authority_verified(self, domain: str) -> bool:
        if self.authority_profile != LIVE_PROFILE:
            return super()._live_authority_verified(domain)
        decision = self._snapshot_decision(domain, now=utc_now())
        return bool(decision.valid)

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
        return super().register_verified_revenue_event(
            event_id,
            contract_id,
            amount,
            currency,
            provider_evidence,
            now=current,
        )
