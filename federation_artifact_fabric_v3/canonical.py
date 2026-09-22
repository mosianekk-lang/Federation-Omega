"""Deterministic encoding and hash helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def merkle_root(hex_hashes: Iterable[str]) -> str:
    leaves = sorted(str(item).lower() for item in hex_hashes)
    if not leaves:
        return sha256_bytes(b"")
    layer = [bytes.fromhex(item) for item in leaves]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [
            hashlib.sha256(layer[index] + layer[index + 1]).digest()
            for index in range(0, len(layer), 2)
        ]
    return layer[0].hex()
