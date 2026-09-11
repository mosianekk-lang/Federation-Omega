from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class MemoryAccessPlan:
    access: str
    reason: str


class MemoryTrustPlanner:
    @staticmethod
    def choose(*, shared_reference: bool, untrusted_input_present: bool,
               write_needed: bool) -> MemoryAccessPlan:
        if shared_reference:
            return MemoryAccessPlan("read_only", "shared reference memory should not be mutated by sessions")
        if untrusted_input_present:
            return MemoryAccessPlan("read_only", "untrusted content can poison persistent writable memory")
        if write_needed:
            return MemoryAccessPlan("read_write", "trusted session requires durable learning")
        return MemoryAccessPlan("read_only", "no write requirement")


@dataclass(frozen=True)
class MemoryVersion:
    version: int
    content: str
    created_by: str


class VersionedMemoryStore:
    """Tiny immutable-version reference store; later versions never rewrite prior versions."""
    def __init__(self) -> None:
        self._items: Dict[str, Tuple[MemoryVersion, ...]] = {}

    def write(self, path: str, content: str, *, actor: str) -> MemoryVersion:
        if not path or path.startswith("../"):
            raise ValueError("invalid memory path")
        prior = self._items.get(path, ())
        v = MemoryVersion(len(prior) + 1, content, actor)
        self._items[path] = prior + (v,)
        return v

    def latest(self, path: str) -> MemoryVersion | None:
        versions = self._items.get(path, ())
        return versions[-1] if versions else None

    def history(self, path: str) -> Tuple[MemoryVersion, ...]:
        return self._items.get(path, ())
