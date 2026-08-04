#!/usr/bin/env python3
"""Federation Omega GitHub control-plane validator.

The validator implements the Alpha→Omega and Formation doctrine as a ratchet:
changed workflows must satisfy the target policy immediately, while a manual
full scan inventories legacy violations without pretending they are resolved.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
DEFAULT_POLICY = ROOT / "governance" / "github_control_plane_policy.json"


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    severity: str
    detail: str


@dataclass(frozen=True)
class Warning:
    path: str
    rule: str
    detail: str


def load_policy(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("policy_id") != "FEDOMEGA-GITHUB-CONTROL-PLANE-V1":
        raise ValueError("unexpected or missing GitHub control-plane policy_id")
    return payload


def workflow_files() -> list[Path]:
    if not WORKFLOW_ROOT.exists():
        return []
    return sorted(
        path for path in WORKFLOW_ROOT.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def changed_workflow_files(base: str, head: str) -> list[Path]:
    command = ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head, "--", ".github/workflows"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed ({result.returncode}): {result.stderr.strip()}"
        )
    paths: list[Path] = []
    for item in result.stdout.splitlines():
        path = ROOT / item.strip()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}:
            paths.append(path)
    return sorted(set(paths))


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def has_event(text: str, event: str) -> bool:
    return re.search(rf"(?m)^\s{{0,4}}{re.escape(event)}\s*:", text) is not None


def has_contents_write(text: str) -> bool:
    return (
        re.search(r"(?mi)^\s*contents\s*:\s*write\s*$", text) is not None
        or re.search(r"(?mi)^\s*permissions\s*:\s*write-all\s*$", text) is not None
    )


def has_oidc_write(text: str) -> bool:
    return re.search(r"(?mi)^\s*id-token\s*:\s*write\s*$", text) is not None


def has_concurrency(text: str) -> bool:
    return re.search(r"(?m)^concurrency\s*:", text) is not None


def workflow_name(text: str, fallback: str) -> str:
    match = re.search(r"(?m)^name\s*:\s*(.+?)\s*$", text)
    return match.group(1).strip(" '\"") if match else fallback


def action_reference_warnings(path: str, text: str) -> list[Warning]:
    warnings: list[Warning] = []
    for line in text.splitlines():
        match = re.search(r"\buses\s*:\s*([^\s#]+)", line)
        if not match:
            continue
        reference = match.group(1)
        if reference.startswith("./") or "@" not in reference:
            continue
        ref = reference.rsplit("@", 1)[1]
        if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
            warnings.append(
                Warning(
                    path=path,
                    rule="ACTION_NOT_IMMUTABLY_PINNED",
                    detail=f"external action reference is mutable: {reference}",
                )
            )
    return warnings


def analyse(path: Path, policy: dict) -> tuple[list[Finding], list[Warning]]:
    text = path.read_text(encoding="utf-8")
    rel = relative(path)
    lower = text.lower()
    name = workflow_name(text, path.name).lower()
    findings: list[Finding] = []

    allowlisted = rel in set(policy.get("allowed_contents_write_workflows", []))
    writes_contents = has_contents_write(text)

    if writes_contents and not allowlisted:
        findings.append(Finding(
            rel,
            "UNAUTHORISED_CONTENTS_WRITE",
            "CRITICAL",
            "workflow requests contents: write but no repository writer is authorised",
        ))

    for forbidden in policy.get("forbidden_shell_patterns", []):
        if forbidden.lower() in lower and not allowlisted:
            findings.append(Finding(
                rel,
                "FORBIDDEN_REPOSITORY_MUTATION_COMMAND",
                "CRITICAL",
                f"workflow contains forbidden command pattern: {forbidden}",
            ))

    markers = policy.get("read_only_name_markers", [])
    if any(marker.lower() in name or marker.lower() in rel.lower() for marker in markers):
        if writes_contents:
            findings.append(Finding(
                rel,
                "READ_ONLY_CLASSIFICATION_CONTRADICTION",
                "CRITICAL",
                "observer/read-only/watch/canary workflow has repository write authority",
            ))

    if policy.get("forbid_workflow_run_with_write_permissions", True):
        if has_event(text, "workflow_run") and writes_contents:
            findings.append(Finding(
                rel,
                "WORKFLOW_RUN_PRIVILEGE_ESCALATION",
                "CRITICAL",
                "workflow_run consumer must not receive repository write authority",
            ))

    if policy.get("forbid_pull_request_target_with_oidc", True):
        if has_event(text, "pull_request_target") and has_oidc_write(text):
            findings.append(Finding(
                rel,
                "PULL_REQUEST_TARGET_OIDC",
                "CRITICAL",
                "pull_request_target workflow may not mint an OIDC token",
            ))

    for event in policy.get("require_concurrency_for_events", []):
        if has_event(text, event) and not has_concurrency(text):
            findings.append(Finding(
                rel,
                "MISSING_CONCURRENCY_CONTROL",
                "HIGH",
                f"{event} workflow has no top-level concurrency control",
            ))

    if policy.get("require_checkout_persist_credentials_false_for_changed_workflows", True):
        if re.search(r"(?m)^\s*-?\s*uses\s*:\s*actions/checkout@", text):
            if "persist-credentials: false" not in lower:
                findings.append(Finding(
                    rel,
                    "CHECKOUT_CREDENTIALS_PERSISTED",
                    "HIGH",
                    "changed workflow uses checkout without persist-credentials: false",
                ))

    if allowlisted:
        if not has_concurrency(text):
            findings.append(Finding(
                rel,
                "AUTHORISED_WRITER_NOT_SERIALISED",
                "CRITICAL",
                "an authorised writer must have a global concurrency lock",
            ))
        if has_event(text, "pull_request") or has_event(text, "pull_request_target"):
            findings.append(Finding(
                rel,
                "AUTHORISED_WRITER_PR_TRIGGER",
                "CRITICAL",
                "an authorised writer may not run from a pull-request event",
            ))

    warnings = action_reference_warnings(rel, text)
    return findings, warnings


def unique(items: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    result: list[Finding] = []
    for item in items:
        key = (item.path, item.rule, item.detail)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--all", action="store_true", dest="scan_all")
    parser.add_argument("--changed-from")
    parser.add_argument("--changed-to", default="HEAD")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    policy = load_policy(args.policy)
    enforcement_scope = "CHANGED_WORKFLOWS"

    if args.scan_all:
        targets = workflow_files()
        enforcement_scope = "FULL_REPOSITORY_INVENTORY"
        enforce = bool(policy.get("strict_full_repository_scan", False))
    elif args.changed_from:
        targets = changed_workflow_files(args.changed_from, args.changed_to)
        enforce = True
    elif args.path:
        targets = [ROOT / item for item in args.path]
        targets = [path for path in targets if path.is_file()]
        enforce = True
    else:
        targets = workflow_files()
        enforcement_scope = "FULL_REPOSITORY_INVENTORY"
        enforce = bool(policy.get("strict_full_repository_scan", False))

    findings: list[Finding] = []
    warnings: list[Warning] = []
    for target in targets:
        file_findings, file_warnings = analyse(target, policy)
        findings.extend(file_findings)
        warnings.extend(file_warnings)

    findings = unique(findings)
    payload = {
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "scope": enforcement_scope,
        "enforced": enforce,
        "workflow_count": len(targets),
        "finding_count": len(findings),
        "warning_count": len(warnings),
        "status": "PASS" if not findings else ("FAIL" if enforce else "LEGACY_FINDINGS_RECORDED"),
        "findings": [asdict(item) for item in findings],
        "warnings": [asdict(item) for item in warnings],
    }

    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")

    return 1 if enforce and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
