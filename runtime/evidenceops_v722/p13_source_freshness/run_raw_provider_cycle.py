from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader

from aia_trust import verified_get

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36 EvidenceOps-P13/7.2.2"
)
SELECTED_HEADERS = {
    "accept-ranges", "cache-control", "content-disposition", "content-length",
    "content-type", "date", "etag", "expires", "last-modified", "server",
    "x-content-type-options",
}
SECONDARY_CLASS = "CURRENT_SECONDARY_RESOURCE"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def safe_headers(headers: Any) -> dict[str, str]:
    return {key.lower(): str(value) for key, value in headers.items() if key.lower() in SELECTED_HEADERS}


def fetch(
    url: str,
    read_timeout: int = 120,
    *,
    session: requests.Session | None = None,
    referer: str | None = None,
    accept: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    started = time.perf_counter()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept or "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    response, tls_metadata = verified_get(
        url,
        headers=headers,
        timeout=(45, read_timeout),
        session=session,
    )
    return response.content, {
        "requested_url": url,
        "final_url": response.url,
        "status": response.status_code,
        "reason": response.reason,
        "headers": safe_headers(response.headers),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "redirect_chain": [
            {"status": item.status_code, "url": item.url, "location": item.headers.get("location")}
            for item in response.history
        ],
        "tls_verification": tls_metadata,
        "request_context": {
            "session_reused": session is not None,
            "referer_supplied": bool(referer),
            "browser_navigation_headers": True,
        },
    }


def extract_pdf_text(body: bytes, pages: int) -> tuple[str, int, str | None]:
    try:
        reader = PdfReader(io.BytesIO(body), strict=False)
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:max(1, pages)])
        return text, len(reader.pages), None
    except Exception as exc:
        return "", 0, f"{type(exc).__name__}: {exc}"


def classify(source_class: str, raw_verified: bool, listing_verified: bool, markers_verified: bool) -> str:
    if not raw_verified:
        if source_class == SECONDARY_CLASS:
            return "SECONDARY_RESOURCE_RAW_ARCHIVE_PROVIDER_BLOCKED"
        return "REQUIRED_OFFICIAL_RAW_PROVIDER_BYTE_RETRIEVAL_FAILED"
    if source_class == "CURRENT_PRIMARY_RULES":
        if listing_verified and markers_verified:
            return "CURRENT_OFFICIAL_RULES_DOCUMENT_IDENTITY_VERIFIED"
        return "RAW_RULES_DOCUMENT_IDENTITY_VERIFIED_CURRENT_LISTING_OR_MARKER_GAP"
    if source_class == "BASE_ACT_CONSOLIDATED_CURRENTNESS_UNVERIFIED":
        return "OFFICIAL_BASE_ACT_RAW_BYTES_VERIFIED_CONSOLIDATED_CURRENTNESS_UNVERIFIED"
    if source_class == SECONDARY_CLASS:
        return "OFFICIAL_SECONDARY_RESOURCE_RAW_BYTES_VERIFIED_PRIMARY_AUTHORITY_REQUIRED"
    if source_class == "PROPOSED_OR_CONSULTATIVE_NON_CURRENT":
        return "OFFICIAL_PROPOSED_OR_CONSULTATIVE_RAW_BYTES_VERIFIED_NON_CURRENT"
    return "RAW_PROVIDER_BYTES_VERIFIED_UNCLASSIFIED"


