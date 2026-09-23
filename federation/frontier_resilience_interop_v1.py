from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

SCHEMA = "FUSE-FRONTIER-RESILIENCE-INTEROP-V1"
VERSION = "1.0.0"
AUTHORITY_CEILING = "A1_INTERNAL"
EXTERNAL_EFFECT_DEFAULT = False

def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256(raw).hexdigest()

class Decision(str, Enum):
    READY = "READY"
    REUSE = "REUSE"
    CREATE = "CREATE"
    HOLD = "HOLD"
    REJECT = "REJECT"

@dataclass(frozen=True, slots=True)
class AsyncJobHandle:
    job_id: str
    provider: str
    state: str
    idempotency_key: str
    effect_id: str = ""
    result_id: str = ""
    result_sha256: str = ""
    def validate(self) -> "AsyncJobHandle":
        if not self.job_id.strip() or not self.provider.strip() or not self.idempotency_key.strip():
            raise ValueError("ASYNC_JOB_IDENTITY_REQUIRED")
        if self.state not in {"QUEUED","IN_PROGRESS","COMPLETED","FAILED","CANCELLED"}:
            raise ValueError("ASYNC_JOB_STATE_INVALID")
        if self.state == "COMPLETED" and (not self.result_id or not self.result_sha256):
            raise ValueError("ASYNC_JOB_COMPLETED_RESULT_REQUIRED")
        return self

@dataclass(frozen=True, slots=True)
class AsyncJobReconcileReceipt:
    decision: Decision
    state: str
    poll_allowed: bool
    push_allowed: bool
    effect_replay_allowed: bool
    reason: str

def reconcile_async_job(prior: AsyncJobHandle, observed: AsyncJobHandle) -> AsyncJobReconcileReceipt:
    prior.validate(); observed.validate()
    if (prior.job_id,prior.provider,prior.idempotency_key) != (observed.job_id,observed.provider,observed.idempotency_key):
        return AsyncJobReconcileReceipt(Decision.REJECT,"IDENTITY_MISMATCH",False,False,False,"job/provider/idempotency identity changed")
    if prior.effect_id and observed.effect_id and prior.effect_id != observed.effect_id:
        return AsyncJobReconcileReceipt(Decision.REJECT,"EFFECT_ID_MISMATCH",False,False,False,"effect identity changed")
    terminal={"COMPLETED","FAILED","CANCELLED"}
    if prior.state in terminal and observed.state != prior.state:
        return AsyncJobReconcileReceipt(Decision.REJECT,"TERMINAL_STATE_REGRESSION",False,False,False,"terminal state cannot regress")
    if prior.state=="COMPLETED" and (prior.result_id!=observed.result_id or prior.result_sha256!=observed.result_sha256):
        return AsyncJobReconcileReceipt(Decision.REJECT,"RESULT_IDENTITY_MISMATCH",False,False,False,"completed result identity changed")
    if observed.state=="COMPLETED":
        return AsyncJobReconcileReceipt(Decision.READY,"RESULT_READY",False,True,False,"deliver existing result; do not replay work")
    if observed.state in {"QUEUED","IN_PROGRESS"}:
        return AsyncJobReconcileReceipt(Decision.REUSE,"ASYNC_JOB_RUNNING",True,True,False,"poll/push against same job handle")
    return AsyncJobReconcileReceipt(Decision.READY,observed.state,False,True,False,"terminal readback never grants replay authority")

@dataclass(frozen=True, slots=True)
class ResumeSnapshot:
    run_id: str
    session_id: str
    snapshot_sha256: str
    pending_batch_sha256: str
    session_tail_sha256: str
    exclusive_owner_token: str

@dataclass(frozen=True, slots=True)
class ResumeGateReceipt:
    decision: Decision
    state: str
    rerun_completed_tools: bool
    reason: str

def exact_resume_gate(snapshot: ResumeSnapshot, *, observed_session_tail_sha256: str, owner_token: str, concurrent_resume: bool=False) -> ResumeGateReceipt:
    required=(snapshot.run_id,snapshot.session_id,snapshot.snapshot_sha256,snapshot.session_tail_sha256,snapshot.exclusive_owner_token)
    if not all(str(x).strip() for x in required):
        raise ValueError("RESUME_SNAPSHOT_IDENTITY_REQUIRED")
    if concurrent_resume:
        return ResumeGateReceipt(Decision.REJECT,"CONCURRENT_RESUME_REJECTED",False,"one session history owner at a time")
    if owner_token != snapshot.exclusive_owner_token:
        return ResumeGateReceipt(Decision.REJECT,"RESUME_OWNER_MISMATCH",False,"exclusive resume ownership changed")
    if observed_session_tail_sha256 != snapshot.session_tail_sha256:
        return ResumeGateReceipt(Decision.HOLD,"SESSION_HISTORY_AMBIGUOUS",False,"repair/reconcile history before resume")
    state="RESUME_PENDING_BATCH_EXACTLY_ONCE" if snapshot.pending_batch_sha256 else "RESUME_FROM_SNAPSHOT"
    return ResumeGateReceipt(Decision.READY,state,False,"resume without rerunning completed tools")

