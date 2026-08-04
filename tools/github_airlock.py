#!/usr/bin/env python3
"""Federation Omega GitHub Airlock v2 admission validator."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "governance" / "github_airlock_policy.json"
WORKFLOW_PREFIX = ".github/workflows/"


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    severity: str
    detail: str


def load_policy(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("policy_id") != "FEDOMEGA-GITHUB-AIRLOCK-V2":
        raise ValueError("unexpected GitHub Airlock policy")
    return payload


def changed_paths(base: str, head: str) -> list[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", base, head],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    result: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        fields = line.split("\t")
        result.append((fields[0], fields[-1]))
    return result


def workflow_events(text: str) -> set[str]:
    known = {
        "pull_request", "pull_request_target", "push", "schedule",
        "workflow_run", "workflow_dispatch", "workflow_call", "merge_group",
        "issues", "issue_comment", "repository_dispatch",
    }
    return {
        event for event in known
        if re.search(rf"(?m)^\s{{0,4}}{re.escape(event)}\s*:", text)
    }


def has_contents_write(text: str) -> bool:
    return bool(
        re.search(r"(?mi)^\s*contents\s*:\s*write\s*$", text)
        or re.search(r"(?mi)^\s*permissions\s*:\s*write-all\s*$", text)
    )


def has_oidc_write(text: str) -> bool:
    return bool(re.search(r"(?mi)^\s*id-token\s*:\s*write\s*$", text))


def has_concurrency(text: str) -> bool:
    return bool(re.search(r"(?m)^concurrency\s*:", text))


def action_reference_findings(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in text.splitlines():
        match = re.search(r"\buses\s*:\s*([^\s#]+)", line)
        if not match:
            continue
        value = match.group(1)
        if value.startswith("./") or "@" not in value:
            continue
        ref = value.rsplit("@", 1)[1]
        if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
            findings.append(Finding(
                path, "MUTABLE_ACTION_REFERENCE", "HIGH",
                f"external action is not pinned to a full commit SHA: {value}",
            ))
    return findings


def analyse_workflow(path: str, text: str, policy: dict) -> list[Finding]:
    findings: list[Finding] = []
    if path not in set(policy["active_workflow_allowlist"]):
        findings.append(Finding(
            path, "WORKFLOW_NOT_ALLOWLISTED", "CRITICAL",
            "new or modified workflow is outside the active Airlock allowlist",
        ))

    lower = text.lower()
    if has_contents_write(text):
        findings.append(Finding(
            path, "REPOSITORY_WRITE_AUTHORITY", "CRITICAL",
            "source-repository workflows must use contents: read",
        ))

    if has_oidc_write(text) and path not in set(policy["oidc_workflow_allowlist"]):
        findings.append(Finding(
            path, "UNAUTHORISED_OIDC", "CRITICAL",
            "workflow can mint OIDC tokens but is not an approved deployment gateway",
        ))

    for pattern in policy["forbidden_repository_mutations"]:
        if pattern in lower:
            findings.append(Finding(
                path, "FORBIDDEN_REPOSITORY_MUTATION", "CRITICAL",
                f"workflow contains forbidden mutation command: {pattern}",
            ))

    events = workflow_events(text)
    allowed_events = set(policy.get("allowed_events", {}).get(path, []))
    unexpected = sorted(events - allowed_events)
    if unexpected:
        findings.append(Finding(
            path, "UNAUTHORISED_TRIGGER", "HIGH",
            f"workflow contains events outside its contract: {', '.join(unexpected)}",
        ))

    if policy.get("require_concurrency") and not has_concurrency(text):
        findings.append(Finding(
            path, "MISSING_CONCURRENCY", "HIGH",
            "active workflow must define top-level concurrency",
        ))

    if policy.get("require_checkout_credentials_disabled"):
        if re.search(r"(?m)^\s*-?\s*uses\s*:\s*actions/checkout@", text):
            if "persist-credentials: false" not in lower:
                findings.append(Finding(
                    path, "CHECKOUT_CREDENTIALS_PERSISTED", "HIGH",
                    "checkout must set persist-credentials: false",
                ))

    if policy.get("require_immutable_action_shas"):
        findings.extend(action_reference_findings(path, text))

    return findings


def evaluate(
    base: str,
    head: str,
    event_name: str,
    policy: dict,
    associated_pr_count: int = 0,
) -> dict:
    changes = changed_paths(base, head)
    findings: list[Finding] = []
    changed_workflows: list[str] = []

    for status, path in changes:
        deleted = status.startswith("D")
        if path.startswith(WORKFLOW_PREFIX) and path.endswith((".yml", ".yaml")):
            if not deleted:
                changed_workflows.append(path)
                findings.extend(analyse_workflow(
                    path, (ROOT / path).read_text(encoding="utf-8"), policy
                ))

        for prefix in policy["forbidden_source_paths"]:
            if path.startswith(prefix) and not deleted:
                findings.append(Finding(
                    path, "RUNTIME_PROOF_IN_SOURCE_REPOSITORY", "CRITICAL",
                    f"runtime proof belongs in an artifact or append-only store, not {prefix}",
                ))

    limit = int(policy["maximum_workflow_files_changed_per_pull_request"])
    if len(changed_workflows) > limit:
        findings.append(Finding(
            ".github/workflows", "WORKFLOW_CHANGE_BUDGET_EXCEEDED", "HIGH",
            f"{len(changed_workflows)} workflow files changed; maximum is {limit}",
        ))

    protected_change = bool(changed_workflows) or any(
        path.startswith(tuple(policy["forbidden_source_paths"])) for _, path in changes
    )
    if event_name == "push" and protected_change and associated_pr_count < 1:
        findings.append(Finding(
            "main", "UNASSOCIATED_DIRECT_PUSH", "CRITICAL",
            "protected changes reached main without an associated pull request",
        ))

    unique = {(f.path, f.rule, f.detail): f for f in findings}
    ordered = sorted(unique.values(), key=lambda x: (x.severity, x.path, x.rule))
    return {
        "schema": "FEDOMEGA-GITHUB-AIRLOCK-REPORT-2",
        "policy_id": policy["policy_id"],
        "base": base,
        "head": head,
        "event": event_name,
        "associated_pr_count": associated_pr_count,
        "change_count": len(changes),
        "changed_workflow_count": len(changed_workflows),
        "status": "PASS" if not ordered else "FAIL",
        "findings": [asdict(item) for item in ordered],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--associated-pr-count", type=int, default=0)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = evaluate(
        args.base,
        args.head,
        args.event,
        load_policy(args.policy),
        args.associated_pr_count,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