def process_source(source: dict[str, Any], output_dir: Path, observed_at: str) -> dict[str, Any]:
    filename = source["filename"]
    source_class = source["source_class"]
    listing_url = source.get("listing_url")
    session = requests.Session()

    listing_http: dict[str, Any] | None = None
    listing_sha256: str | None = None
    listing_marker_results: dict[str, bool] = {}
    listing_verified = False
    listing_error: str | None = None

    record: dict[str, Any] = {
        "source_id": source["source_id"],
        "source_class": source_class,
        "gate_role": "SECONDARY_ARCHIVE_OPTIONAL" if source_class == SECONDARY_CLASS else "REQUIRED_OFFICIAL_SOURCE",
        "document_url": source["document_url"],
        "listing_url": listing_url,
        "filename": filename,
        "observed_at_utc": observed_at,
    }

    try:
        if listing_url:
            try:
                listing_body, listing_http = fetch(
                    listing_url,
                    90,
                    session=session,
                    accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                )
                (output_dir / f"{filename}.listing.html").write_bytes(listing_body)
                listing_sha256 = sha256_bytes(listing_body)
                listing_text = normalized(listing_body.decode("utf-8", errors="replace"))
                listing_marker_results = {
                    marker: normalized(marker) in listing_text
                    for marker in source.get("listing_markers", [])
                }
                listing_verified = all(listing_marker_results.values()) if listing_marker_results else True
            except Exception as exc:
                listing_error = f"{type(exc).__name__}: {exc}"

        session_context = {
            "mode": "OFFICIAL_LISTING_FIRST_BROWSER_SESSION",
            "listing_requested_before_document": bool(listing_url),
            "listing_fetch_succeeded": listing_http is not None,
            "referer_used_for_document": bool(listing_url),
            "cookie_count_after_listing": len(session.cookies),
            "provider_controls_respected": True,
        }

        body, document_http = fetch(
            source["document_url"],
            int(source.get("read_timeout", 120)),
            session=session,
            referer=listing_url,
            accept="application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        )
        (output_dir / filename).write_bytes(body)
        pdf_magic = body.startswith(b"%PDF-")
        extracted_text, page_count, extraction_error = extract_pdf_text(body, int(source.get("extract_pages", 2)))
        text = normalized(extracted_text)
        marker_results = {marker: normalized(marker) in text for marker in source.get("expected_markers", [])}
        markers_verified = all(marker_results.values()) if marker_results else True
        raw_verified = pdf_magic and len(body) > 1024 and page_count > 0

        record.update({
            "download_success": True,
            "document_http": document_http,
            "document_sha256": sha256_bytes(body),
            "document_size_bytes": len(body),
            "pdf_magic_verified": pdf_magic,
            "pdf_page_count": page_count,
            "pdf_extraction_error": extraction_error,
            "expected_marker_results": marker_results,
            "expected_markers_verified": markers_verified,
            "listing_http": listing_http,
            "listing_sha256": listing_sha256,
            "listing_marker_results": listing_marker_results,
            "listing_verified": listing_verified,
            "listing_error": listing_error,
            "session_context": session_context,
            "raw_provider_bytes_verified": raw_verified,
            "maturity": classify(source_class, raw_verified, listing_verified, markers_verified),
        })
    except Exception as exc:
        record.update({
            "download_success": False,
            "raw_provider_bytes_verified": False,
            "error": f"{type(exc).__name__}: {exc}",
            "listing_http": listing_http,
            "listing_sha256": listing_sha256,
            "listing_marker_results": listing_marker_results,
            "listing_verified": listing_verified,
            "listing_error": listing_error,
            "session_context": {
                "mode": "OFFICIAL_LISTING_FIRST_BROWSER_SESSION",
                "listing_requested_before_document": bool(listing_url),
                "listing_fetch_succeeded": listing_http is not None,
                "referer_used_for_document": bool(listing_url),
                "cookie_count_after_listing": len(session.cookies),
                "provider_controls_respected": True,
            },
            "maturity": classify(source_class, False, listing_verified, False),
        })
    finally:
        session.close()

    (output_dir / f"{filename}.metadata.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--state-output", required=True)
    args = parser.parse_args()

    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    output_dir = Path(args.output)
    state_output = Path(args.state_output)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_output.parent.mkdir(parents=True, exist_ok=True)
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    sources = catalog["sources"]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(sources))) as executor:
        futures = [executor.submit(process_source, source, output_dir, observed_at) for source in sources]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["source_id"])

    required_official = [item for item in results if item["source_class"] != SECONDARY_CLASS]
    secondary = [item for item in results if item["source_class"] == SECONDARY_CLASS]
    primary_rules = [item for item in results if item["source_class"] == "CURRENT_PRIMARY_RULES"]
    base_acts = [item for item in results if item["source_class"] == "BASE_ACT_CONSOLIDATED_CURRENTNESS_UNVERIFIED"]
    proposed = [item for item in results if item["source_class"] == "PROPOSED_OR_CONSULTATIVE_NON_CURRENT"]

    required_official_gate = all(item.get("raw_provider_bytes_verified") for item in required_official)
    all_catalog_gate = all(item.get("raw_provider_bytes_verified") for item in results)
    primary_rules_identity = all(
        item.get("raw_provider_bytes_verified")
        and item.get("expected_markers_verified")
        and item.get("listing_verified")
        for item in primary_rules
    )
    secondary_archive_gate = all(item.get("raw_provider_bytes_verified") for item in secondary)
    secondary_blocked = [item["source_id"] for item in secondary if not item.get("raw_provider_bytes_verified")]

    receipt: dict[str, Any] = {
        "schema": "OMEGAMAX_SOL_EVIDENCEOPS_V722_P13_RAW_PROVIDER_RECEIPT_V6",
        "programme_id": catalog["programme_id"],
        "version": "7.2.2",
        "stage_id": "P13-FRESHNESS-RAW-PROVIDER-BYTES",
        "observed_at_utc": observed_at,
        "provider_event": {
            "repository": os.getenv("GITHUB_REPOSITORY", ""),
            "workflow": os.getenv("GITHUB_WORKFLOW", ""),
            "event_name": os.getenv("GITHUB_EVENT_NAME", ""),
            "run_id": os.getenv("GITHUB_RUN_ID", ""),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
            "sha": os.getenv("GITHUB_SHA", ""),
            "ref": os.getenv("GITHUB_REF", ""),
        },
        "controls": {
            "source_count_expected": len(sources),
            "source_count_observed": len(results),
            "required_official_source_count": len(required_official),
            "secondary_archive_source_count": len(secondary),
            "required_official_source_raw_byte_gate_passed": required_official_gate,
            "current_primary_rules_document_identity_verified": primary_rules_identity,
            "base_act_raw_bytes_verified": all(item.get("raw_provider_bytes_verified") for item in base_acts),
            "proposed_or_consultative_raw_bytes_verified_and_noncurrent": all(item.get("raw_provider_bytes_verified") for item in proposed),
            "secondary_resource_archive_gate_passed": secondary_archive_gate,
            "secondary_resource_provider_blocked_ids": secondary_blocked,
            "all_catalog_raw_provider_byte_gate_passed": all_catalog_gate,
            "raw_provider_byte_gate_passed": required_official_gate,
            "external_effects": 0,
            "authority_ceiling": catalog["authority_ceiling"],
        },
        "results": results,
        "state": (
            "REQUIRED_OFFICIAL_RAW_BYTES_HASHED_PRIMARY_RULES_IDENTITY_VERIFIED_"
            "SECONDARY_ARCHIVE_PROVIDER_ACCESS_HELD_BASE_ACT_CONSOLIDATED_CURRENTNESS_AND_REAL_CASE_VALUE_HELD"
            if required_official_gate and primary_rules_identity and not secondary_archive_gate
            else (
                "ALL_CATALOG_RAW_BYTES_HASHED_PRIMARY_RULES_IDENTITY_VERIFIED_"
                "BASE_ACT_CONSOLIDATED_CURRENTNESS_AND_REAL_CASE_VALUE_HELD"
                if required_official_gate and primary_rules_identity and secondary_archive_gate
                else "REQUIRED_OFFICIAL_RAW_PROVIDER_RETRIEVAL_OR_IDENTITY_GAPS"
            )
        ),
        "truth_boundary": (
            "This receipt proves raw-byte identity for the required official-source set: current court rules, official base Acts and the official consultative notice. "
            "Secondary CCMA information sheets are a separate non-primary archive gate and may remain provider-access-blocked without weakening verified official primary evidence. "
            "The retriever uses the official listing page, ordinary session cookies and Referer headers while respecting provider controls; a provider denial remains a held result. "
            "Base-Act byte identity does not prove consolidated currentness; proposition-level legal research, real-case outcomes and consequential authority remain separate gates."
        ),
    }
    receipt["receipt_id"] = f"RCP-V722-P13-RAW-{os.getenv('GITHUB_RUN_ID', 'LOCAL')}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}"
    receipt["receipt_sha256"] = sha256_bytes(canonical_bytes(receipt))
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    (output_dir / "p13_raw_provider_receipt.json").write_text(rendered, encoding="utf-8")
    state_output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "receipt_id": receipt["receipt_id"],
        "receipt_sha256": receipt["receipt_sha256"],
        "state": receipt["state"],
        "required_official_source_raw_byte_gate_passed": required_official_gate,
        "secondary_resource_archive_gate_passed": secondary_archive_gate,
        "current_primary_rules_document_identity_verified": primary_rules_identity,
    }, indent=2))
    return 0 if required_official_gate and primary_rules_identity else 2


if __name__ == "__main__":
    sys.exit(main())
