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


def build_lease_commit_spec(
    repo_root: Path,
    lease: Mapping[str, Any],
    *,
    predecessor_lease_sha: str,
    turn_capture_witness: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fail-closed lease commit spec from the declared source-head tree.

    The returned tree_sha MUST be used when creating the lock commit. This prevents
    a new lease from silently inheriting the predecessor lock commit's tree.
    The caller must supply an exact provider-readback witness for Turn_Capture.
    This function does not create provider authority, mutate refs, or query private
    Google state itself.
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
    if not SHA40.fullmatch(str(predecessor_lease_sha)):
        raise ValueError("PREDECESSOR_LEASE_SHA_INVALID")

    _validate_capture_witness(lease, turn_capture_witness, policy_payload)

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
        "lease_ref": str(policy_payload.get("lease_ref", "")),
        "source_head": source_head,
        "tree_sha": source_tree,
        "parent_sha": str(predecessor_lease_sha),
        "message": message,
        "turn_capture_id": str(lease["turn_capture_id"]),
        "capture_witness": {
            "provider": str(turn_capture_witness["provider"]),
            "capture_id": str(turn_capture_witness["capture_id"]),
            "provider_readback_verified": True,
        },
        "provider_effect_authorized": False,
    }
