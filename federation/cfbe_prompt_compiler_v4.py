"""CFBE v4 mission compiler: deterministic DAGs, safe parallelism, strict proof."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable

SCHEMA="CFBE-PARALLEL-MISSION-COMPILER-V4"; VERSION="4.0.0"; AUTHORITY_CEILING="A1_INTERNAL"
LANES=("LANE-A-REPOSITORY_SOURCE_INTELLIGENCE","LANE-B-ARCHITECTURE_IMPLEMENTATION","LANE-C-BUILD_COMPILER_RUNTIME","LANE-D-TEST_SIMULATION","LANE-E-SECURITY_REDTEAM_FALSIFICATION","LANE-F-PROVIDER_DEPLOYMENT_READINESS","LANE-G-CFBE_FRONTIER_BENCHMARK","LANE-H-DOCUMENTATION_PROOF_LEARNING")
CONSTITUTIONAL_INVARIANTS=frozenset({"PROOF_BEFORE_CLAIM","AIRLOCK_ADMISSION","SOURCE_PROVENANCE","SECRET_NON_DISCLOSURE","MINIMUM_AUTHORITY","PROVIDER_NATIVE_READBACK","ROLLBACK_REQUIRED","NO_TRUST_TRANSFER","OWNER_RESERVED_CONSEQUENTIAL_EFFECTS","CREATIVE_FREEDOM_WITHIN_INVARIANTS"})
PROOF_LADDER=("HYPOTHESIS","DESIGNED","SOURCE_PRESENT","TESTED","ADMITTED","MERGED","DEPLOYED","RUNTIME_VERIFIED","BEHAVIOR_VERIFIED","PRODUCTION_VERIFIED")
class CompilerError(ValueError): pass
class EffectClass(StrEnum):
    READ_ONLY="READ_ONLY"; INTERNAL_A1="INTERNAL_A1"; PROVIDER_MUTATION="PROVIDER_MUTATION"; EXTERNAL_EFFECT="EXTERNAL_EFFECT"
class PacketDisposition(StrEnum):
    READY="READY"; HELD_EXTERNAL_AUTHORITY="HELD_EXTERNAL_AUTHORITY"; HELD_DEPENDENCY="HELD_DEPENDENCY"
def _canon(v:Any)->str:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _digest(v:Any)->str:return sha256(_canon(v).encode()).hexdigest()
def _id(v:str,label:str)->str:
    v=str(v).strip(); allowed=set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:/-")
    if not v or len(v)>240 or any(c not in allowed for c in v): raise CompilerError(f"{label}_INVALID")
    return v
def _uniq(v:Iterable[str])->tuple[str,...]:return tuple(dict.fromkeys(str(x).strip() for x in v if str(x).strip()))

@dataclass(frozen=True,slots=True)
class MissionTask:
    task_id:str; objective:str; lane:str; depends_on:tuple[str,...]=(); collision_keys:tuple[str,...]=(); effect_class:EffectClass=EffectClass.READ_ONLY; priority:int=50; required_capabilities:tuple[str,...]=(); acceptance_test:str=""; proof_type:str="DETERMINISTIC"; rollback_pointer:str=""; canonical_write:bool=False; shared_target:str=""
    def validate(self):
        _id(self.task_id,"TASK_ID")
        if not self.objective.strip(): raise CompilerError("TASK_OBJECTIVE_REQUIRED")
        if self.lane not in LANES: raise CompilerError("UNKNOWN_LANE")
        for x in (*self.depends_on,*self.collision_keys,*self.required_capabilities): _id(x,"TASK_REFERENCE")
        if isinstance(self.priority,bool) or not isinstance(self.priority,int) or not 0<=self.priority<=100: raise CompilerError("TASK_PRIORITY_INVALID")
        if self.shared_target:_id(self.shared_target,"SHARED_TARGET")
        if self.canonical_write and self.effect_class in (EffectClass.PROVIDER_MUTATION,EffectClass.EXTERNAL_EFFECT): raise CompilerError("EXTERNAL_PACKET_CANNOT_BE_CANONICAL_SOURCE_WRITE")
        return self

@dataclass(frozen=True,slots=True)
class WorkPacket:
    packet_id:str; lane_id:str; task_id:str; input_fingerprint:str; objective:str; expected_output:str; dependencies:tuple[str,...]; collision_keys:tuple[str,...]; acceptance_test:str; proof_type:str; rollback_pointer:str; required_capabilities:tuple[str,...]; effect_class:EffectClass; canonical_write:bool; shared_target:str; priority:int; disposition:PacketDisposition; hold_reason:str=""
    @property
    def parallel_eligible(self): return self.disposition is PacketDisposition.READY and self.effect_class is EffectClass.READ_ONLY and not self.canonical_write and not self.shared_target
    @property
    def serialized(self): return self.disposition is PacketDisposition.READY and (self.effect_class is EffectClass.INTERNAL_A1 or self.canonical_write or bool(self.shared_target))
    def body(self):
        d=asdict(self); d["effect_class"]=self.effect_class.value; d["disposition"]=self.disposition.value; return d

@dataclass(frozen=True,slots=True)
class ParallelWave: wave_id:str; packet_ids:tuple[str,...]; reason:str
@dataclass(frozen=True,slots=True)
class MissionGraph:
    mission_id:str; target_state:str; current_verified_state:str; deliverables:tuple[str,...]; acceptance_tests:tuple[str,...]; proof_requirements:tuple[str,...]; packets:tuple[WorkPacket,...]; held_packets:tuple[str,...]; critical_path:tuple[str,...]; constitutional_invariants:frozenset[str]=CONSTITUTIONAL_INVARIANTS; authority_ceiling:str=AUTHORITY_CEILING; external_effect_default:bool=False; graph_sha256:str=""
    def body(self): return {"schema":SCHEMA,"version":VERSION,"mission_id":self.mission_id,"target_state":self.target_state,"current_verified_state":self.current_verified_state,"deliverables":self.deliverables,"acceptance_tests":self.acceptance_tests,"proof_requirements":self.proof_requirements,"packets":[p.body() for p in self.packets],"held_packets":self.held_packets,"critical_path":self.critical_path,"constitutional_invariants":sorted(self.constitutional_invariants),"authority_ceiling":self.authority_ceiling,"external_effect_default":self.external_effect_default}
    def validate_hash(self):
        if self.graph_sha256!=_digest(self.body()): raise CompilerError("MISSION_GRAPH_HASH_MISMATCH")
        return self

class MissionCompiler:
    @staticmethod
    def _acyclic(tasks):
        deps={t.task_id:set(t.depends_on) for t in tasks}; remaining=set(deps)
        while remaining:
            ready={n for n in remaining if not deps[n]&remaining}
            if not ready: raise CompilerError("MISSION_GRAPH_CYCLE")
            remaining-=ready
    @staticmethod
    def _critical(tasks):
        by={t.task_id:t for t in tasks}; children={k:[] for k in by}
        for t in tasks:
            for d in t.depends_on: children[d].append(t.task_id)
        memo={}
        def best(n):
            if n in memo:return memo[n]
            if not children[n]: r=(1,by[n].priority,(n,))
            else:
                b=max((best(c) for c in children[n]),key=lambda x:(x[0],x[1],x[2])); r=(1+b[0],by[n].priority+b[1],(n,)+b[2])
            memo[n]=r; return r
        roots=[t.task_id for t in tasks if not t.depends_on]
        return max((best(r) for r in roots),key=lambda x:(x[0],x[1],x[2]))[2]
    def compile(self,*,objective,current_verified_state,target_state,deliverables,acceptance_tests,proof_requirements,tasks,mission_id=None):
        if not str(objective).strip(): raise CompilerError("OBJECTIVE_REQUIRED")
        ds,ats,prs=_uniq(deliverables),_uniq(acceptance_tests),_uniq(proof_requirements); ts=tuple(t.validate() for t in tasks)
        if not ts: raise CompilerError("FINITE_TASK_SET_REQUIRED")
        ids=[t.task_id for t in ts]
        if len(ids)!=len(set(ids)): raise CompilerError("DUPLICATE_TASK_ID")
        known=set(ids)
        if any(set(t.depends_on)-known or t.task_id in t.depends_on for t in ts): raise CompilerError("TASK_DEPENDENCY_INVALID")
        self._acyclic(ts); mission_id=_id(mission_id or f"MISSION-{_digest([objective,target_state,ids])[:16]}","MISSION_ID")
        disp={t.task_id:(PacketDisposition.HELD_EXTERNAL_AUTHORITY,"A1_INTERNAL_CEILING_EXTERNAL_EFFECT_DEFAULT_FALSE") if t.effect_class in (EffectClass.PROVIDER_MUTATION,EffectClass.EXTERNAL_EFFECT) else (PacketDisposition.READY,"") for t in ts}
        changed=True
        while changed:
            changed=False
            for t in ts:
                if disp[t.task_id][0] is not PacketDisposition.READY: continue
                blocked=[d for d in t.depends_on if disp[d][0] is not PacketDisposition.READY]
                if blocked: disp[t.task_id]=(PacketDisposition.HELD_DEPENDENCY,"HELD_DEPENDENCY:"+",".join(sorted(blocked))); changed=True
        fp=_digest({"objective":objective,"current":current_verified_state,"target":target_state,"deliverables":ds,"acceptance":ats,"proof":prs,"tasks":[asdict(t) for t in ts]})
        packets=tuple(WorkPacket(f"PKT-{t.task_id}",t.lane,t.task_id,fp,t.objective,f"VERIFIABLE_OUTPUT:{t.task_id}",tuple(f"PKT-{d}" for d in t.depends_on),t.collision_keys,t.acceptance_test or f"ASSERT:{t.task_id}:COMPLETE",t.proof_type,t.rollback_pointer or f"ROLLBACK:{t.task_id}",t.required_capabilities,t.effect_class,t.canonical_write,t.shared_target,t.priority,*disp[t.task_id]) for t in ts)
        g=MissionGraph(mission_id,str(target_state).strip(),str(current_verified_state).strip(),ds,ats,prs,packets,tuple(p.packet_id for p in packets if p.disposition is not PacketDisposition.READY),tuple(f"PKT-{x}" for x in self._critical(ts)))
        return replace(g,graph_sha256=_digest(g.body()))
    def schedule_waves(self,graph,max_parallel=8):
        graph.validate_hash()
        if isinstance(max_parallel,bool) or not isinstance(max_parallel,int) or max_parallel<1: raise CompilerError("MAX_PARALLEL_INVALID")
        by={p.packet_id:p for p in graph.packets}; active={p.packet_id for p in graph.packets if p.disposition is PacketDisposition.READY}; done=set(); out=[]
        while active:
            ready=[by[i] for i in active if set(by[i].dependencies)<=done]
            if not ready: raise CompilerError("ACTIVE_PACKET_DEADLOCK")
            ready.sort(key=lambda p:(p.packet_id not in graph.critical_path,-p.priority,p.packet_id)); serial=[p for p in ready if p.serialized]
            if serial: batch=[serial[0]]; reason="SERIALIZED_CANONICAL_OR_INTERNAL_MUTATION"
            else:
                batch=[]; occupied=set()
                for p in ready:
                    k=set(p.collision_keys)
                    if k&occupied: continue
                    batch.append(p); occupied|=k
                    if len(batch)>=max_parallel: break
                reason="COLLISION_SAFE_PARALLEL_READ_WAVE"
            ids=tuple(p.packet_id for p in batch); out.append(ParallelWave(f"WAVE-{len(out)+1:03d}",ids,reason)); done.update(ids); active-=set(ids)
        return tuple(out)
    def to_cfbe_vnext_execution_graph(self,graph,*,max_parallel=8,maximum_total_cost=0.0,baseline_quality=1.0):
        graph.validate_hash(); logical=[p for p in graph.packets if p.parallel_eligible]
        if not logical: raise CompilerError("NO_EFFECT_FREE_PACKETS_FOR_CFBE_VNEXT_ADAPTER")
        try: from benchmarking.cfbe_omega.mission_execution_kernel_vnext.multistream import ExecutionGraph,PathCandidate,StreamNode
        except ImportError as e: raise CompilerError("CFBE_VNEXT_MULTISTREAM_UNAVAILABLE") from e
        ids={p.packet_id for p in logical}; streams=[]; paths=[]
        for p in logical:
            streams.append(StreamNode(stream_id=p.packet_id,requirement_ids=(p.task_id,),depends_on=tuple(d for d in p.dependencies if d in ids),collision_keys=p.collision_keys))
            paths.append(PathCandidate(path_id=f"PATH-{p.task_id}",stream_id=p.packet_id,family="CFBE_PROMPT_COMPILER_V4",independent_group=p.lane_id,required_capabilities=p.required_capabilities,collision_keys=p.collision_keys,expected_quality=1.0,estimated_cost=0.0,priority=p.priority,logical_only=True,external_effect=False))
        return ExecutionGraph.create(graph_id=f"CFBEV4-{graph.mission_id}",mission_id=graph.mission_id,mission_version=1,contract_sha256=graph.graph_sha256,formation_plan_sha256=_digest({"mission":graph.mission_id,"critical":graph.critical_path}),streams=streams,paths=paths,max_parallel=max_parallel,maximum_total_cost=maximum_total_cost,baseline_quality=baseline_quality)

@dataclass(frozen=True,slots=True)
class CircuitDecision: failure_fingerprint:str; count:int; circuit_open:bool; required_route:str
class FailureCircuitBreaker:
    def __init__(self,threshold=2):
        if isinstance(threshold,bool) or threshold<2: raise CompilerError("CIRCUIT_THRESHOLD_MUST_BE_AT_LEAST_TWO")
        self.threshold=threshold; self._counts={}
    def record(self,failure_fingerprint):
        f=str(failure_fingerprint).strip()
        if not f: raise CompilerError("FAILURE_FINGERPRINT_REQUIRED")
        n=self._counts.get(f,0)+1; self._counts[f]=n; opened=n>=self.threshold
        return CircuitDecision(f,n,opened,"MATERIALLY_DIFFERENT_ROUTE_REQUIRED" if opened else "BOUNDED_RETRY_OR_SAFE_REPAIR_ALLOWED")

@dataclass(frozen=True,slots=True)
class ProofReceipt: state:str; evidence_refs:tuple[str,...]; provider_readback_ref:str=""; runtime_receipt_ref:str=""; rollback_proof_ref:str=""
class ProofLadder:
    @staticmethod
    def validate(r):
        if r.state not in PROOF_LADDER: raise CompilerError("UNKNOWN_PROOF_STATE")
        i=PROOF_LADDER.index(r.state)
        if i>=PROOF_LADDER.index("TESTED") and not r.evidence_refs: raise CompilerError("TESTED_OR_HIGHER_REQUIRES_EVIDENCE")
        if i>=PROOF_LADDER.index("DEPLOYED") and not r.runtime_receipt_ref: raise CompilerError("DEPLOYED_OR_HIGHER_REQUIRES_RUNTIME_RECEIPT")
        if i>=PROOF_LADDER.index("RUNTIME_VERIFIED") and not r.provider_readback_ref: raise CompilerError("RUNTIME_VERIFIED_REQUIRES_PROVIDER_READBACK")
        if i>=PROOF_LADDER.index("PRODUCTION_VERIFIED") and not r.rollback_proof_ref: raise CompilerError("PRODUCTION_VERIFIED_REQUIRES_ROLLBACK_PROOF")
        return r
    @staticmethod
    def promote(current,candidate):
        ProofLadder.validate(current); ProofLadder.validate(candidate)
        if PROOF_LADDER.index(candidate.state)<PROOF_LADDER.index(current.state): raise CompilerError("PROOF_STATE_REGRESSION")
        return candidate

@dataclass(frozen=True,slots=True)
class PropagationTarget: target_id:str; compatible:bool; regression_green:bool; rollback_ref:str
@dataclass(frozen=True,slots=True)
class PropagationDecision: target_id:str; action:str; reason:str
def plan_version_propagation(targets):
    out=[]
    for t in targets:
        _id(t.target_id,"PROPAGATION_TARGET")
        if not t.compatible:r=("HOLD","INCOMPATIBLE_RECEIVER")
        elif not t.regression_green:r=("HOLD","RECEIVER_REGRESSION_NOT_GREEN")
        elif not t.rollback_ref.strip():r=("HOLD","ROLLBACK_PROOF_REQUIRED")
        else:r=("ELIGIBLE","COMPATIBLE_REGRESSION_GREEN")
        out.append(PropagationDecision(t.target_id,*r))
    return tuple(out)
