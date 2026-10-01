from __future__ import annotations
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from federation.durable_scheduler_bus_v1 import (
    DurableMission, ExecutionReceipt, MissionState, ScheduleKind, default_handlers, due
)

TITLE_PREFIX = "[FUSE-MISSION]"
BEGIN = "<!-- FUSE_DURABLE_MISSION_V1"
END = "FUSE_DURABLE_MISSION_V1 -->"

def _request(url: str, token: str, *, method: str = "GET", body: dict[str, Any] | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "FUSE-Durable-Scheduler/1.0",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        return json.loads(raw.decode()) if raw else None

def parse_mission(body: str) -> DurableMission:
    if BEGIN not in body or END not in body:
        raise ValueError("DURABLE_MISSION_ENVELOPE_MISSING")
    payload = json.loads(body.split(BEGIN, 1)[1].split(END, 1)[0].strip())
    if payload.get("schema") != "FUSE_DURABLE_MISSION_V1":
        raise ValueError("DURABLE_MISSION_SCHEMA_INVALID")
    return DurableMission(
        mission_id=payload["mission_id"],
        idempotency_key=payload["idempotency_key"],
        task_type=payload["task_type"],
        objective=payload["objective"],
        schedule_kind=ScheduleKind(payload.get("schedule_kind", "IMMEDIATE")),
        not_before=payload.get("not_before", ""),
        interval_seconds=int(payload.get("interval_seconds", 0)),
        authority_class=payload.get("authority_class", "A0_INTERNAL"),
        effect_class=payload.get("effect_class", "NO_EFFECT"),
        required_capabilities=tuple(payload.get("required_capabilities", [])),
        payload=payload.get("payload", {}),
        max_attempts=int(payload.get("max_attempts", 3)),
        source_epoch=payload.get("source_epoch", ""),
    ).validate()

def make_issue_body(mission: DurableMission) -> str:
    payload = {
        "schema": "FUSE_DURABLE_MISSION_V1",
        "mission_id": mission.mission_id,
        "idempotency_key": mission.idempotency_key,
        "task_type": mission.task_type,
        "objective": mission.objective,
        "schedule_kind": mission.schedule_kind.value,
        "not_before": mission.not_before,
        "interval_seconds": mission.interval_seconds,
        "authority_class": mission.authority_class,
        "effect_class": mission.effect_class,
        "required_capabilities": list(mission.required_capabilities),
        "payload": dict(mission.payload),
        "max_attempts": mission.max_attempts,
        "source_epoch": mission.source_epoch,
    }
    return (
        "FUSE durable mission. Machine-owned queue item; issue closure alone is not mission proof.\n\n"
        + BEGIN + "\n"
        + json.dumps(payload, sort_keys=True) + "\n"
        + END + "\n"
    )

class GitHubIssueDurableWorker:
    def __init__(self, repository: str, token: str, worker_id: str = "GITHUB-SCHEDULER-V1"):
        self.repository = repository
        self.token = token
        self.worker_id = worker_id
        self.base = f"https://api.github.com/repos/{repository}"
        self.handlers = default_handlers()

    def list_open(self):
        # Use the Search API rather than the first page of /issues. Large FUSE
        # repositories routinely have >100 open issues, and durable missions
        # must not disappear simply because their issue number falls outside
        # the first page.
        query = f'repo:{self.repository} is:issue is:open in:title "{TITLE_PREFIX}"'
        url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({
            "q": query,
            "per_page": 100,
            "sort": "created",
            "order": "asc",
        })
        data = _request(url, self.token)
        return [
            item for item in (data.get("items") or [])
            if str(item.get("title", "")).startswith(TITLE_PREFIX)
        ]

    def comment(self, number: int, text: str):
        return _request(
            f"{self.base}/issues/{number}/comments", self.token,
            method="POST", body={"body": text},
        )

    def close(self, number: int):
        return _request(
            f"{self.base}/issues/{number}", self.token,
            method="PATCH", body={"state": "closed", "state_reason": "completed"},
        )

    def tick(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for issue in self.list_open():
            number = int(issue["number"])
            try:
                mission = parse_mission(issue.get("body") or "")
            except Exception as exc:
                rows.append({"issue": number, "state": "REJECTED", "error": str(exc)})
                continue
            if mission.idempotency_key in seen:
                rows.append({"issue": number, "mission_id": mission.mission_id, "state": "DUPLICATE_SUPPRESSED"})
                continue
            seen.add(mission.idempotency_key)
            if not due(mission, now=now):
                rows.append({"issue": number, "mission_id": mission.mission_id, "state": "NOT_DUE"})
                continue
            if mission.effect_class != "NO_EFFECT":
                rows.append({
                    "issue": number, "mission_id": mission.mission_id, "state": "HELD",
                    "reason": "EFFECTFUL_MISSION_REQUIRES_QUALIFIED_EXECUTOR_AND_AUTHORITY",
                })
                continue
            if not self.handlers.has(mission.task_type):
                rows.append({
                    "issue": number, "mission_id": mission.mission_id, "state": "HELD",
                    "reason": "NO_QUALIFIED_HANDLER",
                })
                continue
            result = dict(self.handlers.run(mission))
            receipt = ExecutionReceipt(
                mission_id=mission.mission_id,
                state=MissionState.SUCCEEDED,
                route_family="GITHUB_SCHEDULED_EXECUTOR",
                worker_id=self.worker_id,
                attempt=1,
                result=result,
                readback_ref=f"github-issue:{number}",
            )
            self.comment(
                number,
                "### FUSE durable scheduler receipt\n\n"
                f"- state: `{receipt.state.value}`\n"
                f"- worker: `{receipt.worker_id}`\n"
                f"- route: `{receipt.route_family}`\n"
                f"- mission digest: `{mission.digest}`\n"
                f"- receipt digest: `{receipt.digest}`\n"
                "- effects: `NONE`\n",
            )
            self.close(number)
            rows.append({
                "issue": number,
                "mission_id": mission.mission_id,
                "state": "SUCCEEDED",
                "receipt_digest": receipt.digest,
            })
        return {
            "schema": "FUSE-GITHUB-ISSUE-DURABLE-WORKER-V1",
            "generated_at": now.isoformat(),
            "repository": self.repository,
            "worker_id": self.worker_id,
            "processed": rows,
            "processed_count": len(rows),
        }

def run_from_env(output: str = "scheduler/runtime/durable-bus.json") -> dict[str, Any]:
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY", "")
    if not token or not repository:
        report = {
            "schema": "FUSE-GITHUB-ISSUE-DURABLE-WORKER-V1",
            "state": "UNBOUND",
            "reason": "GITHUB_RUNTIME_BINDING_MISSING",
            "processed": [],
            "processed_count": 0,
        }
    else:
        report = GitHubIssueDurableWorker(repository, token).tick()
        report["state"] = "BOUND"
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
