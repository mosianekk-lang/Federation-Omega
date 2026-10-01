from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import repository_coordination as legacy
from . import repository_coordination_v3 as scoped

SCHEMA = "FEDERATION-REPOSITORY-LEASE-COMMIT-SPEC-V1"
LEASE_SCHEMA = scoped.LEASE_SCHEMA
DEFAULT_POLICY = scoped.DEFAULT_POLICY
SHA40 = re.compile(r"^[0-9a-f]{40}$")
TERMINAL_STATES = frozenset({"RELEASED", "ABORTED"})


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    return scoped.load_policy(path)


def _run_git(repo_root: Path, args: list[str]) -> str:
    process = subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or "git read failed")
    return process.stdout.strip()


def _validate_capture_witness(lease, witness, policy):
    if witness.get("provider") != policy.get("turn_capture_provider", "FEDERATION_SYNC_BUS_TURN_CAPTURE"):
        raise ValueError("TURN_CAPTURE_PROVIDER_MISMATCH")
    if not lease.get("turn_capture_id") or witness.get("capture_id") != lease.get("turn_capture_id"):
        raise ValueError("TURN_CAPTURE_ID_MISMATCH")
    if witness.get("provider_readback_verified") is not True:
        raise ValueError("TURN_CAPTURE_REFERENCE_UNVERIFIED")


def _resolve_current_lease_ref_head(root, ref):
    canonical = scoped.normalize_ref(ref)
    try:
        rows = _run_git(root, ["ls-remote", "--refs", "origin", canonical]).splitlines()
    except RuntimeError as exc:
        raise ValueError("CANONICAL_LEASE_REF_READBACK_FAILED") from exc
    matches = [row.split()[0] for row in rows if len(row.split()) == 2 and row.split()[1] == canonical]
    if len(matches) != 1 or not SHA40.fullmatch(matches[0]):
        raise ValueError("CANONICAL_LEASE_REF_UNRESOLVED")
    return matches[0]


def _current(root, ref, expected, label):
    if not SHA40.fullmatch(str(expected or "")):
        raise ValueError(label + "_SHA_INVALID")
    if _resolve_current_lease_ref_head(root, ref) != expected:
        raise ValueError(label + "_NOT_CURRENT_REF")


def _message(root, sha):
    try:
        _run_git(root, ["cat-file", "-e", f"{sha}^{{commit}}"])
    except RuntimeError:
        _run_git(root, ["fetch", "--no-tags", "--quiet", "origin", sha])
    return _run_git(root, ["show", "-s", "--format=%B", sha])


def _source_tree(root, head, *, expected=None, current=False):
    if not SHA40.fullmatch(str(head or "")):
        raise ValueError("LEASE_SOURCE_HEAD_INVALID")
    if current and _resolve_current_lease_ref_head(root, "refs/heads/main") != head:
        raise ValueError("LEASE_SOURCE_HEAD_NOT_CURRENT_MAIN")
    try:
        _message(root, head)
        tree = _run_git(root, ["show", "-s", "--format=%T", head])
    except RuntimeError as exc:
        raise ValueError("LEASE_SOURCE_HEAD_UNRESOLVED") from exc
    if not SHA40.fullmatch(tree) or (expected is not None and tree != expected):
        raise ValueError("LEASE_SOURCE_TREE_MISMATCH")
    return tree


def _raise_findings(findings):
    if findings:
        raise ValueError(findings[0].rule)


def _registry(root, expected, policy, now):
    _current(root, policy["registry_ref"], expected, "V3_REGISTRY")
    registry = scoped.parse_registry_message(_message(root, expected))
    if not isinstance(registry, dict):
        raise ValueError("V3_REGISTRY_REQUIRED")
    _raise_findings(scoped._registry_findings(registry, policy, now))
    return registry


def _legacy_descriptor(root, sha):
    descriptor = legacy.parse_lease_message(_message(root, sha))
    if not isinstance(descriptor, dict):
        raise ValueError("MIGRATION_LEGACY_DESCRIPTOR_INVALID")
    return descriptor


