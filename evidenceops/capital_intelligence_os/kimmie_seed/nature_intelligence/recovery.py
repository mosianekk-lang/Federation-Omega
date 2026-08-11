#!/usr/bin/env python3
"""Run a controlled corruption, rejection and deterministic recovery drill."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import translate

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "source_manifest.json"
HEALTH_PATH = ROOT / "monitoring" / "latest_health.json"
RECOVERY_DIR = ROOT / "recovery"
RECEIPT_PATH = RECOVERY_DIR / "latest_recovery_receipt.json"


def run_recovery_drill(manifest: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    baseline = translate.build_translation(manifest, health)
    translate.validate_translation(baseline)
    corrupted = copy.deepcopy(baseline)
    corrupted["records"][0]["engineering_pattern"] = "CORRUPTED_PATTERN"
    rejection = "NOT_TESTED"
    try:
        translate.validate_translation(corrupted)
    except ValueError as exc:
        rejection = f"PASS:{exc}"
    if not rejection.startswith("PASS:"):
        raise RuntimeError("controlled_corruption_was_not_rejected")
    recovered = translate.build_translation(manifest, health)
    translate.validate_translation(recovered)
    if recovered["translation_sha256"] != baseline["translation_sha256"]:
        raise RuntimeError("deterministic_recovery_hash_mismatch")
    return translate.add_digest({
        "receipt_id": "NATURE-RECOVERY-" + baseline["translation_sha256"][:20],
        "lane_id": baseline["lane_id"],
        "baseline_translation_sha256": baseline["translation_sha256"],
        "corruption_injected": "records[0].engineering_pattern",
        "tamper_rejection": rejection,
        "recovered_translation_sha256": recovered["translation_sha256"],
        "exact_restoration": "PASS",
        "controlled_recovery": "PASS",
        "identity_drift": "NONE_DETECTED",
        "proof_boundary": "Proves that a controlled translation-output corruption is rejected and the deterministic runtime restores the exact baseline hash. It does not prove recovery from every infrastructure or provider failure."
    }, "receipt_sha256")


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    health = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    receipt = run_recovery_drill(manifest, health)
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "receipt_sha256": receipt["receipt_sha256"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
