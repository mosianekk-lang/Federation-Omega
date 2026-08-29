from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .version_tree import BranchConflictError, VersionTree


class CreativeGraphError(ValueError):
    pass


class GraphConflictError(CreativeGraphError):
    pass


class LockedNodeError(CreativeGraphError):
    pass


class CreativeNodeKind(str, Enum):
    CONCEPT = "CONCEPT"
    WORLD = "WORLD"
    CHARACTER = "CHARACTER"
    SCENE = "SCENE"
    SHOT = "SHOT"
    ASSET = "ASSET"
    EDIT = "EDIT"
    PACKAGE = "PACKAGE"
    EXPERIMENT = "EXPERIMENT"
    VALUE = "VALUE"
    OTHER = "OTHER"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _normalize_id(value: str, *, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise CreativeGraphError(f"{field_name} is required")
    if any(ch.isspace() for ch in value):
        raise CreativeGraphError(f"{field_name} cannot contain whitespace")
    return value


def _normalize_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    if attributes is None:
        return {}
    normalized = json.loads(_stable_json(dict(attributes)))
    if not isinstance(normalized, dict):
        raise CreativeGraphError("attributes must normalize to an object")
    return normalized


@dataclass(frozen=True, slots=True)
class CreativeGraphNode:
    node_id: str
    kind: CreativeNodeKind
    attributes: Mapping[str, Any]
    locked: bool = False

    def canonical_record(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "attributes": dict(self.attributes),
            "locked": self.locked,
        }


@dataclass(frozen=True, slots=True)
class CreativeGraphEdge:
    source_id: str
    target_id: str
    relation: str = "depends_on"

    def canonical_record(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
        }


@dataclass(frozen=True, slots=True)
class GraphImpact:
    changed_node_ids: tuple[str, ...]
    invalidated_node_ids: tuple[str, ...]
    blocked_locked_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GraphMutationReceipt:
    schema: str
    graph_id: str
    operation: str
    version_id: str
    changed_node_ids: tuple[str, ...]
    invalidated_node_ids: tuple[str, ...]
    blocked_locked_node_ids: tuple[str, ...]
    graph_sha256: str
    version_tree_integrity_verified: bool
    external_effect_performed: bool
    provider_effect_performed: bool
    destructive_mutation_performed: bool
    receipt_sha256: str


class CreativeGraph:
    """Versioned creative state graph for promptless SOVARA workflows.

    Edges point from an upstream dependency to a downstream dependent. Mutations
    are committed into SC-VERSION-TREE as canonical JSON snapshots. Accepted
    nodes can be locked; propagation stops at a locked node and reports it as a
    blocked invalidation rather than silently changing approved work.

    This class is deterministic and internal-only. It performs no provider,
    media-generation, publishing, financial, credential, or production effect.
    """

    def __init__(self, graph_id: str) -> None:
        self.graph_id = _normalize_id(graph_id, field_name="graph_id")
        self._nodes: dict[str, CreativeGraphNode] = {}
        self._edges: set[tuple[str, str, str]] = set()
        self._versions = VersionTree(asset_id=f"creative-graph:{self.graph_id}")
        root = self._versions.create_root(
            content=self._state_bytes(),
            metadata={"graph_id": self.graph_id, "operation": "GRAPH_ROOT"},
        )
        self._head = root.version_id

    @property
    def head_version(self) -> str:
        return self._head

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def node(self, node_id: str) -> CreativeGraphNode:
        node_id = _normalize_id(node_id, field_name="node_id")
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise CreativeGraphError(f"unknown node_id: {node_id}") from exc

    def nodes(self) -> tuple[CreativeGraphNode, ...]:
        return tuple(self._nodes[node_id] for node_id in sorted(self._nodes))

    def edges(self) -> tuple[CreativeGraphEdge, ...]:
        return tuple(
            CreativeGraphEdge(source, target, relation)
            for source, target, relation in sorted(self._edges)
        )

    def _state_record(self) -> dict[str, Any]:
        return {
            "schema": "SOVARA_CREATIVE_GRAPH_STATE_V1",
            "graph_id": self.graph_id,
            "nodes": [node.canonical_record() for node in self.nodes()],
            "edges": [edge.canonical_record() for edge in self.edges()],
        }

    def _state_bytes(self) -> bytes:
        return _stable_json(self._state_record()).encode("utf-8")

    def state_sha256(self) -> str:
        return sha256(self._state_bytes()).hexdigest()

    def _require_head(self, expected_version: str) -> None:
        if expected_version != self._head:
            raise GraphConflictError(
                f"graph head mismatch: expected {expected_version}, observed {self._head}"
            )

    def _commit(
        self,
        *,
        expected_version: str,
        operation: str,
        impact: GraphImpact,
        metadata: Mapping[str, Any] | None = None,
    ) -> GraphMutationReceipt:
        self._require_head(expected_version)
        commit_metadata = {
            "graph_id": self.graph_id,
            "operation": operation,
            "changed_node_ids": list(impact.changed_node_ids),
            "invalidated_node_ids": list(impact.invalidated_node_ids),
            "blocked_locked_node_ids": list(impact.blocked_locked_node_ids),
            "metadata": _normalize_attributes(metadata),
        }
        try:
            node = self._versions.commit(
                branch="main",
                expected_head=expected_version,
                content=self._state_bytes(),
                metadata=commit_metadata,
            )
        except BranchConflictError as exc:
            raise GraphConflictError(str(exc)) from exc
        self._head = node.version_id
        return self._receipt(operation=operation, impact=impact)

    def _receipt(self, *, operation: str, impact: GraphImpact) -> GraphMutationReceipt:
        tree_receipt = self._versions.receipt()
        base = {
            "schema": "SOVARA_CREATIVE_GRAPH_MUTATION_RECEIPT_V1",
            "graph_id": self.graph_id,
            "operation": operation,
            "version_id": self._head,
            "changed_node_ids": list(impact.changed_node_ids),
            "invalidated_node_ids": list(impact.invalidated_node_ids),
            "blocked_locked_node_ids": list(impact.blocked_locked_node_ids),
            "graph_sha256": self.state_sha256(),
            "version_tree_integrity_verified": tree_receipt.integrity_verified,
            "external_effect_performed": False,
            "provider_effect_performed": False,
            "destructive_mutation_performed": False,
        }
        return GraphMutationReceipt(
            schema=base["schema"],
            graph_id=self.graph_id,
            operation=operation,
            version_id=self._head,
            changed_node_ids=tuple(base["changed_node_ids"]),
            invalidated_node_ids=tuple(base["invalidated_node_ids"]),
            blocked_locked_node_ids=tuple(base["blocked_locked_node_ids"]),
            graph_sha256=base["graph_sha256"],
            version_tree_integrity_verified=tree_receipt.integrity_verified,
            external_effect_performed=False,
            provider_effect_performed=False,
            destructive_mutation_performed=False,
            receipt_sha256=_sha(base),
        )

    def _replace_node(
        self,
        node: CreativeGraphNode,
        *,
        attributes: Mapping[str, Any] | None = None,
        locked: bool | None = None,
    ) -> None:
        normalized = _normalize_attributes(attributes) if attributes is not None else dict(node.attributes)
        self._nodes[node.node_id] = CreativeGraphNode(
            node_id=node.node_id,
            kind=node.kind,
            attributes=MappingProxyType(normalized),
            locked=node.locked if locked is None else locked,
        )

    def add_node(
        self,
        *,
        expected_version: str,
        node_id: str,
        kind: CreativeNodeKind,
        attributes: Mapping[str, Any] | None = None,
        locked: bool = False,
    ) -> GraphMutationReceipt:
        self._require_head(expected_version)
        node_id = _normalize_id(node_id, field_name="node_id")
        if not isinstance(kind, CreativeNodeKind):
            raise CreativeGraphError("kind must be CreativeNodeKind")
        if node_id in self._nodes:
            raise CreativeGraphError(f"node already exists: {node_id}")
        self._nodes[node_id] = CreativeGraphNode(
            node_id=node_id,
            kind=kind,
            attributes=MappingProxyType(_normalize_attributes(attributes)),
            locked=bool(locked),
        )
        impact = GraphImpact((node_id,), (), ())
        return self._commit(
            expected_version=expected_version,
            operation="ADD_NODE",
            impact=impact,
        )

    def _downstream(self, node_id: str) -> tuple[str, ...]:
        return tuple(
            target
            for source, target, _relation in sorted(self._edges)
            if source == node_id
        )

    def _reachable(self, start_id: str, target_id: str) -> bool:
        pending = [start_id]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(self._downstream(current))
        return False

    def add_dependency(
        self,
        *,
        expected_version: str,
        source_id: str,
        target_id: str,
        relation: str = "depends_on",
    ) -> GraphMutationReceipt:
        self._require_head(expected_version)
        source_id = _normalize_id(source_id, field_name="source_id")
        target_id = _normalize_id(target_id, field_name="target_id")
        relation = _normalize_id(relation, field_name="relation")
        self.node(source_id)
        self.node(target_id)
        if source_id == target_id:
            raise CreativeGraphError("self dependency is not allowed")
        edge = (source_id, target_id, relation)
        if edge in self._edges:
            raise CreativeGraphError("dependency already exists")
        if self._reachable(target_id, source_id):
            raise CreativeGraphError("dependency would create a cycle")
        self._edges.add(edge)
        impact = GraphImpact((source_id, target_id), (), ())
        return self._commit(
            expected_version=expected_version,
            operation="ADD_DEPENDENCY",
            impact=impact,
        )

    def impact(self, changed_node_ids: Iterable[str]) -> GraphImpact:
        changed = tuple(sorted({_normalize_id(value, field_name="changed_node_id") for value in changed_node_ids}))
        for node_id in changed:
            self.node(node_id)
        invalidated: set[str] = set()
        blocked: set[str] = set()
        pending = list(changed)
        visited = set(changed)
        while pending:
            current = pending.pop(0)
            for dependent in self._downstream(current):
                if dependent in visited:
                    continue
                visited.add(dependent)
                node = self._nodes[dependent]
                if node.locked:
                    blocked.add(dependent)
                    continue
                invalidated.add(dependent)
                pending.append(dependent)
        return GraphImpact(
            changed_node_ids=changed,
            invalidated_node_ids=tuple(sorted(invalidated)),
            blocked_locked_node_ids=tuple(sorted(blocked)),
        )

    def update_node(
        self,
        *,
        expected_version: str,
        node_id: str,
        patch: Mapping[str, Any],
    ) -> GraphMutationReceipt:
        self._require_head(expected_version)
        node = self.node(node_id)
        if node.locked:
            raise LockedNodeError(f"node is locked: {node.node_id}")
        patch_value = _normalize_attributes(patch)
        merged = dict(node.attributes)
        merged.update(patch_value)
        impact = self.impact((node.node_id,))
        self._replace_node(node, attributes=merged)
        return self._commit(
            expected_version=expected_version,
            operation="UPDATE_NODE",
            impact=impact,
            metadata={"patch_sha256": _sha(patch_value)},
        )

    def set_lock(
        self,
        *,
        expected_version: str,
        node_id: str,
        locked: bool,
    ) -> GraphMutationReceipt:
        self._require_head(expected_version)
        node = self.node(node_id)
        if node.locked == bool(locked):
            raise CreativeGraphError("lock state is unchanged")
        self._replace_node(node, locked=bool(locked))
        impact = GraphImpact((node.node_id,), (), ())
        return self._commit(
            expected_version=expected_version,
            operation="LOCK_NODE" if locked else "UNLOCK_NODE",
            impact=impact,
        )

    def graph_receipt(self) -> GraphMutationReceipt:
        return self._receipt(
            operation="READBACK",
            impact=GraphImpact((), (), ()),
        )
