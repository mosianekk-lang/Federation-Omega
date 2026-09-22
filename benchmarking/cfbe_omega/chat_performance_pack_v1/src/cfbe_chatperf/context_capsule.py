"""Deterministic task-bounded context capsules."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical import canonical_json, sha256_hex

REQUIRED_SECTIONS = ("objective", "requirements", "constraints", "source_epochs", "routes", "open_gates")
OPTIONAL_SECTIONS = ("recent_failures", "next_actions", "notes")


class CapsuleError(ValueError):
    pass


def build_capsule(source: Mapping[str, Any], max_bytes: int = 4000) -> dict[str, Any]:
    if max_bytes < 256:
        raise CapsuleError("max_bytes must be at least 256")
    missing = [key for key in REQUIRED_SECTIONS if key not in source]
    if missing:
        raise CapsuleError(f"missing sections: {','.join(missing)}")
    capsule: dict[str, Any] = {key: source[key] for key in REQUIRED_SECTIONS}
    omitted: list[str] = []
    included_optional: list[str] = []
    for key in OPTIONAL_SECTIONS:
        if key not in source:
            continue
        capsule[key] = source[key]
        included_optional.append(key)
    known = set(REQUIRED_SECTIONS + OPTIONAL_SECTIONS)
    omitted.extend(sorted(set(source) - known))

    def finalize() -> dict[str, Any]:
        value = dict(capsule)
        value["omitted"] = sorted(set(omitted))
        value["schema"] = "CFBE-CONTEXT-CAPSULE-1"
        value["digest"] = sha256_hex({k: v for k, v in value.items() if k != "digest"})
        value["bytes"] = 0
        for _ in range(4):
            value["bytes"] = len(canonical_json(value))
        return value

    result = finalize()
    while result["bytes"] > max_bytes and included_optional:
        key = included_optional.pop()
        capsule.pop(key, None)
        omitted.append(key)
        result = finalize()
    if result["bytes"] > max_bytes:
        raise CapsuleError(f"required context exceeds byte budget: {result['bytes']}>{max_bytes}")
    return result
