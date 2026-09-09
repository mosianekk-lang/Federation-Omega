#!/usr/bin/env python3
"""Normalize Cloud Run environment bindings without exposing values.

The Cloud Run v1/Knative and v2 provider surfaces use different nesting and
secret-reference keys. This module walks the complete provider document,
classifies every environment entry, and emits metadata-only evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator


SECRET_REF_KEYS = {"secretkeyref", "secret_key_ref"}
SECRET_CONTAINER_KEYS = {"valuefrom", "valuesource", "value_source"}


class TemplateNormalizationError(ValueError):
    """Fail-closed provider-template normalization error."""


def _canonical_key(value: object) -> str:
    return str(value).replace("-", "").replace("_", "").lower()


def _walk(value: Any, path: tuple[object, ...] = ()) -> Iterator[tuple[tuple[object, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + (index,))


def _secret_ref(entry: dict[str, Any]) -> tuple[str, str] | None:
    for path, value in _walk(entry):
        if not path or not isinstance(value, dict):
            continue
        key = _canonical_key(path[-1])
        if key not in SECRET_REF_KEYS:
            continue
        secret = str(value.get("name") or value.get("secret") or "").strip()
        version = str(value.get("key") or value.get("version") or "").strip()
        if not secret:
            raise TemplateNormalizationError("SECRET_REFERENCE_NAME_MISSING")
        return secret, version
    return None


def _looks_secret_backed(entry: dict[str, Any]) -> bool:
    for path, _ in _walk(entry):
        if not path:
            continue
        key = _canonical_key(path[-1])
        if key in SECRET_REF_KEYS or key in SECRET_CONTAINER_KEYS:
            return True
    return False


def _env_collections(document: Any) -> Iterator[tuple[tuple[object, ...], list[Any]]]:
    for path, value in _walk(document):
        if path and _canonical_key(path[-1]) == "env" and isinstance(value, list):
            yield path, value


def normalize(document: dict[str, Any], expected_service: str | None = None) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise TemplateNormalizationError("PROVIDER_DOCUMENT_NOT_OBJECT")

    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    service_name = str(metadata.get("name") or document.get("name") or "").strip()
    if expected_service and service_name != expected_service:
        raise TemplateNormalizationError(
            f"SERVICE_IDENTITY_MISMATCH:{service_name or '<missing>'}"
        )

    normalized: list[dict[str, Any]] = []
    collections = 0
    for path, entries in _env_collections(document):
        collections += 1
        for index, raw in enumerate(entries):
            if not isinstance(raw, dict):
                raise TemplateNormalizationError("ENV_ENTRY_NOT_OBJECT")
            name = str(raw.get("name") or "").strip()
            if not name:
                raise TemplateNormalizationError("ENV_NAME_MISSING")
            secret = _secret_ref(raw)
            if secret:
                secret_name, version = secret
                normalized.append(
                    {
                        "name": name,
                        "kind": "secret",
                        "secret_name": secret_name,
                        "secret_version": version or None,
                        "path": ".".join(str(part) for part in path + (index,)),
                    }
                )
            elif _looks_secret_backed(raw):
                raise TemplateNormalizationError(f"UNRECOGNIZED_SECRET_BINDING:{name}")
            elif "value" in raw:
                normalized.append(
                    {
                        "name": name,
                        "kind": "direct",
                        "value_present": raw.get("value") is not None,
                        "path": ".".join(str(part) for part in path + (index,)),
                    }
                )
            else:
                raise TemplateNormalizationError(f"ENV_BINDING_KIND_UNKNOWN:{name}")

    if collections == 0:
        raise TemplateNormalizationError("ENV_COLLECTION_MISSING")

    normalized.sort(key=lambda item: (item["name"], item["path"]))
    secret_names = sorted({item["name"] for item in normalized if item["kind"] == "secret"})
    direct_names = sorted({item["name"] for item in normalized if item["kind"] == "direct"})
    semantic = {
        "schema": "CLOUD_RUN_TEMPLATE_NORMALIZED_V1",
        "service_name": service_name,
        "env_collection_count": collections,
        "binding_count": len(normalized),
        "secret_backed_count": len([item for item in normalized if item["kind"] == "secret"]),
        "secret_backed_names": secret_names,
        "direct_names": direct_names,
        "bindings": normalized,
        "raw_values_emitted": False,
    }
    digest_input = json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
    semantic["semantic_sha256"] = hashlib.sha256(digest_input).hexdigest()
    return semantic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-service")
    parser.add_argument("--require-secret-env", action="append", default=[])
    args = parser.parse_args()

    document = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = normalize(document, args.expected_service)
    missing = sorted(set(args.require_secret_env) - set(result["secret_backed_names"]))
    if missing:
        raise TemplateNormalizationError(
            "REQUIRED_SECRET_BINDING_NOT_FOUND:" + ",".join(missing)
        )
    Path(args.output).write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
