from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Protocol


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("utf-8")


@dataclass(frozen=True)
class StoredLedgerSnapshot:
    snapshot: dict[str, Any]
    snapshot_sha256: str
    generation: int


class LedgerStore(Protocol):
    def load(self) -> StoredLedgerSnapshot | None:
        ...

    def save(
        self,
        snapshot: dict[str, Any],
        *,
        expected_current_sha256: str | None = None,
    ) -> StoredLedgerSnapshot:
        ...


class AtomicJsonFileLedgerStore:
    """Atomic, hash-verified local durability adapter.

    This adapter is suitable for provider-disabled and single-writer runtime
    canaries. A provider deployment must place the file on a genuinely durable
    volume or replace this adapter with a transactional external store.
    """

    STORE_SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @staticmethod
    def _snapshot_hash(snapshot: dict[str, Any]) -> str:
        return sha256(_canonical_bytes(snapshot)).hexdigest()

    def load(self) -> StoredLedgerSnapshot | None:
        if not self.path.exists():
            return None
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("ledger store is unreadable or invalid JSON") from exc
        if envelope.get("store_schema_version") != self.STORE_SCHEMA_VERSION:
            raise ValueError("unsupported ledger store schema")
        snapshot = envelope.get("snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError("ledger store snapshot must be a dictionary")
        expected_hash = envelope.get("snapshot_sha256")
        actual_hash = self._snapshot_hash(snapshot)
        if expected_hash != actual_hash:
            raise ValueError("ledger store snapshot hash mismatch")
        generation = envelope.get("generation")
        if not isinstance(generation, int) or generation < 1:
            raise ValueError("ledger store generation must be >= 1")
        return StoredLedgerSnapshot(
            snapshot=snapshot,
            snapshot_sha256=actual_hash,
            generation=generation,
        )

    def save(
        self,
        snapshot: dict[str, Any],
        *,
        expected_current_sha256: str | None = None,
    ) -> StoredLedgerSnapshot:
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot must be a dictionary")
        current = self.load()
        if expected_current_sha256 is not None:
            current_hash = (
                current.snapshot_sha256 if current is not None else None
            )
            if current_hash != expected_current_sha256:
                raise ValueError("ledger compare-and-set conflict")
        generation = 1 if current is None else current.generation + 1
        snapshot_hash = self._snapshot_hash(snapshot)
        envelope = {
            "store_schema_version": self.STORE_SCHEMA_VERSION,
            "generation": generation,
            "snapshot_sha256": snapshot_hash,
            "snapshot": snapshot,
        }
        payload = _canonical_bytes(envelope)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            temp_path = None
            try:
                directory_fd = os.open(self.path.parent, os.O_DIRECTORY)
            except (AttributeError, OSError):
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        stored = self.load()
        if stored is None:
            raise RuntimeError("ledger snapshot missing after atomic write")
        return stored
