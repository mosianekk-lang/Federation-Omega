#!/usr/bin/env python3
"""Apply the reproducible subset of a private owner-device profile to an ADB target.

Both legacy V1 and progressive high-fidelity V2 owner profiles are accepted. The
applicator never pretends that app ecology, real content, literal identifiers or
other physical-only variables have been reproduced when the target AVD cannot
faithfully express them; those variables remain explicit fidelity gaps.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

SUPPORTED_PROFILE_SCHEMAS = {"FUSE_OWNER_DEVICE_PROFILE_V1", "FUSE_OWNER_DEVICE_PROFILE_V2"}


def adb(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["adb", *args], text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"adb command failed: {' '.join(args)}: {proc.stderr.strip()}")
    return proc


def shell(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb("shell", *args, check=check)


def profile_secret_boundary_is_safe(profile: dict[str, Any]) -> bool:
    schema = profile.get("schema")
    if schema == "FUSE_OWNER_DEVICE_PROFILE_V1":
        privacy = profile.get("privacy", {})
        return (
            privacy.get("credentials_or_tokens_captured") is False
            and privacy.get("hardware_unique_identifiers_captured") is False
        )
    if schema == "FUSE_OWNER_DEVICE_PROFILE_V2":
        controls = profile.get("capture_controls", {})
        return (
            controls.get("credentials_or_tokens_captured") is False
            and controls.get("live_secret_clone_allowed") is False
            and controls.get("public_repository_storage_allowed") is False
        )
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--report", default="mdtaf-owner-profile-application.json")
    args = parser.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    schema = profile.get("schema")
    if schema not in SUPPORTED_PROFILE_SCHEMAS:
        raise SystemExit("Unsupported owner-device profile schema")
    if not profile_secret_boundary_is_safe(profile):
        raise SystemExit("Refusing owner profile without a safe live-secret boundary")

    if adb("get-state").stdout.strip() != "device":
        raise SystemExit("ADB target is not ready")

    applied: dict[str, object] = {}
    gaps: list[str] = []

    size = profile.get("display", {}).get("size_px")
    if isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and v > 0 for v in size):
        shell("wm", "size", f"{size[0]}x{size[1]}")
        applied["display_size_px"] = size
    else:
        gaps.append("display_size_unavailable")

    density = profile.get("display", {}).get("density_dpi")
    if isinstance(density, int) and density > 0:
        shell("wm", "density", str(density))
        applied["density_dpi"] = density
    else:
        gaps.append("display_density_unavailable")

    font_scale = profile.get("display", {}).get("font_scale")
    if isinstance(font_scale, (float, int)) and font_scale > 0:
        shell("settings", "put", "system", "font_scale", str(font_scale))
        applied["font_scale"] = float(font_scale)
    else:
        gaps.append("font_scale_unavailable")

    locale = profile.get("regional", {}).get("locale")
    timezone = profile.get("regional", {}).get("timezone")
    if locale:
        gaps.append("locale_requires_avd_or_privileged_configuration")
    if timezone:
        gaps.append("timezone_requires_avd_or_privileged_configuration")

    owner_sdk = profile.get("android", {}).get("sdk")
    target_sdk_raw = shell("getprop", "ro.build.version.sdk").stdout.strip()
    target_sdk = int(target_sdk_raw) if target_sdk_raw.isdigit() else None
    if owner_sdk != target_sdk:
        gaps.append(f"android_api_mismatch_owner_{owner_sdk}_target_{target_sdk}")

    owner_abi = profile.get("android", {}).get("abi")
    target_abi = shell("getprop", "ro.product.cpu.abi").stdout.strip()
    if owner_abi and owner_abi != target_abi:
        gaps.append(f"abi_mismatch_owner_{owner_abi}_target_{target_abi}")

    high_fidelity_sections: list[str] = []
    if schema == "FUSE_OWNER_DEVICE_PROFILE_V2":
        for section in (
            "power",
            "connectivity",
            "application_ecology",
            "account_ecology",
            "content_structure_counts",
            "consent_bound_real_data",
        ):
            if section in profile:
                high_fidelity_sections.append(section)

        if "application_ecology" in profile:
            gaps.append("application_ecology_requires_package_fixture_matrix_or_physical_validation")
        if "account_ecology" in profile:
            gaps.append("account_ecology_requires_identity_fixture_or_physical_validation")
        if "content_structure_counts" in profile:
            gaps.append("content_structure_requires_fixture_generation_or_physical_validation")
        if "consent_bound_real_data" in profile:
            gaps.append("consent_bound_real_data_requires_private_fixture_injection_or_physical_validation")
        if "connectivity" in profile:
            gaps.append("carrier_sim_vpn_dns_proxy_fidelity_requires_specialized_avd_or_physical_validation")
        if "power" in profile:
            gaps.append("battery_thermal_fidelity_requires_fault_injection_or_physical_validation")

    report = {
        "schema": "FUSE_OWNER_PROFILE_APPLICATION_V2",
        "state": "OWNER_PROFILE_APPLIED_WITH_FIDELITY_REPORT",
        "source_profile_schema": schema,
        "source_fidelity_level": profile.get("fidelity_level"),
        "applied": applied,
        "high_fidelity_sections_observed": high_fidelity_sections,
        "fidelity_gaps": sorted(set(gaps)),
        "owner_android_sdk": owner_sdk,
        "target_android_sdk": target_sdk,
        "owner_abi": owner_abi,
        "target_abi": target_abi,
        "sensitive_real_data_used_for_generic_avd_application": False,
        "live_secret_material_used": False,
        "truth_boundary": "A fidelity gap is preserved as evidence; unsupported real-world variables are never silently treated as reproduced.",
    }
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
