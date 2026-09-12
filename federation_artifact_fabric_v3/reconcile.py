"""Independent Drive/ledger/projection reconciliation for Artifact Fabric v3."""

from __future__ import annotations

from .adapters import RegistryProjection, StorageAdapter
from .ledger import ArtifactLedger
from .model import DriftFinding, TransactionState


class ArtifactReconciler:
    def __init__(
        self,
        *,
        ledger: ArtifactLedger,
        storage: StorageAdapter,
        projection: RegistryProjection,
    ) -> None:
        self.ledger = ledger
        self.storage = storage
        self.projection = projection

    def inspect(self) -> list[DriftFinding]:
        findings: list[DriftFinding] = []
        for transaction in self.ledger.list_transactions(state=TransactionState.DELIVERED):
            transaction_id = str(transaction["transaction_id"])
            provider = transaction.get("provider_object") or {}
            object_id = str(provider.get("object_id", ""))
            if not object_id:
                findings.append(DriftFinding(transaction_id, "PROVIDER_OBJECT_REFERENCE_MISSING", "CRITICAL", "provider object reference", "missing", False))
                continue
            try:
                readback = self.storage.readback(object_id)
            except Exception as exc:
                findings.append(DriftFinding(transaction_id, "PROVIDER_READBACK_FAILED", "CRITICAL", "readable private object", str(exc), False))
                continue
            checks = (
                ("OBJECT_NAME_DRIFT", transaction["artifact_name"], readback.object_name, False),
                ("PARENT_DRIFT", transaction["destination_alias"], readback.parent_ref, False),
                ("MIME_DRIFT", transaction["media_type"], readback.media_type, False),
                ("SIZE_DRIFT", str(transaction["size_bytes"]), str(readback.size_bytes), False),
                ("HASH_DRIFT", transaction["content_sha256"], readback.sha256, False),
                ("SHARING_DRIFT", "False", str(readback.shared), False),
                ("TRASH_DRIFT", "False", str(readback.trashed), False),
            )
            for code, expected, observed, repairable in checks:
                if str(expected) != str(observed):
                    findings.append(
                        DriftFinding(
                            transaction_id=transaction_id,
                            code=code,
                            severity="CRITICAL" if code in {"HASH_DRIFT", "SHARING_DRIFT"} else "HIGH",
                            expected=str(expected),
                            observed=str(observed),
                            repairable=repairable,
                        )
                    )
            try:
                projection = self.projection.readback(transaction_id)
            except Exception as exc:
                findings.append(DriftFinding(transaction_id, "PROJECTION_MISSING", "HIGH", "committed registry projection", str(exc), True))
                continue
            if projection.sha256 != transaction["content_sha256"]:
                findings.append(DriftFinding(transaction_id, "PROJECTION_HASH_DRIFT", "CRITICAL", transaction["content_sha256"], projection.sha256, True))
            if projection.object_id != object_id:
                findings.append(DriftFinding(transaction_id, "PROJECTION_OBJECT_DRIFT", "HIGH", object_id, projection.object_id, True))
        return findings

    def repair_projection(self, transaction_id: str) -> bool:
        transaction = self.ledger.get(transaction_id)
        if not transaction or transaction["state"] != TransactionState.DELIVERED:
            return False
        provider = transaction.get("provider_object") or {}
        object_id = str(provider.get("object_id", ""))
        if not object_id:
            return False
        readback = self.storage.readback(object_id)
        if (
            readback.shared or readback.trashed
            or readback.sha256 != transaction["content_sha256"]
            or readback.size_bytes != transaction["size_bytes"]
            or readback.parent_ref != transaction["destination_alias"]
        ):
            return False
        receipt = transaction.get("receipt") or {}
        self.projection.repair(transaction, receipt)
        verified = self.projection.readback(transaction_id)
        return (
            verified.sha256 == transaction["content_sha256"]
            and verified.object_id == object_id
            and verified.status == "COMMITTED"
        )
