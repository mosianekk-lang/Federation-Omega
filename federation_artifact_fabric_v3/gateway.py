"""Proof-bound transactional Artifact Gateway."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .adapters import ReceiptSigner, RegistryProjection, StorageAdapter
from .canonical import canonical_json_bytes, sha256_bytes
from .ledger import ArtifactLedger, utc_now
from .model import (
    ArtifactRequest,
    DeliveryOutcome,
    PermanentProviderError,
    ProviderObject,
    ScanViolation,
    TemporaryProviderError,
    TransactionState,
)
from .security import scan_artifact, scan_report_dict


class InjectedCrash(RuntimeError):
    """Test-only interruption after a verified state transition."""


class ArtifactGateway:
    """Runs the mandatory release transaction and never self-certifies delivery."""

    def __init__(
        self,
        *,
        ledger: ArtifactLedger,
        storage: StorageAdapter,
        projection: RegistryProjection,
        signer: ReceiptSigner,
        max_attempts: int = 5,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.ledger = ledger
        self.storage = storage
        self.projection = projection
        self.signer = signer
        self.max_attempts = max_attempts

    def deliver(
        self,
        request: ArtifactRequest,
        *,
        crash_after: TransactionState | None = None,
    ) -> DeliveryOutcome:
        content_sha256 = sha256_bytes(request.content)
        transaction, created = self.ledger.get_or_create(
            request,
            content_sha256=content_sha256,
            size_bytes=len(request.content),
        )
        transaction_id = str(transaction["transaction_id"])
        if transaction["state"] == TransactionState.DELIVERED:
            return DeliveryOutcome(
                transaction_id=transaction_id,
                idempotency_key=str(transaction["idempotency_key"]),
                state=TransactionState.DELIVERED,
                receipt=transaction.get("receipt"),
                reused_existing=True,
                reason="IDEMPOTENT_REUSE",
            )
        if transaction["state"] == TransactionState.DEAD_LETTER:
            return self._outcome(transaction, reason="DEAD_LETTER_REQUIRES_EXPLICIT_REARM")
        if transaction["state"] == TransactionState.FAILED:
            return self._outcome(transaction, reason="PERMANENT_FAILURE")
        if transaction["state"] == TransactionState.HOLD:
            last_error = str(transaction.get("last_error") or "")
            if not last_error.startswith("TEMPORARY_PROVIDER_ERROR"):
                return self._outcome(
                    transaction,
                    reason="NON_RETRYABLE_HOLD_REQUIRES_NEW_ARTIFACT_OR_EXPLICIT_REARM",
                )
            transaction = self.ledger.resume_hold(transaction_id)
        try:
            transaction = self._run(request, transaction, crash_after=crash_after)
            return self._outcome(transaction, reused_existing=not created)
        except InjectedCrash:
            raise
        except ScanViolation as exc:
            held = self.ledger.hold(
                transaction_id,
                reason=f"SECURITY_SCAN_FAILED: {exc}",
                retryable=False,
                max_attempts=self.max_attempts,
            )
            return self._outcome(held, reason=str(exc))
        except TemporaryProviderError as exc:
            held = self.ledger.hold(
                transaction_id,
                reason=f"TEMPORARY_PROVIDER_ERROR: {exc}",
                retryable=True,
                max_attempts=self.max_attempts,
            )
            return self._outcome(held, reason=str(exc))
        except PermanentProviderError as exc:
            failed = self._fail_permanently(transaction_id, str(exc))
            return self._outcome(failed, reason=str(exc))

    def _run(
        self,
        request: ArtifactRequest,
        transaction: Mapping[str, Any],
        *,
        crash_after: TransactionState | None,
    ) -> dict[str, Any]:
        tx_id = str(transaction["transaction_id"])
        state = TransactionState(str(transaction["state"]))
        if state == TransactionState.RECEIVED:
            transaction = self.ledger.transition(
                tx_id, TransactionState.QUARANTINED,
                event_type="QUARANTINE_ADMITTED",
                payload={"artifact_name": request.artifact_name},
            )
            self._crash_if(TransactionState.QUARANTINED, crash_after)
            state = transaction["state"]
        if state == TransactionState.QUARANTINED:
            report = scan_artifact(request)
            transaction = self.ledger.transition(
                tx_id, TransactionState.VALIDATED,
                event_type="SECURITY_VALIDATED",
                payload={"scanner_version": report.scanner_version, "archive_entries": report.archive_entries},
                scan_report=scan_report_dict(report),
            )
            self._crash_if(TransactionState.VALIDATED, crash_after)
            state = transaction["state"]
        if state == TransactionState.VALIDATED:
            transaction = self.ledger.transition(
                tx_id, TransactionState.DRIVE_WRITE_PENDING,
                event_type="PROVIDER_WRITE_PLANNED",
                payload={"destination_alias": request.destination_alias},
            )
            self._crash_if(TransactionState.DRIVE_WRITE_PENDING, crash_after)
            state = transaction["state"]
        if state == TransactionState.DRIVE_WRITE_PENDING:
            provider_object = self.storage.put_if_absent(
                content_key=str(transaction["idempotency_key"]),
                destination_alias=request.destination_alias,
                object_name=request.artifact_name,
                content=request.content,
                media_type=request.media_type,
            )
            transaction = self.ledger.transition(
                tx_id, TransactionState.DRIVE_WRITTEN,
                event_type="PROVIDER_OBJECT_WRITTEN",
                payload={"object_id": provider_object.object_id, "created_new": provider_object.created_new},
                provider_object=provider_object,
            )
            self._crash_if(TransactionState.DRIVE_WRITTEN, crash_after)
            state = transaction["state"]
        if state == TransactionState.DRIVE_WRITTEN:
            provider = ProviderObject(**dict(transaction["provider_object"]))
            readback = self.storage.readback(provider.object_id)
            mismatch = self._readback_mismatch(request, transaction, readback)
            if mismatch:
                if provider.created_new:
                    self.storage.delete_if_created(provider.object_id)
                raise PermanentProviderError(mismatch)
            transaction = self.ledger.transition(
                tx_id, TransactionState.READBACK_VERIFIED,
                event_type="PROVIDER_READBACK_VERIFIED",
                payload={"object_id": readback.object_id, "revision": readback.revision, "shared": readback.shared},
            )
            self._crash_if(TransactionState.READBACK_VERIFIED, crash_after)
            state = transaction["state"]
        if state == TransactionState.READBACK_VERIFIED:
            unsigned_receipt = self._unsigned_receipt(transaction)
            self.projection.commit(transaction, unsigned_receipt)
            projection = self.projection.readback(tx_id)
            expected_object = str((transaction.get("provider_object") or {}).get("object_id", ""))
            if (
                projection.transaction_id != tx_id
                or projection.idempotency_key != transaction["idempotency_key"]
                or projection.object_id != expected_object
                or projection.sha256 != transaction["content_sha256"]
                or projection.status != "COMMITTED"
            ):
                raise PermanentProviderError("registry semantic readback mismatch")
            transaction = self.ledger.transition(
                tx_id, TransactionState.REGISTRY_COMMITTED,
                event_type="REGISTRY_COMMITTED_AND_READ_BACK",
                payload=asdict(projection), projection=asdict(projection),
            )
            self._crash_if(TransactionState.REGISTRY_COMMITTED, crash_after)
            state = transaction["state"]
        if state == TransactionState.REGISTRY_COMMITTED:
            receipt = self._unsigned_receipt(transaction)
            receipt["delivery_state"] = "DELIVERED"
            receipt["event_chain_head_before_delivery"] = self.ledger.event_chain_head()
            signature = self.signer.sign(receipt)
            if not self.signer.verify(receipt, signature):
                raise PermanentProviderError("receipt signature self-check failed")
            transaction = self.ledger.transition(
                tx_id, TransactionState.RECEIPT_SIGNED,
                event_type="RECEIPT_SIGNED",
                payload={
                    "algorithm": signature.algorithm,
                    "signer_id": signature.signer_id,
                    "signed_payload_sha256": signature.signed_payload_sha256,
                },
                receipt=receipt, signature=signature,
            )
            self._crash_if(TransactionState.RECEIPT_SIGNED, crash_after)
            state = transaction["state"]
        if state == TransactionState.RECEIPT_SIGNED:
            final_receipt = dict(transaction["receipt"])
            final_receipt["signature"] = dict(transaction["signature"])
            final_receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(final_receipt))
            transaction = self.ledger.transition(
                tx_id, TransactionState.DELIVERED,
                event_type="DELIVERED",
                payload={"receipt_sha256": final_receipt["receipt_sha256"]},
                receipt=final_receipt,
            )
            self._crash_if(TransactionState.DELIVERED, crash_after)
        return transaction

    def _unsigned_receipt(self, transaction: Mapping[str, Any]) -> dict[str, Any]:
        provider = dict(transaction.get("provider_object") or {})
        return {
            "schema": "FEDERATION-ARTIFACT-FABRIC-DELIVERY-RECEIPT-3",
            "transaction_id": transaction["transaction_id"],
            "idempotency_key": transaction["idempotency_key"],
            "artifact_name": transaction["artifact_name"],
            "content_sha256": transaction["content_sha256"],
            "size_bytes": transaction["size_bytes"],
            "media_type": transaction["media_type"],
            "workstream": transaction["workstream"],
            "version": transaction["version"],
            "retention_class": transaction["retention_class"],
            "sensitivity": transaction["sensitivity"],
            "destination_alias": transaction["destination_alias"],
            "provider_object": {
                "object_id": provider.get("object_id", ""),
                "object_name": provider.get("object_name", ""),
                "parent_ref": provider.get("parent_ref", ""),
                "revision": provider.get("revision", ""),
            },
            "scan_report": transaction.get("scan_report"),
            "provider_readback_verified": True,
            "registry_readback_verified": transaction["state"] in {
                TransactionState.REGISTRY_COMMITTED,
                TransactionState.RECEIPT_SIGNED,
                TransactionState.DELIVERED,
            },
            "shared": False,
            "event_chain_head": self.ledger.event_chain_head(),
            "recorded_at": utc_now(),
            "truth_boundary": (
                "The receipt proves the exact bounded gateway transaction. It does not "
                "create provider authority, an immutable external anchor or an always-on runtime."
            ),
        }

    @staticmethod
    def _readback_mismatch(request: ArtifactRequest, transaction: Mapping[str, Any], readback: Any) -> str:
        if readback.trashed:
            return "provider object is trashed"
        if readback.shared:
            return "provider object is unexpectedly shared"
        if readback.object_name != request.artifact_name:
            return "provider object name mismatch"
        if readback.parent_ref != request.destination_alias:
            return "provider parent mismatch"
        if readback.media_type != request.media_type:
            return "provider MIME mismatch"
        if readback.size_bytes != transaction["size_bytes"]:
            return "provider size mismatch"
        if readback.sha256 != transaction["content_sha256"]:
            return "provider hash mismatch"
        return ""

    def _fail_permanently(self, transaction_id: str, reason: str) -> dict[str, Any]:
        current = self.ledger.get(transaction_id)
        if current is None:
            raise KeyError(transaction_id)
        if current["state"] in {TransactionState.DELIVERED, TransactionState.FAILED, TransactionState.DEAD_LETTER}:
            return current
        return self.ledger.transition(
            transaction_id, TransactionState.FAILED,
            event_type="PERMANENT_FAILURE", payload={"reason": reason}, last_error=reason,
        )

    @staticmethod
    def _crash_if(state: TransactionState, crash_after: TransactionState | None) -> None:
        if crash_after == state:
            raise InjectedCrash(f"injected crash after {state}")

    @staticmethod
    def _outcome(
        transaction: Mapping[str, Any],
        *,
        reused_existing: bool = False,
        reason: str = "",
    ) -> DeliveryOutcome:
        return DeliveryOutcome(
            transaction_id=str(transaction["transaction_id"]),
            idempotency_key=str(transaction["idempotency_key"]),
            state=TransactionState(str(transaction["state"])),
            receipt=transaction.get("receipt"),
            reused_existing=reused_existing,
            reason=reason,
        )
