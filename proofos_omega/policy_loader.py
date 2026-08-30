"""Public-safe additive ProofOS policy loader.

This module is intentionally separated from CLI diagnostic redaction patterns so the
Phoenix Core exporter can retain policy loading without weakening its secret-marker
exclusion rules.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .core import PolicyError, ProofPolicy


_EXTENSION_SCHEMA = "FEDERATION-PROOFOS-OMEGA-EXTENSION-V1"
_EXTENSION_FILENAME = "policy_extensions_v1.json"
_EXTENSION_ALLOWED_KEYS = {
    "schema",
    "version",
    "base_policy_version",
    "authority_ceiling",
    "external_effect_default",
    "purpose",
    "risk_rules",
    "subsystem_rules",
    "historical_associations",
    "tests",
}
_EXTENSION_APPEND_KEYS = (
    "risk_rules",
    "subsystem_rules",
    "historical_associations",
    "tests",
)


def _merge_policy_extension(base: dict, extension: dict) -> dict:
    """Merge one extension additively and fail closed on any override attempt."""
    unexpected = set(extension) - _EXTENSION_ALLOWED_KEYS
    if unexpected:
        raise PolicyError(f"ProofOS extension contains forbidden keys: {sorted(unexpected)}")
    if extension.get("schema") != _EXTENSION_SCHEMA:
        raise PolicyError("unsupported ProofOS extension schema")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(extension.get("version", ""))):
        raise PolicyError("invalid ProofOS extension version")
    if str(extension.get("base_policy_version", "")) != str(base.get("version", "")):
        raise PolicyError("ProofOS extension base policy version mismatch")
    if extension.get("authority_ceiling") != "A1_INTERNAL":
        raise PolicyError("ProofOS extension may not expand authority")
    if extension.get("external_effect_default") is not False:
        raise PolicyError("ProofOS extension may not enable external effects")

    existing_subsystems = {
        str(item.get("subsystem", "")) for item in base.get("subsystem_rules", [])
    }
    extension_subsystems = [
        str(item.get("subsystem", "")) for item in extension.get("subsystem_rules", [])
    ]
    if not all(extension_subsystems) or len(extension_subsystems) != len(
        set(extension_subsystems)
    ):
        raise PolicyError(
            "ProofOS extension subsystem identities must be non-empty and unique"
        )
    overlap_subsystems = existing_subsystems & set(extension_subsystems)
    if overlap_subsystems:
        raise PolicyError(
            "ProofOS extension may not replace subsystem identities: "
            f"{sorted(overlap_subsystems)}"
        )

    existing_tests = {str(item.get("id", "")) for item in base.get("tests", [])}
    extension_tests = [
        str(item.get("id", "")) for item in extension.get("tests", [])
    ]
    if not all(extension_tests) or len(extension_tests) != len(set(extension_tests)):
        raise PolicyError("ProofOS extension test identities must be non-empty and unique")
    overlap_tests = existing_tests & set(extension_tests)
    if overlap_tests:
        raise PolicyError(
            f"ProofOS extension may not replace test identities: {sorted(overlap_tests)}"
        )

    merged = json.loads(json.dumps(base))
    for key in _EXTENSION_APPEND_KEYS:
        merged.setdefault(key, [])
        merged[key].extend(json.loads(json.dumps(extension.get(key, []))))
    return merged


def _load_policy(
    policy_path: str | Path, repo_root: str | Path = "."
) -> ProofPolicy:
    """Load the canonical policy plus an optional validated additive extension."""
    path = Path(policy_path)
    base = json.loads(path.read_text(encoding="utf-8"))
    extension_path = Path(repo_root) / "proofos_omega" / _EXTENSION_FILENAME
    if extension_path.is_file():
        extension = json.loads(extension_path.read_text(encoding="utf-8"))
        base = _merge_policy_extension(base, extension)
    return ProofPolicy(base)
