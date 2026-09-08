#!/usr/bin/env python3
"""Capture a progressive high-fidelity Android owner-device profile through ADB.

The collector is read-only and writes only to a caller-selected private output path.
It supports progressively richer real-world fidelity rather than treating personal
or sensitive variables as categorically irrelevant. Live secrets are never copied
into the twin; their behavioral effect must be reproduced through secure auth/test
mechanisms instead.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run(*args: str, required: bool = True) -> str | None:
    proc = subprocess.run(["adb", *args], text=True, capture_output=True)
    if proc.returncode != 0:
        if required:
            raise SystemExit(f"adb command failed: {' '.join(args)}: {proc.stderr.strip()}")
        return None
    return proc.stdout.strip()


def shell(*args: str, required: bool = True) -> str | None:
    return run("shell", *args, required=required)


def prop(name: str) -> str:
    return str(shell("getprop", name) or "").strip()


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


def parse_key_values(text: str | None, keys: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    if not text:
        return out
    for raw in text.splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        if key in keys:
            out[key] = value.strip()
    return out


def package_inventory(include_system: bool) -> list[dict[str, Any]]:
    args = ["pm", "list", "packages"]
    if not include_system:
        args.append("-3")
    text = str(shell(*args, required=False) or "")
    packages = sorted({line.removeprefix("package:").strip() for line in text.splitlines() if line.startswith("package:")})
    inventory: list[dict[str, Any]] = []
    for package in packages:
        detail = str(shell("dumpsys", "package", package, required=False) or "")
        version_name = re.search(r"versionName=([^\s]+)", detail)
        version_code = re.search(r"versionCode=(\d+)", detail)
        inventory.append(
            {
                "package": package,
                "version_name": version_name.group(1) if version_name else None,
                "version_code": int(version_code.group(1)) if version_code else None,
            }
        )
    return inventory


def account_provider_types() -> list[str]:
    text = str(shell("dumpsys", "account", required=False) or "")
    types = set(re.findall(r"type=([^,}\s]+)", text))
    types.update(re.findall(r"AccountAuthenticator\{type=([^,}\s]+)", text))
    return sorted(types)


def content_count(uri: str) -> dict[str, Any]:
    text = shell("content", "query", "--uri", uri, "--projection", "_id", required=False)
    if text is None:
        return {"state": "UNAVAILABLE", "count": None}
    rows = [line for line in text.splitlines() if line.lstrip().startswith("Row:")]
    return {"state": "CAPTURED", "count": len(rows)}


def real_content_sample(kind: str, limit: int) -> dict[str, Any]:
    commands = {
        "contacts": ("content", "query", "--uri", "content://contacts/phones", "--projection", "display_name:number"),
        "sms": ("content", "query", "--uri", "content://sms", "--projection", "_id:address:date:type:body"),
        "media": ("content", "query", "--uri", "content://media/external/file", "--projection", "_id:_data:mime_type:_size:date_modified"),
    }
    text = shell(*commands[kind], required=False)
    if text is None:
        return {"state": "UNAVAILABLE", "records": []}
    rows = [line.strip() for line in text.splitlines() if line.lstrip().startswith("Row:")]
    return {"state": "CAPTURED", "records": rows[:limit], "truncated": len(rows) > limit}


def literal_identifier_probe() -> dict[str, Any]:
    text = str(shell("dumpsys", "iphonesubinfo", required=False) or "")
    values: dict[str, str] = {}
    for label, pattern in {
        "imei": r"(?:IMEI|Device ID)\s*[:=]\s*([0-9]{14,17})",
        "line1_number": r"(?:Line1 Number|Phone Number)\s*[:=]\s*([^\s]+)",
    }.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            values[label] = match.group(1)
    return {"state": "CAPTURED" if values else "UNAVAILABLE_OR_RESTRICTED", "values": values}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Private JSON output path")
    parser.add_argument("--fidelity-level", type=int, choices=(1, 2, 3, 4), default=2)
    parser.add_argument("--include-system-packages", action="store_true")
    parser.add_argument("--include-literal-identifiers", action="store_true")
    parser.add_argument("--real-content-sample", action="append", choices=("contacts", "sms", "media"), default=[])
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--acknowledge-sensitive-capture", action="store_true")
    args = parser.parse_args()

    if args.sample_limit < 1 or args.sample_limit > 100:
        raise SystemExit("--sample-limit must be between 1 and 100")
    sensitive_requested = bool(args.include_literal_identifiers or args.real_content_sample)
    if sensitive_requested and not args.acknowledge_sensitive_capture:
        raise SystemExit("Sensitive Level-4 capture requires --acknowledge-sensitive-capture")
    if sensitive_requested and args.fidelity_level < 4:
        raise SystemExit("Sensitive real-data capture requires --fidelity-level 4")

    state = run("get-state")
    if state != "device":
        raise SystemExit(f"ADB target is not ready: {state!r}")

    size = parse_wm(str(shell("wm", "size") or ""))
    density = parse_density(str(shell("wm", "density") or ""))
    mem_total_kib = first_int(str(shell("cat", "/proc/meminfo") or ""))
    data_line = str(shell("df", "-k", "/data") or "").splitlines()
    data_total_kib = None
    data_free_kib = None
    if len(data_line) >= 2:
        fields = data_line[-1].split()
        if len(fields) >= 4 and fields[1].isdigit() and fields[3].isdigit():
            data_total_kib = int(fields[1])
            data_free_kib = int(fields[3])

    font_scale_raw = str(shell("settings", "get", "system", "font_scale") or "")
    try:
        font_scale = float(font_scale_raw)
    except ValueError:
        font_scale = None

    battery = parse_key_values(
        shell("dumpsys", "battery", required=False),
        {"level", "scale", "status", "health", "temperature", "voltage", "AC powered", "USB powered", "Wireless powered"},
    )
    connectivity = {
        "airplane_mode": shell("settings", "get", "global", "airplane_mode_on", required=False),
        "wifi_on": shell("settings", "get", "global", "wifi_on", required=False),
        "sim_state": prop("gsm.sim.state"),
        "carrier_alpha": prop("gsm.operator.alpha"),
        "carrier_numeric": prop("gsm.operator.numeric"),
        "multi_sim_config": prop("persist.radio.multisim.config"),
        "vpn_dump_available": shell("dumpsys", "vpn_management", required=False) is not None,
    }

    profile: dict[str, Any] = {
        "schema": "FUSE_OWNER_DEVICE_PROFILE_V2",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "capture_method": "ADB_PROGRESSIVE_HIGH_FIDELITY",
        "fidelity_level": args.fidelity_level,
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
        "display": {"size_px": size, "density_dpi": density, "font_scale": font_scale},
        "capacity": {
            "ram_total_kib": mem_total_kib,
            "data_partition_total_kib": data_total_kib,
            "data_partition_free_kib": data_free_kib,
        },
        "regional": {
            "timezone": prop("persist.sys.timezone"),
            "locale": prop("persist.sys.locale") or prop("ro.product.locale"),
        },
        "power": {"battery": battery},
        "connectivity": connectivity,
        "capture_controls": {
            "public_repository_storage_allowed": False,
            "sensitive_capture_acknowledged": bool(args.acknowledge_sensitive_capture),
            "credentials_or_tokens_captured": False,
            "live_secret_clone_allowed": False,
        },
    }

    if args.fidelity_level >= 2:
        profile["application_ecology"] = {
            "installed_packages": package_inventory(args.include_system_packages),
            "system_packages_included": bool(args.include_system_packages),
        }

    if args.fidelity_level >= 3:
        profile["account_ecology"] = {"provider_types": account_provider_types(), "literal_account_names_stored": False}
        profile["content_structure_counts"] = {
            "contacts": content_count("content://contacts/contacts"),
            "sms": content_count("content://sms"),
            "images": content_count("content://media/external/images/media"),
            "videos": content_count("content://media/external/video/media"),
            "files": content_count("content://media/external/file"),
        }

    if args.fidelity_level >= 4:
        profile["consent_bound_real_data"] = {
            "literal_identifiers": literal_identifier_probe() if args.include_literal_identifiers else {"state": "NOT_REQUESTED"},
            "samples": {kind: real_content_sample(kind, args.sample_limit) for kind in args.real_content_sample},
        }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "state": "OWNER_DEVICE_PROFILE_CAPTURED",
                "schema": profile["schema"],
                "fidelity_level": args.fidelity_level,
                "sensitive_capture": sensitive_requested,
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
