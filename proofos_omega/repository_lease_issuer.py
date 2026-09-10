from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "FEDERATION-REPOSITORY-LEASE-COMMIT-SPEC-V1"
LEASE_SCHEMA = "FEDERATION_REPOSITORY_LEASE_V2"
DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "governance" / "federation_repository_coordination_v2.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
TERMINAL_STATES = frozenset({"RELEASED", "ABORTED"})


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "FEDERATION-REPOSITORY-COORDINATION-V2":
        raise ValueError("unexpected repository coordination policy")
    return payload


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


def _require_text(mapping: Mapping[str, Any], field: str) -> str:
    value = mapping.get(field)
    if value in (None, "", []):
        raise ValueError(f"LEASE_DESCRIPTOR_FIELD_MISSING:{field}")
    return str(value)


def _validate_capture_witness(
    lease: Mapping[str, Any],
    witness: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> None:
    expected_provider = str(policy.get("turn_capture_provider", "FEDERATION_SYNC_BUS_TURN_CAPTURE"))
    if str(witness.get("provider", "")) != expected_provider:
        raise ValueError("TURN_CAPTURE_PROVIDER_MISMATCH")
    if str(witness.get("capture_id", "")) != str(lease.get("turn_capture_id", "")):
        raise ValueError("TURN_CAPTURE_ID_MISMATCH")
    if witness.get("provider_readback_verified") is not True:
        raise ValueError("TURN_CAPTURE_REFERENCE_UNVERIFIED")


def _parse_lease_message(message: str) -> dict[str, Any]:
    first, sep, remainder = str(message or "").strip().partition("\n")
    if first.strip() != LEASE_SCHEMA or not sep or not remainder.strip():
        raise ValueError("PREDECESSOR_LEASE_DESCRIPTOR_MALFORMED")
    try:
        payload = json.loads(remainder.strip())
    except json.JSONDecodeError as exc:
        raise ValueError("PREDECESSOR_LEASE_DESCRIPTOR_MALFORMED") from exc
    if not isinstance(payload, dict) or payload.get("schema") != LEASE_SCHEMA:
        raise ValueError("PREDECESSOR_LEASE_DESCRIPTOR_MALFORMED")
    return payload


def _normalise_ref(value: str) -> str:
    value = str(value or "").strip()
    if value.startswith("refs/"):
        return value
    if value.startswith("heads/"):
        return "refs/" + value
    return "refs/heads/" + value.lstrip("/")


def _resolve_current_lease_ref_head(repo_root: Path, lease_ref: str) -> str:
    """Resolve the provider-visible canonical lock ref without mutating it."""
    canonical = _normalise_ref(lease_ref)
    try:
        output = _run_git(repo_root, ["ls-remote", "--refs", "origin", canonical])
    except RuntimeError as exc:
        raise ValueError("CANONICAL_LEASE_REF_READBACK_FAILED") from exc
    rows = [line.split() for line in output.splitlines() if line.strip()]
    exact = [parts[0] for parts in rows if len(parts) >= 2 and parts[1] == canonical]
    if len(exact) != 1 or not SHA40.fullmatch(exact[0]):
        raise ValueError("CANONICAL_LEASE_REF_UNRESOLVED")
    return exact[0]


def _load_predecessor_lease(repo_root: Path, predecessor_lease_sha: str) -> dict[str, Any]:
    try:
        _run_git(repo_root, ["cat-file", "-e", f"{predecessor_lease_sha}^{{commit}}"])
    except RuntimeError:
        try:
            _run_git(repo_root, ["fetch", "--no-tags", "--quiet", "origin", predecessor_lease_sha])
            _run_git(repo_root, ["cat-file", "-e", f"{predecessor_lease_sha}^{{commit}}"])
        except RuntimeError as exc:
            raise ValueError("PREDECESSOR_LEASE_UNRESOLVED") from exc
    return _parse_lease_message(
        _run_git(repo_root, ["show", "-s", "--format=%B", predecessor_lease_sha])
    )


def _validate_terminal_predecessor(
    repo_root: Path,
    lease: Mapping[str, Any],
    predecessor_lease_sha: str,
) -> dict[str, Any]:
    predecessor = _load_predecessor_lease(repo_root, predecessor_lease_sha)
    state = str(predecessor.get("state") or "")
    if state not in TERMINAL_STATES:
        raise ValueError("PREDECESSOR_LEASE_NOT_TERMINAL")
    if str(predecessor.get("effect")) != "NONE":
        raise ValueError("PREDECESSOR_LEASE_EFFECT_SCOPE_INVALID")
    try:
        previous_token = int(predecessor.get("fencing_token"))
        next_token = int(lease.get("fencing_token"))
    except (TypeError, ValueError) as exc:
        raise ValueError("LEASE_FENCING_TOKEN_INVALID") from exc
    if next_token <= previous_token:
        raise ValueError("LEASE_FENCING_TOKEN_NOT_MONOTONIC")
    return predecessor


def build_lease_commit_spec(
    repo_root: Path,
    lease: Mapping[str, Any],
    *,
    predecessor_lease_sha: str,
    turn_capture_witness: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fail-closed successor lease commit spec.

    The predecessor must be the exact provider-visible current canonical lock-ref
    head and must resolve to an explicit RELEASED or ABORTED lease. A stale
    historical terminal commit cannot authorize a successor after the lock ref has
    advanced. The source tree is derived from source_head, and the Turn_Capture
    reference must be independently read back. This function mutates no provider
    state and grants no provider authority.
    """

    root = Path(repo_root)
    policy_payload = dict(policy or load_policy())

    for field in policy_payload.get("required_lease_fields", []):
        _require_text(lease, str(field))

    if str(lease.get("schema", LEASE_SCHEMA)) != LEASE_SCHEMA:
        raise ValueError("LEASE_DESCRIPTOR_SCHEMA_MISMATCH")
    if str(lease.get("state")) != "ACTIVE":
        raise ValueError("LEASE_ISSUER_REQUIRES_ACTIVE_STATE")
    if str(lease.get("effect")) != "NONE":
        raise ValueError("LEASE_EFFECT_SCOPE_INVALID")

    source_head = str(lease.get("source_head", ""))
    if not SHA40.fullmatch(source_head):
        raise ValueError("LEASE_SOURCE_HEAD_INVALID")
    predecessor_sha = str(predecessor_lease_sha)
    if not SHA40.fullmatch(predecessor_sha):
        raise ValueError("PREDECESSOR_LEASE_SHA_INVALID")

    _validate_capture_witness(lease, turn_capture_witness, policy_payload)

    canonical_ref = str(policy_payload.get("lease_ref") or "")
    current_ref_head = _resolve_current_lease_ref_head(root, canonical_ref)
    if current_ref_head != predecessor_sha:
        raise ValueError("PREDECESSOR_LEASE_NOT_CURRENT_LOCK_REF")

    predecessor = _validate_terminal_predecessor(root, lease, predecessor_sha)

    try:
        _run_git(root, ["cat-file", "-e", f"{source_head}^{{commit}}"])
    except RuntimeError:
        _run_git(root, ["fetch", "--no-tags", "--quiet", "origin", source_head])
        _run_git(root, ["cat-file", "-e", f"{source_head}^{{commit}}"])

    source_tree = _run_git(root, ["show", "-s", "--format=%T", source_head])
    if not SHA40.fullmatch(source_tree):
        raise RuntimeError("SOURCE_TREE_RESOLUTION_FAILED")

    message = LEASE_SCHEMA + "\n" + json.dumps(
        dict(lease),
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "schema": SCHEMA,
        "lease_ref": canonical_ref,
        "current_lease_ref_head": current_ref_head,
        "source_head": source_head,
        "tree_sha": source_tree,
        "parent_sha": predecessor_sha,
        "predecessor_state": str(predecessor["state"]),
        "predecessor_fencing_token": int(predecessor["fencing_token"]),
        "message": message,
        "turn_capture_id": str(lease["turn_capture_id"]),
        "capture_witness": {
            "provider": str(turn_capture_witness["provider"]),
            "capture_id": str(turn_capture_witness["capture_id"]),
            "provider_readback_verified": True,
        },
        "provider_effect_authorized": False,
    }
