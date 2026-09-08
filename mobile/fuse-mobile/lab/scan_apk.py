#!/usr/bin/env python3
"""Fail closed when an APK contains common credential-like material."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

PATTERNS = {
    "pem_private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openrouter_key": re.compile(rb"sk-or-v1-[A-Za-z0-9_-]{20,}"),
    "openai_style_key": re.compile(rb"sk-[A-Za-z0-9_-]{24,}"),
    "google_api_key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    "github_pat": re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    apk = Path(args.apk)
    if not apk.is_file():
        raise SystemExit("APK not found")

    matches: list[dict[str, str]] = []

    def scan(label: str, data: bytes) -> None:
        for name, pattern in PATTERNS.items():
            if pattern.search(data):
                matches.append({"location": label, "pattern": name})

    raw = apk.read_bytes()
    scan("APK_RAW", raw)
    members = 0
    with zipfile.ZipFile(apk) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            members += 1
            with archive.open(info) as handle:
                scan(info.filename, handle.read())

    receipt = {
        "schema": "FUSE_MOBILE_APK_SECURITY_SCAN_V1",
        "state": "APK_CREDENTIAL_SCAN_CLEAN" if not matches else "APK_CREDENTIAL_SCAN_FAILED",
        "apk_sha256": hashlib.sha256(raw).hexdigest(),
        "archive_members_scanned": members,
        "pattern_names": sorted(PATTERNS),
        "matches": matches,
        "credential_values_recorded": False,
    }
    Path(args.output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": receipt["state"], "archive_members_scanned": members, "match_count": len(matches)}, sort_keys=True))
    return 1 if matches else 0


if __name__ == "__main__":
    raise SystemExit(main())
