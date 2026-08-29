from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from .version_tree import VersionTree, VersionTreeError


_ASSET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_REF_SCHEMA = "SOVARA_CREATIVE_VERSION_TREE_LOCAL_REFS_V1"
_STORE_RECEIPT_SCHEMA = "SOVARA_CREATIVE_VERSION_TREE_LOCAL_STORE_RECEIPT_V1"


class VersionTreeStoreError(RuntimeError):
    pass


class StoreNotInitializedError(VersionTreeStoreError):
    pass


class StoreAlreadyInitializedError(VersionTreeStoreError):
    pass


class StoreCorruptionError(VersionTreeStoreError):
    pass


class StoreConcurrentMutationError(VersionTreeStoreError):
    pass


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha_json(value: object) -> str:
    return _sha_bytes(_stable_json(value).encode("utf-8"))


def _canonical_json_bytes(value: object) -> bytes:
    return (_stable_json(value) + "\n").encode("utf-8")


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        _fsync_dir(path.parent)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _write_once_verified(path: Path, data: bytes) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise StoreCorruptionError(f"unexpected storage object at {path.name}")
        if path.read_bytes() != data:
            raise StoreCorruptionError(f"immutable object collision at {path.name}")
        return
    _atomic_write(path, data)


def _validated_asset_id(asset_id: str) -> str:
    if not isinstance(asset_id, str):
        raise VersionTreeStoreError("asset_id must be a string")
    canonical = asset_id.strip()
    if canonical != asset_id:
        raise VersionTreeStoreError(
            "asset_id leading or trailing whitespace is forbidden"
        )
    if not _ASSET_ID.fullmatch(asset_id):
        raise VersionTreeStoreError("asset_id contains unsafe path characters")
    if asset_id in {".", ".."} or ".." in asset_id:
        raise VersionTreeStoreError("asset_id path traversal is forbidden")
    return asset_id


@dataclass(frozen=True, slots=True)
class LocalStoreReceipt:
    schema: str
    asset_id: str
    generation: int
    node_count: int
    branch_heads: dict[str, str]
    refs_sha256: str
    tree_receipt_sha256: str
    integrity_verified: bool
    restart_readback_verified: bool
    atomic_replace_protocol: bool
    local_filesystem_only: bool
    external_effect_performed: bool
    provider_effect_performed: bool
    production_deployment_performed: bool
    receipt_sha256: str


