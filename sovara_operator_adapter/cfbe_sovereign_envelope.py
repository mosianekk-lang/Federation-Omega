#!/usr/bin/env python3
"""Portable JSON invocation envelope for CFBE-Ω sovereign core.

The envelope is intentionally provider-neutral and transport-neutral. A runtime
may receive the JSON through stdin/stdout, an HTTP body, a queue, Apps Script,
GitHub Actions, Cloud Run, or another authorised transport without changing the
semantic contract.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from .cfbe_sovereign_core import (
    AdapterCapability,
    Authority,
    MissionRequirement,
    SovereignCoreError,
    canonical_sha256,
    failover_route,
    portable_state_projection,
    rank_routes,
)

ENVELOPE_CONTRACT = "CFBE_OMEGA_SOVEREIGN_ENVELOPE_V1"
ENVELOPE_VERSION = "1.0.0"


def _authority(value: Any) -> Authority:
    if isinstance(value, int):
        return Authority(value)
    normalized = str(value or "A0_READ").strip().upper()
    try:
        return Authority[normalized]
    except KeyError as exc:
        raise SovereignCoreError(f"unsupported authority {value!r}") from exc


def _adapter(raw: Mapping[str, Any]) -> AdapterCapability:
    return AdapterCapability(
        adapter_id=str(raw["adapter_id"]),
        surface_class=str(raw["surface_class"]),
        capabilities=frozenset(str(v) for v in raw.get("capabilities", ())),
        authority_ceiling=_authority(raw.get("authority_ceiling", "A0_READ")),
        presence_state=str(raw.get("presence_state", "NOT_CONNECTED")),
        provider_execution_state=str(
            raw.get("provider_execution_state", "PROVIDER_UNVERIFIED")
        ),
        freshness_state=str(raw.get("freshness_state", "STALE")),
        cost_class=str(raw.get("cost_class", "UNKNOWN")),
        reversible=bool(raw.get("reversible", False)),
        semantic_readback=bool(raw.get("semantic_readback", False)),
        proof_ref=str(raw.get("proof_ref", "")),
        truth_boundary=str(raw.get("truth_boundary", "")),
    )


def _mission(raw: Mapping[str, Any]) -> MissionRequirement:
    return MissionRequirement(
        objective_id=str(raw["objective_id"]),
        capability=str(raw["capability"]),
        authority_required=_authority(raw.get("authority_required", "A0_READ")),
        provider_execution_required=bool(raw.get("provider_execution_required", False)),
        independent_verifier_required=bool(
            raw.get("independent_verifier_required", False)
        ),
        reversible_required=bool(raw.get("reversible_required", False)),
        included_cost_only=bool(raw.get("included_cost_only", True)),
        excluded_surface_classes=frozenset(
            str(v) for v in raw.get("excluded_surface_classes", ())
        ),
    )


def execute_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("contract") != ENVELOPE_CONTRACT:
        raise SovereignCoreError("unsupported or missing sovereign envelope contract")
    operation = str(payload.get("operation", "RANK_ROUTES")).upper()
    mission = _mission(payload["mission"])
    adapters = [_adapter(item) for item in payload.get("adapters", ())]
    state = dict(payload.get("state", {}))
    failed_adapter_ids = tuple(str(v) for v in payload.get("failed_adapter_ids", ()))

    projection = portable_state_projection(state=state, adapters=adapters)
    routes = rank_routes(mission, adapters)

    response: dict[str, Any] = {
        "contract": ENVELOPE_CONTRACT,
        "version": ENVELOPE_VERSION,
        "objective_id": mission.objective_id,
        "operation": operation,
        "state_fingerprint": projection["state_fingerprint"],
        "ranked_routes": [
            {
                "adapter_id": route.adapter_id,
                "surface_class": route.surface_class,
                "rank_score": route.rank_score,
                "proof_ref": route.proof_ref,
                "truth_boundary": route.truth_boundary,
            }
            for route in routes
        ],
        "selected_route": None,
        "truth_boundary": (
            "Envelope output is a deterministic route decision, not proof that a "
            "provider effect occurred. Provider execution requires action-specific "
            "semantic readback."
        ),
    }

    if operation == "RANK_ROUTES":
        if routes:
            response["selected_route"] = response["ranked_routes"][0]
    elif operation == "FAILOVER":
        selected = failover_route(mission, adapters, failed_adapter_ids)
        response["selected_route"] = {
            "adapter_id": selected.adapter_id,
            "surface_class": selected.surface_class,
            "rank_score": selected.rank_score,
            "proof_ref": selected.proof_ref,
            "truth_boundary": selected.truth_boundary,
        }
        response["failed_adapter_ids"] = sorted(failed_adapter_ids)
    else:
        raise SovereignCoreError(f"unsupported envelope operation {operation}")

    response["response_fingerprint"] = canonical_sha256(response)
    return response


def execute_json(text: str) -> str:
    payload = json.loads(text)
    if not isinstance(payload, Mapping):
        raise SovereignCoreError("envelope payload must be a JSON object")
    return json.dumps(execute_envelope(payload), sort_keys=True, separators=(",", ":"))
