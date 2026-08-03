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

USER_AGENT = (
    "Mozilla/5.0 (compatible; EvidenceOps-P13-Freshness/7.2.2; "
    "+https://github.com/mosianekk-lang/Federation-Omega)"
)
SELECTED_HEADERS = {
    "accept-ranges", "cache-control", "content-disposition", "content-length",
    "content-type", "date", "etag", "expires", "last-modified", "server",
    "x-content-type-options",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def safe_headers(headers: Any) -> dict[str, str]:
    return {key.lower(): str(value) for key, value in headers.items() if key.lower() in SELECTED_HEADERS}


def fetch(url: str, read_timeout: int = 60) -> tuple[bytes, dict[str, Any]]:
    started = time.perf_counter()
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-ZA,en;q=0.9",
        },
        timeout=(12, read_timeout),
        allow_redirects=True,
    )
    response.raise_for_status()
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
        "tls_verification": "CERTIFI_DEFAULT_VERIFIED",
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
        return "RAW_PROVIDER_BYTE_RETRIEVAL_FAILED"
    if source_class == "CURRENT_PRIMARY_RULES":
        if listing_verified and markers_verified:
            return "CURRENT_OFFICIAL_RULES_DOCUMENT_IDENTITY_VERIFIED"
        return "RAW_RULES_DOCUMENT_IDENTITY_VERIFIED_CURRENT_LISTING_OR_MARKER_GAP"
    if source_class == "BASE_ACT_CONSOLIDATED_CURRENTNESS_UNVERIFIED":
        return "OFFICIAL_BASE_ACT_RAW_BYTES_VERIFIED_CONSOLIDATED_CURRENTNESS_UNVERIFIED"
    if source_class == "CURRENT_SECONDARY_RESOURCE":
        return "OFFICIAL_SECONDARY_RESOURCE_RAW_BYTES_VERIFIED_PRIMARY_AUTHORITY_REQUIRED"
    if source_class == "PROPOSED_OR_CONSULTATIVE_NON_CURRENT":
        return "OFFICIAL_PROPOSED_OR_CONSULTATIVE_RAW_BYTES_VERIFIED_NON_CURRENT"
    return "RAW_PROVIDER_BYTES_VERIFIED_UNCLASSIFIED"


def process_source(source: dict[str, Any], output_dir: Path, observed_at: str) -> dict[str, Any]:
    filename = source["filename"]
    record: dict[str, Any] = {
        "source_id": source["source_id"],
        "source_class": source["source_class"],
        "document_url": source["document_url"],
        "listing_url": source.get("listing_url"),
        "filename": filename,
        "observed_at_utc": observed_at,
    }
    try:
        body, document_http = fetch(source["document_url"], int(source.get("read_timeout", 60)))
        (output_dir / filename).write_bytes(body)
        pdf_magic = body.startswith(b"%PDF-")
        extracted_text, page_count, extraction_error = extract_pdf_text(body, int(source.get("extract_pages", 2)))
        text = normalized(extracted_text)
        marker_results = {marker: normalized(marker) in text for marker in source.get("expected_markers", [])}
        markers_verified = all(marker_results.values()) if marker_results else True

        listing_http: dict[str, Any] | None = None
        listing_sha256: str | None = None
        listing_marker_results: dict[str, bool] = {}
        listing_verified = False
        listing_error: str | None = None
        if source.get("listing_url"):
            try:
                listing_body, listing_http = fetch(source["listing_url"], 45)
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
            "raw_provider_bytes_verified": raw_verified,
            "maturity": classify(source["source_class"], raw_verified, listing_verified, markers_verified),
        })
    except Exception as exc:
        record.update({
            "download_success": False,
            "raw_provider_bytes_verified": False,
            "error": f"{type(exc).__name__}: {exc}",
            "maturity": "RAW_PROVIDER_BYTE_RETRIEVAL_FAILED",
        })
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

    raw_gate = all(item.get("raw_provider_bytes_verified") for item in results)
    primary = [item for item in results if item["source_class"] == "CURRENT_PRIMARY_RULES"]
    primary_identity = all(
        item.get("raw_provider_bytes_verified")
        and item.get("expected_markers_verified")
        and item.get("listing_verified")
        for item in primary
    )
    base = [item for item in results if item["source_class"] == "BASE_ACT_CONSOLIDATED_CURRENTNESS_UNVERIFIED"]
    secondary = [item for item in results if item["source_class"] == "CURRENT_SECONDARY_RESOURCE"]
    proposed = [item for item in results if item["source_class"] == "PROPOSED_OR_CONSULTATIVE_NON_CURRENT"]

    receipt: dict[str, Any] = {
        "schema": "OMEGAMAX_SOL_EVIDENCEOPS_V722_P13_RAW_PROVIDER_RECEIPT_V3",
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
            "raw_provider_byte_gate_passed": raw_gate,
            "current_primary_rules_document_identity_verified": primary_identity,
            "base_act_raw_bytes_verified": all(item.get("raw_provider_bytes_verified") for item in base),
            "secondary_resource_raw_bytes_verified": all(item.get("raw_provider_bytes_verified") for item in secondary),
            "proposed_or_consultative_raw_bytes_verified_and_noncurrent": all(item.get("raw_provider_bytes_verified") for item in proposed),
            "external_effects": 0,
            "authority_ceiling": catalog["authority_ceiling"],
        },
        "results": results,
        "state": (
            "RAW_PROVIDER_BYTES_HASHED_AND_DOCUMENT_IDENTITIES_VERIFIED_BASE_ACT_CONSOLIDATED_CURRENTNESS_AND_REAL_CASE_VALUE_HELD"
            if raw_gate and primary_identity
            else "RAW_PROVIDER_RETRIEVAL_PARTIAL_OR_IDENTITY_GAPS"
        ),
        "truth_boundary": (
            "This receipt proves byte-level retrieval, HTTP metadata capture, SHA-256 identity, PDF structure and bounded text-marker checks for observed official-provider files. "
            "It does not prove that base statutes are consolidated/current, replace proposition-level legal research, establish a case outcome, or grant consequential authority."
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
        "raw_provider_byte_gate_passed": raw_gate,
        "current_primary_rules_document_identity_verified": primary_identity,
    }, indent=2))
    return 0 if raw_gate and primary_identity else 2


if __name__ == "__main__":
    sys.exit(main())
