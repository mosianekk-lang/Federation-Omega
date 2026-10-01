"""Reconcile the existing unified service contract with ecosystem definitions.

This is a source projection and a compatibility adapter for FuseEcosystemKernel.
It does not inspect providers, create observations, execute effects, or establish
runtime readiness. Missing service definitions stay unresolved.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from federation.capability_truth_v1 import CapabilityCurrentnessFabric
from federation.fuse_ecosystem_v1 import (
    EcosystemServiceSpec,
    FUSE_ECOSYSTEM_SERVICES,
    FuseEcosystemKernel,
)


SCHEMA = "FUSE_UNIFIED_SERVICE_CATALOG_V1"
_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "fuse-unified-capability-fabric-v1.json"
)
_LEGACY_ALIASES = {"workflow.enterprise": "enterprise.workflow"}


def _read_contract() -> tuple[list[str], dict[str, str]]:
    """Require a complete, unambiguous family assignment for every contract ID."""
    contract = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise ValueError("UNIFIED_SERVICE_CONTRACT_INVALID")
    ids = contract.get("registered_services")
    families = contract.get("capability_families")
    if (
        contract.get("schema") != "FUSE_UNIFIED_CAPABILITY_FABRIC_V1"
        or not isinstance(ids, list)
        or not ids
        or any(not isinstance(item, str) or not item.strip() for item in ids)
        or len(ids) != len(set(ids))
        or type(contract.get("service_count")) is not int
        or contract["service_count"] != len(ids)
        or not isinstance(families, dict)
    ):
        raise ValueError("UNIFIED_SERVICE_CONTRACT_INVALID")

    family_by_id: dict[str, str] = {}
    for family, members in families.items():
        if not isinstance(family, str) or not family.strip() or not isinstance(members, list):
            raise ValueError("UNIFIED_SERVICE_FAMILY_INVALID")
        for service_id in members:
            if not isinstance(service_id, str) or service_id not in ids or service_id in family_by_id:
                raise ValueError("UNIFIED_SERVICE_FAMILY_AMBIGUOUS")
            family_by_id[service_id] = family
    if set(family_by_id) != set(ids):
        raise ValueError("UNIFIED_SERVICE_FAMILY_INCOMPLETE")
    return ids, family_by_id


def _definition(service_id: str) -> tuple[EcosystemServiceSpec | None, str | None]:
    implementation_id = service_id
    spec = FUSE_ECOSYSTEM_SERVICES.get(service_id)
    if spec is None:
        implementation_id = _LEGACY_ALIASES.get(service_id, service_id)
        spec = FUSE_ECOSYSTEM_SERVICES.get(implementation_id)
    if spec is None:
        return None, None
    spec.validate()
    if spec.service_id != implementation_id:
        raise ValueError("UNIFIED_SERVICE_DEFINITION_ID_MISMATCH")
    return spec, implementation_id


def resolve_unified_service(service_id: str) -> EcosystemServiceSpec:
    """Resolve one canonical source definition; never invent missing capabilities."""
    ids, _ = _read_contract()
    if service_id not in ids:
        raise ValueError(f"UNIFIED_SERVICE_UNKNOWN:{service_id}")
    spec, implementation_id = _definition(service_id)
    if spec is None:
        raise ValueError(f"UNIFIED_SERVICE_DEFINITION_MISSING:{service_id}")
    return spec if implementation_id == service_id else replace(spec, service_id=service_id)


def build_unified_kernel(fabric: CapabilityCurrentnessFabric) -> FuseEcosystemKernel:
    """Add canonical aliases to the existing kernel without changing its gates.

Legacy service IDs remain accepted. Undefined canonical services are omitted, so
the existing kernel's ECOSYSTEM_SERVICE_UNKNOWN error remains fail-closed.
Callability, authority, privacy and currentness still come from the given fabric.
"""
    ids, _ = _read_contract()
    services = dict(FUSE_ECOSYSTEM_SERVICES)
    for service_id in ids:
        spec, implementation_id = _definition(service_id)
        if spec is not None:
            services[service_id] = (
                spec if implementation_id == service_id else replace(spec, service_id=service_id)
            )
    return FuseEcosystemKernel(fabric, services=services)


def build_unified_service_catalog() -> dict[str, Any]:
    """Return public-safe source metadata; runtime readiness is explicitly unknown.

The output contains no filesystem paths, private locators, provider observations
or credentials. A definition is a composition contract, not an implementation or
execution receipt for its underlying capabilities.
"""
    ids, family_by_id = _read_contract()
    rows: list[dict[str, Any]] = []
    for service_id in ids:
        spec, implementation_id = _definition(service_id)
        alias_of = implementation_id if implementation_id != service_id else None
        source_state = (
            "UNRESOLVED_DEFINITION" if spec is None else "LEGACY_ALIAS" if alias_of else "DEFINED"
        )
        rows.append(
            {
                "service_id": service_id,
                "family": family_by_id[service_id],
                "source_state": source_state,
                "source_supported": spec is not None,
                "implementation_service_id": implementation_id,
                "alias_of": alias_of,
                "required_capabilities": list(spec.required_capabilities) if spec else None,
                "optional_capabilities": list(spec.optional_capabilities) if spec else None,
                "required_maturity": spec.required_maturity.name if spec else None,
                "description": spec.description if spec else "",
                "runtime_readiness": "NOT_ASSESSED",
                "callable_now": None,
            }
        )
    return {
        "schema": SCHEMA,
        "projection_only": True,
        "sovereign_controller_created": False,
        "services": rows,
        "counts": {
            "registered_services": len(rows),
            "source_supported": sum(row["source_supported"] for row in rows),
            "source_missing": sum(not row["source_supported"] for row in rows),
            "legacy_aliases": sum(row["source_state"] == "LEGACY_ALIAS" for row in rows),
            "runtime_assessed": 0,
        },
        "runtime_readiness": "NOT_ASSESSED",
        "truth_boundary": (
            "SERVICE_DEFINITION_NE_IMPLEMENTED_CAPABILITIES_NE_PROVIDER_CALLABLE_NE_"
            "PROVIDER_EXECUTED_NE_PRODUCTION_READY"
        ),
    }


__all__ = ["build_unified_service_catalog", "build_unified_kernel", "resolve_unified_service"]
