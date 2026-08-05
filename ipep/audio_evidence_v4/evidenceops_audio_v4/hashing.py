from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


def canonical_json_bytes(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes suitable for hashing and receipts."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path, block_size: int = 1024 * 1024) -> str:
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_record_hash(value: dict[str, Any], *, exclude: Iterable[str] = ()) -> str:
    omitted = set(exclude)
    payload = {key: item for key, item in value.items() if key not in omitted}
    return sha256_bytes(canonical_json_bytes(payload))


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_json(path: str | Path, value: Any) -> None:
    atomic_write_bytes(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")


def merkle_root(leaves: Iterable[str]) -> str:
    """Compute a deterministic SHA-256 Merkle root over hexadecimal leaves."""
    nodes = [bytes.fromhex(leaf) for leaf in leaves]
    if not nodes:
        return sha256_bytes(b"")
    while len(nodes) > 1:
        if len(nodes) % 2:
            nodes.append(nodes[-1])
        nodes = [hashlib.sha256(nodes[i] + nodes[i + 1]).digest() for i in range(0, len(nodes), 2)]
    return nodes[0].hex()
