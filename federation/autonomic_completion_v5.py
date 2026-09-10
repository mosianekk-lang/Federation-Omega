"""FUSE Autonomic Completion Kernel v5.

This module makes recurrence explicit.  It can continue multiple internal cycles
in one process and can queue re-entry when a persistent runner is available.
It never claims a future invocation happened merely because a prompt requested it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor

from .federation_learning_v1 import FederationLearningLedger, LearningEvent
from .prompt_scientist_v2 import PromptGenome, PromptRunMetrics, PromptScientistV2
from .run_store_v1 import Checkpoint, RunStore
from .commercial_maturity_v1 import CommercialMaturityController, DEFAULT_STAGES


class RuntimeMode(StrEnum):
    CURRENT_RUN="CURRENT_RUN"; PERSISTENT_RUNNER="PERSISTENT_RUNNER"; NO_PERSISTENT_RUNNER="NO_PERSISTENT_RUNNER"
class OutputClass(StrEnum):
    PROGRESS_UPDATE="PROGRESS_UPDATE"; OWNER_DECISION="OWNER_DECISION"; TERMINAL_REPORT="TERMINAL_REPORT"; RESUME_CAPSULE="RESUME_CAPSULE"
class TerminalState(StrEnum):
    COMPLETE_VERIFIED="COMPLETE_VERIFIED"; PRODUCTION_VERIFIED="PRODUCTION_VERIFIED"; COMMERCIAL_READY_VERIFIED="COMMERCIAL_READY_VERIFIED"; OBJECTIVE_EXHAUSTED="OBJECTIVE_EXHAUSTED"; IRREDUCIBLE_OWNER_DECISION="IRREDUCIBLE_OWNER_DECISION"; IRREDUCIBLE_EXTERNAL_BOUNDARY="IRREDUCIBLE_EXTERNAL_BOUNDARY"; SAFETY_OR_AUTHORITY_BOUNDARY="SAFETY_OR_AUTHORITY_BOUNDARY"


COMMERCIAL_LADDER=("DESIGNED","SOURCE_COMPLETE","LOCAL_TESTED","INTEGRATION_TESTED","SIMULATION_VERIFIED","SECURITY_QUALIFIED","PERFORMANCE_QUALIFIED","PROVIDER_SHADOW","CANARY","PROVIDER_LIVE","RELIABILITY_PROVEN","RECOVERY_PROVEN","OBSERVABILITY_READY","COST_QUALIFIED","SUPPLY_CHAIN_QUALIFIED","DOCUMENTED","OPERATIONS_READY","RELEASE_CANDIDATE","PRODUCTION_VERIFIED","COMMERCIAL_READY_VERIFIED","VALUE_PROVEN")

# V11 broadens concurrency only for packet classes that remain bounded,
# reversible/read-only, and collision-key isolated.  Shared/canonical/provider
# mutation and consequential effects remain serialized and authority-gated.
PARALLEL_SAFE_EFFECT_CLASSES=frozenset({
    "READ_ONLY", "LOCAL_REVERSIBLE", "BUILD_TEST", "CI_VALIDATION", "PROVIDER_READ"
})
OWNER_EFFECT_CLASSES=frozenset({
    "PROVIDER_MUTATION", "EXTERNAL_EFFECT", "IAM_SECURITY_MUTATION", "PRODUCTION_TRAFFIC", "SPEND"
})


@dataclass(frozen=True, slots=True)
class WorkPacket:
    packet_id: str
    dependencies: tuple[str,...] = ()
    collision_keys: tuple[str,...] = ()
    effect_class: str = "READ_ONLY"
    owner_reserved: bool = False
    done: bool = False

    @property
    def parallel_eligible(self) -> bool:
        return self.effect_class in PARALLEL_SAFE_EFFECT_CLASSES and not self.owner_reserved


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    mission_id: str
    mission_class: str
    target_state: str
    runtime_mode: RuntimeMode
    prompt_genome: PromptGenome
    packets: tuple[WorkPacket,...]
    current_maturity: str = "DESIGNED"
    owner_effect_authority: bool = False
    maximum_parallelism: int = 8
    commercial_evidence: Mapping[str, bool] = field(default_factory=dict)
    commercial_applicable_gates: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CycleTelemetry:
    cycle: int
    ready_packets: int
    executed_packets: int
    achieved_parallelism: int
    owner_interventions: int
    output_class: str
    terminal: bool
    evidence_refs: tuple[str,...] = ()


@dataclass(frozen=True, slots=True)
class CycleResult:
    context: ExecutionContext
    telemetry: CycleTelemetry
    checkpoint: Checkpoint
    next_ready_packets: tuple[str,...]
    learning_event_id: str
    reentry_id: str = ""
    resume_capsule: Mapping[str, object] | None = None
    terminal_state: str = ""
    maturity_gaps: tuple[str, ...] = ()
    recompile_required: bool = False


def _sha(v: object) -> str:
    return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


class AutonomicCompletionKernel:
    def __init__(self, store: RunStore, learning: FederationLearningLedger, scientist: PromptScientistV2 | None = None, *, prompt_evaluator: Callable[[PromptGenome, object], PromptRunMetrics] | None = None, prompt_fixtures: Sequence[object] = (), mission_recompiler: Callable[[ExecutionContext, tuple[str, ...]], ExecutionContext] | None = None, commercial_evidence_provider: Callable[[ExecutionContext], Mapping[str, bool]] | None = None):
        self.store=store; self.learning=learning; self.scientist=scientist or PromptScientistV2()
        self.prompt_evaluator=prompt_evaluator; self.prompt_fixtures=tuple(prompt_fixtures)
        self.mission_recompiler=mission_recompiler
        self.commercial_evidence_provider=commercial_evidence_provider

    @staticmethod
    def _ready(ctx: ExecutionContext) -> list[WorkPacket]:
        done={p.packet_id for p in ctx.packets if p.done}
        return [p for p in ctx.packets if not p.done and set(p.dependencies)<=done]

    @staticmethod
    def _wave(ctx: ExecutionContext, ready: Sequence[WorkPacket]) -> list[WorkPacket]:
        if not ready: return []
        owner=[p for p in ready if p.owner_reserved or p.effect_class in OWNER_EFFECT_CLASSES]
        if owner and not ctx.owner_effect_authority:
            ready=[p for p in ready if p not in owner]

        # Prefer a useful collision-safe parallel wave when one exists.  Serial
        # packets remain queued and cannot inherit authority from parallel work.
        parallel=[p for p in ready if p.parallel_eligible]
        if parallel:
            wave=[]; occupied=set()
            for p in parallel:
                keys=set(p.collision_keys)
                if keys & occupied: continue
                wave.append(p); occupied |= keys
                if len(wave)>=ctx.maximum_parallelism: break
            return wave

        serial=[p for p in ready if not p.parallel_eligible]
        return [serial[0]] if serial else []

    @staticmethod
    def _advance(ctx: ExecutionContext, executed: Iterable[str]) -> ExecutionContext:
        ids=set(executed)
        packets=tuple(WorkPacket(p.packet_id,p.dependencies,p.collision_keys,p.effect_class,p.owner_reserved,p.done or p.packet_id in ids) for p in ctx.packets)
        # Packet completion is execution evidence only.  It must never promote
        # commercial maturity by itself; maturity is decided by an explicit court.
        return ExecutionContext(
            ctx.mission_id,ctx.mission_class,ctx.target_state,ctx.runtime_mode,ctx.prompt_genome,packets,
            ctx.current_maturity,ctx.owner_effect_authority,ctx.maximum_parallelism,
            dict(ctx.commercial_evidence),ctx.commercial_applicable_gates,
        )

    @staticmethod
    def _commercial_court(ctx: ExecutionContext):
        if ctx.target_state != "COMMERCIAL_READY_VERIFIED":
            return None
        applicable = ctx.commercial_applicable_gates or DEFAULT_STAGES
        return CommercialMaturityController(tuple(applicable)).evaluate(ctx.commercial_evidence)

    def run_cycle(self, ctx: ExecutionContext, *, cycle: int, packet_executor: Callable[[WorkPacket], tuple[bool,str]], force_platform_boundary: bool=False) -> CycleResult:
        ready=self._ready(ctx); wave=self._wave(ctx,ready)
        evidence=[]; executed=[]
        if len(wave) > 1 and all(p.parallel_eligible for p in wave):
            with ThreadPoolExecutor(max_workers=min(len(wave), ctx.maximum_parallelism)) as pool:
                outcomes=list(pool.map(packet_executor, wave))
            for p,(ok,ref) in zip(wave,outcomes):
                if ok: executed.append(p.packet_id)
                evidence.append(ref)
        else:
            for p in wave:
                ok,ref=packet_executor(p)
                if ok: executed.append(p.packet_id)
                evidence.append(ref)
        new_ctx=self._advance(ctx,executed)
        if self.commercial_evidence_provider is not None and new_ctx.target_state == "COMMERCIAL_READY_VERIFIED":
            refreshed=dict(self.commercial_evidence_provider(new_ctx))
            new_ctx=ExecutionContext(
                new_ctx.mission_id,new_ctx.mission_class,new_ctx.target_state,new_ctx.runtime_mode,new_ctx.prompt_genome,new_ctx.packets,
                new_ctx.current_maturity,new_ctx.owner_effect_authority,new_ctx.maximum_parallelism,refreshed,new_ctx.commercial_applicable_gates,
            )
        ready_after=self._ready(new_ctx)
        remaining=[p.packet_id for p in ready_after]
        all_done=all(p.done for p in new_ctx.packets)
        owner_blocked=bool(ready_after) and not self._wave(new_ctx,ready_after) and all(
            (p.owner_reserved or p.effect_class in OWNER_EFFECT_CLASSES) and not new_ctx.owner_effect_authority
            for p in ready_after
        )
        terminal_state=""; maturity_gaps=(); recompile_required=False
        commercial_court=self._commercial_court(new_ctx)
        if all_done and commercial_court is not None:
            if commercial_court.state == "COMMERCIAL_READY_VERIFIED":
                new_ctx=ExecutionContext(
                    new_ctx.mission_id,new_ctx.mission_class,new_ctx.target_state,new_ctx.runtime_mode,new_ctx.prompt_genome,new_ctx.packets,
                    "COMMERCIAL_READY_VERIFIED",new_ctx.owner_effect_authority,new_ctx.maximum_parallelism,
                    dict(new_ctx.commercial_evidence),new_ctx.commercial_applicable_gates,
                )
                terminal_state=TerminalState.COMMERCIAL_READY_VERIFIED.value; out=OutputClass.TERMINAL_REPORT
            else:
                maturity_gaps=tuple(commercial_court.failed + commercial_court.missing)
                recompile_required=True
                out=OutputClass.PROGRESS_UPDATE
        elif all_done:
            terminal_state=TerminalState.COMPLETE_VERIFIED.value
            out=OutputClass.TERMINAL_REPORT
        elif owner_blocked:
            terminal_state=TerminalState.IRREDUCIBLE_OWNER_DECISION.value; out=OutputClass.OWNER_DECISION
        elif force_platform_boundary and new_ctx.runtime_mode is RuntimeMode.NO_PERSISTENT_RUNNER:
            out=OutputClass.RESUME_CAPSULE
        else:
            out=OutputClass.PROGRESS_UPDATE

        # Automatic prompt-science pass after every material cycle.  Promotion is
        # evidence-gated: without a matched evaluator the incumbent is retained.
        total_packets=max(1,len(new_ctx.packets)); done_packets=sum(1 for p in new_ctx.packets if p.done)
        parallelizable=sum(1 for p in ready if p.parallel_eligible)
        cycle_metrics=PromptRunMetrics(
            prompt_version=new_ctx.prompt_genome.version, mission_class=new_ctx.mission_class,
            completion_ratio=done_packets/total_packets, correctness=1.0, proof_completeness=1.0,
            execution_efficiency=1.0, parallelizable_packets=parallelizable, achieved_parallelism=len(wave),
            owner_interventions=1 if out is OutputClass.OWNER_DECISION else 0,
            output_boundary_stop=out is OutputClass.RESUME_CAPSULE,
            persistent_runner_available=new_ctx.runtime_mode is RuntimeMode.PERSISTENT_RUNNER,
            reentry_enqueued=new_ctx.runtime_mode is RuntimeMode.PERSISTENT_RUNNER and not terminal_state,
            commercial_maturity_gap=new_ctx.target_state=="COMMERCIAL_READY_VERIFIED" and new_ctx.current_maturity!="COMMERCIAL_READY_VERIFIED",
        )
        diagnoses=self.scientist.diagnose(cycle_metrics)
        prompt_mutation=(); promotion_state="PROMPT_RETAINED"; promotion_reason="NO_DIAGNOSIS_OR_MATCHED_EVALUATOR"
        if diagnoses:
            challengers=self.scientist.generate_challengers(new_ctx.prompt_genome, diagnoses)
            if self.prompt_evaluator is not None and self.prompt_fixtures:
                inc_eval=self.scientist.matched_evaluate(new_ctx.prompt_genome,self.prompt_fixtures,self.prompt_evaluator,evidence_prefix=f"{new_ctx.mission_id}:P0")
                ch_evals=[self.scientist.matched_evaluate(c,self.prompt_fixtures,self.prompt_evaluator,evidence_prefix=f"{new_ctx.mission_id}:{c.version}") for c in challengers]
                decision=self.scientist.select_for_promotion(inc_eval,ch_evals)
                promotion_state=decision.state; promotion_reason=decision.reason
                if decision.state=="PROMPT_PROMOTED":
                    winner=next(c for c in challengers if c.version==decision.selected_candidate_id)
                    prompt_mutation=winner.mutation_plan
                    new_ctx=ExecutionContext(new_ctx.mission_id,new_ctx.mission_class,new_ctx.target_state,new_ctx.runtime_mode,winner,new_ctx.packets,new_ctx.current_maturity,new_ctx.owner_effect_authority,new_ctx.maximum_parallelism,dict(new_ctx.commercial_evidence),new_ctx.commercial_applicable_gates)
            else:
                promotion_state="PROMPT_CHALLENGERS_SHADOW_REQUIRED"
                promotion_reason="MATCHED_EVALUATOR_UNAVAILABLE"

        state={"mission_id":new_ctx.mission_id,"cycle":cycle,"target_state":new_ctx.target_state,"current_maturity":new_ctx.current_maturity,"prompt_version":new_ctx.prompt_genome.version,"packets":[asdict(p) for p in new_ctx.packets],"terminal_state":terminal_state,"prompt_promotion_state":promotion_state,"commercial_evidence":dict(new_ctx.commercial_evidence),"maturity_gaps":maturity_gaps,"recompile_required":recompile_required}
        prev=self.store.read(new_ctx.mission_id)
        checkpoint=self.store.put(new_ctx.mission_id,state,expected_version=None if prev is None else prev.version)
        event_id=f"LEARN-{new_ctx.mission_id}-{checkpoint.version}-{checkpoint.state_sha256[:10]}"
        event=LearningEvent(event_id,"CURRENT_RUN",new_ctx.mission_id,new_ctx.mission_class,new_ctx.prompt_genome.version,dict(new_ctx.prompt_genome.genes),new_ctx.current_maturity,"MISSION_CYCLE","EXECUTE_READY_WAVE","EXECUTE_READY_WAVE",parallelism_available=parallelizable,parallelism_achieved=max(1,len(wave)) if wave else 0,prompt_mutation=tuple(prompt_mutation),algorithm_mutation=("THREADPOOL_FANOUT_FANIN_V11",) if len(wave)>1 else (),evidence_refs=tuple(evidence)+(f"PROMPT:{promotion_state}:{promotion_reason}",),receiver_compatibility=("CFBE","STRATEGIC_FUSE","FORMATION","PROMPT_SCIENTIST"),rollback_ref=f"PROMPT:{new_ctx.prompt_genome.parent_version or new_ctx.prompt_genome.version}",promotion_state=promotion_state)
        self.learning.append(event); self.store.append_learning(event_id,new_ctx.mission_id,event.body())
        reentry_id=""; capsule=None
        if not terminal_state and new_ctx.runtime_mode is RuntimeMode.PERSISTENT_RUNNER:
            reentry_id=self.store.enqueue_reentry(new_ctx.mission_id,checkpoint,{"next_ready_packets":remaining,"prompt_version":new_ctx.prompt_genome.version,"maturity_gaps":maturity_gaps,"recompile_required":recompile_required})
        elif out is OutputClass.RESUME_CAPSULE:
            capsule={"mission_id":new_ctx.mission_id,"checkpoint_version":checkpoint.version,"checkpoint_sha256":checkpoint.state_sha256,"verified_state":new_ctx.current_maturity,"next_ready_packets":remaining,"prompt_version":new_ctx.prompt_genome.version,"learning_event_ids":[event_id],"maturity_gaps":maturity_gaps,"recompile_required":recompile_required,"continuation_instruction":"RECOMPILE_MATURITY_GAPS_AND_EXECUTE" if recompile_required else "CONSUME_CHECKPOINT_AND_EXECUTE_NEXT_READY_WAVE"}
        telemetry=CycleTelemetry(cycle,len(ready),len(executed),len(wave),0,out.value,bool(terminal_state),tuple(evidence))
        return CycleResult(new_ctx,telemetry,checkpoint,tuple(remaining),event_id,reentry_id,capsule,terminal_state,maturity_gaps,recompile_required)

    def execute_until_boundary(self, ctx: ExecutionContext, packet_executor: Callable[[WorkPacket], tuple[bool,str]], *, max_cycles: int=100, force_platform_boundary_at: int | None=None) -> list[CycleResult]:
        results=[]; current=ctx
        for cycle in range(1,max_cycles+1):
            res=self.run_cycle(current,cycle=cycle,packet_executor=packet_executor,force_platform_boundary=(force_platform_boundary_at==cycle))
            results.append(res); current=res.context
            if res.terminal_state or res.resume_capsule is not None: break
            if res.recompile_required:
                if self.mission_recompiler is None:
                    break
                current=self.mission_recompiler(res.context,res.maturity_gaps)
                continue
            # progress output is explicitly non-terminal: continue in the same run.
        return results

    @staticmethod
    def prompt_metrics(results: Sequence[CycleResult]) -> PromptRunMetrics:
        if not results: raise ValueError("RESULTS_REQUIRED")
        total_packets=len(results[0].context.packets)
        done=sum(1 for p in results[-1].context.packets if p.done)
        parallelizable=max((sum(1 for p in r.context.packets if not p.done and p.parallel_eligible) for r in results),default=0)
        achieved=max((r.telemetry.achieved_parallelism for r in results),default=1)
        final=results[-1]
        return PromptRunMetrics(
            prompt_version=final.context.prompt_genome.version,
            mission_class=final.context.mission_class,
            completion_ratio=done/max(1,total_packets),
            correctness=1.0,
            proof_completeness=1.0,
            execution_efficiency=min(1.0, total_packets/max(1,sum(r.telemetry.executed_packets for r in results))),
            parallelizable_packets=parallelizable,
            achieved_parallelism=achieved,
            owner_interventions=0,
            recovery_success=1.0,
            context_efficiency=1.0,
            creative_freedom=1.0,
            output_boundary_stop=any(r.telemetry.output_class==OutputClass.RESUME_CAPSULE.value for r in results),
            persistent_runner_available=final.context.runtime_mode is RuntimeMode.PERSISTENT_RUNNER,
            reentry_enqueued=bool(final.reentry_id),
            commercial_maturity_gap=final.context.target_state=="COMMERCIAL_READY_VERIFIED" and final.context.current_maturity!="COMMERCIAL_READY_VERIFIED",
        )