from __future__ import annotations

"""CFBE-Ω Ultimate Execution Spine v1.

Composes existing Bubbles authority routing, AAA failure memory and Living State.
No provider authority is created here. Automatic workarounds are read/internal only.
"""

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import inspect, json, time
from typing import Any, Callable, Mapping

from bubbles.control_plane import ActionRequest, BubblesControlPlane, EffectClass
from evidenceops.build_system.aaa_chat_resilience import evaluate_failure_with_aaa
from federation.living_state.ingress import IngressEnvelope, LivingStateIngress
from federation.living_state.types import NodeKind, ProofMaturity


def _digest(v: Any) -> str:
    return sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class State(str, Enum):
    SUCCESS="SUCCESS"; FAILED="FAILED"; BLOCKED="BLOCKED"
    SKIP_LOW_VALUE="SKIP_LOW_VALUE"; RESUME_HIT="RESUME_HIT"

@dataclass(frozen=True)
class Task:
    task_id: str
    route_id: str
    adapter_id: str
    action: str
    effect: EffectClass = EffectClass.READ
    target_alias: str = "LOCAL"
    depends_on: tuple[str,...] = ()
    required: bool = True
    info_gain: float = 1.0
    proofs: frozenset[str] = frozenset()
    retries: int = 1
    payload: Mapping[str,object] = field(default_factory=dict)

    def validate(self):
        if not all((self.task_id,self.route_id,self.adapter_id,self.action)): raise ValueError("task identity required")
        if not 0 <= self.info_gain <= 1: raise ValueError("info_gain")
        if self.retries not in range(0,6): raise ValueError("retries")
        if self.task_id in self.depends_on: raise ValueError("self dependency")
        return self

    @property
    def fingerprint(self):
        body=asdict(self); body["effect"]=self.effect.value; body["proofs"]=sorted(self.proofs)
        return _digest(body)

@dataclass
class Result:
    task_id: str
    fingerprint: str
    state: State
    route_id: str
    attempts: int = 0
    value_digest: str = ""
    failure_fingerprint: str = ""
    failure_class: str = ""
    workaround: str = ""
    reason: str = ""
    learning_receipt: str = ""