@dataclass(frozen=True, slots=True)
class ToolCatalogueCacheEntry:
    subject: str
    payload_sha256: str
    fetched_at_ms: int
    ttl_ms: int
    cache_scope: str
    capability_epoch: str
    auth_epoch: str

@dataclass(frozen=True, slots=True)
class CacheDecision:
    reusable: bool
    reason: str
    expires_at_ms: int

def tool_catalogue_cache_decision(entry: ToolCatalogueCacheEntry, *, now_ms: int, required_scope: str, capability_epoch: str, auth_epoch: str) -> CacheDecision:
    if min(entry.ttl_ms,entry.fetched_at_ms,now_ms) < 0:
        raise ValueError("TOOL_CACHE_TIME_INVALID")
    expires=entry.fetched_at_ms+entry.ttl_ms
    if entry.cache_scope != required_scope: return CacheDecision(False,"CACHE_SCOPE_MISMATCH",expires)
    if entry.capability_epoch != capability_epoch: return CacheDecision(False,"CAPABILITY_EPOCH_CHANGED",expires)
    if entry.auth_epoch != auth_epoch: return CacheDecision(False,"AUTH_EPOCH_CHANGED",expires)
    if now_ms > expires: return CacheDecision(False,"TTL_EXPIRED",expires)
    return CacheDecision(True,"CACHE_CURRENT",expires)

@dataclass(frozen=True, slots=True)
class StatefulTask:
    task_id: str
    context_id: str
    state: str
    artifact_ids: tuple[str,...]=()
    subscription_id: str=""

@dataclass(frozen=True, slots=True)
class TaskDeliveryReceipt:
    decision: Decision
    same_task_identity: bool
    terminal: bool
    resubscribe_allowed: bool
    push_allowed: bool
    artifact_ids: tuple[str,...]

def task_delivery_plan(task: StatefulTask, *, requested_task_id: str, requested_context_id: str) -> TaskDeliveryReceipt:
    if not task.task_id or not task.context_id: raise ValueError("TASK_IDENTITY_REQUIRED")
    same=task.task_id==requested_task_id and task.context_id==requested_context_id
    if not same: return TaskDeliveryReceipt(Decision.REJECT,False,False,False,False,())
    terminal=task.state in {"COMPLETED","FAILED","CANCELLED","REJECTED"}
    return TaskDeliveryReceipt(Decision.REUSE,True,terminal,not terminal,bool(task.subscription_id),tuple(task.artifact_ids))

@dataclass(frozen=True, slots=True)
class OffscreenContextPlan:
    decision: Decision
    existing_context_count: int
    creation_singleflight_required: bool
    writer_authority_granted: bool
    reason: str

def offscreen_context_plan(*, existing_context_count: int, creation_inflight: bool, dom_helper_required: bool) -> OffscreenContextPlan:
    if existing_context_count < 0: raise ValueError("OFFSCREEN_CONTEXT_COUNT_INVALID")
    if not dom_helper_required: return OffscreenContextPlan(Decision.READY,existing_context_count,False,False,"helper not required")
    if existing_context_count > 1: return OffscreenContextPlan(Decision.REJECT,existing_context_count,True,False,"duplicate helper contexts")
    if existing_context_count == 1: return OffscreenContextPlan(Decision.REUSE,1,True,False,"reuse existing helper")
    if creation_inflight: return OffscreenContextPlan(Decision.REUSE,0,True,False,"await in-flight singleflight creation")
    return OffscreenContextPlan(Decision.CREATE,0,True,False,"create one helper; effect authority remains elsewhere")

@dataclass(frozen=True, slots=True)
class WorkflowVersionReceipt:
    decision: Decision
    state: str
    replay_effects_allowed: bool
    reason: str

def workflow_version_gate(*, history_version: str, code_version: str, compatible_versions: Iterable[str], history_complete: bool) -> WorkflowVersionReceipt:
    allowed={str(v) for v in compatible_versions}
    if not history_complete: return WorkflowVersionReceipt(Decision.HOLD,"HISTORY_INCOMPLETE",False,"durable history incomplete")
    if history_version==code_version or history_version in allowed:
        return WorkflowVersionReceipt(Decision.READY,"REPLAY_COMPATIBLE",False,"replay history; completed effects remain history")
    return WorkflowVersionReceipt(Decision.HOLD,"VERSION_MIGRATION_REQUIRED",False,"incompatible history requires explicit migration/version gate")

@dataclass(frozen=True, slots=True)
class WorkerSlotPlan:
    desired_slots: int
    state: str
    reason: str

