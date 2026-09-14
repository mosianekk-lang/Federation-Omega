"""Evidence-bound import of already-delivered v2 artifacts into the v3 ledger."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Any

from .adapters import ReceiptSigner
from .canonical import canonical_json_bytes, sha256_bytes
from .ledger import ArtifactLedger, utc_now
from .model import (
    ArtifactRequest,
    ProviderObject,
    RetentionClass,
    SensitivityClass,
    TransactionState,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class LegacyArtifactRecord:
    artifact_name: str
    content_sha256: str
    size_bytes: int
    media_type: str
    object_id: str
    parent_alias: str
    workstream: str
    version: str
    evidence_ref: str
    retention_class: RetentionClass = RetentionClass.CANONICAL
    shared: bool = False
    readback_verified: bool = True
    revision: str = ""


class GenesisImporter:
    """Imports exact legacy proof without re-performing or inventing provider work."""

    def __init__(self, *, ledger: ArtifactLedger, signer: ReceiptSigner) -> None:
        self.ledger = ledger
        self.signer = signer

    def import_record(self, record: LegacyArtifactRecord) -> dict[str, Any]:
        self._validate(record)
        request = ArtifactRequest(
            artifact_name=record.artifact_name,
            content=b"LEGACY-PROOF-ONLY-NOT-CONTENT",
            media_type=record.media_type,
            workstream=record.workstream,
            version=record.version,
            destination_alias=record.parent_alias,
            retention_class=record.retention_class,
            sensitivity=SensitivityClass.PRIVATE,
            source_ref=record.evidence_ref,
            metadata={"migration_schema_ref": "FAF3-LEGACY-IMPORT-1"},
        )
        transaction, created = self.ledger.get_or_create(
            request,
            content_sha256=record.content_sha256,
            size_bytes=record.size_bytes,
        )
        if transaction["state"] == TransactionState.DELIVERED:
            return transaction
        if not created:
            raise ValueError("existing legacy import is incomplete; explicit reconciliation required")
        tx_id = transaction["transaction_id"]
        transaction = self.ledger.transition(
            tx_id, TransactionState.QUARANTINED,
            event_type="LEGACY_RECORD_QUARANTINED",
            payload={"evidence_ref": record.evidence_ref},
        )
        transaction = self.ledger.transition(
            tx_id, TransactionState.VALIDATED,
            event_type="LEGACY_PROOF_VALIDATED",
            payload={"readback_verified": True, "shared": False},
            scan_report={
                "passed": True,
                "sha256": record.content_sha256,
                "size_bytes": record.size_bytes,
                "scanner_version": "LEGACY-EXTERNAL-PROOF",
                "findings": [],
                "truth_boundary": "Artifact bytes were not rescanned during migration.",
            },
        )
        transaction = self.ledger.transition(
            tx_id, TransactionState.DRIVE_WRITE_PENDING,
            event_type="LEGACY_PROVIDER_WRITE_ALREADY_COMPLETED",
            payload={"provider_effect_replayed": False},
        )
        provider_object = ProviderObject(
            object_id=record.object_id,
            object_name=record.artifact_name,
            parent_ref=record.parent_alias,
            media_type=record.media_type,
            size_bytes=record.size_bytes,
            sha256=record.content_sha256,
            revision=record.revision,
            created_new=False,
        )
        transaction = self.ledger.transition(
            tx_id, TransactionState.DRIVE_WRITTEN,
            event_type="LEGACY_PROVIDER_OBJECT_BOUND",
            payload={"object_id": record.object_id},
            provider_object=provider_object,
        )
        transaction = self.ledger.transition(
            tx_id, TransactionState.READBACK_VERIFIED,
            event_type="LEGACY_READBACK_PROOF_IMPORTED",
            payload={"evidence_ref": record.evidence_ref},
        )
        projection = {
            "transaction_id": tx_id,
            "idempotency_key": transaction["idempotency_key"],
            "object_id": record.object_id,
            "sha256": record.content_sha256,
            "status": "MIGRATED_VERIFIED",
        }
        transaction = self.ledger.transition(
            tx_id, TransactionState.REGISTRY_COMMITTED,
            event_type="LEGACY_REGISTRY_PROOF_IMPORTED",
            payload=projection,
            projection=projection,
        )
        receipt = {
            "schema": "FEDERATION-ARTIFACT-FABRIC-MIGRATION-RECEIPT-3",
            "transaction_id": tx_id,
            "idempotency_key": transaction["idempotency_key"],
            "artifact": asdict(record),
            "delivery_state": "DELIVERED",
            "provider_effect_replayed": False,
            "migration_recorded_at": utc_now(),
            "event_chain_head_before_delivery": self.ledger.event_chain_head(),
            "truth_boundary": (
                "Migration imports existing exact provider/readback evidence. It does not "
                "rescan unavailable historical bytes or repeat the provider upload."
            ),
        }
        signature = self.signer.sign(receipt)
        if not self.signer.verify(receipt, signature):
            raise ValueError("migration signature self-check failed")
        transaction = self.ledger.transition(
            tx_id, TransactionState.RECEIPT_SIGNED,
            event_type="MIGRATION_RECEIPT_SIGNED",
            payload={"signer_id": signature.signer_id},
            receipt=receipt,
            signature=signature,
        )
        final = dict(receipt)
        final["signature"] = asdict(signature)
        final["receipt_sha256"] = sha256_bytes(canonical_json_bytes(final))
        return self.ledger.transition(
            tx_id, TransactionState.DELIVERED,
            event_type="LEGACY_ARTIFACT_MIGRATED",
            payload={"receipt_sha256": final["receipt_sha256"]},
            receipt=final,
        )

    @staticmethod
    def _validate(record: LegacyArtifactRecord) -> None:
        if not _SHA256.fullmatch(record.content_sha256.lower()):
            raise ValueError("legacy content_sha256 must be a 64-character lowercase hex digest")
        if record.size_bytes <= 0:
            raise ValueError("legacy artifact size must be positive")
        if record.shared:
            raise ValueError("shared legacy artifacts are not eligible for canonical migration")
        if not record.readback_verified:
            raise ValueError("legacy provider readback must be verified")
        if not record.object_id or not record.evidence_ref:
            raise ValueError("legacy object ID and evidence reference are required")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", record.parent_alias):
            raise ValueError("legacy parent must be represented by a symbolic private alias")
