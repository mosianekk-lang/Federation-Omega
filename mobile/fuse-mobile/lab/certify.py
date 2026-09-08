#!/usr/bin/env python3
"""Compile MDTAF runtime evidence into a proof-before-claim release certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-sha", default=os.getenv("GITHUB_SHA", "UNKNOWN"))
    args = parser.parse_args()

    evidence = Path(args.evidence_dir)
    smoke = load(evidence / "smoke-receipt.json")
    security = load(evidence / "apk-security-scan.json")
    owner_profile = load(evidence / "owner-profile-application.json")
    cloud_matrix = load(evidence / "cloud-device-matrix.json")
    physical = load(evidence / "physical-device-validation.json")
    masvs = load(evidence / "masvs-review.json")
    performance = load(evidence / "performance-regression.json")

    smoke_apk_sha = smoke.get("apk_sha256") if smoke else None
    security_apk_sha = security.get("apk_sha256") if security else None
    artifact_hash_binding = bool(
        isinstance(smoke_apk_sha, str)
        and isinstance(security_apk_sha, str)
        and smoke_apk_sha
        and security_apk_sha
        and smoke_apk_sha == security_apk_sha
    )

    required = {
        "android_smoke": bool(smoke and smoke.get("state") == "ANDROID_SMOKE_PASS"),
        "apk_credential_scan": bool(security and security.get("state") == "APK_CREDENTIAL_SCAN_CLEAN"),
        "artifact_hash_binding": artifact_hash_binding,
        "first_launch": bool(smoke and smoke.get("first_launch_state") == "PASS"),
        "relaunch": bool(smoke and smoke.get("relaunch_state") == "PASS"),
        "network_baseline": bool(smoke and smoke.get("network_baseline_state") == "PASS"),
        "connectivity_loss_verified": bool(smoke and smoke.get("connectivity_loss_state") == "PASS"),
        "offline_launch": bool(smoke and smoke.get("offline_launch_state") == "PASS"),
        "network_recovery": bool(smoke and smoke.get("network_recovery_state") == "PASS"),
        "recovery_launch": bool(smoke and smoke.get("recovery_launch_state") == "PASS"),
        "no_fatal_or_anr": bool(smoke and not smoke.get("fatal_or_anr_hits")),
    }

    expansion = {
        "owner_reference_profile": bool(owner_profile and owner_profile.get("state") == "OWNER_PROFILE_APPLIED_WITH_FIDELITY_REPORT"),
        "cloud_virtual_device_matrix": bool(cloud_matrix and cloud_matrix.get("state") == "PASS"),
        "physical_device_validation": bool(physical and physical.get("state") == "PASS"),
        "owasp_masvs_review": bool(masvs and masvs.get("state") == "PASS"),
        "performance_regression": bool(performance and performance.get("state") == "PASS"),
    }

    failed_required = sorted(k for k, ok in required.items() if not ok)
    limitations = sorted(k for k, ok in expansion.items() if not ok)

    if failed_required:
        verdict = "NOT_RELEASE_READY"
    elif limitations:
        verdict = "RELEASE_VERIFIED_WITH_DECLARED_LIMITATIONS"
    else:
        verdict = "RELEASE_VERIFIED"

    certificate = {
        "schema": "FUSE_MOBILE_MDTAF_RELEASE_CERTIFICATE_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha": args.source_sha,
        "apk_sha256": smoke_apk_sha,
        "security_scan_apk_sha256": security_apk_sha,
        "artifact_hash_binding_state": "PASS" if artifact_hash_binding else "FAIL",
        "verdict": verdict,
        "required_gates": required,
        "failed_required_gates": failed_required,
        "expansion_gates": expansion,
        "declared_limitations": limitations,
        "truth_boundary": {
            "virtual_device_is_not_physical_device": True,
            "source_is_not_runtime": True,
            "offline_process_survival_alone_is_not_offline_proof": True,
            "security_receipt_requires_exact_apk_hash_match": True,
            "certificate_does_not_grant_provider_authority": True,
            "personal_device_data_cloned": False,
        },
    }
    canonical = json.dumps(certificate, indent=2, sort_keys=True) + "\n"
    certificate["certificate_payload_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(certificate, sort_keys=True))
    return 1 if verdict == "NOT_RELEASE_READY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
