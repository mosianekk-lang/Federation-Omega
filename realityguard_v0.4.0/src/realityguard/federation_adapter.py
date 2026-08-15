"""One source adapter for every system in a supplied Federation contract."""

from __future__ import annotations

from typing import Any

from .schema import InputError
from .upgrade import GovernedUpgradeEngine


class FederationUpgradeAdapter:
    """Bind registered system identity to the RealityGuard upgrade decision.

    Calling this adapter proves only that the source route was invoked. It does
    not prove that the named target system is deployed, bound or running.
    """

    schema_version = "federation.realityguard-auto-upgrade-runtime.v1"

    def evaluate(
        self,
        payload: dict[str, Any],
        capability_manifest: dict[str, Any],
        adapter_contract: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(adapter_contract, dict):
            raise InputError("adapter contract must be an object")
        if adapter_contract.get("contract") != GovernedUpgradeEngine.schema_version:
            raise InputError("adapter contract must bind realityguard.upgrade.v1")
        if adapter_contract.get("mode") != GovernedUpgradeEngine.invocation_mode:
            raise InputError("adapter contract invocation mode is invalid")
        if adapter_contract.get("background_daemon") is not False:
            raise InputError("adapter contract cannot enable a background daemon")
        if adapter_contract.get("authority_expansion") is not False:
            raise InputError("adapter contract cannot expand authority")
        if adapter_contract.get("formation_single_use_permit_required_before_execution") is not True:
            raise InputError("adapter contract must require a Formation permit before execution")

        systems = adapter_contract.get("systems")
        if not isinstance(systems, list) or not systems:
            raise InputError("adapter contract systems must be a non-empty array")
        entries: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(systems):
            if not isinstance(item, dict) or not isinstance(item.get("system_id"), str) or not item["system_id"].strip():
                raise InputError(f"adapter contract systems[{index}] is invalid")
            system_id = item["system_id"].strip()
            if system_id in entries:
                raise InputError(f"duplicate adapter system_id: {system_id}")
            entries[system_id] = item

        cycle = payload.get("cycle") if isinstance(payload, dict) else None
        if not isinstance(cycle, dict):
            raise InputError("cycle must be an object")
        system_id = str(cycle.get("system_id", "")).strip()
        if system_id not in entries:
            raise InputError(f"system_id is not registered in the Federation adapter contract: {system_id}")

        decision = GovernedUpgradeEngine().evaluate(payload, capability_manifest).to_dict()
        entry = entries[system_id]
        live_proof = all((
            entry.get("integration_state") == "LIVE_BOUND_VERIFIED",
            entry.get("current") is True,
            isinstance(entry.get("runtime_binding_evidence"), list),
            bool(entry.get("runtime_binding_evidence")),
        ))
        decision["federation_adapter"] = {
            "schema_version": self.schema_version,
            "system_id": system_id,
            "source_adapter_supported": True,
            "adapter_invocation_observed": True,
            "integration_state": str(entry.get("integration_state", "ADAPTER_REQUIRED")),
            "target_runtime_binding_proven": live_proof,
            "all_registered_systems_use_one_contract": True,
            "manual_user_tasks": [],
            "owner_action_required": False,
        }
        return decision
