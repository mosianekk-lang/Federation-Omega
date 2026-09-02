from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

LEASE_SCHEMA = "FEDERATION_REPOSITORY_LEASE_V2"
CLAIM_SCHEMA = "FEDERATION_COORDINATION_V1"
DEFAULT_LEASE_REF = "refs/heads/locks/fdof-repository-critical-section"
DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "governance" / "federation_repository_coordination_v2.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class CoordinationFinding:
    rule: str
    detail: str


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "FEDERATION-REPOSITORY-COORDINATION-V2":
        raise ValueError("unexpected repository coordination policy")
    return payload


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be offset-aware")
    return parsed.astimezone(timezone.utc)


def _normalise_ref(value: str) -> str:
    value = str(value or "").strip()
    if value.startswith("refs/heads/"):
        return value
    if value.startswith("heads/"):
        return "refs/" + value
    return "refs/heads/" + value.lstrip("/")


def parse_lease_message(message: str) -> dict[str, Any] | None:
    text = str(message or "").strip()
    if not text:
        return None
    first, _, remainder = text.partition("\n")
    if first.strip() != LEASE_SCHEMA:
        return None
    if not remainder.strip():
        raise ValueError("lease descriptor JSON is missing")
    lease = json.loads(remainder.strip())
    if not isinstance(lease, dict) or lease.get("schema") != LEASE_SCHEMA:
        raise ValueError("lease descriptor schema mismatch")
    return lease


