from __future__ import annotations

import secrets
from typing import Any, Protocol

from .authority import FormationPermitAuthority
from .compiler import IntentCompiler
from .models import CloudEvent, ExecutionContract
from .resolver import CapabilityResolver
from .store import FabricStore
from .util import digest_json, reject_sensitive, utc_now


class Adapter(Protocol):
    provider_id: str
    effectful: bool

    def execute(
        self,
        action: str,
        payload: dict[str, Any],
        *,
        dry_run: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        ...


class DeterministicObservationAdapter:
    effectful = False

    def __init__(self, provider_id: str, observations: dict[str, Any]):
        self.provider_id = provider_id
        self._observations = observations

    def execute(
        self,
        action: str,
        payload: dict[str, Any],
        *,
        dry_run: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if action not in self._observations:
            raise KeyError("observation action unavailable")
        return {
            "provider_id": self.provider_id,
            "action": action,
            "dry_run": dry_run,
            "idempotency_key_hash": digest_json(idempotency_key),
            "semantic_result": self._observations[action],
            "external_mutation_performed": False,
            "observed_at": utc_now(),
        }


class FabricRuntime:
    def __init__(
        self,
        store: FabricStore,
        *,
        formation_authority: FormationPermitAuthority | None = None,
        executor_identity: str = "urn:cfbe:sovara:executor",
    ):
        self.store = store
        self.compiler = IntentCompiler()
        self.resolver = CapabilityResolver()
        self.formation_authority = formation_authority
        self.executor_identity = executor_identity
        self.adapters: dict[str, Adapter] = {}

    def register_adapter(self, adapter: Adapter) -> None:
        if adapter.provider_id in self.adapters:
            raise ValueError("adapter already registered")
        self.adapters[adapter.provider_id] = adapter

    def plan(self, intent: dict[str, Any], providers: list[dict[str, Any]]) -> dict[str, Any]:
        compiled = self.compiler.compile(intent)
        resolution = self.resolver.resolve(
            compiled,
            providers,
            verified_proof_stages=self.store.verified_provider_stages(
                mission_id=compiled["mission_id"],
                mission_version=compiled["mission_version"],
                action_id=compiled["proof_action_id"],
            ),
        )
        return {"compiled": compiled, "resolution": resolution}

    def build_execution_contract(
        self,
        *,
        compiled: dict[str, Any],
        resolution: dict[str, Any],
        action: str,
        payload: dict[str, Any],
    ) -> ExecutionContract:
        reject_sensitive(payload)
        winner = resolution.get("winner")
        if resolution.get("decision") != "ROUTE_SELECTED" or not winner:
            raise PermissionError("no admissible route")
        route_fingerprint = digest_json(winner)
        payload_digest = digest_json(payload)
        seed = {
            "mission_id": compiled["mission_id"],
            "mission_version": compiled["mission_version"],
            "objective": compiled["objective"],
            "capabilities": compiled["required_capabilities"],
            "constraints": compiled["constraints"],
            "stop_conditions": compiled["stop_conditions"],
            "provider_id": winner["provider_id"],
            "action": action,
            "payload_digest": payload_digest,
            "route_fingerprint": route_fingerprint,
            "executor_identity": self.executor_identity,
        }
        idempotency_key = digest_json(seed)
        return ExecutionContract.from_mapping(
            {
                "id": "XCT-" + idempotency_key[:24],
                "mission_id": compiled["mission_id"],
                "mission_version": compiled["mission_version"],
                "objective": compiled["objective"],
                "provider_id": winner["provider_id"],
                "action": action,
                "capabilities": compiled["required_capabilities"],
                "authority_class": compiled["constraints"]["authority_class"],
                "effectful": winner["effectful"],
                "dry_run": compiled["constraints"]["dry_run"],
                "idempotency_key": idempotency_key,
                "payload_digest": payload_digest,
                "route_fingerprint": route_fingerprint,
                "executor_identity": self.executor_identity,
                "maximum_incremental_cost": compiled["constraints"][
                    "maximum_incremental_cost"
                ],
                "required_proof_stage": compiled["constraints"]["minimum_proof_stage"],
                "stop_conditions": compiled["stop_conditions"],
                "issued_at": utc_now(),
            }
        )

    def execute(
        self,
        *,
        contract: ExecutionContract,
        payload: dict[str, Any],
        formation_permit: str,
    ) -> dict[str, Any]:
        reject_sensitive(payload)
        if contract.payload_digest != digest_json(payload):
            raise PermissionError("execution payload does not match contract")
        if contract.executor_identity != self.executor_identity:
            raise PermissionError("execution contract belongs to another executor")
        adapter = self.adapters.get(contract.provider_id)
        if not adapter:
            raise KeyError("adapter not registered")
        if adapter.provider_id != contract.provider_id:
            raise PermissionError("adapter identity does not match governed route")
        if bool(adapter.effectful) != contract.effectful:
            raise PermissionError("adapter effectfulness does not match governed route")
        if contract.effectful and contract.dry_run:
            raise PermissionError("effectful contract cannot execute as dry run")

        existing = self.store.execution_result(contract.idempotency_key)
        if existing:
            if existing["contract_hash"] != contract.fingerprint:
                raise ValueError("idempotency key is bound to a different execution contract")
            if existing["state"] == "COMMITTED":
                return {**existing["result"], "idempotent_replay": True}
            raise RuntimeError("prior execution outcome is pending or ambiguous; semantic readback required")

        if self.formation_authority is None:
            raise PermissionError("trusted Formation authority is not configured")
        self.formation_authority.validate(formation_permit, contract)
        request = {
            "contract_hash": contract.fingerprint,
            "payload_digest": contract.payload_digest,
        }
        request_hash = digest_json(request)
        fence_token = secrets.token_hex(16)
        reservation = self.store.authorize_and_reserve_execution(
            token_hash=digest_json(formation_permit),
            key=contract.idempotency_key,
            contract_hash=contract.fingerprint,
            mission_id=contract.mission_id,
            mission_version=contract.mission_version,
            authority_class=contract.authority_class,
            maximum_cost=contract.maximum_incremental_cost,
            request_hash=request_hash,
            provider_id=contract.provider_id,
            action_id=contract.id,
            fence_token=fence_token,
            effectful=contract.effectful,
        )
        if reservation != "RESERVED":
            existing = self.store.execution_result(contract.idempotency_key)
            if existing and existing["state"] == "COMMITTED":
                return {**existing["result"], "idempotent_replay": True}
            raise RuntimeError("execution already pending or ambiguous")
        try:
            result = adapter.execute(
                contract.action,
                payload,
                dry_run=contract.dry_run,
                idempotency_key=contract.idempotency_key,
            )
            reject_sensitive(result, "adapter_result")
            event = CloudEvent(
                id="EVT-" + contract.idempotency_key[:24],
                source="urn:cfbe:acf:runtime",
                type="org.cfbe.acf.execution.v1",
                subject=contract.provider_id,
                data={
                    "contract_hash": contract.fingerprint,
                    "request_hash": request_hash,
                    "result_hash": digest_json(result),
                },
            )
            self.store.complete_execution(
                key=contract.idempotency_key,
                fence_token=fence_token,
                result=result,
                event=event,
            )
        except Exception as exc:
            self.store.mark_execution_ambiguous(
                key=contract.idempotency_key,
                fence_token=fence_token,
                detail=f"{type(exc).__name__}: semantic readback required",
            )
            raise
        return {**result, "idempotent_replay": False}

    def health(self) -> dict[str, Any]:
        integrity = self.store.integrity_check()
        blockers = self.store.active_blockers()
        healthy = (
            integrity["state"] == "OK"
            and integrity["integrity_anchor"] == "VERIFIED"
            and not blockers
        )
        state = (
            "DEGRADED_LOCAL"
            if not healthy
            else "READY_LOCAL"
            if self.formation_authority is not None
            else "READY_LOCAL_NO_EXECUTION"
        )
        return {
            "schema": "CFBE-ACF-HEALTH-V1",
            "state": state,
            "runtime_state": "ON_DEMAND_GOVERNED",
            "formation_authority_configured": self.formation_authority is not None,
            "registered_adapters": sorted(self.adapters),
            "store": integrity,
            "active_blockers": len(blockers),
            "completion_claim_allowed": healthy,
            "provider_runtime_proven": False,
            "durable_autonomy_proven": False,
        }