def _tombstone(root, policy, expected=None):
    sha = _resolve_current_lease_ref_head(root, policy["legacy_v2_ref"])
    if expected is not None and sha != expected:
        raise ValueError("MIGRATION_TOMBSTONE_NOT_CURRENT_REF")
    descriptor = _legacy_descriptor(root, sha)
    _raise_findings(scoped.migration_tombstone_findings(descriptor, policy=policy))
    tree = _source_tree(root, descriptor.get("source_head"))
    if _run_git(root, ["show", "-s", "--format=%T", sha]) != tree:
        raise ValueError("MIGRATION_TOMBSTONE_TREE_MISMATCH")
    # This is immutable source provenance, not executed-code attestation. It
    # need not remain the current main after cutover.
    migration = descriptor["migration"]
    _source_tree(root, migration["issuer_source_head"], expected=migration["issuer_source_tree"])
    return sha, descriptor


def _admitted_registry(root, expected, policy, now):
    # The immutable V2 barrier is checked before every V3 operation. These two
    # reads are not a two-ref atomic transaction; all *new* leases use only V3.
    legacy_sha, tombstone = _tombstone(root, policy)
    registry = _registry(root, expected, policy, now)
    _raise_findings(scoped.migration_binding_findings(registry, tombstone, legacy_sha, policy=policy))
    return registry


def _spec(root, *, ref, parent, source_head, payload, schema, capture, witness, policy):
    _validate_capture_witness({"turn_capture_id": capture}, witness, policy)
    return {
        "schema": SCHEMA, "lease_ref": ref, "current_lease_ref_head": parent,
        "parent_sha": parent, "source_head": source_head, "tree_sha": _source_tree(root, source_head),
        "message": schema + "\n" + json.dumps(payload, sort_keys=True, separators=(",", ":")),
        "turn_capture_id": capture,
        "capture_witness": {"provider": witness["provider"], "capture_id": capture, "provider_readback_verified": True},
        "provider_effect_authorized": False,
    }


def build_migration_freeze_commit_spec(repo_root: Path, *, predecessor_lease_sha: str,
        predecessor_registry_sha: str, cutover_id: str, turn_capture_id: str,
        turn_capture_witness: Mapping[str, Any], now=None, policy=None) -> dict[str, Any]:
    """Form the one-way V2 barrier from an exact explicit terminal predecessor.

    Publish by non-forced fast-forward CAS. A racing old V2 acquisition and this
    tombstone share a parent; only one can win. Never retire ACTIVE or infer
    release from expiry. This builder performs no provider write.
    """
    root, policy = Path(repo_root), dict(policy or load_policy())
    now = now or datetime.now(timezone.utc)
    _validate_capture_witness({"turn_capture_id": turn_capture_id}, turn_capture_witness, policy)
    _current(root, policy["legacy_v2_ref"], predecessor_lease_sha, "MIGRATION_LEGACY")
    prior = _legacy_descriptor(root, predecessor_lease_sha)
    if prior.get("state") not in TERMINAL_STATES:
        raise ValueError("PREDECESSOR_LEASE_NOT_TERMINAL")
    _raise_findings(legacy._terminal_lease_findings(prior))
    registry = _registry(root, predecessor_registry_sha, policy, now)
    if registry["active_leases"]:
        raise ValueError("MIGRATION_REQUIRES_EMPTY_REGISTRY")
    if "migration" in registry:
        raise ValueError("MIGRATION_ALREADY_RECORDED")
    issuer_head = _resolve_current_lease_ref_head(root, "refs/heads/main")
    issuer_tree = _source_tree(root, issuer_head, current=True)
    migration = {"schema": scoped.MIGRATION_SCHEMA, "state": "FROZEN", "cutover_id": cutover_id,
        "legacy_ref": policy["legacy_v2_ref"], "registry_ref": policy["registry_ref"],
        "predecessor_registry_sha": predecessor_registry_sha, "turn_capture_id": turn_capture_id,
        "issuer_source_head": issuer_head, "issuer_source_tree": issuer_tree}
    _raise_findings(scoped.migration_findings(migration, state="FROZEN", policy=policy))
    descriptor = dict(prior, state=scoped.MIGRATION_TOMBSTONE_STATE, migration=migration,
                      fencing_token=int(prior["fencing_token"])+1, turn_capture_id=turn_capture_id,
                      migration_frozen_at=now.isoformat())
    return _spec(root, ref=policy["legacy_v2_ref"], parent=predecessor_lease_sha,
        source_head=prior["source_head"], payload=descriptor, schema=legacy.LEASE_SCHEMA,
        capture=turn_capture_id, witness=turn_capture_witness, policy=policy)


