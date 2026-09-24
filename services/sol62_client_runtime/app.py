from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Annotated, Any, Mapping

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.fuse_mobile_gateway.bindings import runtime_from_environment as gateway_from_environment
from services.fuse_mobile_gateway.runtime import GatewayRuntime, RuntimeBindingError, bearer_token
from services.sol62_client_runtime import VERSION
from services.sol62_client_runtime.gateway_adapter import GatewayChatAdapter
from services.sol62_client_runtime.autonomous_harvester import FuseAutonomousHarvester
from services.sol62_client_runtime.capability_registry import compile_registry
from services.sol62_client_runtime.runtime_upgrade_genome import UPGRADE_GENOME, genome_summary
from services.sol62_client_runtime.browser_carrier_resilience import (
    BrowserCarrierSupervisor,
    CarrierRegistration,
    SCHEMA as BROWSER_CARRIER_SCHEMA,
)
from sol_61_runtime.sol_62 import (
    GatewayPolicy,
    MissionSpec,
    Sol62Runtime,
    TransitionSpec,
    WorkloadIdentityPolicy,
)
from sol_61_runtime.sol_62_complete_client_runtime import (
    RouteCandidate,
    Sol62CompleteClientRuntime,
    TransitionBinding,
)
from sol_61_runtime.sol_62_genesis_client_bridge import Sol62GenesisWakeBridge
from sol_61_runtime.sol_62_sovereign_plane_binding import Sol62SovereignPlaneBinding


STATIC_ROOT = Path(__file__).with_name("static")


class ChatBody(BaseModel):
    intent: str = Field(min_length=1, max_length=100_000)
    mode: str = "AUTO"
    requested_models: list[str] = Field(default_factory=list, max_length=16)
    requested_sources: list[str] = Field(default_factory=list, max_length=32)
    requested_agents: list[str] = Field(default_factory=list, max_length=16)


class MissionBody(BaseModel):
    mission_id: str | None = None
    objective: str = Field(min_length=1, max_length=20_000)
    initial_state: dict[str, Any] = Field(default_factory=lambda: {"state": "OPEN"})
    target_state: dict[str, Any] = Field(default_factory=lambda: {"state": "DONE"})
    success_proofs: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class TransitionBody(BaseModel):
    transition_id: str | None = None
    operation: str = Field(min_length=1, max_length=128)
    target: str = Field(min_length=1, max_length=512)
    from_state: dict[str, Any]
    to_state: dict[str, Any]
    dependencies: list[str] = Field(default_factory=list)
    required_proofs: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    conflict_domains: list[str] = Field(default_factory=list)
    priority: int = 50
    risk_class: str = "LOW"
    consequential: bool = False
    simulation_required: bool = False
    source_version: str = "UNPINNED"
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_readback: dict[str, Any] = Field(default_factory=lambda: {"status": "COMPLETE"})
    semantics: str = "IDEMPOTENT"
    rollback_required: bool = False
    mode: str = "AUTO"
    requested_models: list[str] = Field(default_factory=list)
    requested_sources: list[str] = Field(default_factory=list)
    requested_agents: list[str] = Field(default_factory=list)
    effect_class: str = "READ_ONLY"
    proof_id: str = ""


class WakeBody(BaseModel):
    inline: bool = False


class CarrierRegisterBody(BaseModel):
    carrier_id: str = Field(min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=256)
    client_kind: str = Field(default="CHATGPT_BROWSER", min_length=1, max_length=128)
    route_id: str = Field(default="CHATGPT_BROWSER", min_length=1, max_length=128)
    priority: int = Field(default=50, ge=0, le=1000)
    conversation_ref_hash: str = Field(default="", max_length=256)
    capabilities: list[str] = Field(default_factory=list, max_length=64)
    failure_domain: str = Field(default="CHATGPT_BROWSER", min_length=1, max_length=128)


class CarrierHeartbeatBody(BaseModel):
    observed_state: str = Field(default="HEALTHY", min_length=1, max_length=32)
    conversation_ref_hash: str = Field(default="", max_length=256)


class CarrierFailureBody(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    event_id: str = Field(default="", max_length=256)


class CarrierAttachBody(BaseModel):
    carrier_id: str = Field(min_length=1, max_length=256)


class CarrierFailoverBody(BaseModel):
    failed_carrier_id: str = Field(min_length=1, max_length=256)
    failure_code: str = Field(min_length=1, max_length=128)
    event_id: str = Field(default="", max_length=256)


class DurabilityPolicyBody(BaseModel):
    mode: str = Field(default="EFFECT_BOUNDARY", min_length=1, max_length=64)
    history_event_limit: int = Field(default=2048, ge=16, le=10000)


class DurabilityInterruptBody(BaseModel):
    interruption_id: str | None = Field(default=None, max_length=256)
    kind: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=2048)
    transition_id: str = Field(default="", max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)


