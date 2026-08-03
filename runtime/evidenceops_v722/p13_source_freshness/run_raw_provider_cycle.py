from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

USER_AGENT = (
    "Mozilla/5.0 (compatible; EvidenceOps-P13-Freshness/7.2.2; "
    "+https://github.com/mosianekk-lang/Federation-Omega)"
)
SELECTED_HEADERS = {
    "accept-ranges",
    "cache-control",
    "content-disposition",
    "content-length",
    "content-type",
    "date",
    "etag",
    "expires",
    "last-modified",
    "server",
    "x-content-type-options",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def safe_headers(headers: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in SELECTED_HEADERS:
            result[lower] = str(value)
    return result


def fetch(url: str, attempts: int = 4, timeout: int = 90) -> tuple[bytes, dict[str, Any]]:
    context = ssl.create_default_context()
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-ZA,en;q=0.9",
            },
        )
        try:
            started = time.perf_counter()
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                body = response.read()
                metadata = {
                    "requested_url": url,
                    "final_url": response.geturl(),
                    "status": getattr(response, "status", None),
                    "reason": getattr(response, "reason", None),
                    "headers": safe_headers(response.headers),
                    "elapsed_seconds": round(time.perf_counter() - started, 6),
                    "attempt": attempt,
                }
                return body, metadata
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def extract_pdf_text(body: bytes, pages: int) -> tuple[str, int, str | None]:
    try:
        reader = PdfReader(io.BytesIO(body), strict=False)
        text_parts: list[str] = []
        for page in reader.pages[: max(1, pages)]:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts), len(reader.pages), None
    except Exception as exc:  # preserve failure rather than fabricating content
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--state-output", required=True)
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    output_dir = Path(args.output)
    state_output = Path(args.state_output)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_output.parent.mkdir(parents=True, exist_ok=True)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    results: list[dict[str, Any]] = []

    for source in catalog["sources"]:
        source_id = source["source_id"]
        filename = source["filename"]
        record: dict[str, Any] = {
            "source_id": source_id,
            "source_class": source["source_class"],
            "document_url": source["document_url"],
            "listing_url": source.get("listing_url"),
            "filename": filename,
            "observed_at_utc": observed_at,
        }
        try:
            document_body, document_http = fetch(source["document_url"])
            document_path = output_dir / filename
            document_path.write_bytes(document_body)
            pdf_magic = document_body.startswith(b"%PDF-")
            extracted_text, page_count, extraction_error = extract_pdf_text(
                document_body, int(source.get("extract_pages", 2))
            )
            normalized_text = normalized(extracted_text)
            marker_results = {
                marker: normalized(marker) in normalized_text
                for marker in source.get("expected_markers", [])
            }
            markers_verified = all(marker_results.values()) if marker_results else True

            listing_verified = False
            listing_http: dict[str, Any] | None = None
            listing_sha256: str | None = None
            listing_marker_results: dict[str, bool] = {}
            listing_error: str | None = None
            if source.get("listing_url"):
                try:
                    listing_body, listing_http = fetch(source["listing_url"])
                    listing_sha256 = sha256_bytes(listing_body)
                    (output_dir / f"{filename}.listing.html").write_bytes(listing_body)
                    listing_text = normalized(listing_body.decode("utf-8", errors="replace"))
                    listing_marker_results = {
                        marker: normalized(marker) in listing_text
                        for marker in source.get("listing_markers", [])
                    }
                    listing_verified = (
                        all(listing_marker_results.values()) if listing_marker_results else True
                    )
                except Exception as exc:
                    listing_error = f"{type(exc).__name__}: {exc}"

            raw_verified = pdf_magic and len(document_body) > 1024 and page_count > 0
            record.update(
                {
                    "download_success": True,
                    "document_http": document_http,
                    "document_sha256": sha256_bytes(document_body),
                    "document_size_bytes": len(document_body),
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
                    "maturity": classify(
                        source["source_class"], raw_verified, listing_verified, markers_verified
                    ),
                }
            )
            metadata_path = output_dir / f"{filename}.metadata.json"
            metadata_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as exc:
            record.update(
                {
                    "download_success": False,
                    "raw_provider_bytes_verified": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "maturity": "RAW_PROVIDER_BYTE_RETRIEVAL_FAILED",
                }
            )
        results.append(record)

    raw_gate = all(item.get("raw_provider_bytes_verified") for item in results)
    primary_rules = [item for item in results if item["source_class"] == "CURRENT_PRIMARY_RULES"]
    primary_rules_identity = all(
        item.get("raw_provider_bytes_verified")
        and item.get("expected_markers_verified")
        and item.get("listing_verified")
        for item in primary_rules
    )
    base_acts = [
        item for item in results
        if item["source_class"] == "BASE_ACT_CONSOLIDATED_CURRENTNESS_UNVERIFIED"
    ]
    base_acts_hashed = all(item.get("raw_provider_bytes_verified") for item in base_acts)
    secondary = [item for item in results if item["source_class"] == "CURRENT_SECONDARY_RESOURCE"]
    secondary_hashed = all(item.get("raw_provider_bytes_verified") for item in secondary)
    proposed = [
        item for item in results
        if item["source_class"] == "PROPOSED_OR_CONSULTATIVE_NON_CURRENT"
    ]
    proposed_hashed_and_blocked = all(item.get("raw_provider_bytes_verified") for item in proposed)

    receipt: dict[str, Any] = {
        "schema": "OMEGAMAX_SOL_EVIDENCEOPS_V722_P13_RAW_PROVIDER_RECEIPT_V1",
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
            "source_count_expected": len(catalog["sources"]),
            "source_count_observed": len(results),
            "raw_provider_byte_gate_passed": raw_gate,
            "current_primary_rules_document_identity_verified": primary_rules_identity,
            "base_act_raw_bytes_verified": base_acts_hashed,
            "secondary_resource_raw_bytes_verified": secondary_hashed,
            "proposed_or_consultative_raw_bytes_verified_and_noncurrent": proposed_hashed_and_blocked,
            "external_effects": 0,
            "authority_ceiling": catalog["authority_ceiling"],
        },
        "results": results,
        "state": (
            "RAW_PROVIDER_BYTES_HASHED_AND_DOCUMENT_IDENTITIES_VERIFIED_"
            "BASE_ACT_CONSOLIDATED_CURRENTNESS_AND_REAL_CASE_VALUE_HELD"
            if raw_gate and primary_rules_identity
            else "RAW_PROVIDER_RETRIEVAL_PARTIAL_OR_IDENTITY_GAPS"
        ),
        "truth_boundary": (
            "This receipt proves byte-level retrieval, HTTP metadata capture, SHA-256 identity, "
            "PDF structure and bounded text-marker checks for the observed official-provider files. "
            "It does not prove that base statutes are consolidated/current, does not replace "
            "proposition-level legal research, does not establish a case outcome, and grants no "
            "external-send, filing, recording, financial, destructive or provider-admin authority."
        ),
    }
    receipt["receipt_id"] = (
        f"RCP-V722-P13-RAW-{os.getenv('GITHUB_RUN_ID', 'LOCAL')}-"
        f"{os.getenv('GITHUB_RUN_ATTEMPT', '1')}"
    )
    receipt["receipt_sha256"] = sha256_bytes(canonical_bytes(receipt))

    receipt_path = output_dir / "p13_raw_provider_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    state_output.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "receipt_id": receipt["receipt_id"],
        "receipt_sha256": receipt["receipt_sha256"],
        "state": receipt["state"],
        "raw_provider_byte_gate_passed": raw_gate,
        "current_primary_rules_document_identity_verified": primary_rules_identity,
    }, indent=2))
    return 0 if raw_gate and primary_rules_identity else 2


if __name__ == "__main__":
    sys.exit(main())
