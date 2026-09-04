from __future__ import annotations

import hashlib
import re
from urllib.parse import quote


def _slug(value: str, limit: int = 48) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-").lower()
    return (value or "object")[:limit]


def kim_id(kind: str, canonical_key: str, namespace: str = "estate") -> str:
    """Create a stable, readable, content-independent Kim Dataverse object identity.

    The human-readable prefix is not the identity guarantee. The suffix is a
    deterministic digest over namespace/kind/canonical key. Existing provider IDs
    remain source keys/provenance and are never replaced or reinterpreted.
    """
    kind = _slug(kind, 24)
    namespace = _slug(namespace, 24)
    key = str(canonical_key).strip()
    if not key:
        raise ValueError("canonical_key is required")
    digest = hashlib.sha256(f"{namespace}\0{kind}\0{key}".encode("utf-8")).hexdigest()[:16]
    return f"kim://{namespace}/{kind}/{quote(_slug(key))}~{digest}"


def preserve_or_map_entity(existing_id: str | None, kind: str, canonical_key: str, namespace: str = "estate") -> str:
    existing_id = str(existing_id or "").strip()
    if existing_id:
        return existing_id
    return kim_id(kind, canonical_key, namespace)
