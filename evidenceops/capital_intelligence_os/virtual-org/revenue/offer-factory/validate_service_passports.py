#!/usr/bin/env python3
"""Deterministic validator for EvidenceOps service passports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_SERVICE_FIELDS = {
    "service_id",
    "title",
    "buyer_problem",
    "scope",
    "deliverables",
    "proof_state",
    "dependencies",
    "exclusions",
    "data_controls",
    "pricing_band_zar",
    "approval_gate",
    "claim_boundary",
}

def validate(payload: dict) -> list[str]:
    errors: list[str] = []
    if payload.get("commercial_status") != "INTERNAL_RELEASE_CANDIDATE":
        errors.append("commercial_status must remain INTERNAL_RELEASE_CANDIDATE")
    if payload.get("external_approval_required") is not True:
        errors.append("external_approval_required must be true")
    services = payload.get("services")
    if not isinstance(services, list) or not services:
        return errors + ["services must be a non-empty list"]

    seen: set[str] = set()
    for index, service in enumerate(services):
        prefix = f"services[{index}]"
        missing = sorted(REQUIRED_SERVICE_FIELDS - set(service))
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
        sid = service.get("service_id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"{prefix}.service_id must be a non-empty string")
        elif sid in seen:
            errors.append(f"{prefix}.service_id is duplicated: {sid}")
        else:
            seen.add(sid)

        price = service.get("pricing_band_zar", {})
        minimum = price.get("minimum")
        maximum = price.get("maximum")
        if not isinstance(minimum, int) or not isinstance(maximum, int):
            errors.append(f"{prefix}.pricing_band_zar minimum/maximum must be integers")
        elif minimum <= 0 or maximum < minimum:
            errors.append(f"{prefix}.pricing_band_zar is invalid")
        if price.get("status") != "INTERNAL_NONBINDING":
            errors.append(f"{prefix}.pricing_band_zar.status must be INTERNAL_NONBINDING")
        if service.get("approval_gate") != "FOUNDER_APPROVAL_BEFORE_EXTERNAL_QUOTE":
            errors.append(f"{prefix}.approval_gate is unsafe")

    return errors

def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("service-passports.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 1
    print(json.dumps({
        "status": "PASS",
        "service_count": len(payload["services"]),
        "service_ids": [service["service_id"] for service in payload["services"]],
        "external_approval_required": payload["external_approval_required"],
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
