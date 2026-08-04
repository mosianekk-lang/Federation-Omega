from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from evidenceops.capability_heartbeat.live_bible_capture import LiveBibleCaptureFabric


def run(*args: str) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def commit_files(commit_sha: str) -> list[str]:
    output = run("git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha)
    return sorted(line for line in output.splitlines() if line)


def collect_commits(last_cursor: str | None, head: str, limit: int) -> list[str]:
    if last_cursor:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", last_cursor, head],
            capture_output=True,
            text=True,
        )
        if ancestor.returncode == 0:
            output = run("git", "rev-list", "--reverse", f"{last_cursor}..{head}")
            commits = [line for line in output.splitlines() if line]
            return commits[-limit:]
    return [head]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    contract_path = Path(args.contract)
    state_path = Path(args.state)
    receipt_path = Path(args.receipt)
    fabric = LiveBibleCaptureFabric(load_json(contract_path))
    previous = load_json(state_path) if state_path.exists() else None
    head = run("git", "rev-parse", "HEAD")
    source_state = (previous or {}).get("source_cursors", {}).get("SRC-GITHUB-FEDERATION", {})
    last_cursor = source_state.get("cursor")
    commits = collect_commits(last_cursor, head, args.limit)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    events = []
    for sha in commits:
        subject = run("git", "show", "-s", "--format=%s", sha)
        files = commit_files(sha)
        if files and all(path.startswith("evidenceops/capability_heartbeat/live_bible_runtime/") for path in files):
            continue
        summary = f"GitHub commit {sha[:12]}: {subject}; changed files: {len(files)}"
        fingerprint = sha256_text(json.dumps({"sha": sha, "subject": subject, "files": files}, sort_keys=True))
        events.append(
            fabric.make_event(
                source_id="SRC-GITHUB-FEDERATION",
                source_event_id=f"GH-{sha[:24]}",
                capture_mode="SCHEDULED_RECONCILIATION",
                occurred_at=run("git", "show", "-s", "--format=%cI", sha),
                observed_at=now,
                event_type="GITHUB_COMMIT",
                summary=summary,
                content_fingerprint=fingerprint,
                source_cursor=sha,
                privacy_tier="P1",
                materiality=0.8,
                provider_receipt_ref=f"github:{os.getenv('GITHUB_REPOSITORY', 'local/repository')}@{sha}",
                workstream_id="WS-A-LB",
            )
        )

    result = fabric.reconcile(events, previous_state=previous, observed_at=now)
    material_change = bool(result["accepted_deltas"] or result["held_events"] or result["conflicts"])
    if not material_change:
        print("NO_MATERIAL_CHANGE")
        return 0

    state_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(result["state"], indent=2) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(result["receipt"], indent=2) + "\n", encoding="utf-8")
    print(result["receipt"]["capture_state"])
    print(result["receipt"]["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
