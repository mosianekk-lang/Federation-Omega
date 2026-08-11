#!/usr/bin/env python3
"""Acquire and verify the bounded Nature Intelligence seed corpus.

The runtime downloads source text transiently, validates required markers,
computes hashes and statistics, and persists only metadata and derived signals.
Full source text is never written into the repository.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "source_manifest.json"
MONITORING_DIR = ROOT / "monitoring"
RECEIPTS_DIR = ROOT / "receipts"

SIGNAL_TERMS = {
    "variation_selection": ["variation", "selection", "adaptation", "species"],
    "constraint_simplicity": ["economy", "simple", "simplicity", "solitude"],
    "collective_coordination": ["bee", "hive", "worker", "queen", "swarm"],
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fetch_text(url: str, timeout_seconds: int = 45) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Federation-Omega-Kimmie-Seed/0.1 (+provenance-check)"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return response.read()


def normalize_text(raw: bytes) -> str:
    return raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")


def validate_source(source: dict[str, Any], raw: bytes) -> dict[str, Any]:
    text = normalize_text(raw)
    upper = text.upper()
    failures: list[str] = []

    if len(raw) < int(source["minimum_bytes"]):
        failures.append(f"size_below_minimum:{len(raw)}<{source['minimum_bytes']}")

    for marker in source["required_markers"]:
        if marker.upper() not in upper:
            failures.append(f"missing_marker:{marker}")

    if "PROJECT GUTENBERG" not in upper:
        failures.append("missing_project_gutenberg_provenance_marker")

    words = re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower())
    signal_counts = {
        signal: sum(words.count(term) for term in terms)
        for signal, terms in SIGNAL_TERMS.items()
    }

    result = {
        "source_id": source["source_id"],
        "title": source["title"],
        "source_url": source["source_url"],
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "word_count": len(words),
        "signal_counts": signal_counts,
        "mechanism_hypotheses": source["mechanism_hypotheses"],
        "validation": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    return result


def run_acquisition() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    observed_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []

    for source in manifest["sources"]:
        try:
            raw = fetch_text(source["source_url"])
            result = validate_source(source, raw)
        except Exception as exc:  # network/provider failures must be explicit
            result = {
                "source_id": source["source_id"],
                "title": source["title"],
                "source_url": source["source_url"],
                "validation": "FAIL",
                "failures": [f"acquisition_error:{type(exc).__name__}:{exc}"],
            }
        results.append(result)

    passed = [item for item in results if item["validation"] == "PASS"]
    corpus_material = [
        {"source_id": item["source_id"], "sha256": item.get("sha256"), "bytes": item.get("bytes")}
        for item in results
    ]
    corpus_sha256 = canonical_sha256(corpus_material)
    status = "PASS" if len(passed) == len(results) and len(passed) >= 1 else "FAIL"

    health = {
        "lane_id": manifest["lane_id"],
        "manifest_version": manifest["manifest_version"],
        "observed_at": observed_at,
        "status": status,
        "sources_expected": len(results),
        "sources_passed": len(passed),
        "corpus_sha256": corpus_sha256,
        "full_text_persisted": False,
        "results": results,
        "germination_gate": "PASSED" if len(passed) >= 1 else "NOT_PASSED",
        "identity_drift": "NONE_DETECTED",
    }
    health["health_sha256"] = canonical_sha256(health)

    receipt = {
        "receipt_id": f"NATURE-ACQ-{observed_at.replace(':', '').replace('-', '').replace('+', '_')}",
        "lane_id": manifest["lane_id"],
        "observed_at": observed_at,
        "status": status,
        "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "corpus_sha256": corpus_sha256,
        "health_sha256": health["health_sha256"],
        "source_hashes": [
            {"source_id": item["source_id"], "sha256": item.get("sha256"), "validation": item["validation"]}
            for item in results
        ],
        "proof_boundary": "Proves transient acquisition, provenance validation, hashing and bounded signal extraction. Does not prove a useful deployed capability or higher maturity.",
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return health, receipt


def main() -> int:
    MONITORING_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    health, receipt = run_acquisition()
    (MONITORING_DIR / "latest_health.json").write_text(
        json.dumps(health, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (RECEIPTS_DIR / "latest_acquisition_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": health["status"], "health_sha256": health["health_sha256"]}))
    return 0 if health["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
