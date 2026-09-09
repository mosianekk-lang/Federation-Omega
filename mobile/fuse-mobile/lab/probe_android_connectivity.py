#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ACTIVE_DEFAULT_RE = re.compile(r"(?m)^Active default network:\s*(\S+)\s*$")
NETWORK_AGENT_RE = re.compile(r"NetworkAgentInfo\{")
CAPABILITIES_RE = re.compile(r"Capabilities:\s*([^\]\n}]*)")


def _network_blocks(text: str) -> list[str]:
    starts = [match.start() for match in NETWORK_AGENT_RE.finditer(text)]
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        blocks.append(text[start:end])
    return blocks


def inspect_connectivity(text: str) -> dict[str, object]:
    active_match = ACTIVE_DEFAULT_RE.search(text)
    active_default = active_match.group(1) if active_match else "UNKNOWN"
    active_default_present = active_default not in {"none", "UNKNOWN", "-1"}
    result: dict[str, object] = {
        "schema": "FUSE_ANDROID_CONNECTIVITY_STATE_V1",
        "active_default_network": active_default,
        "active_default_present": active_default_present,
        "internet_capability": False,
        "validated_capability": False,
        "state": "UNVALIDATED_OR_ABSENT",
    }
    if not active_default_present:
        return result

    target = f"network{{{active_default}}}"
    for block in _network_blocks(text):
        if target not in block:
            continue
        capabilities_match = CAPABILITIES_RE.search(block)
        capabilities = capabilities_match.group(1) if capabilities_match else block
        tokens = set(re.findall(r"[A-Z][A-Z0-9_]+", capabilities))
        has_internet = "INTERNET" in tokens
        has_validated = "VALIDATED" in tokens
        result["internet_capability"] = has_internet
        result["validated_capability"] = has_validated
        if has_internet and has_validated:
            result["state"] = "VALIDATED_ONLINE"
        break
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--expect", required=True, choices=["online", "offline"])
    parser.add_argument("--json-output")
    args = parser.parse_args()

    source = Path(args.input)
    result = inspect_connectivity(source.read_text(encoding="utf-8", errors="replace"))
    is_online = result["state"] == "VALIDATED_ONLINE"
    expectation_met = is_online if args.expect == "online" else not is_online
    result["expectation"] = args.expect
    result["expectation_met"] = expectation_met

    if args.json_output:
        Path(args.json_output).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, sort_keys=True))
    return 0 if expectation_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