def _extract_json_claim(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if payload.get("schema") == CLAIM_SCHEMA:
        return dict(payload)
    direct = payload.get("coordination")
    if isinstance(direct, Mapping):
        return dict(direct)
    nested = payload.get("payload")
    if isinstance(nested, Mapping):
        coordination = nested.get("coordination")
        if isinstance(coordination, Mapping):
            return dict(coordination)
    return None


def extract_coordination_claim(body: str) -> dict[str, Any] | None:
    text = str(body or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, Mapping):
        claim = _extract_json_claim(parsed)
        if claim is not None:
            return claim

    marker = re.search(
        r"<!--\s*FEDERATION_COORDINATION_V1\s*(\{.*?\})\s*-->",
        text,
        re.DOTALL,
    )
    if marker:
        claim = json.loads(marker.group(1))
        if not isinstance(claim, dict):
            raise ValueError("coordination comment must contain a JSON object")
        return claim
    return None


def _lease_validation_findings(lease: Mapping[str, Any], policy: Mapping[str, Any]) -> list[CoordinationFinding]:
    findings: list[CoordinationFinding] = []
    for field in policy.get("required_lease_fields", []):
        if field not in lease or lease.get(field) in (None, "", []):
            findings.append(CoordinationFinding("LEASE_DESCRIPTOR_FIELD_MISSING", str(field)))
    if lease.get("state") not in {"ACTIVE", "RELEASED"}:
        findings.append(CoordinationFinding("LEASE_DESCRIPTOR_STATE_INVALID", str(lease.get("state"))))
    try:
        if int(lease.get("fencing_token", 0)) < 1:
            raise ValueError
    except (TypeError, ValueError):
        findings.append(CoordinationFinding("LEASE_FENCING_TOKEN_INVALID", str(lease.get("fencing_token"))))
    if not SHA40.fullmatch(str(lease.get("source_head", ""))):
        findings.append(CoordinationFinding("LEASE_SOURCE_HEAD_INVALID", str(lease.get("source_head"))))
    try:
        _parse_time(str(lease.get("acquired_at", "")))
        _parse_time(str(lease.get("expires_at", "")))
    except (TypeError, ValueError):
        findings.append(CoordinationFinding("LEASE_TIME_INVALID", "acquired_at/expires_at must be offset-aware ISO-8601"))
    if lease.get("effect") != "NONE":
        findings.append(CoordinationFinding("LEASE_EFFECT_SCOPE_INVALID", str(lease.get("effect"))))
    return findings


def evaluate_coordination(
    *,
    base_sha: str,
    pr_body: str,
    lease_message: str,
    lease_commit_sha: str,
    lease_tree_matches_source: bool,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = dict(policy or load_policy())
    findings: list[CoordinationFinding] = []
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    try:
        lease = parse_lease_message(lease_message)
    except (ValueError, json.JSONDecodeError) as exc:
        findings.append(CoordinationFinding("LEASE_DESCRIPTOR_MALFORMED", str(exc)))
        lease = None
        return _assessment("FAIL", "MALFORMED_LEASE", lease_commit_sha, None, findings)

    if lease is None:
        return _assessment("PASS", "NO_ACTIVE_V2_LEASE", lease_commit_sha, None, findings)

    findings.extend(_lease_validation_findings(lease, policy))
    if findings:
        return _assessment("FAIL", "INVALID_LEASE", lease_commit_sha, lease, findings)

    expires_at = _parse_time(str(lease["expires_at"]))
    if lease["state"] == "RELEASED":
        return _assessment("PASS", "LEASE_RELEASED", lease_commit_sha, lease, findings)
    if expires_at <= now_utc:
        return _assessment("PASS", "LEASE_EXPIRED", lease_commit_sha, lease, findings)

    if str(lease["source_head"]) != str(base_sha):
        findings.append(CoordinationFinding(
            "ACTIVE_LEASE_SOURCE_EPOCH_MISMATCH",
            f"active lease source {lease['source_head']} does not equal PR base {base_sha}",
        ))
    if not lease_tree_matches_source:
        findings.append(CoordinationFinding(
            "ACTIVE_LEASE_TREE_MISMATCH",
            "lock commit tree does not match the declared source-head tree",
        ))

    try:
        claim = extract_coordination_claim(pr_body)
    except (ValueError, json.JSONDecodeError) as exc:
        findings.append(CoordinationFinding("PR_COORDINATION_CLAIM_MALFORMED", str(exc)))
        claim = None

    if claim is None:
        findings.append(CoordinationFinding(
            "ACTIVE_REPOSITORY_LEASE_UNCLAIMED",
            "an unexpired repository lease exists but this PR does not claim it",
        ))
        return _assessment("FAIL", "ACTIVE_LEASE_UNCLAIMED", lease_commit_sha, lease, findings)

    if claim.get("schema") not in (None, CLAIM_SCHEMA):
        findings.append(CoordinationFinding("PR_COORDINATION_SCHEMA_MISMATCH", str(claim.get("schema"))))

    aliases = {
        "turn_capture_id": ("turn_capture_id", "sync_capture_id"),
        "lock_ref": ("lock_ref", "shared_lock_ref"),
    }
    normalised_claim = dict(claim)
    for target, names in aliases.items():
        if target not in normalised_claim:
            for name in names:
                if name in normalised_claim:
                    normalised_claim[target] = normalised_claim[name]
                    break

    for field in policy.get("required_pr_claim_fields", []):
        if field not in normalised_claim or normalised_claim.get(field) in (None, ""):
            findings.append(CoordinationFinding("PR_COORDINATION_FIELD_MISSING", str(field)))

    exact_fields = (
        "writer_node",
        "system",
        "workstream",
        "transaction_id",
        "idempotency_key",
        "source_head",
        "turn_capture_id",
        "fencing_token",
    )
    for field in exact_fields:
        if field in normalised_claim and str(normalised_claim.get(field)) != str(lease.get(field)):
            findings.append(CoordinationFinding(
                "PR_COORDINATION_LEASE_MISMATCH",
                f"{field} does not match active lease",
            ))

    if normalised_claim.get("lease_commit_sha") != lease_commit_sha:
        findings.append(CoordinationFinding(
            "PR_COORDINATION_FENCE_COMMIT_MISMATCH",
            "lease_commit_sha does not bind the current lock-ref commit",
        ))
    expected_ref = _normalise_ref(str(policy.get("lease_ref", DEFAULT_LEASE_REF)))
    if "lock_ref" in normalised_claim and _normalise_ref(str(normalised_claim.get("lock_ref"))) != expected_ref:
        findings.append(CoordinationFinding(
            "PR_COORDINATION_LOCK_REF_MISMATCH",
            "PR lock_ref does not identify the canonical repository critical-section ref",
        ))

    status = "PASS" if not findings else "FAIL"
    state = "ACTIVE_LEASE_CLAIM_VERIFIED" if status == "PASS" else "ACTIVE_LEASE_CLAIM_REJECTED"
    return _assessment(status, state, lease_commit_sha, lease, findings)


def _assessment(
    status: str,
    state: str,
    lease_commit_sha: str,
    lease: Mapping[str, Any] | None,
    findings: list[CoordinationFinding],
) -> dict[str, Any]:
    return {
        "schema": "FEDERATION-REPOSITORY-COORDINATION-ASSESSMENT-V2",
        "status": status,
        "state": state,
        "lease_commit_sha": lease_commit_sha,
        "lease": dict(lease) if lease is not None else None,
        "findings": [asdict(item) for item in findings],
        "provider_branch_protection_equivalent": False,
        "provider_effect_authorized": False,
    }


def _run_git(repo_root: Path, args: list[str]) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or f"git {' '.join(args)} failed")
    return process.stdout.strip()


def _runtime_lease(repo_root: Path, lease_ref: str) -> tuple[str, str, bool]:
    remote = _run_git(repo_root, ["ls-remote", "origin", lease_ref])
    if not remote:
        return "", "", True
    lease_sha = remote.split()[0]
    _run_git(repo_root, ["fetch", "--no-tags", "--quiet", "origin", lease_ref])
    message = _run_git(repo_root, ["show", "-s", "--format=%B", lease_sha])
    lease = parse_lease_message(message)
    if lease is None:
        return lease_sha, message, True
    source_head = str(lease.get("source_head", ""))
    if SHA40.fullmatch(source_head):
        try:
            _run_git(repo_root, ["cat-file", "-e", f"{source_head}^{{commit}}"])
        except RuntimeError:
            _run_git(repo_root, ["fetch", "--no-tags", "--quiet", "origin", source_head])
        lease_tree = _run_git(repo_root, ["show", "-s", "--format=%T", lease_sha])
        source_tree = _run_git(repo_root, ["show", "-s", "--format=%T", source_head])
        return lease_sha, message, lease_tree == source_tree
    return lease_sha, message, False


def evaluate_hosted_pull_request(repo_root: Path | None = None) -> dict[str, Any]:
    root = Path(repo_root or Path(__file__).resolve().parents[1])
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return _assessment("PASS", "NOT_APPLICABLE_OUTSIDE_HOSTED_PULL_REQUEST", "", None, [])

    policy = load_policy()
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return _assessment(
            "FAIL",
            "HOSTED_EVENT_CONTEXT_MISSING",
            "",
            None,
            [CoordinationFinding("GITHUB_EVENT_PATH_MISSING", "hosted pull request lacks event payload path")],
        )
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pull_request = event.get("pull_request") or {}
    base_sha = str((pull_request.get("base") or {}).get("sha") or "")
    pr_body = str(pull_request.get("body") or "")
    if not SHA40.fullmatch(base_sha):
        return _assessment(
            "FAIL",
            "HOSTED_BASE_SHA_INVALID",
            "",
            None,
            [CoordinationFinding("PULL_REQUEST_BASE_SHA_INVALID", base_sha)],
        )
    try:
        lease_sha, lease_message, tree_matches = _runtime_lease(
            root,
            str(policy.get("lease_ref", DEFAULT_LEASE_REF)),
        )
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return _assessment(
            "FAIL",
            "LEASE_PROVIDER_READBACK_FAILED",
            "",
            None,
            [CoordinationFinding("REPOSITORY_LEASE_PROVIDER_READBACK_FAILED", str(exc))],
        )
    return evaluate_coordination(
        base_sha=base_sha,
        pr_body=pr_body,
        lease_message=lease_message,
        lease_commit_sha=lease_sha,
        lease_tree_matches_source=tree_matches,
        policy=policy,
    )
