from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_ZIP_SHA256 = "8c4c781ca806f3839733ae3e32503323257acb7c2c5d12f7eb315418f8e7554d"
EXPECTED_MANIFEST_SHA256 = "bf0845c9f17402d1eee25240c1725ac21a617348c2292aab731c2121fdcf150e"
EXPECTED_BOUNDARY_SHA256 = "028d213d3388d694d6373befe0daff2cb1fa641977bfe8bb1d4ef286c9b44bcc"


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha256(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def main() -> int:
    status = load("FINAL_STATUS.json")
    receipt = load("RELEASE_RECEIPT.json")
    boundary = load("BOUNDARY_RESOLUTION.json")

    assert status["programme_id"] == "AO-FED-CONSOLIDATE-24H-001"
    assert status["version"] == "1.0.1"
    assert status["state"] == "ALL_CURRENT_COMPLETION_BOUNDARIES_RESOLVED_SCOPED"
    assert status["zip_sha256"] == EXPECTED_ZIP_SHA256
    assert status["manifest_sha256"] == EXPECTED_MANIFEST_SHA256
    assert status["tests_source"] == 10
    assert status["tests_clean_extract"] == 10
    assert status["database_quick_check"] == "ok"
    assert status["external_effects"] == 0

    assert receipt["sha256"] == EXPECTED_ZIP_SHA256
    assert receipt["source_manifest_sha256"] == EXPECTED_MANIFEST_SHA256
    assert receipt["boundary_resolution_sha256"] == EXPECTED_BOUNDARY_SHA256
    assert receipt["manifest_file_count"] == 41
    assert receipt["archive_entry_count"] == 42
    assert receipt["reproducible_build"] is True
    assert receipt["external_effects"] == 0

    assert sha256("BOUNDARY_RESOLUTION.json") == EXPECTED_BOUNDARY_SHA256
    assert boundary["state"] == "ALL_CURRENT_COMPLETION_BOUNDARIES_RESOLVED_SCOPED"
    assert boundary["authority_ceiling"] == "A1_REVERSIBLE_INTERNAL"
    assert boundary["external_effects"] == 0

    items = boundary["boundaries"]
    assert len(items) == 12
    assert len({item["id"] for item in items}) == 12
    by_id = {item["id"]: item["state"] for item in items}
    assert by_id["B06"] == "NOT_REQUIRED_CURRENT_MATURITY"
    assert by_id["B07"] == "NOT_REQUIRED_CURRENT_MATURITY"
    assert by_id["B09"] == "MEASUREMENT_ACTIVE_TIME_BOUND"
    assert by_id["B10"] == "PERMANENT_GUARDRAIL_ACTIVE_BY_DESIGN"
    assert by_id["B12"] == "RESOLVED_BY_V1_0_1_REBUILD"

    print(
        json.dumps(
            {
                "valid": True,
                "programme_id": status["programme_id"],
                "version": status["version"],
                "state": status["state"],
                "boundaries": len(items),
                "external_effects": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
