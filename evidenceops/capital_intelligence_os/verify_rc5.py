from __future__ import annotations

from .deal_workspace import DealWorkspaceService
from .ingestion import DocumentIngestRequest, DocumentIngestionService, IngestionError, parse_document
from .models import InformationClass
from .policy import RuntimePolicy
from .tenancy import TenantContext
from .vault import DocumentVault
from .verify_rc4 import verify as verify_rc4


def verify() -> dict[str, object]:
    rc4 = verify_rc4()
    vault = DocumentVault(":memory:")
    ctx = TenantContext("verification-tenant", "verification-user", ("operator", "deal_member"))
    ingestion = DocumentIngestionService(vault)
    workspace = DealWorkspaceService(vault)
    request = DocumentIngestRequest(
        logical_key="verification-financials",
        filename="financials.json",
        document_type="audited financial statements",
        content_type="application/json",
        content=b'{"revenue":100,"ebitda":20}',
        information_class=InformationClass.CONFIDENTIAL,
        source_id="verification-fixture",
        tags=("synthetic", "verification"),
    )
    try:
        before = ingestion.diligence_status(ctx)["completeness"]
        receipt = ingestion.ingest(ctx, request)
        after = ingestion.diligence_status(ctx)["completeness"]
        snapshot = workspace.snapshot(ctx)
        policy = RuntimePolicy("x" * 32)
        policy.authorize("POST", "/v1/documents")
        policy.authorize("POST", "/v1/search")
        policy.authorize("GET", "/v1/diligence")
        policy.authorize("GET", "/v1/workspace")
        trade_denied = False
        try:
            policy.authorize("POST", "/trade/order")
        except PermissionError:
            trade_denied = True
        pdf_failed_closed = False
        try:
            parse_document(b"%PDF-reference", "application/pdf")
        except IngestionError as exc:
            pdf_failed_closed = str(exc) == "PDF_TEXT_EXTRACTION_REQUIRED"
        checks = {
            "rc4_regression": bool(rc4.get("passed")),
            "json_ingestion_succeeds": receipt.get("state") == "SUCCESS"
            and receipt.get("parser", {}).get("parser_id") == "JSON_STDLIB_V1",
            "diligence_progresses_from_ingested_evidence": float(after) > float(before),
            "workspace_export_is_digest_bound": snapshot.get("document_count") == 1
            and len(str(snapshot.get("bundle_sha256", ""))) == 64,
            "workspace_export_omits_extracted_text": all(
                "extracted_text" not in document for document in snapshot.get("documents", [])
            ),
            "workspace_export_preserves_human_authority": snapshot.get("requires_human_decision") is True
            and snapshot.get("external_effects") is False,
            "safe_workspace_routes_admitted": True,
            "consequential_route_still_denied": trade_denied,
            "pdf_extraction_fails_closed_without_text_proof": pdf_failed_closed,
            "provider_maturity_not_overpromoted": rc4.get("maturity") == "PROVIDER_BINDING_READY",
        }
    finally:
        vault.close()

    return {
        "passed": all(checks.values()),
        "release": "1.0.0-rc5",
        "maturity": "PROVIDER_BINDING_READY",
        "internal_product_state": "INTERNAL_COMPLETION_CANDIDATE",
        "checks": checks,
        "production_claim": False,
    }
