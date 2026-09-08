#!/usr/bin/env python3
"""Capture a privacy-minimised Android environment profile through ADB.

The output is intended for a private evidence/configuration plane. This script does
not enumerate user applications or read personal files, accounts or application data.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run(*args: str) -> str:
    proc = subprocess.run(["adb", *args], text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"adb command failed: {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def shell(*args: str) -> str:
    return run("shell", *args)


def prop(name: str) -> str:
    return shell("getprop", name).strip()


def parse_wm(text: str) -> list[int] | None:
    matches = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", text)
    if not matches:
        return None
    width, height = matches[-1]
    return [int(width), int(height)]


def parse_density(text: str) -> int | None:
    matches = re.findall(r"(?:Physical|Override) density:\s*(\d+)", text)
    return int(matches[-1]) if matches else None


def first_int(text: str) -> int | None:
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Private JSON output path")
    args = parser.parse_args()

    state = run("get-state")
    if state != "device":
        raise SystemExit(f"ADB target is not ready: {state!r}")

    size = parse_wm(shell("wm", "size"))
    density = parse_density(shell("wm", "density"))
    mem_total_kib = first_int(shell("cat", "/proc/meminfo"))
    data_line = shell("df", "-k", "/data").splitlines()
    data_total_kib = None
    if len(data_line) >= 2:
        fields = data_line[-1].split()
        if len(fields) >= 2 and fields[1].isdigit():
            data_total_kib = int(fields[1])

    font_scale_raw = shell("settings", "get", "system", "font_scale")
    try:
        font_scale = float(font_scale_raw)
    except ValueError:
        font_scale = None

    profile = {
        "schema": "FUSE_OWNER_DEVICE_PROFILE_V1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "capture_method": "ADB_NON_PERSONAL_DEVICE_CHARACTERISTICS_ONLY",
        "android": {
            "manufacturer": prop("ro.product.manufacturer"),
            "brand": prop("ro.product.brand"),
            "model": prop("ro.product.model"),
            "device": prop("ro.product.device"),
            "product": prop("ro.product.name"),
            "release": prop("ro.build.version.release"),
            "sdk": first_int(prop("ro.build.version.sdk")),
            "security_patch": prop("ro.build.version.security_patch"),
            "abi": prop("ro.product.cpu.abi"),
            "abi_list": [x for x in prop("ro.product.cpu.abilist").split(",") if x],
            "build_type": prop("ro.build.type"),
            "low_ram": prop("ro.config.low_ram").lower() == "true",
        },
        "display": {
            "size_px": size,
            "density_dpi": density,
            "font_scale": font_scale,
        },
        "capacity": {
            "ram_total_kib": mem_total_kib,
            "data_partition_total_kib": data_total_kib,
        },
        "regional": {
            "timezone": prop("persist.sys.timezone"),
            "locale": prop("persist.sys.locale") or prop("ro.product.locale"),
        },
        "privacy": {
            "personal_data_captured": False,
            "hardware_unique_identifiers_captured": False,
            "application_inventory_captured": False,
            "application_private_data_captured": False,
            "credentials_or_tokens_captured": False,
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": "OWNER_DEVICE_PROFILE_CAPTURED", "output": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
