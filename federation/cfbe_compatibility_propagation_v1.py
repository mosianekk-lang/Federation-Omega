"""Fail-closed compatibility-window propagation for CFBE Build Intelligence.

This module plans proof-bearing changes only. It neither executes a change nor
grants source/provider authority; the existing FDOF, ProofOS and mission spine
remain the admission and execution authorities.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence


SCHEMA = "CFBE-COMPATIBILITY-PROPAGATION-V1"
VERSION = "0.2.0"
_SHA256_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def _sha256(value: str, field_name: str) -> str:
    match = _SHA256_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"{field_name}_SHA256_REQUIRED")
    return "sha256:" + match.group(1)


def _version(value: str, field_name: str) -> tuple[int, int, int]:
    match = _SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"{field_name}_SEMVER_REQUIRED")
    return tuple(int(part) for part in match.groups())


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CompatibilityWindow:
    minimum: str
    maximum: str

    def validate(self) -> "CompatibilityWindow":
        if _version(self.minimum, "MINIMUM_VERSION") > _version(self.maximum, "MAXIMUM_VERSION"):
            raise ValueError("COMPATIBILITY_WINDOW_INVERTED")
        return self

    def contains(self, value: str) -> bool:
        self.validate()
        parsed = _version(value, "TARGET_VERSION")
        return _version(self.minimum, "MINIMUM_VERSION") <= parsed <= _version(self.maximum, "MAXIMUM_VERSION")


@dataclass(frozen=True, slots=True)
class RepositoryPropagation:
    repository: str
    current_version: str
    target_version: str
    source_epoch_sha256: str
    rollback_sha256: str
    canary_artifact_sha256: str
    changed_paths: tuple[str, ...]
    semantic_change_points: int
    observation_cycles: int
    dependencies: tuple[str, ...] = ()

    def validate(self) -> "RepositoryPropagation":
        if not self.repository.strip() or not self.changed_paths:
            raise ValueError("PROPAGATION_IDENTITY_REQUIRED")
        current = _version(self.current_version, "CURRENT_VERSION")
        target = _version(self.target_version, "TARGET_VERSION")
        if target <= current:
            raise ValueError("TARGET_VERSION_MUST_ADVANCE")
        _sha256(self.source_epoch_sha256, "SOURCE_EPOCH")
        _sha256(self.rollback_sha256, "ROLLBACK")
        _sha256(self.canary_artifact_sha256, "CANARY_ARTIFACT")
        if self.semantic_change_points < 0 or self.observation_cycles < 0:
            raise ValueError("PROPAGATION_BUDGET_VALUE_INVALID")
        if len(set(self.changed_paths)) != len(self.changed_paths):
            raise ValueError("DUPLICATE_PROPAGATION_PATH")
        if any(not path.strip() or path.startswith("/") or ".." in path.split("/") for path in self.changed_paths):
            raise ValueError("PROPAGATION_PATH_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class CreativeOverrideReceipt:
    repository: str
    source_epoch_sha256: str
    allowed_paths: tuple[str, ...]
    receipt_sha256: str

    def validate_for(self, change: RepositoryPropagation, protected_paths: set[str]) -> None:
        _sha256(self.receipt_sha256, "OWNER_OVERRIDE_RECEIPT")
        if self.repository != change.repository:
            raise PermissionError("OWNER_OVERRIDE_REPOSITORY_MISMATCH")
        if _sha256(self.source_epoch_sha256, "OWNER_OVERRIDE_SOURCE_EPOCH") != _sha256(change.source_epoch_sha256, "SOURCE_EPOCH"):
            raise PermissionError("OWNER_OVERRIDE_SOURCE_EPOCH_MISMATCH")
        if not protected_paths <= set(self.allowed_paths):
            raise PermissionError("OWNER_OVERRIDE_PATH_SCOPE_MISMATCH")


@dataclass(frozen=True, slots=True)
class PropagationPolicy:
    current_source_epoch_sha256: str
    allowed_repositories: frozenset[str]
    compatibility_windows: Mapping[str, CompatibilityWindow]
    protected_path_prefixes: tuple[str, ...] = ("ui/", "brand/", "content/")
    maximum_repositories: int = 1
    maximum_total_changed_paths: int = 20
    maximum_total_semantic_change_points: int = 10
    minimum_observation_cycles: int = 3

    def validate(self) -> "PropagationPolicy":
        _sha256(self.current_source_epoch_sha256, "POLICY_SOURCE_EPOCH")
        if not self.allowed_repositories:
            raise ValueError("REPOSITORY_ALLOWLIST_REQUIRED")
        if self.maximum_repositories < 1 or self.maximum_total_changed_paths < 1:
            raise ValueError("BLAST_RADIUS_BUDGET_INVALID")
        if self.maximum_total_semantic_change_points < 0 or self.minimum_observation_cycles < 1:
            raise ValueError("SEMANTIC_OR_OBSERVATION_BUDGET_INVALID")
        for repository in self.allowed_repositories:
            if repository not in self.compatibility_windows:
                raise ValueError("COMPATIBILITY_WINDOW_REQUIRED:" + repository)
            self.compatibility_windows[repository].validate()
        return self


@dataclass(frozen=True, slots=True)
class PropagationStep:
    repository: str
    stage: str
    source_epoch_sha256: str
    target_version: str
    rollback_sha256: str


@dataclass(frozen=True, slots=True)
class PropagationReceipt:
    schema: str
    source_epoch_sha256: str
    ordered_repositories: tuple[str, ...]
    steps: tuple[PropagationStep, ...]
    total_changed_paths: int
    total_semantic_change_points: int
    rollback_identities: tuple[str, ...]
    canary_identities: tuple[str, ...]
    promotion_authorized: bool
    receipt_digest: str


class CompatibilityPropagationPlanner:
    """Produce a deterministic proof plan without authorizing any effect."""

    def plan(
        self,
        changes: Sequence[RepositoryPropagation],
        policy: PropagationPolicy,
        overrides: Mapping[str, CreativeOverrideReceipt] | None = None,
    ) -> PropagationReceipt:
        policy.validate()
        if not changes:
            raise ValueError("PROPAGATION_CHANGE_REQUIRED")
        if len(changes) > policy.maximum_repositories:
            raise PermissionError("REPOSITORY_BLAST_RADIUS_EXCEEDED")
        override_map = dict(overrides or {})
        by_repo: dict[str, RepositoryPropagation] = {}
        policy_epoch = _sha256(policy.current_source_epoch_sha256, "POLICY_SOURCE_EPOCH")
        total_paths = 0
        total_semantic = 0
        for change in changes:
            change.validate()
            if change.repository in by_repo:
                raise ValueError("DUPLICATE_PROPAGATION_REPOSITORY")
            if change.repository not in policy.allowed_repositories:
                raise PermissionError("REPOSITORY_NOT_ALLOWLISTED:" + change.repository)
            if _sha256(change.source_epoch_sha256, "SOURCE_EPOCH") != policy_epoch:
                raise PermissionError("SOURCE_EPOCH_MISMATCH:" + change.repository)
            if not policy.compatibility_windows[change.repository].contains(change.target_version):
                raise PermissionError("TARGET_OUTSIDE_COMPATIBILITY_WINDOW:" + change.repository)
            if change.observation_cycles < policy.minimum_observation_cycles:
                raise PermissionError("OBSERVATION_WINDOW_TOO_SHORT:" + change.repository)
            protected = {
                path for path in change.changed_paths
                if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in policy.protected_path_prefixes)
            }
            if protected:
                receipt = override_map.get(change.repository)
                if receipt is None:
                    raise PermissionError("PROTECTED_CREATIVE_LAYER_EXCLUDED:" + change.repository)
                receipt.validate_for(change, protected)
            by_repo[change.repository] = change
            total_paths += len(set(change.changed_paths))
            total_semantic += change.semantic_change_points
        if total_paths > policy.maximum_total_changed_paths:
            raise PermissionError("CHANGED_PATH_BUDGET_EXCEEDED")
        if total_semantic > policy.maximum_total_semantic_change_points:
            raise PermissionError("SEMANTIC_CHANGE_BUDGET_EXCEEDED")
        for change in changes:
            missing = sorted(set(change.dependencies) - set(by_repo))
            if missing:
                raise ValueError("MISSING_PROPAGATION_DEPENDENCY:" + ",".join(missing))
        remaining = set(by_repo)
        completed: set[str] = set()
        ordered: list[str] = []
        while remaining:
            ready = sorted(repo for repo in remaining if set(by_repo[repo].dependencies) <= completed)
            if not ready:
                raise ValueError("CYCLIC_PROPAGATION_GRAPH")
            ordered.extend(ready)
            completed.update(ready)
            remaining.difference_update(ready)
        steps = tuple(
            PropagationStep(
                repository=repo,
                stage=stage,
                source_epoch_sha256=policy_epoch,
                target_version=by_repo[repo].target_version,
                rollback_sha256=_sha256(by_repo[repo].rollback_sha256, "ROLLBACK"),
            )
            for repo in ordered
            for stage in ("PREIMAGE", "CANARY", "OBSERVATION", "PROMOTION_READY")
        )
        payload = {
            "schema": SCHEMA,
            "source_epoch_sha256": policy_epoch,
            "ordered_repositories": ordered,
            "steps": [
                {"repository": step.repository, "stage": step.stage, "target_version": step.target_version,
                 "rollback_sha256": step.rollback_sha256}
                for step in steps
            ],
            "changes": [
                {
                    "repository": repo,
                    "current_version": by_repo[repo].current_version,
                    "target_version": by_repo[repo].target_version,
                    "source_epoch_sha256": _sha256(by_repo[repo].source_epoch_sha256, "SOURCE_EPOCH"),
                    "rollback_sha256": _sha256(by_repo[repo].rollback_sha256, "ROLLBACK"),
                    "canary_artifact_sha256": _sha256(by_repo[repo].canary_artifact_sha256, "CANARY_ARTIFACT"),
                    "changed_paths": sorted(by_repo[repo].changed_paths),
                    "semantic_change_points": by_repo[repo].semantic_change_points,
                    "observation_cycles": by_repo[repo].observation_cycles,
                    "dependencies": sorted(by_repo[repo].dependencies),
                }
                for repo in ordered
            ],
            "total_changed_paths": total_paths,
            "total_semantic_change_points": total_semantic,
            "promotion_authorized": False,
        }
        return PropagationReceipt(
            schema=SCHEMA,
            source_epoch_sha256=policy_epoch,
            ordered_repositories=tuple(ordered),
            steps=steps,
            total_changed_paths=total_paths,
            total_semantic_change_points=total_semantic,
            rollback_identities=tuple(_sha256(by_repo[repo].rollback_sha256, "ROLLBACK") for repo in ordered),
            canary_identities=tuple(_sha256(by_repo[repo].canary_artifact_sha256, "CANARY_ARTIFACT") for repo in ordered),
            promotion_authorized=False,
            receipt_digest=_digest(payload),
        )
