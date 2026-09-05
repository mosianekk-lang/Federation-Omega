#!/usr/bin/env python3
"""Federation Omega GitHub control-plane validator.

The validator implements a market-frontier ratchet over the existing GitHub
control plane. Changed GitHub control surfaces must satisfy the target policy
immediately, while full-estate inventory remains an explicit debt/scorecard
view rather than silently pretending historical material is remediated.

The control plane is deliberately non-sovereign: it validates repository
source and policy. It does not activate GitHub provider rulesets, mint provider
authority, execute deployments, or convert source presence into runtime proof.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
AGENT_ROOT = ROOT / ".github" / "agents"
HOOK_ROOT = ROOT / ".github" / "hooks"
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


def _files(root: Path, suffixes: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    )


def workflow_files() -> list[Path]:
    return _files(WORKFLOW_ROOT, {".yml", ".yaml"})


def agent_profile_files() -> list[Path]:
    if not AGENT_ROOT.exists():
        return []
    return sorted(
        path
        for path in AGENT_ROOT.rglob("*")
        if path.is_file()
        and (path.name.endswith(".agent.md") or path.name.endswith(".md"))
    )


def hook_files() -> list[Path]:
    return _files(HOOK_ROOT, {".json"})


def changed_control_files(base: str, head: str) -> list[Path]:
    command = [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        base,
        head,
        "--",
        ".github/workflows",
        ".github/agents",
        ".github/hooks",
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed ({result.returncode}): {result.stderr.strip()}"
        )
    paths: list[Path] = []
    for item in result.stdout.splitlines():
        path = ROOT / item.strip()
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def changed_workflow_files(base: str, head: str) -> list[Path]:
    """Backward-compatible workflow-only selector used by existing callers."""
    return [
        path
        for path in changed_control_files(base, head)
        if WORKFLOW_ROOT in path.resolve().parents
    ]


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


def has_explicit_permissions(text: str) -> bool:
    return re.search(r"(?m)^permissions\s*:", text) is not None


def has_write_all(text: str) -> bool:
    return re.search(r"(?mi)^\s*permissions\s*:\s*write-all\s*$", text) is not None


def workflow_name(text: str, fallback: str) -> str:
    match = re.search(r"(?m)^name\s*:\s*(.+?)\s*$", text)
    return match.group(1).strip(" '\"") if match else fallback


def action_references(text: str) -> list[str]:
    refs: list[str] = []
    for line in text.splitlines():
        match = re.search(r"\buses\s*:\s*([^\s#]+)", line)
        if match:
            refs.append(match.group(1))
    return refs


def mutable_action_references(text: str) -> list[str]:
    result: list[str] = []
    for reference in action_references(text):
        if reference.startswith("./") or "@" not in reference:
            continue
        ref = reference.rsplit("@", 1)[1]
        if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
            result.append(reference)
    return result


def checkout_credentials_isolated(text: str) -> bool:
    if not re.search(r"(?m)^\s*-?\s*uses\s*:\s*actions/checkout@", text):
        return True
    return "persist-credentials: false" in text.lower()


def _pattern_exception(path: str, pattern: str, policy: Mapping[str, object]) -> bool:
    exceptions = policy.get("forbidden_pattern_exceptions", {})
    if not isinstance(exceptions, dict):
        return False
    allowed = exceptions.get(path, [])
    return isinstance(allowed, list) and pattern in allowed


def analyse_workflow_text(path: str, text: str, policy: dict) -> tuple[list[Finding], list[Warning]]:
    lower = text.lower()
    name = workflow_name(text, Path(path).name).lower()
    findings: list[Finding] = []
    warnings: list[Warning] = []

    allowlisted_writers = set(policy.get("allowed_contents_write_workflows", []))
    allowed_schedules = set(policy.get("allowed_scheduled_workflows", []))
    allowed_pr_target = set(policy.get("allowed_pull_request_target_workflows", []))
    allowed_oidc = set(policy.get("allowed_oidc_workflows", []))

    writes_contents = has_contents_write(text)
    oidc = has_oidc_write(text)
    schedule = has_event(text, "schedule")
    workflow_run = has_event(text, "workflow_run")
    pr_target = has_event(text, "pull_request_target")
    allowlisted_writer = path in allowlisted_writers

    if policy.get("require_explicit_permissions_for_changed_workflows", True):
        if not has_explicit_permissions(text):
            findings.append(Finding(
                path,
                "MISSING_EXPLICIT_PERMISSIONS",
                "HIGH",
                "workflow must declare explicit top-level permissions",
            ))

    if policy.get("forbid_write_all_permissions", True) and has_write_all(text):
        findings.append(Finding(
            path,
            "WRITE_ALL_PERMISSIONS_FORBIDDEN",
            "CRITICAL",
            "permissions: write-all is forbidden",
        ))

    if writes_contents and not allowlisted_writer:
        findings.append(Finding(
            path,
            "UNAUTHORISED_CONTENTS_WRITE",
            "CRITICAL",
            "workflow requests contents: write but no repository writer is authorised",
        ))

    for forbidden in policy.get("forbidden_shell_patterns", []):
        if forbidden.lower() in lower and not _pattern_exception(path, forbidden, policy):
            if not allowlisted_writer:
                findings.append(Finding(
                    path,
                    "FORBIDDEN_REPOSITORY_MUTATION_COMMAND",
                    "CRITICAL",
                    f"workflow contains forbidden command pattern: {forbidden}",
                ))

    markers = policy.get("read_only_name_markers", [])
    if any(marker.lower() in name or marker.lower() in path.lower() for marker in markers):
        if writes_contents:
            findings.append(Finding(
                path,
                "READ_ONLY_CLASSIFICATION_CONTRADICTION",
                "CRITICAL",
                "observer/read-only/watch/canary workflow has repository write authority",
            ))

    if policy.get("forbid_scheduled_workflows_for_changed_files", True):
        if schedule and path not in allowed_schedules:
            findings.append(Finding(
                path,
                "SCHEDULED_WORKFLOW_OWNER_DISABLED",
                "HIGH",
                "scheduled GitHub execution is owner-disabled unless explicitly allowlisted",
            ))

    if policy.get("forbid_pull_request_target_for_changed_files", True):
        if pr_target and path not in allowed_pr_target:
            findings.append(Finding(
                path,
                "PULL_REQUEST_TARGET_ZERO_TRUST",
                "CRITICAL",
                "pull_request_target is forbidden unless explicitly registered and separately reviewed",
            ))

    if policy.get("forbid_workflow_run_with_write_permissions", True):
        if workflow_run and writes_contents:
            findings.append(Finding(
                path,
                "WORKFLOW_RUN_PRIVILEGE_ESCALATION",
                "CRITICAL",
                "workflow_run consumer must not receive repository write authority",
            ))

    if policy.get("forbid_workflow_run_with_oidc", True):
        if workflow_run and oidc:
            findings.append(Finding(
                path,
                "WORKFLOW_RUN_OIDC_ESCALATION",
                "CRITICAL",
                "workflow_run consumer must not mint an OIDC token",
            ))

    if policy.get("forbid_pull_request_target_with_oidc", True):
        if pr_target and oidc:
            findings.append(Finding(
                path,
                "PULL_REQUEST_TARGET_OIDC",
                "CRITICAL",
                "pull_request_target workflow may not mint an OIDC token",
            ))

    if policy.get("forbid_scheduled_oidc", True):
        if schedule and oidc:
            findings.append(Finding(
                path,
                "SCHEDULED_OIDC_FORBIDDEN",
                "CRITICAL",
                "scheduled workflow may not mint an OIDC token under the no-schedule policy",
            ))

    if oidc and path not in allowed_oidc:
        findings.append(Finding(
            path,
            "OIDC_WORKFLOW_NOT_REGISTERED",
            "CRITICAL",
            "id-token: write requires an explicit workflow registration",
        ))

    if policy.get("require_concurrency_for_oidc", True) and oidc and not has_concurrency(text):
        findings.append(Finding(
            path,
            "OIDC_WITHOUT_CONCURRENCY",
            "HIGH",
            "OIDC-capable workflow must serialize its trust surface with concurrency",
        ))

    for event in policy.get("require_concurrency_for_events", []):
        if has_event(text, event) and not has_concurrency(text):
            findings.append(Finding(
                path,
                "MISSING_CONCURRENCY_CONTROL",
                "HIGH",
                f"{event} workflow has no top-level concurrency control",
            ))

    if policy.get("require_checkout_persist_credentials_false_for_changed_workflows", True):
        if not checkout_credentials_isolated(text):
            findings.append(Finding(
                path,
                "CHECKOUT_CREDENTIALS_PERSISTED",
                "HIGH",
                "changed workflow uses checkout without persist-credentials: false",
            ))

    mutable_refs = mutable_action_references(text)
    for reference in mutable_refs:
        if policy.get("require_action_sha_pinning_for_changed_workflows", True):
            findings.append(Finding(
                path,
                "ACTION_NOT_IMMUTABLY_PINNED",
                "HIGH",
                f"external action reference is mutable: {reference}",
            ))
        else:
            warnings.append(Warning(
                path,
                "ACTION_NOT_IMMUTABLY_PINNED",
                f"external action reference is mutable: {reference}",
            ))

    if allowlisted_writer:
        if not has_concurrency(text):
            findings.append(Finding(
                path,
                "AUTHORISED_WRITER_NOT_SERIALISED",
                "CRITICAL",
                "an authorised writer must have a global concurrency lock",
            ))
        if has_event(text, "pull_request") or pr_target:
            findings.append(Finding(
                path,
                "AUTHORISED_WRITER_PR_TRIGGER",
                "CRITICAL",
                "an authorised writer may not run from a pull-request event",
            ))

    return findings, warnings


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return text[4:end] if end >= 0 else ""


def _frontmatter_value_block(frontmatter: str, key: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(key)}\s*:\s*(.*?)(?=^[A-Za-z0-9_-]+\s*:|\Z)",
        frontmatter,
    )
    return match.group(1).strip() if match else ""


def analyse_agent_profile_text(path: str, text: str, policy: dict) -> tuple[list[Finding], list[Warning]]:
    findings: list[Finding] = []
    warnings: list[Warning] = []
    frontmatter = _frontmatter(text)
    if not frontmatter:
        findings.append(Finding(path, "AGENT_FRONTMATTER_MISSING", "HIGH", "agent profile requires YAML frontmatter"))
        return findings, warnings

    tools_block = _frontmatter_value_block(frontmatter, "tools")
    target = _frontmatter_value_block(frontmatter, "target").strip(" '\"")
    disable_model = _frontmatter_value_block(frontmatter, "disable-model-invocation").lower()
    user_invocable = _frontmatter_value_block(frontmatter, "user-invocable").lower()
    mcp_block = _frontmatter_value_block(frontmatter, "mcp-servers")

    if policy.get("require_github_copilot_agent_target", True) and target != "github-copilot":
        findings.append(Finding(
            path,
            "AGENT_TARGET_NOT_GITHUB_COPILOT",
            "HIGH",
            "repository agent must explicitly target github-copilot",
        ))

    if not tools_block:
        findings.append(Finding(
            path,
            "AGENT_TOOLS_IMPLICIT_ALL",
            "CRITICAL",
            "agent must declare an explicit least-privilege tools list; omitted tools default to broad access",
        ))
    else:
        normalized = re.sub(r"[\[\]\n,'\"]", " ", tools_block).lower()
        tokens = {token.strip() for token in normalized.split() if token.strip()}
        if "*" in tokens:
            findings.append(Finding(path, "AGENT_WILDCARD_TOOLS", "CRITICAL", "agent wildcard tools are forbidden"))
        privileged_aliases = {"edit", "execute", "agent"}
        privileged = sorted(tokens & privileged_aliases)
        if privileged and path not in set(policy.get("allowed_privileged_agent_profiles", [])):
            findings.append(Finding(
                path,
                "AGENT_PRIVILEGED_TOOLS_NOT_REGISTERED",
                "CRITICAL",
                f"agent requests privileged tools without explicit registration: {privileged}",
            ))

    if policy.get("require_manual_agent_invocation", True) and user_invocable not in {"true", "yes"}:
        findings.append(Finding(
            path,
            "AGENT_NOT_MANUAL_INVOCATION",
            "HIGH",
            "agent must be explicitly user-invocable under foreground-only execution policy",
        ))

    if mcp_block and path not in set(policy.get("allowed_agent_mcp_profiles", [])):
        findings.append(Finding(
            path,
            "AGENT_MCP_NOT_REGISTERED",
            "CRITICAL",
            "agent MCP servers require explicit policy registration",
        ))

    if disable_model not in {"true", "yes"}:
        warnings.append(Warning(
            path,
            "AGENT_MODEL_INVOCATION_ENABLED",
            "agent may invoke a model; preserve this only when the profile needs reasoning rather than deterministic inspection",
        ))

    return findings, warnings


def analyse_hook_text(path: str, text: str, policy: dict) -> tuple[list[Finding], list[Warning]]:
    findings: list[Finding] = []
    warnings: list[Warning] = []
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        findings.append(Finding(path, "COPILOT_HOOK_INVALID_JSON", "HIGH", f"hook JSON is invalid: {exc}"))
        return findings, warnings

    if path not in set(policy.get("allowed_copilot_hook_files", [])):
        findings.append(Finding(
            path,
            "COPILOT_HOOK_NOT_REGISTERED",
            "CRITICAL",
            "Copilot hook can intercept tool/session events and must be explicitly registered",
        ))
    return findings, warnings


def analyse(path: Path, policy: dict) -> tuple[list[Finding], list[Warning]]:
    text = path.read_text(encoding="utf-8")
    rel = relative(path)
    resolved = path.resolve()
    if WORKFLOW_ROOT.exists() and WORKFLOW_ROOT.resolve() in resolved.parents:
        return analyse_workflow_text(rel, text, policy)
    if AGENT_ROOT.exists() and AGENT_ROOT.resolve() in resolved.parents:
        return analyse_agent_profile_text(rel, text, policy)
    if HOOK_ROOT.exists() and HOOK_ROOT.resolve() in resolved.parents:
        return analyse_hook_text(rel, text, policy)
    return [], []


def unique(items: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    result: list[Finding] = []
    for item in items:
        key = (item.path, item.rule, item.detail)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def workflow_facts(path: Path, policy: dict) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    rel = relative(path)
    return {
        "path": rel,
        "schedule": has_event(text, "schedule"),
        "workflow_run": has_event(text, "workflow_run"),
        "pull_request_target": has_event(text, "pull_request_target"),
        "oidc": has_oidc_write(text),
        "contents_write": has_contents_write(text),
        "explicit_permissions": has_explicit_permissions(text),
        "concurrency": has_concurrency(text),
        "checkout_credentials_isolated": checkout_credentials_isolated(text),
        "mutable_action_refs": mutable_action_references(text),
        "oidc_registered": rel in set(policy.get("allowed_oidc_workflows", [])),
    }


def estate_metrics_from_texts(workflows: Mapping[str, str], agents: Mapping[str, str], hooks: Mapping[str, str], policy: dict) -> dict:
    facts = []
    all_findings: list[Finding] = []
    agent_findings: list[Finding] = []
    hook_findings: list[Finding] = []

    for path, text in workflows.items():
        facts.append({
            "path": path,
            "schedule": has_event(text, "schedule"),
            "workflow_run": has_event(text, "workflow_run"),
            "pull_request_target": has_event(text, "pull_request_target"),
            "oidc": has_oidc_write(text),
            "contents_write": has_contents_write(text),
            "explicit_permissions": has_explicit_permissions(text),
            "concurrency": has_concurrency(text),
            "checkout_credentials_isolated": checkout_credentials_isolated(text),
            "mutable_action_refs": mutable_action_references(text),
            "oidc_registered": path in set(policy.get("allowed_oidc_workflows", [])),
        })
        f, _ = analyse_workflow_text(path, text, policy)
        all_findings.extend(f)

    for path, text in agents.items():
        f, _ = analyse_agent_profile_text(path, text, policy)
        agent_findings.extend(f)
    for path, text in hooks.items():
        f, _ = analyse_hook_text(path, text, policy)
        hook_findings.extend(f)

    scheduled = sum(bool(x["schedule"]) for x in facts)
    pr_target = sum(bool(x["pull_request_target"]) for x in facts)
    oidc = sum(bool(x["oidc"]) for x in facts)
    unregistered_oidc = sum(bool(x["oidc"]) and not bool(x["oidc_registered"]) for x in facts)
    mutable_refs = sum(len(x["mutable_action_refs"]) for x in facts)
    missing_permissions = sum(not bool(x["explicit_permissions"]) for x in facts)
    checkout_unsafe = sum(not bool(x["checkout_credentials_isolated"]) for x in facts)
    privileged_no_concurrency = sum(
        (bool(x["oidc"]) or bool(x["contents_write"])) and not bool(x["concurrency"])
        for x in facts
    )

    dimensions = {
        "no_unregistered_schedules": scheduled == 0,
        "no_pull_request_target": pr_target == 0,
        "oidc_explicitly_registered": unregistered_oidc == 0,
        "third_party_actions_immutable": mutable_refs == 0,
        "permissions_explicit": missing_permissions == 0,
        "checkout_credentials_isolated": checkout_unsafe == 0,
        "privileged_surfaces_serialised": privileged_no_concurrency == 0,
        "agent_tool_governance_clean": len(agent_findings) == 0,
        "copilot_hooks_registered": len(hook_findings) == 0,
    }
    passed = sum(dimensions.values())
    score = round(100.0 * passed / len(dimensions), 1)
    return {
        "workflow_count": len(workflows),
        "agent_profile_count": len(agents),
        "copilot_hook_file_count": len(hooks),
        "scheduled_workflows": scheduled,
        "pull_request_target_workflows": pr_target,
        "oidc_workflows": oidc,
        "unregistered_oidc_workflows": unregistered_oidc,
        "mutable_action_references": mutable_refs,
        "missing_explicit_permissions": missing_permissions,
        "checkout_credentials_not_isolated": checkout_unsafe,
        "privileged_without_concurrency": privileged_no_concurrency,
        "agent_governance_findings": len(agent_findings),
        "unregistered_copilot_hooks": len(hook_findings),
        "frontier_control_score": score,
        "frontier_control_dimensions": dimensions,
        "truth_boundary": "source/control-plane coverage score only; not provider protection, deployment, runtime, security certification, or owner-value proof",
    }


def current_estate_metrics(policy: dict) -> dict:
    workflows = {relative(p): p.read_text(encoding="utf-8") for p in workflow_files()}
    agents = {relative(p): p.read_text(encoding="utf-8") for p in agent_profile_files()}
    hooks = {relative(p): p.read_text(encoding="utf-8") for p in hook_files()}
    return estate_metrics_from_texts(workflows, agents, hooks, policy)


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
    enforcement_scope = "CHANGED_GITHUB_CONTROL_SURFACES"

    all_controls = workflow_files() + agent_profile_files() + hook_files()
    if args.scan_all:
        targets = all_controls
        enforcement_scope = "FULL_GITHUB_CONTROL_INVENTORY"
        enforce = bool(policy.get("strict_full_repository_scan", False))
    elif args.changed_from:
        targets = changed_control_files(args.changed_from, args.changed_to)
        enforce = True
    elif args.path:
        targets = [ROOT / item for item in args.path]
        targets = [path for path in targets if path.is_file()]
        enforce = True
    else:
        targets = all_controls
        enforcement_scope = "FULL_GITHUB_CONTROL_INVENTORY"
        enforce = bool(policy.get("strict_full_repository_scan", False))

    findings: list[Finding] = []
    warnings: list[Warning] = []
    for target in targets:
        file_findings, file_warnings = analyse(target, policy)
        findings.extend(file_findings)
        warnings.extend(file_warnings)

    findings = unique(findings)
    estate = current_estate_metrics(policy)
    payload = {
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "scope": enforcement_scope,
        "enforced": enforce,
        "control_file_count": len(targets),
        "finding_count": len(findings),
        "warning_count": len(warnings),
        "status": "PASS" if not findings else ("FAIL" if enforce else "LEGACY_FINDINGS_RECORDED"),
        "findings": [asdict(item) for item in findings],
        "warnings": [asdict(item) for item in warnings],
        "estate": estate,
        "estate_targets": policy.get("estate_targets", {}),
        "provider_targets": policy.get("provider_targets", {}),
        "supply_chain_targets": policy.get("supply_chain_targets", {}),
        "frontier_genes": policy.get("harvested_frontier_genes", []),
    }

    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")

    return 1 if enforce and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
