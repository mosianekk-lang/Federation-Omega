from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from authority_snapshot import digest, valid_sha256
from provider_reconciliation_recovery import (
    ChallengeBoundMockProviderAdapter,
    RECONCILIATION_EVIDENCE_PACKAGE_CLASS,
    RECONCILIATION_RECOVERY_CLASS,
    RecoverableVaultedProviderDispatchCommercialControlPlane,
)

RECONCILIATION_RECOVERY_COMPLETION_CLASS = (
    "LOCAL_PROVIDER_RECONCILIATION_RECOVERY_COMPLETION_V18"
)


class ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
    RecoverableVaultedProviderDispatchCommercialControlPlane
):
    """V18 makes restart recovery completion receipts deterministically repairable.

    V17 can commit the recovered provider outcome before it writes its local recovery
    ledger receipt. A process interruption in that narrow gap leaves the provider
    dispatch safely resolved, but the recovery audit result is incomplete. V18 adds
    a content-addressed, atomically published completion receipt. Exact retries
    reconstruct a missing receipt from the vaulted evidence and the already-committed
    hash-chained resolution event without repeating provider reconciliation.

    This is a local managed-service control. It performs no external provider
    mutation and does not establish provider-native reconciliation authority.
    """

    CAPABILITY_REVISION = (
        "AO-COMMERCIAL-PROVIDER-RECONCILIATION-RECOVERY-COMPLETION-V18"
    )
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.provider_reconciliation_recovery_receipt_dir = (
            Path(self.state_dir) / "provider_reconciliation_recovery_receipts"
        )
        self.provider_reconciliation_recovery_receipt_dir.mkdir(
            parents=True, exist_ok=True
        )
        self._remove_incomplete_recovery_receipts()
        self._verify_recovery_completion_receipt_state()

    def _remove_incomplete_recovery_receipts(self) -> None:
        removed = False
        for path in self.provider_reconciliation_recovery_receipt_dir.glob(
            ".publish-*.tmp"
        ):
            if path.is_file():
                path.unlink()
                removed = True
        if removed:
            self._fsync_directory(
                self.provider_reconciliation_recovery_receipt_dir
            )

    def _completion_receipt_path(self, reconciliation_sha256: str) -> Path:
        if not valid_sha256(reconciliation_sha256):
            raise ValueError("provider reconciliation completion SHA-256 invalid")
        destination = (
            self.provider_reconciliation_recovery_receipt_dir
            / f"{reconciliation_sha256}.json"
        )
        if (
            destination.parent.resolve()
            != self.provider_reconciliation_recovery_receipt_dir.resolve()
        ):
            raise RuntimeError("provider reconciliation completion path invalid")
        return destination

    def _resolved_reconciliation_reference(
        self,
        state: dict[str, Any],
        reconciliation_sha256: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
        matches: list[tuple[str, dict[str, Any]]] = []
        histories = state.get("provider_dispatch_claim_history", {})
        if not isinstance(histories, dict):
            raise RuntimeError("provider dispatch claim history invalid")
        for dispatch_id, raw in histories.items():
            events = self._verify_claim_history(raw, str(dispatch_id))
            for event in events:
                if event.get("outcome_reconciliation_sha256") == reconciliation_sha256:
                    matches.append((str(dispatch_id), dict(event)))
        if len(matches) != 1:
            raise RuntimeError("provider reconciliation completion reference invalid")

        dispatch_id, event = matches[0]
        if event.get("event_type") not in {
            "OUTCOME_RESOLVED_NO_EFFECT",
            "COMPLETED",
        }:
            raise RuntimeError("provider reconciliation completion event invalid")

        dispatches = state.get("provider_dispatches", {})
        if not isinstance(dispatches, dict):
            raise RuntimeError("provider dispatch state invalid")
        record = dispatches.get(dispatch_id)
        if not isinstance(record, dict):
            raise RuntimeError("resolved provider dispatch missing")
        self._verify_dispatch_record(record)

        package = self._load_evidence_package(reconciliation_sha256)
        evidence = package.get("evidence")
        if not isinstance(evidence, dict) or evidence.get("dispatch_id") != dispatch_id:
            raise RuntimeError("recovery completion evidence dispatch mismatch")
        return dispatch_id, event, dict(record), package

    def _build_recovery_completion_receipt(
        self,
        state: dict[str, Any],
        reconciliation_sha256: str,
    ) -> dict[str, Any]:
        dispatch_id, event, record, package = self._resolved_reconciliation_reference(
            state, reconciliation_sha256
        )
        evidence = package["evidence"]
        receipt: dict[str, Any] = {
            "completion_class": RECONCILIATION_RECOVERY_COMPLETION_CLASS,
            "predecessor_recovery_class": RECONCILIATION_RECOVERY_CLASS,
            "dispatch_id": dispatch_id,
            "reconciliation_sha256": reconciliation_sha256,
            "evidence_package_sha256": package["package_sha256"],
            "resolution_event_type": event["event_type"],
            "resolution_event_sha256": event["event_sha256"],
            "resolved_dispatch_record_sha256": record["record_sha256"],
            "replay_time": evidence["observed_at"],
            "provider_native_reconciliation_authority": (
                "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            ),
            "external_mutation_performed": False,
        }
        receipt["completion_receipt_sha256"] = digest(receipt)
        return receipt

    def _verify_recovery_completion_receipt(
        self,
        receipt: Any,
        *,
        expected_reconciliation_sha256: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(receipt, dict):
            raise RuntimeError("provider reconciliation completion receipt invalid")
        payload = dict(receipt)
        observed = payload.pop("completion_receipt_sha256", None)
        if observed != digest(payload):
            raise RuntimeError("provider reconciliation completion receipt hash invalid")
        if receipt.get("completion_class") != RECONCILIATION_RECOVERY_COMPLETION_CLASS:
            raise RuntimeError("provider reconciliation completion class invalid")
        reconciliation_sha256 = str(receipt.get("reconciliation_sha256", ""))
        if (
            expected_reconciliation_sha256 is not None
            and reconciliation_sha256 != expected_reconciliation_sha256
        ):
            raise RuntimeError("provider reconciliation completion reference mismatch")
        current_state = state if state is not None else self._read_state()
        expected = self._build_recovery_completion_receipt(
            current_state, reconciliation_sha256
        )
        if receipt != expected:
            raise RuntimeError("provider reconciliation completion receipt binding invalid")
        return dict(receipt)

    def _load_recovery_completion_receipt(
        self,
        reconciliation_sha256: str,
        *,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        destination = self._completion_receipt_path(reconciliation_sha256)
        if not destination.is_file():
            raise RuntimeError("provider reconciliation completion receipt missing")
        try:
            receipt = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "provider reconciliation completion receipt unreadable"
            ) from exc
        return self._verify_recovery_completion_receipt(
            receipt,
            expected_reconciliation_sha256=reconciliation_sha256,
            state=state,
        )

    def _persist_recovery_completion_receipt(
        self,
        state: dict[str, Any],
        reconciliation_sha256: str,
    ) -> dict[str, Any]:
        receipt = self._build_recovery_completion_receipt(
            state, reconciliation_sha256
        )
        destination = self._completion_receipt_path(reconciliation_sha256)
        if destination.exists():
            existing = self._load_recovery_completion_receipt(
                reconciliation_sha256, state=state
            )
            if existing != receipt:
                raise RuntimeError(
                    "provider reconciliation completion receipt conflict"
                )
            return existing

        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".publish-",
                suffix=".tmp",
                dir=self.provider_reconciliation_recovery_receipt_dir,
                delete=False,
            ) as stream:
                temporary_name = stream.name
                stream.write(self._canonical_bytes(receipt))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, destination)
            temporary_name = None
            self._fsync_directory(
                self.provider_reconciliation_recovery_receipt_dir
            )
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

        return self._load_recovery_completion_receipt(
            reconciliation_sha256, state=state
        )

    def _available_recovery_completion_receipts(self) -> set[str]:
        available: set[str] = set()
        state = self._read_state()
        for path in self.provider_reconciliation_recovery_receipt_dir.glob("*.json"):
            reconciliation_sha256 = path.stem
            self._load_recovery_completion_receipt(
                reconciliation_sha256, state=state
            )
            available.add(reconciliation_sha256)
        return available

    def _verify_recovery_completion_receipt_state(self) -> dict[str, Any]:
        evidence = self._verify_provider_reconciliation_evidence_state()
        receipts = self._available_recovery_completion_receipts()
        referenced = set(evidence["referenced"])
        unexpected = sorted(receipts - referenced)
        if unexpected:
            raise RuntimeError(
                "provider reconciliation completion receipt is unreferenced: "
                + ",".join(unexpected)
            )
        return {
            "receipts": receipts,
            "referenced": referenced,
            "referenced_without_completion_receipt": referenced - receipts,
        }

    def provider_reconciliation_recovery_completion_receipt(
        self, reconciliation_sha256: str
    ) -> dict[str, Any]:
        with self._action_coordination_locked():
            return self._load_recovery_completion_receipt(
                reconciliation_sha256
            )

    def resume_provider_reconciliation_from_vault(
        self,
        reconciliation_sha256: str,
    ) -> dict[str, Any]:
        """Complete or repair one exact local reconciliation recovery."""

        with self._action_coordination_locked():
            self._load_evidence_package(reconciliation_sha256)
            state = self._read_state()
            referenced = self._referenced_evidence_hashes(state)
            if reconciliation_sha256 in referenced:
                existed = self._completion_receipt_path(
                    reconciliation_sha256
                ).is_file()
                receipt = self._persist_recovery_completion_receipt(
                    state, reconciliation_sha256
                )
                return {
                    "status": "ALREADY_RESOLVED",
                    "dispatch_id": receipt["dispatch_id"],
                    "reconciliation_sha256": reconciliation_sha256,
                    "recovery_completion_receipt": receipt,
                    "completion_receipt_repaired": not existed,
                    "external_mutation_performed": False,
                }

            if not self._is_recoverable_package(state, reconciliation_sha256):
                raise RuntimeError("provider reconciliation evidence is not recoverable")

            result = super().resume_provider_reconciliation_from_vault(
                reconciliation_sha256
            )
            committed_state = self._read_state()
            receipt = self._persist_recovery_completion_receipt(
                committed_state, reconciliation_sha256
            )
            result["recovery_completion_receipt"] = receipt
            result["completion_receipt_repaired"] = False
            return result

    def provider_reconciliation_recovery_completion_readback(
        self,
    ) -> dict[str, Any]:
        base = super().provider_reconciliation_recovery_readback()
        with self._action_coordination_locked():
            integrity = self._verify_recovery_completion_receipt_state()
            return {
                **base,
                "capability_revision": self.CAPABILITY_REVISION,
                "stage_scope": list(self.STAGE_SCOPE),
                "recovery_completion_class": (
                    RECONCILIATION_RECOVERY_COMPLETION_CLASS
                ),
                "recovery_completion_receipts": len(integrity["receipts"]),
                "referenced_without_completion_receipt": len(
                    integrity["referenced_without_completion_receipt"]
                ),
                "atomic_completion_receipt_publication": True,
                "post_resolution_receipt_repair_supported": True,
                "exact_retry_returns_verified_completion_receipt": True,
                "reconciliation_reexecution_on_receipt_repair": False,
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
        result["predecessor_class"] = (
            "RecoverableVaultedProviderDispatchCommercialControlPlane"
        )
        result["provider_reconciliation_recovery_completion_v18"] = (
            self.provider_reconciliation_recovery_completion_readback()
        )
        return result


__all__ = [
    "ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane",
    "ChallengeBoundMockProviderAdapter",
    "RECONCILIATION_RECOVERY_COMPLETION_CLASS",
    "RECONCILIATION_RECOVERY_CLASS",
    "RECONCILIATION_EVIDENCE_PACKAGE_CLASS",
]