def build_registry_cutover_commit_spec(repo_root: Path, *, predecessor_registry_sha: str,
        migration_tombstone_sha: str, turn_capture_witness: Mapping[str, Any], now=None,
        policy=None) -> dict[str, Any]:
    """Resume the same cutover after its exact V2 barrier is provider-visible.

    Any changed seed/head fails closed; no silent rebind or rollback is allowed.
    Existing registry mode and other metadata are retained, without promotion.
    """
    root, policy = Path(repo_root), dict(policy or load_policy())
    now = now or datetime.now(timezone.utc)
    sha, tombstone = _tombstone(root, policy, migration_tombstone_sha)
    migration = tombstone["migration"]
    _validate_capture_witness(migration, turn_capture_witness, policy)
    if migration["predecessor_registry_sha"] != predecessor_registry_sha:
        raise ValueError("MIGRATION_REGISTRY_SEED_MISMATCH")
    registry = _registry(root, predecessor_registry_sha, policy, now)
    if registry["active_leases"] or "migration" in registry:
        raise ValueError("MIGRATION_REQUIRES_EMPTY_UNMIGRATED_REGISTRY")
    updated = scoped._registry_copy(registry)
    updated["migration"] = dict(migration, state="COMPLETE", legacy_tombstone_sha=sha)
    updated["generation"] += 1
    updated["updated_at"] = now.isoformat()
    _raise_findings(scoped._registry_findings(updated, policy, now))
    return _spec(root, ref=policy["registry_ref"], parent=predecessor_registry_sha,
        source_head=tombstone["source_head"], payload=updated, schema=scoped.REGISTRY_SCHEMA,
        capture=migration["turn_capture_id"], witness=turn_capture_witness, policy=policy)


