#!/usr/bin/env python3
"""Apply the reproducible subset of a private owner-device profile to an ADB target."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def adb(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["adb", *args], text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"adb command failed: {' '.join(args)}: {proc.stderr.strip()}")
    return proc


def shell(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb("shell", *args, check=check)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--report", default="mdtaf-owner-profile-application.json")
    args = parser.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    if profile.get("schema") != "FUSE_OWNER_DEVICE_PROFILE_V1":
        raise SystemExit("Unsupported owner-device profile schema")
    if profile.get("privacy", {}).get("personal_data_captured") is not False:
        raise SystemExit("Refusing a profile that does not declare privacy-minimised capture")

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

    report = {
        "schema": "FUSE_OWNER_PROFILE_APPLICATION_V1",
        "state": "OWNER_PROFILE_APPLIED_WITH_FIDELITY_REPORT",
        "applied": applied,
        "fidelity_gaps": gaps,
        "owner_android_sdk": owner_sdk,
        "target_android_sdk": target_sdk,
        "owner_abi": owner_abi,
        "target_abi": target_abi,
        "personal_data_used": False,
    }
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
