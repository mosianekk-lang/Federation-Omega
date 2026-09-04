#!/usr/bin/env python3
"""Plan and verify a bounded Cloud Run traffic rollback rehearsal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def allocation(service: dict) -> dict[str, int]:
    """Return the normal (untagged) traffic allocation by concrete revision."""
    result: dict[str, int] = {}
    for row in service.get("status", {}).get("traffic", []):
        revision = row.get("revisionName")
        percent = int(row.get("percent") or 0)
        if revision and percent:
            result[revision] = result.get(revision, 0) + percent
    if sum(result.values()) != 100:
        raise ValueError(f"normal traffic must total 100, got {result!r}")
    return dict(sorted(result.items()))


def traffic_state(service: dict) -> list[dict]:
    """Canonicalize every durable traffic field, including revision tags."""
    fields = ("revisionName", "latestRevision", "percent", "tag")
    rows = [
        {key: row[key] for key in fields if key in row}
        for row in service.get("status", {}).get("traffic", [])
    ]
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))


def spec(values: dict[str, int]) -> str:
    return ",".join(f"{revision}={percent}" for revision, percent in sorted(values.items()) if percent)


def rehearsal_plan(service: dict, canary_revision: str) -> tuple[dict[str, int], dict[str, int]]:
    before = allocation(service)
    if canary_revision in before:
        raise ValueError("canary already receives normal traffic; rehearsal is not zero-traffic")
    donor = max(before, key=lambda revision: (before[revision], revision))
    if before[donor] < 1:
        raise ValueError("no revision can donate the bounded rehearsal allocation")
    during = dict(before)
    during[donor] -= 1
    during[canary_revision] = 1
    during = {key: value for key, value in during.items() if value}
    return before, dict(sorted(during.items()))


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("service_json")
    plan.add_argument("canary_revision")
    verify = sub.add_parser("verify")
    verify.add_argument("expected_service_json")
    verify.add_argument("actual_service_json")
    args = parser.parse_args()

    try:
        if args.command == "plan":
            before, during = rehearsal_plan(load(args.service_json), args.canary_revision)
            print(f"BEFORE_SPEC={spec(before)}")
            print(f"REHEARSAL_SPEC={spec(during)}")
        else:
            expected_service = load(args.expected_service_json)
            actual_service = load(args.actual_service_json)
            expected = allocation(expected_service)
            actual = allocation(actual_service)
            if actual != expected:
                raise ValueError(f"traffic invariant violated: expected {expected!r}, got {actual!r}")
            if traffic_state(actual_service) != traffic_state(expected_service):
                raise ValueError("traffic tags or target semantics changed during rollback rehearsal")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