class DurabilityResolutionBody(BaseModel):
    decision: str = Field(min_length=1, max_length=32)
    proof_refs: list[str] = Field(default_factory=list, max_length=64)


class WorkerIdentityProvider:
    """Server-side workload-identity binding. No browser/client credentials are accepted."""

    def __init__(self) -> None:
        self.issuer = os.getenv("SOL62_WORKER_ISSUER", "").strip()
        self.audience = os.getenv("SOL62_WORKER_AUDIENCE", "").strip()
        self.subject = os.getenv("SOL62_WORKER_SUBJECT", "").strip()
        self.credential_type = os.getenv("SOL62_WORKER_CREDENTIAL_TYPE", "oidc").strip()

    @property
    def ready(self) -> bool:
        return bool(self.issuer and self.audience and self.subject and self.credential_type == "oidc")

    def claims(self, now_epoch: int) -> dict[str, Any]:
        if not self.ready:
            raise RuntimeError("SOL62_WORKER_IDENTITY_UNBOUND")
        return {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": self.subject,
            "iat": now_epoch - 5,
            "exp": now_epoch + 300,
            "credential_type": self.credential_type,
        }


def _sol_runtime() -> Sol62Runtime:
    root = Path(os.getenv("SOL62_CLIENT_ROOT", "./sol62-client-state"))
    runtime_id = os.getenv("SOL62_RUNTIME_ID", "sol-6.2")
    gateway_id = os.getenv("SOL62_GATEWAY_ID", "sol-gateway")
    issuer = os.getenv("SOL62_WORKER_ISSUER", "https://token.actions.githubusercontent.com")
    audience = os.getenv("SOL62_WORKER_AUDIENCE", "sol-runtime")
    subject_prefix = os.getenv(
        "SOL62_WORKER_SUBJECT_PREFIX",
        "repo:mosianekk-lang/Federation-Omega:",
    )
    return Sol62Runtime(
        root,
        gateway_policy=GatewayPolicy(gateway_id, runtime_id),
        identity_policy=WorkloadIdentityPolicy(
            allowed_issuers={issuer},
            audience=audience,
            subject_prefix=subject_prefix,
            max_ttl_seconds=600,
        ),
    )


class ServiceContext:
    def __init__(
        self,
        *,
        gateway: GatewayRuntime | None = None,
        sol: Sol62Runtime | None = None,
    ) -> None:
        self.gateway = gateway or gateway_from_environment()
        self.sol = sol or _sol_runtime()
        self.sovereign_plane = Sol62SovereignPlaneBinding()
        self.client = Sol62CompleteClientRuntime(self.sol, sovereign_plane=self.sovereign_plane)
        self.browser_carriers = BrowserCarrierSupervisor(self.client)
        self.worker_identity = WorkerIdentityProvider()
        self.genesis = Sol62GenesisWakeBridge(
            os.getenv("FUSE_GENESIS_HOST_ROOT", "./fuse-host-state")
        )
        self.source_frontier = os.getenv("SOL62_SOURCE_FRONTIER", "CURRENT_MAIN_REQUIRED")
        executor_route_id = self.gateway.execution_route_id or "FUSE-AUTO"
        executor_provider = self.gateway.execution_provider or "FUSE_GATEWAY"
        self.client.register_route(
            RouteCandidate(
                executor_route_id,
                executor_provider,
                operations=("*",),
                current=True,
                callable=self.gateway.execution_ready,
                authorized=True,
                privacy_ok=True,
                priority=100,
                failure_domain=executor_provider,
            )
        )

    def close(self) -> None:
        self.sol.close()


