#!/usr/bin/env python3
"""Live-source guarded wrapper around the exact-lease v3.1 controller."""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED_FLAG = "--expected-source-sha"
HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")


def extract_expected_source(argv: list[str]) -> tuple[str, list[str]]:
    if EXPECTED_FLAG not in argv:
        raise RuntimeError("--expected-source-sha is required")
    index = argv.index(EXPECTED_FLAG)
    if index + 1 >= len(argv):
        raise RuntimeError("--expected-source-sha value is missing")
    expected = argv[index + 1]
    if not HEX40.fullmatch(expected):
        raise RuntimeError("--expected-source-sha is invalid")
    remaining = argv[:index] + argv[index + 2 :]
    return expected.lower(), remaining


EXPECTED_SOURCE_SHA, sys.argv = extract_expected_source(sys.argv)
BASE_PATH = HERE / "provider_cutover_v3_1.py"
if not BASE_PATH.is_file():
    raise RuntimeError("provider cutover v3.1 base is missing")
SPEC = importlib.util.spec_from_file_location("phoenix_v3_live_guard_base", BASE_PATH)
assert SPEC and SPEC.loader
V31 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = V31
SPEC.loader.exec_module(V31)
V3 = V31.V3
ORIGINAL_DETECT = V3.detect_authority
ORIGINAL_WRITE = V3.write_receipt


def guarded_detect(api, owner, legacy, requested="auto"):
    authority = ORIGINAL_DETECT(api, owner, legacy, requested)
    payload = api.request("GET", f"/repos/{owner}/{legacy}/git/ref/heads/main")[1]
    observed = payload.get("object", {}).get("sha") if isinstance(payload, dict) else None
    if not isinstance(observed, str) or not HEX40.fullmatch(observed):
        raise V3.CutoverError("Legacy main returned an invalid provider SHA")
    observed = observed.lower()
    if observed != EXPECTED_SOURCE_SHA:
        raise V3.CutoverError(
            "Legacy main moved after authorization: "
            f"expected {EXPECTED_SOURCE_SHA}, observed {observed}"
        )
    authority["legacy_source_head_sha"] = observed
    authority["legacy_source_head_verified"] = True
    return authority


def guarded_write(path, payload):
    payload["source_sha"] = EXPECTED_SOURCE_SHA
    payload["legacy_source_head_verified"] = True
    ORIGINAL_WRITE(path, payload)


V3.detect_authority = guarded_detect
V3.write_receipt = guarded_write


def main() -> int:
    if os.getenv("FEDOMEGA_GUARDED_APPLY") != "1":
        raise RuntimeError("guarded provider controller requires launcher context")
    return V31.main()


if __name__ == "__main__":
    raise SystemExit(main())
