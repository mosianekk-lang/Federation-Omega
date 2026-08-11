#!/usr/bin/env python3
"""Build a fail-closed source-provenance receipt for commits pushed to main."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def build_report(repository: str, head_sha: str, rows: list[dict]) -> dict:
    normalized = []
    for row in rows:
        sha = str(row.get("sha", "")).strip()
        if not sha:
            continue
        count = int(row.get("associated_pr_count", 0))
        normalized.append(
            {
                "sha": sha,
                "associated_pr_count": count,
                "admitted_by_pull_request": count > 0,
            }
        )
    unadmitted = [row["sha"] for row in normalized if not row["admitted_by_pull_request"]]
    payload = {
        "schema": "FEDOMEGA-PHOENIX-SOURCE-PROVENANCE-1",
        "repository": repository,
        "head_sha": head_sha,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "commit_count": len(normalized),
        "admitted_commit_count": len(normalized) - len(unadmitted),
        "unadmitted_commit_count": len(unadmitted),
        "unadmitted_commits": unadmitted,
        "commits": normalized,
        "status": "VERIFIED" if normalized and not unadmitted else "UNADMITTED_HISTORY",
        "platform_prevention_active": False,
        "truth_boundary": "Detection occurs after a push unless a GitHub ruleset requires this status before merge.",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("input must be a JSON list")
    report = build_report(args.repository, args.head, rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
