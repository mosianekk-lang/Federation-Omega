from __future__ import annotations

from typing import Any

from authority_snapshot import digest
from provider_reconciliation_evidence_vault import (
    ChallengeBoundMockProviderAdapter,
    RECONCILIATION_EVIDENCE_PACKAGE_CLASS,
    VaultedProviderDispatchCommercialControlPlane,
)

RECONCILIATION_RECOVERY_CLASS = "LOCAL_PROVIDER_RECONCILIATION_RECOVERY_V17"


class RecoverableVaultedProviderDispatchCommercialControlPlane(
    VaultedProviderDispatchCommercialControlPlane
):
    """V17 makes valid pre-resolution evidence recoverable after interruption.

    V16 publishes complete provider-reconciliation evidence before changing the
    dispatch state. A process interruption in that gap leaves a valid package that
    is not yet referenced by the claim history. V17 distinguishes those packages
    from invalid or rejected evidence, protects them from pruning, and permits an
    exact deterministic replay using the observation time already bound into the
    one-time challenge evidence.

    This remains a local managed-service control. It performs no external provider
    mutation and does not establish provider-native reconciliation authority.
    """

    CAPABILITY_REVISION = "AO-COMMERCIAL-PROVIDER-RECONCILIATION-RECOVERY-V17"
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]

    def _is_recoverable_package(
        self,
        state: dict[str, Any],
        reconciliation_sha256: str,
    ) -> bool:
        package = self._load_evidence_package(reconciliation_sha256)
        evidence = package.get("evidence")
        if not isinstance(evidence, dict):
            return False
        dispatch_id = str(evidence.get("dispatch_id", ""))
        observed_at = str(evidence.get("observed_at", ""))
        if not dispatch_id or not observed_at:
            return False

        dispatches = state.get("provider_dispatches", {})
        if not isinstance(dispatches, dict):
            return False
        record = dispatches.get(dispatch_id)
        if not isinstance(record, dict):
            return False
        self._verify_dispatch_record(record)

        histories = state.get("provider_dispatch_claim_history", {})
        if not isinstance(histories, dict):
            return False
        claim_events = self._verify_claim_history(histories.get(dispatch_id), dispatch_id)
        unknown = self._unresolved(claim_events)
        if unknown is None:
            return False

        try:
            self._verified_challenge_for_evidence(
                state,
                dispatch_id,
                unknown,
                evidence,
                observed_at,
            )
        except (KeyError, TypeError, ValueError, RuntimeError):
            return False

        claim_reference = str(unknown.get("claim_reference", ""))
        started = self._event(claim_events, claim_reference, "STARTED")
        submitted = self._event(claim_events, claim_reference, "SUBMITTED")
        if started is None or submitted is None:
            return False

        expected = {
            "dispatch_id": dispatch_id,
            "provider_domain": record.get("provider_domain"),
            "operation": record.get("operation"),
            "provider_idempotency_key": record.get("provider_idempotency_key"),
            "dispatch_attempt_reference": unknown.get("dispatch_attempt_reference"),
            "claim_reference": unknown.get("claim_reference"),
            "fencing_epoch": unknown.get("fencing_epoch"),
            "provider_dispatch_record_sha256": started.get(
                "prepared_dispatch_record_sha256"
            ),
            "attempt_envelope_sha256": unknown.get("attempt_envelope_sha256"),
        }
        return all(evidence.get(field) == value for field, value in expected.items())

    def _classify_unreferenced_evidence(
        self,
        state: dict[str, Any],
        available: set[str],
        referenced: set[str],
    ) -> tuple[set[str], set[str]]:
        recoverable: set[str] = set()
        invalid: set[str] = set()
        for reconciliation_sha256 in sorted(available - referenced):
            try:
                if self._is_recoverable_package(state, reconciliation_sha256):
                    recoverable.add(reconciliation_sha256)
                else:
                    invalid.add(reconciliation_sha256)
            except (KeyError, TypeError, ValueError, RuntimeError):
                invalid.add(reconciliation_sha256)
        return recoverable, invalid

    def _verify_provider_reconciliation_evidence_state(self) -> dict[str, Any]:
        integrity = super()._verify_provider_reconciliation_evidence_state()
        state = self._read_state()
        recoverable, invalid = self._classify_unreferenced_evidence(
            state,
            set(integrity["available"]),
            set(integrity["referenced"]),
        )
        return {
            **integrity,
            "recoverable": recoverable,
            "invalid_orphaned": invalid,
        }

    def resume_provider_reconciliation_from_vault(
        self,
        reconciliation_sha256: str,
    ) -> dict[str, Any]:
        """Resolve one interrupted reconciliation from its exact vaulted package."""

        with self._action_coordination_locked():
            package = self._load_evidence_package(reconciliation_sha256)
            evidence = package["evidence"]
            dispatch_id = str(evidence.get("dispatch_id", ""))
            observed_at = str(evidence.get("observed_at", ""))
            if not dispatch_id or not observed_at:
                raise RuntimeError("recoverable provider reconciliation identity missing")

            state = self._read_state()
            referenced = self._referenced_evidence_hashes(state)
            if reconciliation_sha256 in referenced:
                return {
                    "status": "ALREADY_RESOLVED",
                    "dispatch_id": dispatch_id,
                    "reconciliation_sha256": reconciliation_sha256,
                    "external_mutation_performed": False,
                }
            if not self._is_recoverable_package(state, reconciliation_sha256):
                raise RuntimeError("provider reconciliation evidence is not recoverable")

            result = super().resolve_provider_dispatch_outcome(
                dispatch_id,
                evidence,
                now=observed_at,
            )
            recovery_receipt = {
                "recovery_class": RECONCILIATION_RECOVERY_CLASS,
                "dispatch_id": dispatch_id,
                "reconciliation_sha256": reconciliation_sha256,
                "evidence_package_sha256": package["package_sha256"],
                "replay_time": observed_at,
                "result_sha256": digest(result),
                "provider_native_reconciliation_authority": (
                    "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
                ),
                "external_mutation_performed": False,
            }
            recovery_receipt["recovery_receipt_sha256"] = digest(recovery_receipt)
            self._ledger(
                "C06",
                "provider_reconciliation.evidence_recovered",
                dispatch_id,
                recovery_receipt,
            )
            result["recovery_receipt"] = recovery_receipt
            return result

    def prune_orphaned_provider_reconciliation_evidence(self) -> dict[str, Any]:
        """Prune only invalid or rejected evidence; protect recoverable packages."""

        with self._action_coordination_locked():
            integrity = self._verify_provider_reconciliation_evidence_state()
            removed = sorted(integrity["invalid_orphaned"])
            protected = sorted(integrity["recoverable"])
            for reconciliation_sha256 in removed:
                self._package_path(reconciliation_sha256).unlink()
            if removed:
                self._fsync_directory(self.provider_reconciliation_evidence_dir)
            receipt = {
                "removed_count": len(removed),
                "removed_reconciliation_sha256": removed,
                "protected_recoverable_count": len(protected),
                "protected_recoverable_reconciliation_sha256": protected,
                "external_mutation_performed": False,
            }
            self._ledger(
                "C06",
                "provider_reconciliation.invalid_evidence_pruned",
                digest(receipt),
                receipt,
            )
            return receipt

    def provider_reconciliation_recovery_readback(self) -> dict[str, Any]:
        base = super().provider_reconciliation_evidence_readback()
        with self._action_coordination_locked():
            integrity = self._verify_provider_reconciliation_evidence_state()
            return {
                **base,
                "capability_revision": self.CAPABILITY_REVISION,
                "stage_scope": list(self.STAGE_SCOPE),
                "recovery_class": RECONCILIATION_RECOVERY_CLASS,
                "recoverable_evidence_packages": len(integrity["recoverable"]),
                "invalid_orphaned_evidence_packages": len(
                    integrity["invalid_orphaned"]
                ),
                "recoverable_evidence_prune_protected": True,
                "deterministic_vault_replay_supported": True,
                "challenge_observation_time_replay_binding": True,
                "provider_native_reconciliation_authority": (
                    "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
                ),
                "provider_native_reconciliation_proven": False,
                "external_mutation_performed": False,
                "live_provider_operation_proven": False,
            }

    def governed_authority_readback(self) -> dict[str, Any]:
        result = super().governed_authority_readback()
        result["canonical_class"] = self.__class__.__name__
        result["predecessor_class"] = "VaultedProviderDispatchCommercialControlPlane"
        result["provider_reconciliation_recovery_v17"] = (
            self.provider_reconciliation_recovery_readback()
        )
        return result


__all__ = [
    "RecoverableVaultedProviderDispatchCommercialControlPlane",
    "ChallengeBoundMockProviderAdapter",
    "RECONCILIATION_RECOVERY_CLASS",
    "RECONCILIATION_EVIDENCE_PACKAGE_CLASS",
]