@dataclass
class Capsule:
    mission_id: str
    objective: str
    source_anchor: str
    results: dict[str,Result] = field(default_factory=dict)
    recovery_checkpoint: dict[str,Any] = field(default_factory=dict)
    recurrence: dict[str,int] = field(default_factory=dict)
    traces: list[dict[str,Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    state: str = "RUNNING"

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def from_json(cls, raw: str) -> "Capsule":
        body=json.loads(raw)
        body["results"]={
            key:Result(**{**value,"state":State(value["state"])})
            for key,value in body.get("results",{}).items()
        }
        return cls(**body)

    @property
    def capsule_sha256(self) -> str:
        return _digest(json.loads(self.to_json()))

@dataclass(frozen=True)
class Mission:
    mission_id: str
    objective: str
    source_anchor: str
    tasks: tuple[Task,...]
    info_gain_floor: float = .12

    def validate(self):
        ids=set()
        for t in self.tasks:
            t.validate()
            if t.task_id in ids: raise ValueError("duplicate task")
            ids.add(t.task_id)
        missing={d for t in self.tasks for d in t.depends_on if d not in ids}
        if missing: raise ValueError(f"missing dependencies:{sorted(missing)}")
        return self

def classify(exc: BaseException) -> str:
    text=f"{type(exc).__name__}:{exc}".lower()
    for name,tokens in (
        ("STALE_SOURCE",("stale","anchor_moved","cas_drift","main drift")),
        ("RATE_LIMIT",("429","rate limit","quota")),
        ("AUTHORITY_BLOCKED",("403","permission","authority","forbidden","unauthorized")),
        ("SEMANTIC_READBACK",("readback","semantic mismatch","verification mismatch")),
        ("TOOL_UNAVAILABLE",("not found","unavailable","missing tool","connector unavailable")),
        ("CONFLICT",("conflict","collision","409","locked")),
    ):
        if any(x in text for x in tokens): return name
    if isinstance(exc,(ValueError,TypeError,KeyError)): return "INVALID_INPUT"
    if isinstance(exc,(TimeoutError,ConnectionError,OSError)): return "TRANSIENT_PROVIDER"
    return "UNKNOWN"

def choose_workaround(kind: str, retry_allowed: bool) -> tuple[str,bool]:
    if kind=="STALE_SOURCE": return "REANCHOR_AND_REPLAN",False
    if kind=="AUTHORITY_BLOCKED": return "HOLD_EFFECT_CONTINUE_SAFE_LANES",False
    if kind=="SEMANTIC_READBACK": return "QUARANTINE_AND_VERIFY",True
    if kind=="CONFLICT": return "SERIALIZE_AND_REFRESH",False
    if kind=="RATE_LIMIT": return "ALTERNATE_READ_ROUTE",True
    if kind=="TOOL_UNAVAILABLE": return "ALTERNATE_READ_ROUTE",True
    if kind=="INVALID_INPUT": return "DIAGNOSTIC_FALLBACK",True
    if kind=="TRANSIENT_PROVIDER" and retry_allowed: return "BOUNDED_RETRY",True
    return "DIAGNOSTIC_FALLBACK",True

def learning_envelope(mission: Mission, task: Task, event: Mapping[str,Any], recurrence: int, aaa: Mapping[str,Any]) -> IngressEnvelope:
    fp=str(event["failure_fingerprint"])
    refs=tuple(sorted(task.proofs)) or ("execution-spine:local-failure",)
    return IngressEnvelope(
        event_id=f"learning:{fp}:{recurrence}", event_class="LEARNING",
        source_ref=f"mission:{mission.mission_id}", observed_at=_now(),
        proof_ref=f"failure:{fp}", proof_maturity=ProofMaturity.RUNTIME_READBACK,
        object_id=f"learning:{fp[:32]}", object_kind=NodeKind.LEARNING.value, state="OBSERVED",
        payload={
            "learning_class":"FAILURE","fingerprint":fp,"route_id":task.route_id,
            "signal":str(event["message"])[:500],"diagnosis":str(event["failure_class"]),
            "hypothesis":"Use changed preconditions or a materially different route; never expand authority.",
            "test_ref":f"task:{task.task_id}","result_ref":f"aaa:{aaa.get('aaa_receipt_sha256','unsealed')}",
            "proof_refs":refs,"recurrence":recurrence,"independent_evidence":False,
        },
        ttl_seconds=86400, confidence=.95, authority_ceiling="A1_INTERNAL"
    )

Executor=Callable[[Task],Any]

class UltimateExecutionSpine:
    def __init__(self, *, control: BubblesControlPlane|None=None, ingress: LivingStateIngress|None=None):
        self.control=control or BubblesControlPlane()
        self.ingress=ingress

    async def run(self, mission: Mission, *, executors: Mapping[str,Executor],
                  alternates: Mapping[str,Executor]|None=None, capsule: Capsule|None=None,
                  current_anchor: Callable[[],str]|None=None) -> Capsule:
        mission.validate()
        cap=capsule or Capsule(mission.mission_id,mission.objective,mission.source_anchor)
        if cap.mission_id!=mission.mission_id or cap.source_anchor!=mission.source_anchor: raise ValueError("capsule mismatch")
        if current_anchor and current_anchor()!=mission.source_anchor:
            cap.state="HOLD_STALE_SOURCE"; cap.blockers.append("REANCHOR_REQUIRED"); return cap

        tasks={t.task_id:t for t in mission.tasks}
        reverse={k:set() for k in tasks}
        for t in mission.tasks:
            for d in t.depends_on: reverse[d].add(t.task_id)
        pending=set(tasks)
        ok={State.SUCCESS,State.RESUME_HIT,State.SKIP_LOW_VALUE}

        while pending:
            progressed=False
            for tid in list(pending):
                t=tasks[tid]; prev=cap.results.get(tid)
                if prev and prev.state is State.SUCCESS and prev.fingerprint==t.fingerprint:
                    cap.results[tid]=Result(tid,t.fingerprint,State.RESUME_HIT,prev.route_id,prev.attempts,prev.value_digest)
                    pending.remove(tid); progressed=True
            runnable=[]
            for tid in sorted(pending):
                t=tasks[tid]; deps=[cap.results.get(d) for d in t.depends_on]
                if any(r and r.state in {State.FAILED,State.BLOCKED} for r in deps):
                    cap.results[tid]=Result(tid,t.fingerprint,State.BLOCKED,t.route_id,reason="DEPENDENCY_BLOCKED")
                    pending.remove(tid); progressed=True; continue
                if not all(r and r.state in ok for r in deps): continue
                downstream_required=any(tasks[c].required for c in reverse[tid])
                if not t.required and not downstream_required and t.info_gain<mission.info_gain_floor:
                    cap.results[tid]=Result(tid,t.fingerprint,State.SKIP_LOW_VALUE,t.route_id,reason="LOW_INFORMATION_VALUE")
                    pending.remove(tid); progressed=True; continue
                runnable.append(t)
            if runnable:
                rows=await asyncio.gather(*(self._one(mission,t,cap,executors,alternates or {},current_anchor) for t in runnable))
                for r in rows: cap.results[r.task_id]=r; pending.discard(r.task_id)
                progressed=True
            if not progressed:
                cap.state="HOLD_DEPENDENCY_DEADLOCK"; cap.blockers.append(",".join(sorted(pending))); break

        if cap.state=="RUNNING":
            req=[cap.results.get(t.task_id) for t in mission.tasks if t.required]
            cap.state="COMPLETE_VERIFIED_LOCAL" if all(r and r.state in {State.SUCCESS,State.RESUME_HIT} for r in req) else "PARTIAL_WITH_BLOCKERS"
        return cap

    async def _one(self, mission: Mission, task: Task, cap: Capsule, executors: Mapping[str,Executor],
                   alternates: Mapping[str,Executor], current_anchor: Callable[[],str]|None) -> Result:
        if current_anchor and task.effect is not EffectClass.READ and current_anchor()!=mission.source_anchor:
            return Result(task.task_id,task.fingerprint,State.BLOCKED,task.route_id,reason="STALE_SOURCE_BEFORE_EFFECT")
        decision=self.control.decide(ActionRequest(task.adapter_id,task.action,task.effect,task.target_alias,task.payload), task.proofs)
        if decision.state!="READY":
            return Result(task.task_id,task.fingerprint,State.BLOCKED,task.route_id,reason=decision.reason)
        executor=executors.get(task.task_id)
        if executor is None:
            return Result(task.task_id,task.fingerprint,State.FAILED,task.route_id,failure_class="TOOL_UNAVAILABLE",reason="EXECUTOR_NOT_REGISTERED")

        started=time.time(); attempts=0
        while attempts<=task.retries:
            attempts+=1
            try:
                value=await self._invoke(executor,task)
                cap.traces.append({"task_id":task.task_id,"route_id":task.route_id,"effect":task.effect.value,
                                   "duration_ms":(time.time()-started)*1000,"status":"OK","source_anchor":mission.source_anchor,
                                   "gen_ai.operation.name":"tool_call","tool.name":task.action})
                return Result(task.task_id,task.fingerprint,State.SUCCESS,task.route_id,attempts,_digest(value))
            except BaseException as exc:
                kind=classify(exc)
                fp=_digest({"task":task.task_id,"route":task.route_id,"kind":kind,"type":type(exc).__name__,"message":str(exc)[:500]})
                event={
                    "event_id":f"spine-failure:{fp[:24]}:{attempts}","objective":mission.objective,
                    "route_id":task.route_id,"route_fingerprint":task.fingerprint,
                    "precondition_fingerprint":_digest({"source_anchor":mission.source_anchor,"proofs":sorted(task.proofs),"payload":dict(task.payload)}),
                    "attempted_at":_now(),"owner_burden":0.0,"proof_quality":1.0,
                    "failure_class":kind,"failure_fingerprint":fp,"message":str(exc)[:500],
                    "evidence_ids":tuple(task.proofs),
                    "route_history":tuple(cap.recovery_checkpoint.get("aaa_route_history",()))
                }
                aaa=evaluate_failure_with_aaa(event,previous_checkpoint=cap.recovery_checkpoint)
                effective=aaa.get("effective_recovery",{})
                if isinstance(effective,Mapping) and isinstance(effective.get("checkpoint"),Mapping):
                    cap.recovery_checkpoint=dict(effective["checkpoint"])
                recurrence=cap.recurrence.get(fp,0)+1; cap.recurrence[fp]=recurrence
                learning_receipt=""
                try:
                    env=learning_envelope(mission,task,event,recurrence,aaa)
                    learning_receipt=self.ingress.ingest(env).receipt_sha256 if self.ingress else env.envelope_sha256
                except Exception as learn_exc:
                    cap.blockers.append(f"LEARNING_PERSISTENCE_DEGRADED:{type(learn_exc).__name__}")
                retry=aaa.get("aaa_route_retry"); retry_allowed=True if retry is None else bool(retry.get("retry_allowed"))
                workaround,auto=choose_workaround(kind,retry_allowed)
                if workaround=="BOUNDED_RETRY" and auto and attempts<=task.retries: continue
                alternate=alternates.get(workaround)
                if alternate and auto and task.effect is EffectClass.READ and workaround in {
                    "ALTERNATE_READ_ROUTE","DIAGNOSTIC_FALLBACK","QUARANTINE_AND_VERIFY"}:
                    try:
                        value=await self._invoke(alternate,task)
                        cap.traces.append({"task_id":task.task_id,"route_id":f"{task.route_id}:{workaround}",
                                           "effect":"READ","duration_ms":(time.time()-started)*1000,
                                           "status":"WORKAROUND_OK","source_anchor":mission.source_anchor,
                                           "gen_ai.operation.name":"tool_call","tool.name":task.action,
                                           "federation.workaround":workaround})
                        return Result(task.task_id,task.fingerprint,State.SUCCESS,f"{task.route_id}:{workaround}",
                                      attempts+1,_digest(value),fp,kind,workaround,"RECOVERED",learning_receipt)
                    except BaseException:
                        pass
                cap.traces.append({"task_id":task.task_id,"route_id":task.route_id,"effect":task.effect.value,
                                   "duration_ms":(time.time()-started)*1000,"status":"ERROR",
                                   "failure_class":kind,"failure_fingerprint":fp,"workaround":workaround,
                                   "gen_ai.operation.name":"tool_call","tool.name":task.action})
                return Result(task.task_id,task.fingerprint,State.FAILED,task.route_id,attempts,
                              failure_fingerprint=fp,failure_class=kind,workaround=workaround,
                              reason=str(exc)[:500],learning_receipt=learning_receipt)
        raise RuntimeError("unreachable")

    @staticmethod
    async def _invoke(executor: Executor, task: Task) -> Any:
        value=executor(task)
        return await value if inspect.isawaitable(value) else value

__all__=["Capsule","Mission","Result","State","Task","UltimateExecutionSpine","choose_workaround","classify","learning_envelope"]
