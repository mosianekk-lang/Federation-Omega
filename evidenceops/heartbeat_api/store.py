"""Immutable object-store contract and deterministic offline implementations."""

from __future__ import annotations

import hashlib
import os
import re
import threading
from bisect import insort
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Protocol, runtime_checkable

from .errors import ImmutableConflict, ResourceNotFound

OBJECT_KEY = re.compile(r"(?:events|receipts)/[0-9a-f]{64}\.json")
PREFIXES = ("events/", "receipts/")
MAX_PAGE_SIZE = 100
MAX_PAGE_OFFSET = 1_000_000
MAX_LOCAL_INDEX_OBJECTS = 10_000


def payload_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _validate_key(key: str) -> str:
    if not isinstance(key, str) or OBJECT_KEY.fullmatch(key) is None:
        raise ValueError("invalid immutable object key")
    return key


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    value: bytes
    object_hash: str
    generation: int = 1


@dataclass(frozen=True, slots=True)
class StoredObjectPage:
    objects: tuple[StoredObject, ...]
    offset: int
    next_offset: int | None
    total: int


def _validate_page(prefix: str, offset: int, limit: int) -> None:
    if prefix not in PREFIXES:
        raise ValueError("unsupported immutable object prefix")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= MAX_PAGE_OFFSET:
        raise ValueError("invalid immutable object page offset")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError("invalid immutable object page limit")


@runtime_checkable
class ImmutableObjectStore(Protocol):
    """Preconditioned create-only interface compatible with cloud object stores."""

    backend_code: str
    durability_class: str

    def create_if_absent(self, key: str, value: bytes) -> tuple[StoredObject, bool]: ...

    def read(self, key: str) -> StoredObject: ...

    def page_prefix(self, prefix: str, *, offset: int, limit: int) -> StoredObjectPage: ...

    def health(self) -> dict[str, object]: ...


class InMemoryImmutableStore:
    backend_code = "MEMORY-IMMUTABLE"
    durability_class = "VOLATILE_MEMORY"

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._keys: dict[str, list[str]] = {prefix: [] for prefix in PREFIXES}
        self._lock = threading.RLock()

    def create_if_absent(self, key: str, value: bytes) -> tuple[StoredObject, bool]:
        key = _validate_key(key)
        if not isinstance(value, bytes) or not value:
            raise ValueError("non-empty immutable bytes required")
        with self._lock:
            existing = self._objects.get(key)
            if existing is not None:
                if existing != value:
                    raise ImmutableConflict("immutable object precondition failed")
                return StoredObject(key, bytes(existing), payload_hash(existing)), False
            self._objects[key] = bytes(value)
            prefix = key.split("/", 1)[0] + "/"
            insort(self._keys[prefix], key)
            return StoredObject(key, bytes(value), payload_hash(value)), True

    def read(self, key: str) -> StoredObject:
        key = _validate_key(key)
        with self._lock:
            try:
                value = self._objects[key]
            except KeyError as exc:
                raise ResourceNotFound("immutable object not found") from exc
            return StoredObject(key, bytes(value), payload_hash(value))

    def page_prefix(self, prefix: str, *, offset: int, limit: int) -> StoredObjectPage:
        _validate_page(prefix, offset, limit)
        with self._lock:
            keys = self._keys[prefix]
            page_keys = keys[offset : offset + limit]
            objects = tuple(
                StoredObject(key, bytes(value), payload_hash(value))
                for key in page_keys
                for value in (self._objects[key],)
            )
            next_offset = offset + len(objects) if offset + len(objects) < len(keys) else None
            return StoredObjectPage(objects, offset, next_offset, len(keys))

    def health(self) -> dict[str, object]:
        with self._lock:
            return {
                "healthy": True,
                "backend_code": self.backend_code,
                "durability_class": self.durability_class,
                "object_count": len(self._objects),
            }


class LocalImmutableObjectStore:
    """Create-only local disk implementation; useful for tests, never cloud durable."""

    backend_code = "LOCAL-IMMUTABLE-OBJECTS"
    durability_class = "LOCAL_PROCESS_DISK"

    def __init__(self, root: str | Path) -> None:
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        self._root = root_path.resolve(strict=True)
        if not self._root.is_dir() or root_path.is_symlink():
            raise ValueError("safe local object directory required")
        self._lock = threading.RLock()
        self._keys: dict[str, list[str]] = {prefix: [] for prefix in PREFIXES}
        self._load_bounded_index()

    def _load_bounded_index(self) -> None:
        seen_entries = 0
        for prefix in PREFIXES:
            directory = self._root / prefix.rstrip("/")
            if not directory.exists():
                continue
            candidates = islice(directory.iterdir(), MAX_LOCAL_INDEX_OBJECTS - seen_entries + 1)
            for path in candidates:
                seen_entries += 1
                if seen_entries > MAX_LOCAL_INDEX_OBJECTS:
                    raise ValueError("local immutable object index capacity exceeded")
                if path.is_symlink() or not path.is_file():
                    continue
                key = str(path.relative_to(self._root))
                if OBJECT_KEY.fullmatch(key) is None:
                    continue
                self._keys[prefix].append(key)
            self._keys[prefix].sort()

    def _path(self, key: str) -> Path:
        key = _validate_key(key)
        target = self._root.joinpath(*key.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = target.parent.resolve(strict=True)
        if self._root not in (resolved_parent, *resolved_parent.parents):
            raise ValueError("object key escaped store root")
        return target

    def create_if_absent(self, key: str, value: bytes) -> tuple[StoredObject, bool]:
        if not isinstance(value, bytes) or not value:
            raise ValueError("non-empty immutable bytes required")
        target = self._path(key)
        with self._lock:
            try:
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if target.is_symlink():
                    raise ValueError("symlinked immutable object prohibited")
                existing = target.read_bytes()
                if existing != value:
                    raise ImmutableConflict("immutable object precondition failed")
                return StoredObject(key, existing, payload_hash(existing)), False
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(value)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            prefix = key.split("/", 1)[0] + "/"
            insort(self._keys[prefix], key)
            return StoredObject(key, bytes(value), payload_hash(value)), True

    def read(self, key: str) -> StoredObject:
        target = self._path(key)
        if target.is_symlink():
            raise ValueError("symlinked immutable object prohibited")
        try:
            value = target.read_bytes()
        except FileNotFoundError as exc:
            raise ResourceNotFound("immutable object not found") from exc
        return StoredObject(key, value, payload_hash(value))

    def page_prefix(self, prefix: str, *, offset: int, limit: int) -> StoredObjectPage:
        _validate_page(prefix, offset, limit)
        with self._lock:
            keys = self._keys[prefix]
            page_keys = keys[offset : offset + limit]
            objects = tuple(self.read(key) for key in page_keys)
            next_offset = offset + len(objects) if offset + len(objects) < len(keys) else None
            return StoredObjectPage(objects, offset, next_offset, len(keys))

    def health(self) -> dict[str, object]:
        return {
            "healthy": self._root.is_dir() and os.access(self._root, os.R_OK | os.W_OK),
            "backend_code": self.backend_code,
            "durability_class": self.durability_class,
            "object_count": sum(len(keys) for keys in self._keys.values()),
        }
