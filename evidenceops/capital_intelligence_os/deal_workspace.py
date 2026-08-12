from __future__ import annotations

from typing import Mapping
import base64

from .ingestion import DocumentIngestRequest, DocumentIngestionService
from .models import InformationClass, stable_sha256, utc_now_iso
from .tenancy import TenantContext
from .vault import DocumentVault


class DealWorkspaceService:
    """Thin product composition layer over the evidence vault and diligence engine."""

    def __init__(self, vault: DocumentVault) -> None:
        self.vault = vault
        self.ingestion = DocumentIngestionService(vault)

    @staticmethod
    def _decode_content(value: object) -> bytes:
        if not isinstance(value, str) or not value:
            raise ValueError("content_base64 is required")
        try:
            return base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("content_base64 is invalid") from exc

    def ingest_payload(self, ctx: TenantContext, data: Mapping[str, object]) -> dict[str, object]:
        tags_value = data.get("tags", ())
        if tags_value is None:
            tags_value = ()
        if not isinstance(tags_value, (list, tuple)):
            raise ValueError("tags must be a list")
        try:
            information_class = InformationClass(str(data["information_class"]))
        except KeyError as exc:
            raise ValueError("information_class is required") from exc
        except ValueError as exc:
            raise ValueError("information_class is invalid") from exc

        request = DocumentIngestRequest(
            logical_key=str(data.get("logical_key", "")),
            filename=str(data.get("filename", "")),
            document_type=str(data.get("document_type", "")),
            content_type=str(data.get("content_type", "")),
            content=self._decode_content(data.get("content_base64")),
            information_class=information_class,
            source_id=str(data.get("source_id", "")),
            extracted_text=str(data.get("extracted_text", "") or ""),
            tags=tuple(str(value) for value in tags_value),
        )
        return self.ingestion.ingest(ctx, request)

    def search_payload(self, ctx: TenantContext, data: Mapping[str, object]) -> dict[str, object]:
        query = str(data.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")
        limit = int(data.get("limit", 20))
        results = self.vault.search(ctx, query, limit=limit)
        return {
            "query": query,
            "result_count": len(results),
            "results": results,
            "external_effects": False,
        }

    def snapshot(self, ctx: TenantContext) -> dict[str, object]:
        records = self.vault.list_records(ctx)
        status = self.ingestion.diligence_status(ctx)
        classes: dict[str, int] = {}
        latest_versions: dict[str, int] = {}
        for record in records:
            classes[record.information_class.value] = classes.get(record.information_class.value, 0) + 1
            latest_versions[record.logical_key] = max(latest_versions.get(record.logical_key, 0), record.version_no)
        documents = [
            {
                "document_id": record.document_id,
                "logical_key": record.logical_key,
                "filename": record.filename,
                "document_type": record.document_type,
                "content_type": record.content_type,
                "sha256": record.sha256,
                "size_bytes": record.size_bytes,
                "information_class": record.information_class.value,
                "version_no": record.version_no,
                "previous_document_id": record.previous_document_id,
                "source_id": record.source_id,
                "created_at": record.created_at,
                "tags": list(record.tags),
            }
            for record in records
        ]
        payload: dict[str, object] = {
            "schema": "CIOS-DEAL-WORKSPACE-SNAPSHOT-V1",
            "tenant_id": ctx.tenant_id,
            "generated_at": utc_now_iso(),
            "document_count": len(documents),
            "logical_document_count": len(latest_versions),
            "classification_counts": dict(sorted(classes.items())),
            "latest_versions": dict(sorted(latest_versions.items())),
            "documents": documents,
            "diligence": status,
            "requires_human_decision": True,
            "external_effects": False,
            "truth_boundary": (
                "This bundle is a tenant-scoped evidence inventory and diligence-status export. "
                "It is not a legal opinion, valuation opinion, transaction approval or production VDR receipt."
            ),
        }
        digest_body = {key: value for key, value in payload.items() if key != "generated_at"}
        payload["bundle_sha256"] = stable_sha256(digest_body)
        return payload