class FileVersionTreeStore:
    """Crash-safe local filesystem persistence for ``VersionTree``.

    Immutable blobs and node records are written before mutable branch refs. Refs are
    replaced atomically and guarded by an observed-state hash. A crash before refs
    replacement can therefore leave only unreachable immutable objects; restart loads
    exclusively from the authoritative heads and ignores those orphan objects.

    This implementation performs local filesystem I/O only. It does not contact a
    cloud storage provider, deploy a runtime, publish media, authorize spend, or make
    any external communication.
    """

    def __init__(self, root: str | Path, asset_id: str) -> None:
        self.root = Path(root)
        self.asset_id = _validated_asset_id(asset_id)
        self.asset_dir = self.root / "assets" / self.asset_id
        self.blob_dir = self.asset_dir / "blobs"
        self.node_dir = self.asset_dir / "nodes"
        self.refs_path = self.asset_dir / "refs.json"

    def _guard_layout(self) -> None:
        for path in (
            self.root,
            self.root / "assets",
            self.asset_dir,
            self.blob_dir,
            self.node_dir,
        ):
            if path.exists() and path.is_symlink():
                raise StoreCorruptionError(
                    f"symlinked storage path rejected: {path.name}"
                )
        if self.refs_path.exists() and (
            self.refs_path.is_symlink() or not self.refs_path.is_file()
        ):
            raise StoreCorruptionError("refs.json must be a regular file")

    def _ensure_layout(self) -> None:
        self._guard_layout()
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self.node_dir.mkdir(parents=True, exist_ok=True)
        self._guard_layout()

    def _read_refs(self) -> tuple[dict[str, Any], bytes, str]:
        self._guard_layout()
        if not self.refs_path.exists():
            raise StoreNotInitializedError("version tree store is not initialized")
        raw = self.refs_path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise StoreCorruptionError("refs.json is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise StoreCorruptionError("refs.json must contain an object")
        if payload.get("schema") != _REF_SCHEMA:
            raise StoreCorruptionError("unexpected refs schema")
        if payload.get("asset_id") != self.asset_id:
            raise StoreCorruptionError("refs asset_id mismatch")

        state_sha = str(payload.get("state_sha256", ""))
        unsigned = {key: value for key, value in payload.items() if key != "state_sha256"}
        if state_sha != _sha_json(unsigned):
            raise StoreCorruptionError("refs state hash mismatch")

        generation = payload.get("generation")
        branches = payload.get("branches")
        if not isinstance(generation, int) or generation < 1:
            raise StoreCorruptionError("refs generation is invalid")
        if not isinstance(branches, dict) or not branches:
            raise StoreCorruptionError("refs branches must be a non-empty object")
        for branch, head in branches.items():
            if (
                not isinstance(branch, str)
                or not branch
                or any(ch.isspace() for ch in branch)
            ):
                raise StoreCorruptionError("refs contains invalid branch name")
            if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{64}", head):
                raise StoreCorruptionError("refs contains invalid version id")
        return payload, raw, _sha_bytes(raw)

    def _refs_document(
        self,
        *,
        tree: VersionTree,
        generation: int,
        previous_refs_sha256: str | None,
    ) -> dict[str, Any]:
        base: dict[str, Any] = {
            "schema": _REF_SCHEMA,
            "asset_id": self.asset_id,
            "generation": generation,
            "branches": tree.branch_heads(),
            "tree_receipt_sha256": tree.receipt().receipt_sha256,
            "previous_refs_sha256": previous_refs_sha256,
        }
        return {**base, "state_sha256": _sha_json(base)}

    def _reachable_versions(self, tree: VersionTree) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for head in tree.branch_heads().values():
            for version_id in tree.lineage(head):
                if version_id not in seen:
                    seen.add(version_id)
                    ordered.append(version_id)
        return tuple(ordered)

    def _persist_immutable_objects(self, tree: VersionTree) -> None:
        self._ensure_layout()
        for version_id in self._reachable_versions(tree):
            node = tree.node(version_id)
            content = tree.content(version_id)
            if _sha_bytes(content) != node.content_sha256:
                raise StoreCorruptionError("in-memory content hash mismatch")
            _write_once_verified(
                self.blob_dir / f"{node.content_sha256}.bin", content
            )
            node_payload = {"version_id": node.version_id, **node.canonical_record()}
            _write_once_verified(
                self.node_dir / f"{node.version_id}.json",
                _canonical_json_bytes(node_payload),
            )

    def _replace_refs_guarded(
        self,
        payload: Mapping[str, Any],
        *,
        expected_current_refs_sha256: str | None,
    ) -> str:
        if self.refs_path.exists():
            observed_raw = self.refs_path.read_bytes()
            observed_sha = _sha_bytes(observed_raw)
            if (
                expected_current_refs_sha256 is None
                or observed_sha != expected_current_refs_sha256
            ):
                raise StoreConcurrentMutationError(
                    "refs changed since the mutation began"
                )
        elif expected_current_refs_sha256 is not None:
            raise StoreConcurrentMutationError(
                "refs disappeared since the mutation began"
            )

        raw = _canonical_json_bytes(dict(payload))
        _atomic_write(self.refs_path, raw)
        reread = self.refs_path.read_bytes()
        if reread != raw:
            raise StoreCorruptionError("refs readback mismatch after atomic replace")
        return _sha_bytes(reread)

    def initialize(
        self,
        *,
        content: bytes,
        branch: str = "main",
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[VersionTree, LocalStoreReceipt]:
        self._ensure_layout()
        if self.refs_path.exists():
            raise StoreAlreadyInitializedError(
                "version tree store already initialized"
            )
        tree = VersionTree(self.asset_id)
        tree.create_root(content=content, branch=branch, metadata=metadata)
        self._persist_immutable_objects(tree)
        refs = self._refs_document(
            tree=tree, generation=1, previous_refs_sha256=None
        )
        self._replace_refs_guarded(
            refs, expected_current_refs_sha256=None
        )
        loaded, receipt = self.load()
        if loaded.receipt().receipt_sha256 != tree.receipt().receipt_sha256:
            raise StoreCorruptionError(
                "restart readback does not match initialized tree"
            )
        return loaded, receipt

    def _node_payload(self, version_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{64}", version_id):
            raise StoreCorruptionError(
                "invalid version id in refs or node lineage"
            )
        path = self.node_dir / f"{version_id}.json"
        if not path.exists() or path.is_symlink() or not path.is_file():
            raise StoreCorruptionError(f"missing immutable node {version_id}")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise StoreCorruptionError(
                f"node {version_id} is not valid JSON"
            ) from exc
        if not isinstance(payload, dict) or payload.get("version_id") != version_id:
            raise StoreCorruptionError("node version_id mismatch")
        record = {
            key: value for key, value in payload.items() if key != "version_id"
        }
        if _sha_json(record) != version_id:
            raise StoreCorruptionError("node canonical hash mismatch")
        return payload

    def _blob(self, content_sha256: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
            raise StoreCorruptionError("invalid content hash")
        path = self.blob_dir / f"{content_sha256}.bin"
        if not path.exists() or path.is_symlink() or not path.is_file():
            raise StoreCorruptionError(
                f"missing immutable blob {content_sha256}"
            )
        content = path.read_bytes()
        if _sha_bytes(content) != content_sha256:
            raise StoreCorruptionError("blob content hash mismatch")
        return content

    def load(self) -> tuple[VersionTree, LocalStoreReceipt]:
        refs, _, refs_sha = self._read_refs()
        tree = VersionTree(self.asset_id)
        loading: set[str] = set()
        loaded: set[str] = set()

        def load_node(version_id: str) -> None:
            if version_id in loaded:
                return
            if version_id in loading:
                raise StoreCorruptionError(
                    "cycle detected in persistent lineage"
                )
            loading.add(version_id)
            payload = self._node_payload(version_id)
            parents = payload.get("parent_ids")
            if not isinstance(parents, list) or len(parents) > 2:
                raise StoreCorruptionError("node parent_ids invalid")

            rollback_of = payload.get("rollback_of")
            dependencies = list(parents)
            if rollback_of is not None:
                if not isinstance(rollback_of, str):
                    raise StoreCorruptionError(
                        "rollback_of must be a version id or null"
                    )
                dependencies.append(rollback_of)
            for dependency in dependencies:
                if not isinstance(dependency, str):
                    raise StoreCorruptionError(
                        "node dependency must be a version id"
                    )
                load_node(dependency)

            content_sha = payload.get("content_sha256")
            metadata = payload.get("metadata")
            if not isinstance(content_sha, str):
                raise StoreCorruptionError("node content_sha256 missing")
            if not isinstance(metadata, dict):
                raise StoreCorruptionError("node metadata must be an object")
            content = self._blob(content_sha)
            try:
                node = tree._make_node(
                    content=content,
                    parents=tuple(parents),
                    operation=str(payload.get("operation", "")),
                    metadata=metadata,
                    rollback_of=rollback_of,
                )
            except VersionTreeError as exc:
                raise StoreCorruptionError(
                    f"persistent node rejected: {version_id}"
                ) from exc
            if node.version_id != version_id:
                raise StoreCorruptionError(
                    "reconstructed version id mismatch"
                )
            loading.remove(version_id)
            loaded.add(version_id)

        branches = refs["branches"]
        for head in branches.values():
            load_node(head)
        tree._branches = dict(branches)
        if not tree.verify_integrity():
            raise StoreCorruptionError(
                "reconstructed tree integrity failed"
            )

        expected_tree_receipt = str(refs.get("tree_receipt_sha256", ""))
        observed_tree_receipt = tree.receipt().receipt_sha256
        if expected_tree_receipt != observed_tree_receipt:
            raise StoreCorruptionError(
                "tree receipt mismatch after restart reconstruction"
            )

        receipt_base = {
            "schema": _STORE_RECEIPT_SCHEMA,
            "asset_id": self.asset_id,
            "generation": refs["generation"],
            "node_count": tree.node_count,
            "branch_heads": tree.branch_heads(),
            "refs_sha256": refs_sha,
            "tree_receipt_sha256": observed_tree_receipt,
            "integrity_verified": True,
            "restart_readback_verified": True,
            "atomic_replace_protocol": True,
            "local_filesystem_only": True,
            "external_effect_performed": False,
            "provider_effect_performed": False,
            "production_deployment_performed": False,
        }
        receipt = LocalStoreReceipt(
            **receipt_base, receipt_sha256=_sha_json(receipt_base)
        )
        return tree, receipt

    def _mutate(
        self, operation: str, **kwargs: Any
    ) -> tuple[VersionTree, LocalStoreReceipt]:
        tree, prior_receipt = self.load()
        _, _, expected_refs_sha = self._read_refs()
        if expected_refs_sha != prior_receipt.refs_sha256:
            raise StoreConcurrentMutationError(
                "refs changed between readback steps"
            )

        if operation == "commit":
            tree.commit(**kwargs)
        elif operation == "create_branch":
            tree.create_branch(**kwargs)
        elif operation == "merge":
            tree.merge(**kwargs)
        elif operation == "rollback":
            tree.rollback(**kwargs)
        else:
            raise VersionTreeStoreError(
                f"unsupported mutation: {operation}"
            )

        self._persist_immutable_objects(tree)
        refs = self._refs_document(
            tree=tree,
            generation=prior_receipt.generation + 1,
            previous_refs_sha256=expected_refs_sha,
        )
        self._replace_refs_guarded(
            refs, expected_current_refs_sha256=expected_refs_sha
        )
        loaded, receipt = self.load()
        if loaded.receipt().receipt_sha256 != tree.receipt().receipt_sha256:
            raise StoreCorruptionError(
                "post-mutation restart readback mismatch"
            )
        return loaded, receipt

    def commit(
        self,
        *,
        branch: str,
        expected_head: str,
        content: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[VersionTree, LocalStoreReceipt]:
        return self._mutate(
            "commit",
            branch=branch,
            expected_head=expected_head,
            content=content,
            metadata=metadata,
        )

    def create_branch(
        self, *, branch: str, from_version: str
    ) -> tuple[VersionTree, LocalStoreReceipt]:
        return self._mutate(
            "create_branch", branch=branch, from_version=from_version
        )

    def merge(
        self,
        *,
        target_branch: str,
        expected_target_head: str,
        source_version: str,
        merged_content: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[VersionTree, LocalStoreReceipt]:
        return self._mutate(
            "merge",
            target_branch=target_branch,
            expected_target_head=expected_target_head,
            source_version=source_version,
            merged_content=merged_content,
            metadata=metadata,
        )

    def rollback(
        self,
        *,
        branch: str,
        expected_head: str,
        target_version: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[VersionTree, LocalStoreReceipt]:
        return self._mutate(
            "rollback",
            branch=branch,
            expected_head=expected_head,
            target_version=target_version,
            metadata=metadata,
        )
