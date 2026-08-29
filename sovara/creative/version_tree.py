from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class VersionTreeError(ValueError):
    pass


class BranchConflictError(VersionTreeError):
    pass


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _normalize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    normalized = json.loads(_stable_json(dict(metadata)))
    if not isinstance(normalized, dict):
        raise VersionTreeError("metadata must normalize to an object")
    return normalized


@dataclass(frozen=True, slots=True)
class VersionNode:
    asset_id: str
    version_id: str
    content_sha256: str
    parent_ids: tuple[str, ...]
    operation: str
    metadata: Mapping[str, Any]
    rollback_of: str | None = None

    def canonical_record(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "content_sha256": self.content_sha256,
            "parent_ids": list(self.parent_ids),
            "operation": self.operation,
            "metadata": dict(self.metadata),
            "rollback_of": self.rollback_of,
        }


@dataclass(frozen=True, slots=True)
class VersionTreeReceipt:
    schema: str
    asset_id: str
    node_count: int
    branch_heads: dict[str, str]
    node_manifest_sha256: str
    integrity_verified: bool
    external_effect_performed: bool
    provider_effect_performed: bool
    destructive_mutation_performed: bool
    receipt_sha256: str


class VersionTree:
    """Deterministic in-memory creative version lineage.

    The tree is append-only: historical nodes cannot be replaced or deleted. Branch
    heads move only through compare-and-swap operations. Rollback creates a new node
    carrying old content; it never rewrites history. Node metadata is exposed through
    a read-only mapping. This object performs no provider, storage, publishing,
    financial, or production effect.
    """

    def __init__(self, asset_id: str) -> None:
        asset_id = asset_id.strip()
        if not asset_id:
            raise VersionTreeError("asset_id is required")
        self.asset_id = asset_id
        self._nodes: dict[str, VersionNode] = {}
        self._branches: dict[str, str] = {}
        self._content: dict[str, bytes] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def branch_heads(self) -> dict[str, str]:
        return dict(sorted(self._branches.items()))

    def node(self, version_id: str) -> VersionNode:
        try:
            return self._nodes[version_id]
        except KeyError as exc:
            raise VersionTreeError(f"unknown version_id: {version_id}") from exc

    def content(self, version_id: str) -> bytes:
        node = self.node(version_id)
        return self._content[node.content_sha256]

    def _validate_branch_name(self, branch: str) -> str:
        branch = branch.strip()
        if not branch:
            raise VersionTreeError("branch is required")
        if any(ch.isspace() for ch in branch):
            raise VersionTreeError("branch cannot contain whitespace")
        return branch

    def _make_node(
        self,
        *,
        content: bytes,
        parents: Iterable[str],
        operation: str,
        metadata: Mapping[str, Any] | None,
        rollback_of: str | None = None,
    ) -> VersionNode:
        if not isinstance(content, bytes):
            raise VersionTreeError("content must be bytes")
        parent_ids = tuple(parents)
        if len(parent_ids) > 2:
            raise VersionTreeError("a version node may have at most two parents")
        if len(set(parent_ids)) != len(parent_ids):
            raise VersionTreeError("parent_ids must be unique")
        for parent_id in parent_ids:
            if parent_id not in self._nodes:
                raise VersionTreeError(f"unknown parent version: {parent_id}")
        if rollback_of is not None and rollback_of not in self._nodes:
            raise VersionTreeError("rollback target is unknown")

        content_sha256 = sha256(content).hexdigest()
        normalized_metadata = _normalize_metadata(metadata)
        record = {
            "asset_id": self.asset_id,
            "content_sha256": content_sha256,
            "parent_ids": list(parent_ids),
            "operation": operation,
            "metadata": normalized_metadata,
            "rollback_of": rollback_of,
        }
        version_id = _sha(record)
        node = VersionNode(
            asset_id=self.asset_id,
            version_id=version_id,
            content_sha256=content_sha256,
            parent_ids=parent_ids,
            operation=operation,
            metadata=MappingProxyType(normalized_metadata),
            rollback_of=rollback_of,
        )
        existing = self._nodes.get(version_id)
        if existing is not None:
            if existing.canonical_record() != node.canonical_record() or self._content.get(content_sha256) != content:
                raise VersionTreeError("content-address collision or conflicting replay")
            return existing
        self._nodes[version_id] = node
        self._content.setdefault(content_sha256, content)
        return node

    def create_root(
        self,
        *,
        content: bytes,
        branch: str = "main",
        metadata: Mapping[str, Any] | None = None,
    ) -> VersionNode:
        branch = self._validate_branch_name(branch)
        if self._nodes or self._branches:
            raise VersionTreeError("root already exists")
        node = self._make_node(
            content=content,
            parents=(),
            operation="ROOT",
            metadata=metadata,
        )
        self._branches[branch] = node.version_id
        return node

    def create_branch(self, *, branch: str, from_version: str) -> str:
        branch = self._validate_branch_name(branch)
        self.node(from_version)
        if branch in self._branches:
            if self._branches[branch] == from_version:
                return from_version
            raise BranchConflictError("branch already exists at another head")
        self._branches[branch] = from_version
        return from_version

    def commit(
        self,
        *,
        branch: str,
        expected_head: str,
        content: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> VersionNode:
        branch = self._validate_branch_name(branch)
        observed = self._branches.get(branch)
        if observed is None:
            raise VersionTreeError("unknown branch")
        if observed != expected_head:
            raise BranchConflictError(
                f"branch head mismatch: expected {expected_head}, observed {observed}"
            )
        node = self._make_node(
            content=content,
            parents=(observed,),
            operation="COMMIT",
            metadata=metadata,
        )
        self._branches[branch] = node.version_id
        return node

    def merge(
        self,
        *,
        target_branch: str,
        expected_target_head: str,
        source_version: str,
        merged_content: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> VersionNode:
        target_branch = self._validate_branch_name(target_branch)
        observed = self._branches.get(target_branch)
        if observed is None:
            raise VersionTreeError("unknown target branch")
        if observed != expected_target_head:
            raise BranchConflictError("target branch changed before merge")
        self.node(source_version)
        if source_version == observed:
            raise VersionTreeError("merge parents must be distinct")
        node = self._make_node(
            content=merged_content,
            parents=(observed, source_version),
            operation="MERGE",
            metadata=metadata,
        )
        self._branches[target_branch] = node.version_id
        return node

    def rollback(
        self,
        *,
        branch: str,
        expected_head: str,
        target_version: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> VersionNode:
        branch = self._validate_branch_name(branch)
        observed = self._branches.get(branch)
        if observed is None:
            raise VersionTreeError("unknown branch")
        if observed != expected_head:
            raise BranchConflictError("branch changed before rollback")
        target = self.node(target_version)
        node = self._make_node(
            content=self._content[target.content_sha256],
            parents=(observed,),
            operation="ROLLBACK",
            metadata=metadata,
            rollback_of=target_version,
        )
        self._branches[branch] = node.version_id
        return node

    def lineage(self, version_id: str) -> tuple[str, ...]:
        self.node(version_id)
        ordered: list[str] = []
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            for parent in self._nodes[node_id].parent_ids:
                visit(parent)
            ordered.append(node_id)

        visit(version_id)
        return tuple(ordered)

    def verify_integrity(self) -> bool:
        if not self._nodes:
            return not self._branches
        for version_id, node in self._nodes.items():
            if node.asset_id != self.asset_id:
                return False
            if _sha(node.canonical_record()) != version_id:
                return False
            content = self._content.get(node.content_sha256)
            if content is None or sha256(content).hexdigest() != node.content_sha256:
                return False
            for parent_id in node.parent_ids:
                if parent_id not in self._nodes:
                    return False
            if node.rollback_of is not None and node.rollback_of not in self._nodes:
                return False
        if any(head not in self._nodes for head in self._branches.values()):
            return False

        visiting: set[str] = set()
        visited: set[str] = set()

        def acyclic(node_id: str) -> bool:
            if node_id in visiting:
                return False
            if node_id in visited:
                return True
            visiting.add(node_id)
            for parent in self._nodes[node_id].parent_ids:
                if not acyclic(parent):
                    return False
            visiting.remove(node_id)
            visited.add(node_id)
            return True

        return all(acyclic(node_id) for node_id in self._nodes)

    def receipt(self) -> VersionTreeReceipt:
        integrity = self.verify_integrity()
        manifest = [
            {"version_id": vid, **self._nodes[vid].canonical_record()}
            for vid in sorted(self._nodes)
        ]
        base = {
            "schema": "SOVARA_CREATIVE_VERSION_TREE_RECEIPT_V1",
            "asset_id": self.asset_id,
            "node_count": len(self._nodes),
            "branch_heads": self.branch_heads(),
            "node_manifest_sha256": _sha(manifest),
            "integrity_verified": integrity,
            "external_effect_performed": False,
            "provider_effect_performed": False,
            "destructive_mutation_performed": False,
        }
        return VersionTreeReceipt(
            **base,
            receipt_sha256=_sha(base),
        )