def adaptive_worker_slots(*, backlog: int, current_slots: int, min_slots: int, max_slots: int, cpu_fraction: float, memory_fraction: float) -> WorkerSlotPlan:
    if min_slots<0 or max_slots<min_slots or current_slots<0 or backlog<0: raise ValueError("WORKER_SLOT_BOUNDS_INVALID")
    if not 0<=cpu_fraction<=1 or not 0<=memory_fraction<=1: raise ValueError("WORKER_RESOURCE_FRACTION_INVALID")
    pressure=max(cpu_fraction,memory_fraction)
    if backlog==0: desired,reason=min_slots,"no backlog"
    elif pressure>=0.9: desired,reason=max(min_slots,min(current_slots,max_slots)),"resource pressure high"
    elif pressure<=0.6 and backlog>current_slots:
        desired,reason=min(max_slots,max(min_slots,current_slots+max(1,min(backlog-current_slots,4)))),"backlog with resource headroom"
    else: desired,reason=min(max_slots,max(min_slots,current_slots)),"hold inside resource envelope"
    return WorkerSlotPlan(desired,"SLOT_PLAN_READY",reason)

@dataclass(frozen=True, slots=True)
class LocalRuntimeQualification:
    decision: Decision
    supported_features: tuple[str,...]
    missing_features: tuple[str,...]
    provider_effect_authorized: bool

def local_openai_compatibility_gate(*, model_listing: bool, responses: bool, tools: bool, mcp: bool, stateful_chat: bool, local_only: bool) -> LocalRuntimeQualification:
    observed={"models":model_listing,"responses":responses,"tools":tools,"mcp":mcp,"stateful_chat":stateful_chat,"local_only":local_only}
    required=("models","responses","tools","mcp","stateful_chat","local_only")
    supported=tuple(k for k in required if observed[k]); missing=tuple(k for k in required if not observed[k])
    return LocalRuntimeQualification(Decision.READY if not missing else Decision.HOLD,supported,missing,False)

@dataclass(frozen=True, slots=True)
class FailureDomainVector:
    route_id: str
    domains: Mapping[str,str]

@dataclass(frozen=True, slots=True)
class PlacementReceipt:
    decision: Decision
    independent_dimensions: tuple[str,...]
    shared_dimensions: tuple[str,...]
    min_cut_cardinality: int
    reason: str

def failure_domain_placement(primary: FailureDomainVector, challenger: FailureDomainVector, *, required_dimensions: Sequence[str]) -> PlacementReceipt:
    if not primary.route_id or not challenger.route_id or primary.route_id==challenger.route_id:
        raise ValueError("DISTINCT_ROUTE_IDENTITIES_REQUIRED")
    independent=[]; shared=[]; unknown=[]
    for dim in required_dimensions:
        a=str(primary.domains.get(dim,"")).strip(); b=str(challenger.domains.get(dim,"")).strip()
        if not a or not b: unknown.append(dim)
        elif a==b: shared.append(dim)
        else: independent.append(dim)
    if unknown: return PlacementReceipt(Decision.HOLD,tuple(independent),tuple(shared+unknown),1,"unknown domains cannot count as independent")
    min_cut=1 if shared else 2
    return PlacementReceipt(Decision.READY if min_cut>=2 else Decision.HOLD,tuple(independent),tuple(shared),min_cut,"independent placement proven" if min_cut>=2 else "shared failure domain remains")

@dataclass(frozen=True, slots=True)
class OAuthBindingReceipt:
    decision: Decision
    issuer_valid: bool
    application_type_valid: bool
    redirect_class_valid: bool
    reason: str

def oauth_binding_gate(*, expected_issuer: str, observed_issuer: str, application_type: str, redirect_uri: str) -> OAuthBindingReceipt:
    issuer_valid=bool(expected_issuer.strip()) and expected_issuer==observed_issuer
    app=application_type.strip().lower(); app_valid=app in {"native","web"}
    loopback=redirect_uri.startswith("http://127.0.0.1") or redirect_uri.startswith("http://localhost")
    redirect_valid=bool(redirect_uri.strip()) and (not loopback or app=="native")
    if not issuer_valid: return OAuthBindingReceipt(Decision.REJECT,False,app_valid,redirect_valid,"authorization issuer mismatch")
    if not app_valid: return OAuthBindingReceipt(Decision.REJECT,True,False,redirect_valid,"application type unsupported")
    if not redirect_valid: return OAuthBindingReceipt(Decision.REJECT,True,True,False,"redirect class inconsistent with application type")
    return OAuthBindingReceipt(Decision.READY,True,True,True,"OAuth binding structurally valid")

def module_summary() -> dict[str, object]:
    return {
        "schema":SCHEMA,"version":VERSION,"authority_ceiling":AUTHORITY_CEILING,
        "external_effect_default":EXTERNAL_EFFECT_DEFAULT,
        "capability_ids":tuple(f"AGF-{i:03d}" for i in range(54,64)),
        "provider_effect_authorized":False,"clean_room_mechanism_contracts":True,
        "summary_sha256":_digest({"schema":SCHEMA,"version":VERSION,"genes":tuple(f"AGF-{i:03d}" for i in range(54,64)),"authority":AUTHORITY_CEILING}),
    }
