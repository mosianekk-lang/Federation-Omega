from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .core import PolicyError, ProofPolicy as _CoreProofPolicy

_EXTENSION_SCHEMA = "FEDERATION-PROOFOS-OMEGA-ADDITIVE-EXTENSION-V1"
_EXTENSION_GLOB = "proofos_omega_policy_extension_*.json"
_ALLOWED_EXTENSION_KEYS = frozenset(
    {
        "schema",
        "version",
        "risk_rules",
        "subsystem_rules",
        "historical_associations",
        "tests",
    }
)
_ADDITIVE_LIST_KEYS = (
    "risk_rules",
    "subsystem_rules",
    "historical_associations",
    "tests",
)


def _load_additive_extension(path: Path) -> Mapping[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise PolicyError(f"ProofOS extension must be an object: {path.name}")
    unknown = sorted(set(raw) - _ALLOWED_EXTENSION_KEYS)
    if unknown:
        raise PolicyError(
            f"ProofOS extension may only add admission records: {path.name}:"
            + ",".join(unknown)
        )
    if raw.get("schema") != _EXTENSION_SCHEMA:
        raise PolicyError(f"unsupported ProofOS extension schema: {path.name}")
    version = str(raw.get("version", ""))
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise PolicyError(f"invalid ProofOS extension version: {path.name}")
    for key in _ADDITIVE_LIST_KEYS:
        value = raw.get(key, [])
        if not isinstance(value, list):
            raise PolicyError(f"ProofOS extension {key} must be a list: {path.name}")
    return raw


class ProofPolicy(_CoreProofPolicy):
    """Canonical ProofOS policy plus authority-neutral additive sidecars.

    Sidecars are deliberately constrained to risk rules, subsystem ownership,
    historical associations and test specifications. They cannot override the
    primary selector, truth boundary, authority ceiling, external-effect
    default, or any existing record. Core ``ProofPolicy`` validation then
    rejects duplicate tests, unknown subsystem dependencies, unsafe targets and
    graph cycles after composition.
    """

    @classmethod
    def from_path(cls, path: str | Path) -> "ProofPolicy":
        primary_path = Path(path)
        raw = json.loads(primary_path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise PolicyError("ProofOS primary policy must be an object")
        merged = json.loads(json.dumps(raw))
        for extension_path in sorted(primary_path.parent.glob(_EXTENSION_GLOB)):
            extension = _load_additive_extension(extension_path)
            for key in _ADDITIVE_LIST_KEYS:
                merged.setdefault(key, [])
                merged[key].extend(json.loads(json.dumps(extension.get(key, []))))
        return cls(merged)


__all__ = ["ProofPolicy"]