def build_lease_commit_spec(repo_root: Path, lease: Mapping[str, Any], *,
        predecessor_lease_sha: str, turn_capture_witness: Mapping[str, Any],
        policy=None, now=None) -> dict[str, Any]:
    """Canonical acquisition: scoped AND repository-global leases share V3 CAS.

    The historical predecessor_lease_sha argument now identifies the V3 registry
    parent. V2 acquisition is always denied, including explicit legacy policies.
    Returned specs grant no provider effect and must be non-force CAS published.
    """
    if lease.get("schema") == legacy.LEASE_SCHEMA:
        raise ValueError("V2_NEW_ACQUISITION_FROZEN")
    root, policy = Path(repo_root), dict(policy or load_policy())
    now = now or datetime.now(timezone.utc)
    if policy.get("schema") != "FEDERATION-REPOSITORY-COORDINATION-V3" or lease.get("schema") != LEASE_SCHEMA:
        raise ValueError("LEASE_DESCRIPTOR_SCHEMA_MISMATCH")
    _validate_capture_witness(lease, turn_capture_witness, policy)
    if lease.get("state") != "ACTIVE" or lease.get("effect") != "NONE":
        raise ValueError("LEASE_STATE_OR_EFFECT_INVALID")
    registry = _admitted_registry(root, predecessor_lease_sha, policy, now)
    if type(lease.get("fencing_token")) is not int or lease["fencing_token"] != registry["generation"]+1:
        raise ValueError("V3_FENCE_NOT_NEXT_GENERATION")
    _source_tree(root, lease.get("source_head"), expected=lease.get("source_tree"), current=True)
    if not isinstance(lease.get("write_set"), list) or not all(isinstance(x, str) for x in lease["write_set"]):
        raise ValueError("V3_WRITE_SET_INVALID")
    write_set = scoped.normalize_write_set(lease["write_set"])
    if any(scoped.write_sets_overlap([x], policy.get("repository_global_paths", [])) for x in write_set) and "repository:*" not in write_set:
        raise ValueError("V3_GLOBAL_PATH_REQUIRES_REPOSITORY_SCOPE")
    if scoped.parse_time(lease.get("expires_at")) <= now or scoped.parse_time(lease.get("acquired_at")) > now or scoped.parse_time(lease.get("acquired_at")) >= scoped.parse_time(lease.get("expires_at")):
        raise ValueError("V3_LEASE_TIME_INVALID")
    preflight = scoped.can_acquire(registry, write_set, now=now, policy=policy)
    if preflight["status"] != "PASS":
        raise ValueError(preflight["findings"][0]["rule"])
    updated = scoped._registry_copy(registry)
    updated["active_leases"].append(dict(lease))
    updated["generation"] += 1
    updated["updated_at"] = now.isoformat()
    _raise_findings(scoped._registry_findings(updated, policy, now))
    return _spec(root, ref=policy["registry_ref"], parent=predecessor_lease_sha,
        source_head=lease["source_head"], payload=updated, schema=scoped.REGISTRY_SCHEMA,
        capture=lease["turn_capture_id"], witness=turn_capture_witness, policy=policy)


def build_release_commit_spec(repo_root: Path, *, predecessor_registry_sha: str,
        lease_id: str, fencing_token: int, writer_node: str, terminal_state: str,
        turn_capture_id: str, turn_capture_witness: Mapping[str, Any], now=None,
        policy=None) -> dict[str, Any]:
    """Retire only the exact current owner/fence; preserve migration and metadata."""
    root, policy = Path(repo_root), dict(policy or load_policy())
    now = now or datetime.now(timezone.utc)
    _validate_capture_witness({"turn_capture_id": turn_capture_id}, turn_capture_witness, policy)
    if terminal_state not in TERMINAL_STATES:
        raise ValueError("V3_RELEASE_TERMINAL_STATE_INVALID")
    registry = _admitted_registry(root, predecessor_registry_sha, policy, now)
    found = scoped._find_lease(registry, lease_id)
    if found is None:
        raise ValueError("V3_RELEASE_LEASE_NOT_FOUND")
    index, lease = found
    if type(fencing_token) is not int or fencing_token != lease["fencing_token"]:
        raise ValueError("V3_RELEASE_FENCE_MISMATCH")
    if not writer_node or writer_node != lease["writer_node"]:
        raise ValueError("V3_RELEASE_OWNER_MISMATCH")
    updated = scoped._registry_copy(registry)
    retired = updated["active_leases"].pop(index)
    retired.update(state=terminal_state, terminal_capture_id=turn_capture_id, terminated_at=now.isoformat())
    history = updated.setdefault("released_leases", [])
    if not isinstance(history, list):
        raise ValueError("V3_RELEASE_HISTORY_INVALID")
    history.append(retired)
    updated["stale_fencing_tokens"] = sorted(scoped._stale_fences(updated) | {fencing_token})
    updated["generation"] += 1
    updated["updated_at"] = now.isoformat()
    _raise_findings(scoped._registry_findings(updated, policy, now))
    return _spec(root, ref=policy["registry_ref"], parent=predecessor_registry_sha,
        source_head=lease["source_head"], payload=updated, schema=scoped.REGISTRY_SCHEMA,
        capture=turn_capture_id, witness=turn_capture_witness, policy=policy)