def create_app(context: ServiceContext | None = None) -> FastAPI:
    ctx = context or ServiceContext()
    app = FastAPI(title="SOL 6.2 FUSE Client Runtime", version=VERSION, docs_url=None, redoc_url=None)
    app.state.sol62_context = ctx
    app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")

    async def identity(
        authorization: str | None,
        x_fuse_authorization: str | None,
    ):
        try:
            token = bearer_token(x_fuse_authorization or authorization)
            return await ctx.gateway.verify_session(token)
        except RuntimeBindingError as error:
            raise HTTPException(status_code=401, detail={"status": "HELD", "reason": error.code}) from error

    @app.get("/")
    async def index():
        return FileResponse(STATIC_ROOT / "index.html")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "schema": "SOL62_COMPLETE_FUSE_CLIENT_RUNTIME_V1",
            "version": VERSION,
            "sol_integrity": ctx.sol.verify_integrity(),
            "fuse_session_ready": ctx.gateway.session_ready,
            "fuse_execution_ready": ctx.gateway.execution_ready,
            "fuse_executor_route_id": ctx.gateway.execution_route_id,
            "fuse_executor_provider": ctx.gateway.execution_provider,
            "worker_identity_ready": ctx.worker_identity.ready,
            "sovereign_plane": ctx.sovereign_plane.status(),
            "sol_role": "TRANSACTIONAL_MISSION_TRUTH_AND_VERIFIED_TRANSITION_KERNEL",
            "genesis_handoff": "BOUND",
            "hypercube_codeforge_harvest": "BOUND",
            "autobuild_handoff": "BOUND",
            "chatgpt_ui_required": False,
            "provider_specific_limits_are_mission_terminal": False,
            "capability_registry": compile_registry(gateway_execution_ready=ctx.gateway.execution_ready)["counts"],
            "runtime_upgrade_genome": genome_summary(),
            "browser_carrier_resilience": {
                "schema": BROWSER_CARRIER_SCHEMA,
                "bound": True,
                "chat_conversation_is_mission_authority": False,
                "carrier_loss_is_mission_terminal": False,
                "effect_replay_on_failover": False,
            },
        }

    @app.get("/v1/capabilities")
    async def capabilities(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        registry = compile_registry(gateway_execution_ready=ctx.gateway.execution_ready)
        registry["owner_subject"] = owner.subject
        registry["source_frontier"] = ctx.source_frontier
        return registry

    @app.get("/v1/runtime-upgrades")
    async def runtime_upgrades(
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        return {
            "owner_subject": owner.subject,
            "summary": genome_summary(),
            "genes": [
                {
                    "gene_id": gene.gene_id,
                    "category": gene.category,
                    "mechanism": gene.mechanism,
                    "tags": list(gene.tags),
                    "provenance": gene.provenance,
                    "maturity": gene.maturity,
                }
                for gene in UPGRADE_GENOME
            ],
        }

    @app.post("/v1/carriers/register")
    async def register_carrier(
        body: CarrierRegisterBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        return ctx.browser_carriers.register(
            CarrierRegistration(
                carrier_id=body.carrier_id,
                owner_subject=owner.subject,
                session_id=body.session_id,
                client_kind=body.client_kind,
                route_id=body.route_id,
                priority=body.priority,
                conversation_ref_hash=body.conversation_ref_hash,
                capabilities=tuple(body.capabilities),
                failure_domain=body.failure_domain,
            )
        )

    @app.post("/v1/carriers/{carrier_id}/heartbeat")
    async def carrier_heartbeat(
        carrier_id: str,
        body: CarrierHeartbeatBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        row = ctx.client._get("sol62.browser.carrier", carrier_id)
        if not row or row["value"].get("owner_subject") != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "CARRIER_NOT_FOUND"})
        return ctx.browser_carriers.heartbeat(
            carrier_id,
            observed_state=body.observed_state,
            conversation_ref_hash=body.conversation_ref_hash,
        )

    @app.post("/v1/carriers/{carrier_id}/failure")
    async def carrier_failure(
        carrier_id: str,
        body: CarrierFailureBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        row = ctx.client._get("sol62.browser.carrier", carrier_id)
        if not row or row["value"].get("owner_subject") != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "CARRIER_NOT_FOUND"})
        return ctx.browser_carriers.report_failure(
            carrier_id,
            code=body.code,
            event_id=body.event_id,
        )

    @app.post("/v1/missions/{mission_id}/carrier/attach")
    async def attach_mission_carrier(
        mission_id: str,
        body: CarrierAttachBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"].get("owner_subject") != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        return ctx.browser_carriers.attach_mission(
            mission_id,
            owner_subject=owner.subject,
            carrier_id=body.carrier_id,
        )

    @app.post("/v1/missions/{mission_id}/carrier/failover")
    async def failover_mission_carrier(
        mission_id: str,
        body: CarrierFailoverBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"].get("owner_subject") != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        return ctx.browser_carriers.failover(
            mission_id,
            owner_subject=owner.subject,
            failed_carrier_id=body.failed_carrier_id,
            failure_code=body.failure_code,
            event_id=body.event_id,
        )

    @app.get("/v1/missions/{mission_id}/carrier/hydration")
    async def mission_carrier_hydration(
        mission_id: str,
        carrier_id: str,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"].get("owner_subject") != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        return ctx.browser_carriers.hydration_packet(mission_id, carrier_id=carrier_id)

    @app.post("/v1/chat")
    async def chat(
        body: ChatBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        from federation.mobile_gateway.fuse_mobile_v1 import EffectClass, MobileRequest, Mode
        try:
            mode = Mode(body.mode)
        except ValueError:
            mode = Mode.AUTO
        request = MobileRequest(
            intent=body.intent,
            mode=mode,
            requested_models=tuple(body.requested_models),
            requested_sources=tuple(body.requested_sources),
            requested_agents=tuple(body.requested_agents),
            effect_class=EffectClass.READ_ONLY,
            verification="HIGH",
        )
        try:
            result = await ctx.gateway.execute(owner, request)
        except RuntimeBindingError as error:
            raise HTTPException(status_code=503, detail={"status": "HELD", "reason": error.code}) from error
        ctx.sol.control.append_event(
            result.trace_id,
            "SOL62_CLIENT_CHAT_READBACK",
            {
                "owner_subject": owner.subject,
                "status": result.status,
                "provider": result.provider,
                "model": result.model,
                "source_refs": list(result.source_refs),
            },
        )
        return {
            "text": result.text,
            "trace_id": result.trace_id,
            "status": result.status,
            "provider": result.provider,
            "model": result.model,
            "source_refs": list(result.source_refs),
        }

    @app.post("/v1/missions")
    async def create_mission(
        body: MissionBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        mission_id = body.mission_id or ("sol62-" + secrets.token_hex(12))
        ctx.sol.register_mission(
            MissionSpec(
                mission_id,
                body.objective,
                dict(body.initial_state),
                dict(body.target_state),
                success_proofs=tuple(body.success_proofs),
                constraints=tuple(body.constraints),
            )
        )
        ctx.client.bind_mission(mission_id, owner_subject=owner.subject)
        return ctx.client.mission_status(mission_id)

    @app.post("/v1/missions/{mission_id}/transitions")
    async def create_transition(
        mission_id: str,
        body: TransitionBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        transition_id = body.transition_id or (mission_id + "-t-" + secrets.token_hex(6))
        ctx.sol.register_transition(
            TransitionSpec(
                transition_id,
                mission_id,
                body.operation,
                body.target,
                dict(body.from_state),
                dict(body.to_state),
                dependencies=tuple(body.dependencies),
                required_proofs=tuple(body.required_proofs),
                constraints=tuple(body.constraints),
                conflict_domains=tuple(body.conflict_domains),
                priority=body.priority,
                risk_class=body.risk_class,
                consequential=body.consequential,
                simulation_required=body.simulation_required,
                source_version=body.source_version,
            )
        )
        ctx.client.bind_transition(
            TransitionBinding(
                transition_id,
                dict(body.payload),
                dict(body.expected_readback),
                semantics=body.semantics,
                rollback_required=body.rollback_required,
                mode=body.mode,
                requested_models=tuple(body.requested_models),
                requested_sources=tuple(body.requested_sources),
                requested_agents=tuple(body.requested_agents),
                effect_class=body.effect_class,
                proof_id=body.proof_id,
            )
        )
        return {"status": "BOUND", "mission_id": mission_id, "transition_id": transition_id}

    @app.get("/v1/missions/{mission_id}")
    async def mission_status(
        mission_id: str,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        return ctx.client.mission_status(mission_id)

    @app.get("/v1/missions/{mission_id}/durability")
    async def mission_durability(
        mission_id: str,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        return ctx.client.durability_status(mission_id)

    @app.put("/v1/missions/{mission_id}/durability/policy")
    async def set_mission_durability_policy(
        mission_id: str,
        body: DurabilityPolicyBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        try:
            stored = ctx.client.set_durability_policy(
                mission_id,
                mode=body.mode,
                history_event_limit=body.history_event_limit,
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail={"status": "HELD", "reason": str(error)}) from error
        return {
            "status": "BOUND",
            "mission_id": mission_id,
            "policy": stored["value"],
            "truth_boundary": "DURABILITY_POLICY_NE_EFFECT_AUTHORITY",
        }

    @app.post("/v1/missions/{mission_id}/interruptions")
    async def create_mission_interruption(
        mission_id: str,
        body: DurabilityInterruptBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        interruption_id = body.interruption_id or ("int-" + secrets.token_hex(12))
        try:
            stored = ctx.client.interrupt_mission(
                mission_id,
                interruption_id=interruption_id,
                kind=body.kind,
                reason=body.reason,
                transition_id=body.transition_id,
                payload=body.payload,
                now_epoch=int(time.time()),
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail={"status": "HELD", "reason": str(error)}) from error
        return {
            "status": "INTERRUPTED",
            "mission_id": mission_id,
            "interruption": stored["value"],
            "effect_authorized": False,
        }

    @app.post("/v1/missions/{mission_id}/interruptions/{interruption_id}/resolve")
    async def resolve_mission_interruption(
        mission_id: str,
        interruption_id: str,
        body: DurabilityResolutionBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        try:
            stored = ctx.client.resolve_interruption(
                mission_id,
                interruption_id=interruption_id,
                decision=body.decision,
                actor=owner.subject,
                proof_refs=tuple(body.proof_refs),
                now_epoch=int(time.time()),
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail={"status": "HELD", "reason": str(error)}) from error
        return {
            "status": "RESOLVED",
            "mission_id": mission_id,
            "interruption": stored["value"],
            "effect_authorized": False,
            "truth_boundary": "INTERRUPTION_DECISION_NE_EFFECT_AUTHORITY",
        }

    @app.get("/v1/missions/{mission_id}/events")
    async def mission_events(
        mission_id: str,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})
        rows = ctx.sol.control.db.execute(
            "SELECT seq,event_id,aggregate,kind,payload_json,event_hash,created_at FROM events "
            "WHERE aggregate=? OR aggregate IN (SELECT item_key FROM state WHERE namespace='sol62.transition' AND json_extract(value_json,'$.mission_id')=?) "
            "ORDER BY seq DESC LIMIT 200",
            (mission_id, mission_id),
        ).fetchall()
        import json
        return {
            "mission_id": mission_id,
            "events": [
                {
                    "seq": int(row["seq"]),
                    "event_id": row["event_id"],
                    "aggregate": row["aggregate"],
                    "kind": row["kind"],
                    "payload": json.loads(row["payload_json"]),
                    "event_hash": row["event_hash"],
                    "created_at": row["created_at"],
                }
                for row in reversed(rows)
            ],
        }

    @app.post("/v1/missions/{mission_id}/wake")
    async def wake_mission(
        mission_id: str,
        body: WakeBody,
        authorization: Annotated[str | None, Header()] = None,
        x_fuse_authorization: Annotated[str | None, Header(alias="X-Fuse-Authorization")] = None,
    ) -> dict[str, Any]:
        owner = await identity(authorization, x_fuse_authorization)
        client = ctx.client._get("sol62.client.mission", mission_id)
        if not client or client["value"]["owner_subject"] != owner.subject:
            raise HTTPException(status_code=404, detail={"status": "HELD", "reason": "MISSION_NOT_FOUND"})

        packet = ctx.client.resume_packet(mission_id, reason="OWNER_OR_RUNTIME_WAKE")
        if not body.inline or not ctx.worker_identity.ready:
            receipt = ctx.genesis.enqueue(packet, now_epoch=time.time())
            return {
                "status": "DURABLY_QUEUED",
                "mission_id": mission_id,
                "receipt": receipt,
                "truth_boundary": "QUEUED_NE_EXECUTED_NE_VERIFIED",
            }

        now = int(time.time())
        adapter = GatewayChatAdapter(ctx.gateway, owner)
        harvester = FuseAutonomousHarvester(source_frontier=ctx.source_frontier)
        result = await ctx.client.wake_until_terminal(
            mission_id,
            adapter=adapter,
            gateway_request={
                "runtime_id": os.getenv("SOL62_RUNTIME_ID", "sol-6.2"),
                "via_gateway": os.getenv("SOL62_GATEWAY_ID", "sol-gateway"),
                "authenticated_principal": "spiffe://sol62-client-runtime/worker",
                "policy_version": "6.2",
            },
            identity_claims=ctx.worker_identity.claims(now),
            worker="sol62-client-runtime",
            now_epoch=now,
            harvester=harvester,
        )
        if result.get("build_required") and result.get("build_packet"):
            build_packet = dict(result["build_packet"])
            build_packet["resume_packet"] = result.get("resume_packet")
            result["build_handoff"] = ctx.genesis.enqueue_build(build_packet, now_epoch=time.time())
        elif result.get("state") != "VERIFIED_REALITY" and result.get("resume_packet"):
            result["durable_handoff"] = ctx.genesis.enqueue(result["resume_packet"], now_epoch=time.time())
        return result

    return app


app = create_app()
