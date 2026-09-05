from __future__ import annotations

"""ChatGov Ω3.5 performance frontier kernel.

Bounded composition inside ChatGov: lifecycle hooks, cache/dedupe, pending-write
recovery, selective specialists/skills, marginal-information stopping, trace-to-
regression and owner-burden measurement. No provider authority or external effect.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json, re
from time import perf_counter_ns
from typing import Any, Callable, Iterable, Mapping, Sequence

NO_EFFECT_CLASSES = frozenset({"NO_EFFECT", "READ_ONLY"})
EFFECTFUL_CLASSES = frozenset({"BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"})


def _json(v: object) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(v: object) -> str:
    return sha256(_json(v).encode()).hexdigest()


def _aware(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    out = datetime.fromisoformat(text)
    if out.tzinfo is None or out.utcoffset() is None:
        raise ValueError("TIMEZONE_AWARE_TIMESTAMP_REQUIRED")
    return out


class HookEvent(str, Enum):
    SESSION_START="SESSION_START"; USER_PROMPT="USER_PROMPT"; PRE_TOOL="PRE_TOOL"
    POST_TOOL="POST_TOOL"; TOOL_FAILURE="TOOL_FAILURE"; PRE_FINAL="PRE_FINAL"; SESSION_END="SESSION_END"


class HookDecision(str, Enum):
    ALLOW="ALLOW"; DENY="DENY"; BLOCK_CONTINUE="BLOCK_CONTINUE"


@dataclass(frozen=True, slots=True)
class HookContext:
    event: HookEvent; mission_id: str; effect_class: str="NO_EFFECT"; material: bool=False
    tool_name: str=""; tool_args: Mapping[str, Any]=field(default_factory=dict); metadata: Mapping[str, Any]=field(default_factory=dict)
    def validate(self) -> None:
        if not self.mission_id: raise ValueError("HOOK_MISSION_REQUIRED")
        if self.effect_class not in NO_EFFECT_CLASSES | EFFECTFUL_CLASSES: raise ValueError("HOOK_EFFECT_CLASS_INVALID")


@dataclass(frozen=True, slots=True)
class HookResult:
    decision: HookDecision=HookDecision.ALLOW; reason: str=""; modified_args: Mapping[str, Any] | None=None; additional_context: str=""


@dataclass(frozen=True, slots=True)
class HookReceipt:
    event: str; mission_id: str; decision: str; reason: str; executed_hooks: tuple[str,...]
    elapsed_ms: float; modified_args: Mapping[str, Any] | None; additional_context: tuple[str,...]; receipt_sha256: str


class LifecycleHookBus:
    """Deterministic hook bus. Material effectful PRE_TOOL/PRE_FINAL errors fail closed."""
    def __init__(self, *, budget_ms: float=5000.0) -> None:
        if budget_ms <= 0: raise ValueError("HOOK_BUDGET_MUST_BE_POSITIVE")
        self.budget_ms=float(budget_ms); self._hooks={event: [] for event in HookEvent}
    def register(self, event: HookEvent, name: str, callback: Callable[[HookContext], HookResult | None], *, priority: int=100) -> None:
        if not name.strip(): raise ValueError("HOOK_NAME_REQUIRED")
        if any(row[1]==name for row in self._hooks[event]): raise ValueError("HOOK_NAME_DUPLICATE")
        self._hooks[event].append((int(priority), name.strip(), callback))
    def emit(self, context: HookContext) -> HookReceipt:
        context.validate(); start=perf_counter_ns(); names=[]; notes=[]; modified=None; decision=HookDecision.ALLOW; reason=""
        fail_closed=context.material and context.effect_class in EFFECTFUL_CLASSES and context.event in {HookEvent.PRE_TOOL,HookEvent.PRE_FINAL}
        for _, name, fn in sorted(self._hooks[context.event], key=lambda row:(row[0],row[1])):
            names.append(name)
            try: result=fn(context) or HookResult()
            except Exception as exc:
                if fail_closed: decision=HookDecision.DENY; reason=f"HOOK_ERROR_FAIL_CLOSED:{name}:{type(exc).__name__}"; break
                notes.append(f"HOOK_ERROR_NONBLOCKING:{name}:{type(exc).__name__}"); continue
            if result.additional_context: notes.append(result.additional_context[:2048])
            if result.modified_args is not None: modified=dict(result.modified_args)
            if result.decision is not HookDecision.ALLOW:
                decision=result.decision; reason=result.reason or f"{decision.value}_BY:{name}"; break
        elapsed=(perf_counter_ns()-start)/1_000_000
        if elapsed > self.budget_ms and decision is HookDecision.ALLOW:
            if fail_closed: decision=HookDecision.DENY; reason="HOOK_BUDGET_EXCEEDED_FAIL_CLOSED"
            else: notes.append("HOOK_BUDGET_EXCEEDED_NONBLOCKING")
        body={"event":context.event.value,"mission_id":context.mission_id,"decision":decision.value,"reason":reason,"hooks":names,"elapsed_ms":round(elapsed,3),"modified_args":modified,"context":notes}
        return HookReceipt(context.event.value,context.mission_id,decision.value,reason,tuple(names),round(elapsed,3),modified,tuple(notes),_digest(body))


@dataclass(frozen=True, slots=True)
class CacheEntry:
    key: str; value: Any; source_version: str; observed_at: str; fresh_until: str; proof_ref: str; value_sha256: str
    def fresh(self, *, now: str, source_version: str) -> bool:
        return source_version==self.source_version and _aware(self.observed_at) <= _aware(now) < _aware(self.fresh_until)


class ToolSchemaCache:
    def __init__(self) -> None: self._entries={}; self.hits=0; self.misses=0
    @staticmethod
    def key(connector: str, scope: str) -> str: return _digest({"connector":connector.strip(),"scope":scope.strip()})
    def put(self, *, connector: str, scope: str, schema: Any, source_version: str, observed_at: str, fresh_until: str, proof_ref: str) -> CacheEntry:
        if not proof_ref: raise ValueError("SCHEMA_CACHE_PROOF_REQUIRED")
        if _aware(fresh_until) <= _aware(observed_at): raise ValueError("SCHEMA_CACHE_WINDOW_INVALID")
        key=self.key(connector,scope); entry=CacheEntry(key,schema,source_version,observed_at,fresh_until,proof_ref,_digest(schema)); self._entries[key]=entry; return entry
    def get(self, *, connector: str, scope: str, source_version: str, now: str) -> CacheEntry | None:
        entry=self._entries.get(self.key(connector,scope))
        if entry and entry.fresh(now=now,source_version=source_version): self.hits+=1; return entry
        self.misses+=1; return None


class SemanticReadCache:
    """Exact source-anchored read cache. Effectful results are never cached."""
    def __init__(self) -> None: self._entries={}; self.hits=0; self.misses=0
    @staticmethod
    def key(target: str, query: Any, source_anchor: str) -> str: return _digest({"target":target,"query":query,"source_anchor":source_anchor})
    def put(self, *, target: str, query: Any, source_anchor: str, result: Any, effect_class: str, observed_at: str, fresh_until: str, proof_ref: str) -> CacheEntry:
        if effect_class not in NO_EFFECT_CLASSES: raise ValueError("EFFECTFUL_RESULT_MUST_NOT_BE_READ_CACHED")
        if not proof_ref: raise ValueError("READ_CACHE_PROOF_REQUIRED")
        if _aware(fresh_until) <= _aware(observed_at): raise ValueError("READ_CACHE_WINDOW_INVALID")
        key=self.key(target,query,source_anchor); entry=CacheEntry(key,result,source_anchor,observed_at,fresh_until,proof_ref,_digest(result)); self._entries[key]=entry; return entry
    def get(self, *, target: str, query: Any, source_anchor: str, now: str) -> CacheEntry | None:
        entry=self._entries.get(self.key(target,query,source_anchor))
        if entry and entry.fresh(now=now,source_version=source_anchor): self.hits+=1; return entry
        self.misses+=1; return None


@dataclass(frozen=True, slots=True)
class SpecialistCandidate:
    specialist_id: str; relevance: float; parallelizable: bool; context_isolated: bool; shared_mutable_dependency: bool=False

@dataclass(frozen=True, slots=True)
class SpecialistPlan:
    mode: str; selected: tuple[str,...]; rejected: tuple[str,...]; reason: str

class ElasticSpecialistPlanner:
    def __init__(self, *, max_active: int=4, relevance_floor: float=.55) -> None:
        if max_active < 1: raise ValueError("SPECIALIST_MAX_ACTIVE_INVALID")
        self.max_active=max_active; self.relevance_floor=float(relevance_floor)
    def plan(self, *, task_complexity: float, candidates: Sequence[SpecialistCandidate]) -> SpecialistPlan:
        if not 0 <= task_complexity <= 1: raise ValueError("TASK_COMPLEXITY_INVALID")
        if task_complexity <= .35: return SpecialistPlan("DIRECT",(),tuple(x.specialist_id for x in candidates),"SIMPLE_TASK_DIRECT_PATH")
        eligible=[x for x in candidates if x.relevance>=self.relevance_floor and x.parallelizable and x.context_isolated and not x.shared_mutable_dependency]
        eligible.sort(key=lambda x:(-x.relevance,x.specialist_id)); selected=tuple(x.specialist_id for x in eligible[:self.max_active]); sel=set(selected)
        rejected=tuple(x.specialist_id for x in candidates if x.specialist_id not in sel)
        if len(selected)>=2: return SpecialistPlan("PARALLEL_SPECIALISTS",selected,rejected,"INDEPENDENT_PARALLEL_VALUE")
        if len(selected)==1: return SpecialistPlan("SINGLE_SPECIALIST",selected,rejected,"ONE_ISOLATED_SPECIALIST_JUSTIFIED")
        return SpecialistPlan("DIRECT",(),rejected,"NO_SAFE_PARALLEL_SPECIALIST")


@dataclass(frozen=True, slots=True)
class PendingWrite:
    task_id: str; task_fingerprint: str; result_ref: str; result_sha256: str

class PendingWorkLedger:
    def __init__(self) -> None: self._writes={}
    def preserve(self, *, task_id: str, task_fingerprint: str, result_ref: str, result: Any) -> PendingWrite:
        if not all((task_id,task_fingerprint,result_ref)): raise ValueError("PENDING_WRITE_IDENTITY_REQUIRED")
        item=PendingWrite(task_id,task_fingerprint,result_ref,_digest(result)); old=self._writes.get(task_id)
        if old and old != item: raise ValueError("PENDING_WRITE_CONFLICT")
        self._writes[task_id]=item; return item
    def reusable(self, *, task_id: str, task_fingerprint: str) -> PendingWrite | None:
        item=self._writes.get(task_id); return item if item and item.task_fingerprint==task_fingerprint else None


@dataclass(frozen=True, slots=True)
class DeltaCapsule:
    changed: Mapping[str,Any]; deleted: tuple[str,...]; previous_sha256: str; current_sha256: str; delta_sha256: str

class DeltaCapsuleCompiler:
    def compile(self, previous: Mapping[str,Any], current: Mapping[str,Any]) -> DeltaCapsule:
        changed={k:current[k] for k in sorted(current) if k not in previous or previous[k]!=current[k]}; deleted=tuple(sorted(set(previous)-set(current)))
        body={"changed":changed,"deleted":deleted,"previous_sha256":_digest(previous),"current_sha256":_digest(current)}
        return DeltaCapsule(changed,deleted,body["previous_sha256"],body["current_sha256"],_digest(body))


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    skill_id: str; tags: frozenset[str]; dependencies: tuple[str,...]=(); load_cost: float=1.0
@dataclass(frozen=True, slots=True)
class SkillPage:
    selected: tuple[str,...]; omitted: tuple[str,...]; reason: str

class SkillPager:
    def __init__(self, skills: Sequence[SkillDefinition], *, max_active: int=6) -> None:
        self.skills={x.skill_id:x for x in skills}; self.max_active=max_active
        if len(self.skills)!=len(skills): raise ValueError("SKILL_ID_DUPLICATE")
        if max_active<1: raise ValueError("SKILL_BUDGET_INVALID")
    def page(self, required_tags: Iterable[str]) -> SkillPage:
        tags=frozenset(str(x).strip().lower() for x in required_tags if str(x).strip()); ranked=[]
        for item in self.skills.values():
            score=len({t.lower() for t in item.tags}&tags)
            if score: ranked.append((score,-item.load_cost,item.skill_id))
        ranked.sort(reverse=True); selected=[]
        def add(skill_id: str, stack: tuple[str,...]=()) -> None:
            if skill_id in stack: raise ValueError("SKILL_DEPENDENCY_CYCLE")
            item=self.skills.get(skill_id)
            if item is None: raise ValueError(f"SKILL_DEPENDENCY_MISSING:{skill_id}")
            for dep in item.dependencies: add(dep,stack+(skill_id,))
            if skill_id not in selected:
                if len(selected)>=self.max_active: raise ValueError("SKILL_ACTIVE_BUDGET_EXCEEDED")
                selected.append(skill_id)
        for _,_,root in ranked:
            try: add(root)
            except ValueError as exc:
                if str(exc)=="SKILL_ACTIVE_BUDGET_EXCEEDED": break
                raise
        omitted=tuple(sorted(set(self.skills)-set(selected))); return SkillPage(tuple(selected),omitted,"RELEVANCE_PLUS_DEPENDENCY_CLOSURE" if selected else "NO_RELEVANT_SKILL")


@dataclass(frozen=True, slots=True)
class InformationGainDecision:
    continue_work: bool; score: float; reason: str

class InformationGainStopRule:
    EPSILON=1e-9
    def __init__(self, *, threshold: float=.25) -> None: self.threshold=float(threshold)
    def decide(self, *, required: bool, decision_flip_probability: float, uncertainty_reduction: float, freshness_gain: float, acquisition_cost: float, acquisition_risk: float, owner_burden: float) -> InformationGainDecision:
        values=(decision_flip_probability,uncertainty_reduction,freshness_gain,acquisition_cost,acquisition_risk,owner_burden)
        if any(v<0 for v in values): raise ValueError("INFORMATION_GAIN_INPUT_NEGATIVE")
        if required: return InformationGainDecision(True,float("inf"),"REQUIRED_WORK")
        score=(decision_flip_probability*uncertainty_reduction*max(freshness_gain,self.EPSILON))/(acquisition_cost+acquisition_risk+owner_burden+self.EPSILON)
        return InformationGainDecision(score>=self.threshold,score,"OPTIONAL_VALUE_ABOVE_THRESHOLD" if score>=self.threshold else "LOW_MARGINAL_VALUE_STOP")


@dataclass(slots=True)
class WorkMetrics:
    duplicate_reads: int=0; schema_rediscovery: int=0; recomputed_successes: int=0; unnecessary_specialists: int=0
    repeated_owner_prompts: int=0; full_log_fetches: int=0; tool_round_trips: int=0
    def waste_units(self) -> float:
        return self.duplicate_reads+self.schema_rediscovery+1.5*self.recomputed_successes+1.5*self.unnecessary_specialists+2*self.repeated_owner_prompts+1.25*self.full_log_fetches+.25*self.tool_round_trips

@dataclass(frozen=True, slots=True)
class PerformanceComparison:
    baseline_waste_units: float; candidate_waste_units: float; reduction_fraction: float; quality_non_degraded: bool; two_x_target_met: bool

class UnnecessaryWorkMeter:
    @staticmethod
    def compare(*, baseline: WorkMetrics, candidate: WorkMetrics, baseline_quality: float, candidate_quality: float) -> PerformanceComparison:
        base=baseline.waste_units(); cand=candidate.waste_units(); reduction=0.0 if base<=0 else max(-1.0,min(1.0,1-cand/base)); quality=candidate_quality>=baseline_quality
        return PerformanceComparison(base,cand,reduction,quality,bool(base>0 and cand<=base*.5 and quality))


_SECRET=re.compile(r"(?i)(api[_-]?key|authorization|bearer|token|secret|password|private[_-]?key)")
def _sanitize(value: Any) -> Any:
    if isinstance(value,Mapping): return {str(k):("[REDACTED]" if _SECRET.search(str(k)) else _sanitize(v)) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_sanitize(v) for v in value]
    return "[REDACTED]" if _SECRET.search(str(value)) else value

@dataclass(frozen=True, slots=True)
class FailureObservation:
    stage: str; error_class: str; tool_name: str; route: str; message: str; context: Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True, slots=True)
class RegressionEnvelope:
    failure_fingerprint: str; test_case_id: str; sanitized_observation: Mapping[str,Any]; auto_commit_authorized: bool; provider_effect_authorized: bool

class TraceToRegressionCompiler:
    def compile(self, observation: FailureObservation) -> RegressionEnvelope:
        sanitized=_sanitize(asdict(observation)); fp=_digest(sanitized); return RegressionEnvelope(fp,f"REG-{fp[:16]}",sanitized,False,False)


@dataclass(frozen=True, slots=True)
class HostBindingContract:
    lifecycle_hooks_bound: bool; pre_tool_guardrail_bound: bool; post_tool_observer_bound: bool; pre_final_gate_bound: bool; durable_checkpoint_bound: bool; trace_exporter_bound: bool=False
    def enforcement_state(self) -> str:
        core=(self.lifecycle_hooks_bound,self.pre_tool_guardrail_bound,self.post_tool_observer_bound,self.pre_final_gate_bound,self.durable_checkpoint_bound)
        return "HOST_BOUND" if all(core) else "PARTIAL_HOST_BINDING" if any(core) else "SOURCE_ONLY_UNBOUND"


@dataclass(frozen=True, slots=True)
class RemainingWork:
    work_id: str; material: bool; safe: bool; authorized: bool; available: bool; owner_only: bool=False
@dataclass(frozen=True, slots=True)
class EfficiencyFinalDecision:
    allow_final: bool; continue_work: bool; owner_decision_required: bool; reason: str; actionable_work_ids: tuple[str,...]

class PreFinalEfficiencyGate:
    def decide(self, remaining: Sequence[RemainingWork]) -> EfficiencyFinalDecision:
        actionable=tuple(x.work_id for x in remaining if x.material and x.safe and x.authorized and x.available and not x.owner_only)
        if actionable: return EfficiencyFinalDecision(False,True,False,"ACTIONABLE_SYSTEM_WORK_REMAINS",actionable)
        owner=tuple(x.work_id for x in remaining if x.material and x.available and x.owner_only)
        if owner: return EfficiencyFinalDecision(True,False,True,"PRECISE_OWNER_DECISION_REQUIRED",owner)
        return EfficiencyFinalDecision(True,False,False,"NO_ACTIONABLE_SYSTEM_WORK_REMAINS",())


@dataclass(frozen=True, slots=True)
class SemanticSpan:
    attributes: Mapping[str,Any]
    @classmethod
    def build(cls, *, mission_id: str, operation_name: str, tool_name: str="", route: str="", cache_hit: bool=False, context_chars: int=0, duration_ms: float=0.0, error_type: str="") -> "SemanticSpan":
        if not mission_id or not operation_name: raise ValueError("SEMANTIC_SPAN_IDENTITY_REQUIRED")
        return cls({"gen_ai.operation.name":operation_name,"mission.id":mission_id,"tool.name":tool_name,"federation.route":route,"cache.hit":bool(cache_hit),"context.chars":max(0,int(context_chars)),"duration.ms":max(0.0,float(duration_ms)),"error.type":error_type})


@dataclass(frozen=True, slots=True)
class PerformanceKernelReceipt:
    schema: str; version: str; capabilities: tuple[str,...]; provider_effect_authorized: bool; native_chatgpt_binding_claimed: bool; stable_promotion_authorized: bool

def performance_kernel_receipt() -> PerformanceKernelReceipt:
    return PerformanceKernelReceipt("CHATGOV-PERFORMANCE-FRONTIER-KERNEL-V1","3.5.0",(
        "LIFECYCLE_HOOK_BUS","TOOL_SCHEMA_CACHE","SEMANTIC_READ_CACHE","ELASTIC_SPECIALIST_PLANNER","PENDING_WORK_LEDGER","DELTA_CAPSULE_COMPILER","DYNAMIC_SKILL_PAGER","INFORMATION_GAIN_STOP_RULE","UNNECESSARY_WORK_METER","TRACE_TO_REGRESSION","HOST_BINDING_CONTRACT","PRE_FINAL_EFFICIENCY_GATE","OTEL_SHAPED_SEMANTIC_SPAN"),False,False,False)
