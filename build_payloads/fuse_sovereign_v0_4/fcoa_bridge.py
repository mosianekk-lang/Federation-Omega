from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Mapping

from .engine import SovereignEngine
from .llm_gateway import LLMGateway, LLMRequest, LLMResponse
from .models import AuthorityEnvelope, EffectClass, TaskEnvelope
from .policy import ReleaseContext
from .update import LLMUpdateBridge


FCOA_AGENT_ID = "FCOA-OMEGA"
FCOA_WORK_PLANE = "WP-FCOA-BOOTSTRAP-001"
FCOA_PASSPORT = "ECP-FCOA-OMEGA-V1-001"


class FCOABridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class FCOAAccessProfile:
    agent_id: str = FCOA_AGENT_ID
    work_plane_id: str = FCOA_WORK_PLANE
    passport_id: str = FCOA_PASSPORT
    discovery_allowed: bool = True
    default_effect_ceiling: EffectClass = EffectClass.READ_ONLY
    allow_llm: bool = True
    allow_fuse_updates: bool = True
    authority_inheritance: bool = False


@dataclass(frozen=True)
class FCOABootstrapSnapshot:
    agent_id: str
    work_plane_id: str
    passport_id: str
    fuse_update: Mapping[str, object]
    llm_providers: tuple[str, ...]
    capabilities: tuple[str, ...]
    executors: tuple[str, ...]
    authority_boundary: str = "MISSION_SCOPED_NO_INHERITANCE"

    @property
    def digest(self) -> str:
        body = asdict(self)
        body["fuse_update"] = dict(self.fuse_update)
        return sha256(json.dumps(body, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


class FCOABridge:
    """Binds the existing FCOA-Ω agent to FUSE currentness, LLM cognition and governed execution."""

    def __init__(
        self,
        *,
        engine: SovereignEngine,
        llm_gateway: LLMGateway,
        update_bridge: LLMUpdateBridge,
        profile: FCOAAccessProfile | None = None,
    ):
        self.engine = engine
        self.llm_gateway = llm_gateway
        self.update_bridge = update_bridge
        self.profile = profile or FCOAAccessProfile()
        self._last_bootstrap: FCOABootstrapSnapshot | None = None

    def capability_snapshot(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        executors = tuple(sorted(e.executor_id for e in self.engine.router.executors if e.healthy and e.current))
        capabilities = tuple(sorted({c for e in self.engine.router.executors if e.healthy and e.current for c in e.capabilities}))
        return capabilities, executors

    def bootstrap(self) -> FCOABootstrapSnapshot:
        update = self.update_bridge.fetch_context() if self.profile.allow_fuse_updates else {
            "schema": "FUSE_LLM_UPDATE_SNAPSHOT_V1",
            "freshness": "DISABLED",
            "authority_boundary": "DATA_ONLY_NO_EFFECT_AUTHORITY",
        }
        capabilities, executors = self.capability_snapshot()
        snapshot = FCOABootstrapSnapshot(
            agent_id=self.profile.agent_id,
            work_plane_id=self.profile.work_plane_id,
            passport_id=self.profile.passport_id,
            fuse_update=dict(update),
            llm_providers=self.llm_gateway.providers(),
            capabilities=capabilities,
            executors=executors,
        )
        self._last_bootstrap = snapshot
        return snapshot

    def think(
        self,
        *,
        request_id: str,
        mission_id: str,
        prompt: str,
        model: str = "",
        preferred_provider: str | None = None,
        extra_context: Mapping[str, object] | None = None,
    ) -> LLMResponse:
        if not self.profile.allow_llm:
            raise FCOABridgeError("FCOA_LLM_ACCESS_DISABLED")
        snapshot = self.bootstrap()
        system_context = {
            "agent": self.profile.agent_id,
            "role": "FUSE in-house Creative Operator Agent",
            "mission_id": mission_id,
            "work_plane": self.profile.work_plane_id,
            "passport": self.profile.passport_id,
            "authority_boundary": snapshot.authority_boundary,
            "fuse_update": snapshot.fuse_update,
            "available_capabilities": snapshot.capabilities,
            "available_executors": snapshot.executors,
            "rule": "LLM output is advisory cognition only. It never grants effect, credential, source, IAM, publication, or lease authority.",
        }
        if extra_context:
            system_context["mission_context"] = dict(extra_context)
        request = LLMRequest(
            request_id=request_id,
            model=model,
            messages=(
                {"role": "system", "content": json.dumps(system_context, sort_keys=True, default=str)},
                {"role": "user", "content": prompt},
            ),
            metadata={"agent_id": self.profile.agent_id, "mission_id": mission_id, "bootstrap_digest": snapshot.digest},
        )
        return self.llm_gateway.infer(request, preferred_provider=preferred_provider)

    def execute_task(
        self,
        *,
        task: TaskEnvelope,
        authority: AuthorityEnvelope,
        release_context: ReleaseContext | None = None,
    ) -> dict:
        if authority.principal not in {self.profile.agent_id, "FUSE/FDOF", "FUSE-ONE"}:
            raise FCOABridgeError("FCOA_AUTHORITY_PRINCIPAL_INVALID")
        if task.effect not in authority.allowed_effects:
            raise FCOABridgeError("FCOA_EFFECT_NOT_AUTHORIZED")
        return self.engine.execute(task, authority, release_context)

    def context_for_model(self) -> dict:
        snap = self._last_bootstrap or self.bootstrap()
        return {
            "schema": "FCOA_FUSE_CONTEXT_V1",
            "agent_id": snap.agent_id,
            "work_plane_id": snap.work_plane_id,
            "passport_id": snap.passport_id,
            "bootstrap_digest": snap.digest,
            "fuse_update": dict(snap.fuse_update),
            "llm_providers": list(snap.llm_providers),
            "capabilities": list(snap.capabilities),
            "executors": list(snap.executors),
            "authority_boundary": snap.authority_boundary,
        }
