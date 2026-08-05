from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .ao_cra import BoundaryEvent, create_build_trigger

SCHEMA = "FEDOMEGA-AWARENESS-READBACK-RECONCILIATION-1"
READBACK_SCHEMA = "FEDOMEGA-PROVIDER-READBACK-1"
FOUNDRY_SCHEMA = "FEDOMEGA-AWARENESS-OPPORTUNITY-FOUNDRY-1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


class ReconciliationError(RuntimeError):
    """Fail-closed foundry receipt or provider-readback error."""


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def reject_secret_material(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in {
                "token", "secret", "password", "api_key",
                "credential_value", "private_key",
            }:
                raise ReconciliationError(f"secret-bearing field prohibited: {path}.{key}")
            reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise ReconciliationError(f"secret-shaped value prohibited at {path}")


def verify_foundry_receipt(receipt: Mapping[str, Any]) -> None:
    reject_secret_material(receipt, "foundry")
    if receipt.get("schema") != FOUNDRY_SCHEMA:
        raise ReconciliationError("foundry receipt schema mismatch")
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or not re.fullmatch(r"[0-9a-f]{64}", claimed):
        raise ReconciliationError("foundry receipt SHA-256 is invalid")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if canonical_sha256(body) != claimed:
        raise ReconciliationError("foundry receipt embedded SHA-256 verification failed")
    if receipt.get("credential_value_recorded") is not False:
        raise ReconciliationError("foundry receipt weakens credential boundary")
    if receipt.get("provider_mutation_performed") is not False:
        raise ReconciliationError("foundry receipt already claims provider mutation")


def _readback_map(readbacks: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    allowed = {
        "READ_PROBE_VERIFIED", "EFFECTFUL_CAPABILITY_VERIFIED",
        "AUTHORITY_BLOCKED", "LOGIN_APPROVAL_GATED",
    }
    mapped: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(readbacks):
        item = dict(raw)
        reject_secret_material(item, f"readbacks[{index}]")
        if item.get("schema") != READBACK_SCHEMA:
            raise ReconciliationError("provider readback schema mismatch")
        alias = str(item.get("source_alias", "")).strip()
        if not alias:
            raise ReconciliationError("provider readback source_alias is required")
        if alias in mapped:
            raise ReconciliationError(f"duplicate provider readback for {alias}")
        if item.get("credential_value_recorded") is not False:
            raise ReconciliationError(f"credential value boundary failed for {alias}")
        if item.get("provider_mutation_performed") is not False:
            raise ReconciliationError(f"read-only canary unexpectedly mutated provider for {alias}")
        if item.get("status") not in allowed:
            raise ReconciliationError(f"unsupported provider readback status for {alias}")
        if not str(item.get("evidence", "")).strip():
            raise ReconciliationError(f"provider readback evidence is required for {alias}")
        mapped[alias] = item
    return mapped


def _build_trigger(
    *, statement: str, capability: str, engine: str,
    workaround: str, dependency: str, source_trigger: str,
    reuse: tuple[str, ...],
) -> dict[str, Any]:
    return create_build_trigger(
        BoundaryEvent(
            statement=statement,
            desired_capability=capability,
            owning_engine=engine,
            workaround=workaround,
            dependency=dependency,
            source_trigger=source_trigger,
        ),
        existing_capabilities=reuse,
    ).to_dict()


def _effectful_successor(original: Mapping[str, Any], readback: Mapping[str, Any]) -> dict[str, Any]:
    alias = str(original["source_alias"])
    capability = (
        f"Least-privilege effectful capability for {alias} with provider-native "
        "semantic readback and rollback proof"
    )
    trigger = _build_trigger(
        statement=(
            f"{alias} read access is verified but effectful authority and native "
            "mutation readback remain unverified"
        ),
        capability=capability,
        engine="FORMATION_INNOVATION_ENGINE",
        workaround="Use the verified read-only connector for discovery and planning",
        dependency=str(readback.get("provider", "provider")),
        source_trigger=f"provider-readback-reconciler:{alias}",
        reuse=("FEDERATION_SURFACE_AWARENESS", "AWARENESS_OPPORTUNITY_FOUNDRY", "AO_CRA"),
    )
    return {
        "opportunity_id": f"OPP-{trigger['build_id'].removeprefix('BUILD-AO-FED-')}",
        "opportunity_class": "PROVIDER_EFFECTFUL_CAPABILITY",
        "source_alias": alias,
        "title": f"Enable least-privilege effectful capability for {alias}",
        "owning_engine": "FORMATION_INNOVATION_ENGINE",
        "desired_capability": capability,
        "current_state": "READ_PROBE_VERIFIED_EFFECTFUL_AUTHORITY_OPEN",
        "buildable_now": False,
        "external_effect": True,
        "priority": int(original.get("priority", 70)),
        "reason": "READ_ACCESS_PROVEN_EFFECTFUL_AUTHORITY_NOT_PROVEN",
        "readback_evidence": str(readback["evidence"]),
        "supersedes_probe_opportunity_id": original.get("opportunity_id"),
        "build_trigger": trigger,
    }


def _drift_opportunity(pointer: str, stored: str, observed: str) -> dict[str, Any]:
    capability = "Automatic private-pointer reconciliation with append-only provenance"
    trigger = _build_trigger(
        statement=f"private pointer {pointer} stores {stored} while live main is {observed}",
        capability=capability,
        engine="FEDERATION_OMEGA_CORE",
        workaround="Read live main before selecting source-bound work",
        dependency="",
        source_trigger=f"private-pointer-drift:{pointer}",
        reuse=("AWARENESS_OPPORTUNITY_FOUNDRY", "GITHUB_CONNECTOR", "KIM_DATAVERSE_PRIVATE_BRIDGE"),
    )
    return {
        "opportunity_id": f"OPP-{trigger['build_id'].removeprefix('BUILD-AO-FED-')}",
        "opportunity_class": "DRIFT_REPAIR",
        "source_alias": "FEDERATION_OMEGA_CONTROL_PLANE",
        "title": f"Reconcile private pointer {pointer}",
        "owning_engine": "FEDERATION_OMEGA_CORE",
        "desired_capability": capability,
        "current_state": "PRIVATE_POINTER_STALE",
        "buildable_now": True,
        "external_effect": False,
        "priority": 120,
        "reason": "PRIVATE_POINTER_DRIFT",
        "build_trigger": trigger,
    }


def reconcile_foundry(
    *, foundry_receipt: Mapping[str, Any],
    provider_readbacks: Sequence[Mapping[str, Any]],
    observed_main: str,
    private_main_pointers: Mapping[str, str],
    source_merge_proof: Mapping[str, Any],
) -> dict[str, Any]:
    verify_foundry_receipt(foundry_receipt)
    observed = observed_main.lower()
    if not HEX40.fullmatch(observed):
        raise ReconciliationError("observed_main must be a 40-character lowercase SHA")
    reject_secret_material(source_merge_proof, "source_merge_proof")
    proof_requirements = {
        "foundry_source_present": "foundry source presence is not proven",
        "airlock_passed": "merge-result Airlock proof is required",
        "leak_guard_passed": "merge-result leak-guard proof is required",
        "phoenix_freeze_verified": "merge-result Phoenix freeze proof is required",
    }
    for field, message in proof_requirements.items():
        if source_merge_proof.get(field) is not True:
            raise ReconciliationError(message)

    readbacks = _readback_map(provider_readbacks)
    reconciled: list[dict[str, Any]] = []
    closed: list[str] = []
    successors: list[str] = []
    for raw in foundry_receipt.get("opportunities", []):
        item = deepcopy(dict(raw))
        readback = readbacks.get(str(item.get("source_alias", "")))
        if item.get("opportunity_class") == "PROVIDER_PROBE" and readback:
            if readback["status"] == "READ_PROBE_VERIFIED":
                item["build_trigger"]["lifecycle_state"] = "VERIFIED_READ_PROBE"
                item["current_state"] = "READ_PROBE_VERIFIED"
                item["closed_by_readback"] = True
                item["readback_evidence"] = readback["evidence"]
                closed.append(str(item["opportunity_id"]))
                reconciled.append(item)
                successor = _effectful_successor(item, readback)
                successors.append(successor["build_trigger"]["build_id"])
                reconciled.append(successor)
                continue
            if readback["status"] == "EFFECTFUL_CAPABILITY_VERIFIED":
                item["build_trigger"]["lifecycle_state"] = "VERIFIED"
                item["current_state"] = "EFFECTFUL_CAPABILITY_VERIFIED"
                item["closed_by_readback"] = True
                item["readback_evidence"] = readback["evidence"]
                closed.append(str(item["opportunity_id"]))
                reconciled.append(item)
                continue
            item["readback_status"] = readback["status"]
            item["readback_evidence"] = readback["evidence"]
        if item.get("opportunity_class") == "INTERNAL_HARDENING":
            item["build_trigger"]["lifecycle_state"] = "SOURCE_IMPLEMENTED_RUNTIME_PROOF_OPEN"
            item["current_state"] = "SOURCE_IMPLEMENTED_RUNTIME_PROOF_OPEN"
        reconciled.append(item)

    drifts = []
    drift_builds = []
    for pointer, stored in sorted(private_main_pointers.items()):
        if str(stored).lower() != observed:
            drift = {"pointer": pointer, "stored": str(stored).lower(), "observed": observed}
            drifts.append(drift)
            opportunity = _drift_opportunity(pointer, drift["stored"], observed)
            drift_builds.append(opportunity["build_trigger"]["build_id"])
            reconciled.append(opportunity)

    dedup = {str(item["opportunity_id"]): item for item in reconciled}
    ordered = sorted(dedup.values(), key=lambda item: (-int(item.get("priority", 0)), item["opportunity_id"]))
    active = [item for item in ordered if not item.get("closed_by_readback")]
    result = {
        "schema": SCHEMA,
        "status": "DRIFT_REPAIR_REQUIRED" if drifts else "VERIFIED_RECONCILED",
        "observed_main": observed,
        "source_foundry_receipt_sha256": foundry_receipt["receipt_sha256"],
        "source_merge_proof": dict(source_merge_proof),
        "provider_readback_aliases": sorted(readbacks),
        "closed_probe_opportunity_ids": sorted(closed),
        "successor_effectful_build_ids": sorted(successors),
        "private_pointer_drifts": drifts,
        "drift_build_ids": sorted(drift_builds),
        "reconciled_opportunities": ordered,
        "active_opportunities": active,
        "active_opportunity_count": len(active),
        "read_probe_satisfied_count": len(closed),
        "credential_value_recorded": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result
