from __future__ import annotations

# ---- routing.py ----
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

class CapabilityLifecycle(str, Enum):
    PROPOSED='PROPOSED'; INCUBATING='INCUBATING'; VALIDATED='VALIDATED'; CHALLENGER='CHALLENGER'; ADMITTED='ADMITTED'; CHAMPION='CHAMPION'; DECLINING='DECLINING'; QUARANTINED='QUARANTINED'; RETIRED='RETIRED'; ARCHIVED='ARCHIVED'

@dataclass(frozen=True)
class MissionContract:
    mission_id: str
    mission_class: str
    desired_outcome: str
    acceptance_metrics: tuple[str,...]
    hard_vetoes: tuple[str,...]
    max_cost: float
    external_effect_authority: str='NONE'
    privacy_class: str='PRIVATE'

@dataclass(frozen=True)
class CapabilityCandidate:
    capability_id: str
    role_family: str
    quality: float
    reliability: float
    information_gain: float
    fallback_value: float
    expected_cost: float
    expected_latency: float
    owner_burden: float
    regression_risk: float
    privacy_allowed: bool=True
    authority_allowed: bool=True
    evidence_floor_met: bool=True
    runtime_healthy: bool=True
    budget_available: bool=True
    epistemic_reputation: float=0.5
    lifecycle: CapabilityLifecycle=CapabilityLifecycle.VALIDATED

@dataclass(frozen=True)
class RouteWeights:
    quality: float=1.0; reliability: float=1.0; information_gain: float=0.5; fallback_value: float=0.25
    cost: float=0.5; latency: float=0.25; owner_burden: float=0.5; regression_risk: float=1.0; reputation: float=0.5

@dataclass(frozen=True)
class RouteDecision:
    selected_capability_id: str
    utility: float
    admissible_count: int
    rejected: tuple[tuple[str,str],...]

class ConstrainedRouteSelector:
    @staticmethod
    def admissibility_reason(c: CapabilityCandidate, mission: MissionContract) -> str|None:
        if not c.privacy_allowed: return 'PRIVACY_NOT_ALLOWED'
        if not c.authority_allowed: return 'AUTHORITY_NOT_ALLOWED'
        if not c.evidence_floor_met: return 'EVIDENCE_FLOOR_NOT_MET'
        if not c.runtime_healthy: return 'RUNTIME_UNHEALTHY'
        if not c.budget_available or c.expected_cost > mission.max_cost: return 'BUDGET_NOT_AVAILABLE'
        if c.lifecycle in {CapabilityLifecycle.QUARANTINED, CapabilityLifecycle.RETIRED, CapabilityLifecycle.ARCHIVED}:
            return f'LIFECYCLE_{c.lifecycle.value}'
        return None

    @staticmethod
    def utility(c: CapabilityCandidate, w: RouteWeights) -> float:
        return (w.quality*c.quality + w.reliability*c.reliability + w.information_gain*c.information_gain +
                w.fallback_value*c.fallback_value + w.reputation*c.epistemic_reputation - w.cost*c.expected_cost -
                w.latency*c.expected_latency - w.owner_burden*c.owner_burden - w.regression_risk*c.regression_risk)

    def select(self, mission: MissionContract, candidates: Sequence[CapabilityCandidate], weights: RouteWeights) -> RouteDecision:
        admissible=[]; rejected=[]
        for c in candidates:
            reason=self.admissibility_reason(c, mission)
            (rejected if reason else admissible).append((c.capability_id, reason) if reason else c)
        if not admissible: raise ValueError('NO_ADMISSIBLE_ROUTE')
        score,winner=max(((self.utility(c,weights),c) for c in admissible), key=lambda x:(x[0],x[1].capability_id))
        return RouteDecision(winner.capability_id, score, len(admissible), tuple(sorted(rejected)))

@dataclass(frozen=True)
class ChallengerTrigger:
    high_impact: bool=False
    evidence_incomplete: bool=False
    confidence: float=1.0
    contradiction_present: bool=False
    route_drifted: bool=False
    novelty: float=0.0
    expected_information_gain: float=0.0
    challenger_cost: float=0.0

class SelectiveParallelism:
    @staticmethod
    def should_challenge(t: ChallengerTrigger, confidence_floor: float=0.8) -> bool:
        return any([t.high_impact,t.evidence_incomplete,t.confidence<confidence_floor,t.contradiction_present,t.route_drifted,t.novelty>=0.8,t.expected_information_gain>t.challenger_cost])

# ---- governance.py ----
import hashlib,hmac,json,secrets,time
from dataclasses import asdict,dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

class ClaimState(str,Enum):
    VERIFIED='VERIFIED'; USER_SUPPLIED='USER_SUPPLIED'; INFERENCE='INFERENCE'; UNVERIFIED='UNVERIFIED'; PROOF_GAP='PROOF_GAP'; CONTRADICTED='CONTRADICTED'; SUPERSEDED='SUPERSEDED'

@dataclass(frozen=True)
class EvidenceClaim:
    claim_id:str; claim_hash:str; state:ClaimState; source_ids:tuple[str,...]=(); contradictions:tuple[str,...]=(); decision_effect:str|None=None

class EvidenceVetoEngine:
    @classmethod
    def validate(cls, claims:Sequence[EvidenceClaim])->list[str]:
        vetoes=[]
        for c in claims:
            if c.state==ClaimState.VERIFIED and not c.source_ids: vetoes.append(f'{c.claim_id}:VERIFIED_WITHOUT_SOURCE')
            if c.state==ClaimState.CONTRADICTED and c.decision_effect=='PROMOTE': vetoes.append(f'{c.claim_id}:CONTRADICTED_PROMOTION')
        return vetoes

@dataclass(frozen=True)
class CapabilityToken:
    token_id:str; mission_id:str; operation_id:str; actor_id:str; connector:str; action:str; target:str; provider:str|None; purpose:str
    max_spend:float; max_calls:int; expires_at:float; rollback_required:bool; nonce:str; signature:str

class CapabilityGateway:
    def __init__(self,signing_key:bytes):
        if len(signing_key)<16: raise ValueError('signing key too short')
        self._key=signing_key; self._reserved=set(); self._consumed=set()
    def _payload(self,v:Mapping[str,Any])->bytes: return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
    def issue(self,*,mission_id:str,operation_id:str,actor_id:str,connector:str,action:str,target:str,provider:str|None,purpose:str,max_spend:float,max_calls:int,ttl_seconds:float,rollback_required:bool,now:float|None=None)->CapabilityToken:
        now=time.time() if now is None else now
        raw={'token_id':secrets.token_hex(16),'mission_id':mission_id,'operation_id':operation_id,'actor_id':actor_id,'connector':connector,'action':action,'target':target,'provider':provider,'purpose':purpose,'max_spend':max_spend,'max_calls':max_calls,'expires_at':now+ttl_seconds,'rollback_required':rollback_required,'nonce':secrets.token_hex(16)}
        sig=hmac.new(self._key,self._payload(raw),hashlib.sha256).hexdigest(); return CapabilityToken(**raw,signature=sig)
    def verify(self,t:CapabilityToken,*,now:float|None=None)->None:
        now=time.time() if now is None else now; v=asdict(t); sig=v.pop('signature'); expected=hmac.new(self._key,self._payload(v),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): raise ValueError('INVALID_CAPABILITY_SIGNATURE')
        if t.expires_at<now: raise ValueError('CAPABILITY_EXPIRED')
        if t.token_id in self._consumed: raise ValueError('CAPABILITY_ALREADY_CONSUMED')
    def reserve(self,t:CapabilityToken,*,now:float|None=None)->None:
        self.verify(t,now=now)
        if t.token_id in self._reserved: raise ValueError('CAPABILITY_ALREADY_RESERVED')
        self._reserved.add(t.token_id)
    def consume(self,t:CapabilityToken,*,now:float|None=None)->None:
        self.verify(t,now=now)
        if t.token_id not in self._reserved: raise ValueError('CAPABILITY_NOT_RESERVED')
        self._reserved.remove(t.token_id); self._consumed.add(t.token_id)

def otel_mission_attributes(*,mission_id:str,mission_class:str,stage:str,route_id:str,route_role:str,accepted:bool|None,evidence_coverage:float|None,hard_veto_count:int,owner_interventions:int,owner_intervention_seconds:float,rollback_available:bool,rollback_executed:bool,model_requested:str|None=None,model_resolved:str|None=None,mission_value:float|None=None,mission_cost:float|None=None,mission_risk:float|None=None,mission_dependencies:tuple[str,...]|None=None,route_context:str|None=None,route_outcome:str|None=None,counterfactual_id:str|None=None,checkpoint_id:str|None=None,capability_state:str|None=None,resource_state:str|None=None,opportunity_gradient:float|None=None,capability_gap:str|None=None,regression_baseline:str|None=None)->dict[str,Any]:
    d={'sovara.mission.id':mission_id,'sovara.mission.class':mission_class,'sovara.mission.stage':stage,'sovara.route.id':route_id,'sovara.route.role':route_role,'sovara.evidence.hard_veto_count':hard_veto_count,'sovara.owner.interventions':owner_interventions,'sovara.owner.intervention_seconds':owner_intervention_seconds,'sovara.rollback.available':rollback_available,'sovara.rollback.executed':rollback_executed}
    optional={'sovara.mission.value':mission_value,'sovara.mission.cost':mission_cost,'sovara.mission.risk':mission_risk,'sovara.mission.dependencies':mission_dependencies,'sovara.route.context':route_context,'sovara.route.outcome':route_outcome,'sovara.route.counterfactual':counterfactual_id,'sovara.mission.checkpoint':checkpoint_id,'sovara.capability.state':capability_state,'sovara.resource.state':resource_state,'sovara.opportunity.gradient':opportunity_gradient,'sovara.capability.gap':capability_gap,'sovara.regression.baseline':regression_baseline}
    if accepted is not None:d['sovara.outcome.accepted']=accepted
    if evidence_coverage is not None:d['sovara.evidence.coverage']=evidence_coverage
    if model_requested:d['gen_ai.request.model']=model_requested
    if model_resolved:d['gen_ai.response.model']=model_resolved
    for k,v in optional.items():
        if v is not None:d[k]=v
    return d

# ---- runtime.py ----
import hashlib,json
from dataclasses import dataclass
from typing import Any,Mapping,Protocol,Sequence

@dataclass(frozen=True)
class MissionCheckpoint:
    checkpoint_id:str; mission_id:str; sequence:int; state_hash:str; parent_checkpoint_id:str|None=None

class DurableMissionRuntime(Protocol):
    def append_event(self,mission_id:str,event:Mapping[str,Any])->str:...
    def checkpoint(self,mission_id:str,state:Mapping[str,Any])->MissionCheckpoint:...
    def replay(self,mission_id:str)->Sequence[Mapping[str,Any]]:...
    def fork(self,checkpoint_id:str,new_mission_id:str)->str:...

class InMemoryDurableMissionRuntime:
    def __init__(self): self.events={}; self.checkpoints={}
    def append_event(self,mission_id,event):
        payload=dict(event); payload['sequence']=len(self.events.setdefault(mission_id,[])); self.events[mission_id].append(payload)
        return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    def checkpoint(self,mission_id,state):
        seq=len(self.events.setdefault(mission_id,[])); state_hash=hashlib.sha256(json.dumps(dict(state),sort_keys=True).encode()).hexdigest(); checkpoint_id=hashlib.sha256(f'{mission_id}|{seq}|{state_hash}'.encode()).hexdigest()[:32]
        cp=MissionCheckpoint(checkpoint_id,mission_id,seq,state_hash); self.checkpoints[checkpoint_id]=(cp,dict(state)); return cp
    def replay(self,mission_id): return tuple(dict(x) for x in self.events.get(mission_id,[]))
    def fork(self,checkpoint_id,new_mission_id):
        if checkpoint_id not in self.checkpoints: raise KeyError('CHECKPOINT_NOT_FOUND')
        cp,state=self.checkpoints[checkpoint_id]; self.events[new_mission_id]=[{'type':'FORK','from':checkpoint_id,'state_hash':cp.state_hash,'sequence':0}]; return new_mission_id

class CausalTimeTravelEngine:
    def __init__(self,runtime:DurableMissionRuntime): self.runtime=runtime
    def fork_counterfactual(self,checkpoint_id:str,branch_mission_id:str,substitution:Mapping[str,Any])->str:
        self.runtime.fork(checkpoint_id,branch_mission_id); self.runtime.append_event(branch_mission_id,{'type':'SUBSTITUTION',**dict(substitution)}); return branch_mission_id

# ---- evolution.py ----
from dataclasses import dataclass
from typing import Iterable,Sequence

@dataclass(frozen=True)
class MissionOutcome:
    mission_id:str; accepted:bool; quality:float; evidence_reliability:float; first_pass_probability:float; recovery_reliability:float; elapsed_time:float; normalized_cost:float; owner_burden:float

class MissionEfficiencyIndex:
    @staticmethod
    def calculate(o:MissionOutcome)->float:
        denominator=max(o.elapsed_time,1e-9)*max(o.normalized_cost,1e-9)*(1+max(o.owner_burden,0))
        return (o.quality*o.evidence_reliability*o.first_pass_probability*o.recovery_reliability)/denominator
    @staticmethod
    def improvement_ratio(new:MissionOutcome,baseline:MissionOutcome)->float:
        b=MissionEfficiencyIndex.calculate(baseline)
        if b<=0: raise ValueError('baseline MEI must be positive')
        return MissionEfficiencyIndex.calculate(new)/b

@dataclass(frozen=True)
class OpportunityCandidate:
    opportunity_id:str; expected_gain:float; confidence:float; reversibility:float; implementation_cost:float; regression_risk:float; owner_burden:float

class OpportunityGradientEngine:
    @staticmethod
    def score(c:OpportunityCandidate)->float:
        return (c.expected_gain*c.confidence*c.reversibility)/max(c.implementation_cost*c.regression_risk*(1+c.owner_burden),1e-9)
    def rank(self,candidates:Sequence[OpportunityCandidate]): return sorted(((self.score(c),c) for c in candidates),key=lambda x:(x[0],x[1].opportunity_id),reverse=True)

@dataclass(frozen=True)
class SequentialEvidenceState:
    accepted_missions:int; hard_vetoes:int; replications:int; confidence_analysis_complete:bool; primary_metric_ratio:float

class SequentialEvidenceEngine:
    def decision(self,s:SequentialEvidenceState)->str:
        if s.hard_vetoes>0:return 'HOLD_HARD_VETO'
        n=s.accepted_missions
        if n<1:return 'INSTRUMENT'
        if n<3:return 'VALIDATE_CHAIN'
        if n<10:return 'REPEATABILITY'
        if n<25:return 'PROVISIONAL_CHAMPION'
        if n<50:return 'LIMITED_CONTROLLED_TRAFFIC'
        if n<100:return 'STABILITY_ASSESSMENT'
        if s.replications>=3 and s.confidence_analysis_complete and s.primary_metric_ratio>=10:return 'TEN_X_CLAIM_ELIGIBLE'
        return 'STRONG_PERFORMANCE_ASSESSMENT'

class EpistemicReputation:
    @staticmethod
    def brier_update(reputation:float,prediction:float,actual:bool,learning_rate:float=0.2)->float:
        outcome=1.0 if actual else 0.0; reward=1-(prediction-outcome)**2; return min(1,max(0,(1-learning_rate)*reputation+learning_rate*reward))

@dataclass(frozen=True)
class EvolutionModule:
    module_id:str; expected_gain:float; confidence:float; reversibility:float; implementation_cost:float; regression_risk:float; complexity_delta:float; required_data_fields:tuple[str,...]=()
@dataclass(frozen=True)
class EvolutionDecision:
    module_id:str; opportunity_gradient:float; decision:str; reason:str

class CFBEEvolutionGate:
    def __init__(self,minimum_gradient:float=1.0,maximum_complexity_delta:float=1.0): self.minimum_gradient=minimum_gradient; self.maximum_complexity_delta=maximum_complexity_delta
    def evaluate(self,module:EvolutionModule,available_fields:Iterable[str])->EvolutionDecision:
        missing=sorted(set(module.required_data_fields)-set(available_fields))
        if missing:return EvolutionDecision(module.module_id,0,'HOLD','MISSING_DATA:'+','.join(missing))
        g=OpportunityGradientEngine.score(OpportunityCandidate(module.module_id,module.expected_gain,module.confidence,module.reversibility,module.implementation_cost,module.regression_risk,max(module.complexity_delta,0)))
        if module.complexity_delta>self.maximum_complexity_delta:return EvolutionDecision(module.module_id,g,'HOLD','COMPLEXITY_DELTA_TOO_HIGH')
        if g<self.minimum_gradient:return EvolutionDecision(module.module_id,g,'HOLD','INSUFFICIENT_OPPORTUNITY_GRADIENT')
        return EvolutionDecision(module.module_id,g,'ADMIT_TO_INCUBATION','POSITIVE_EXPECTED_VALUE')

# ---- v4_contract.py ----
from dataclasses import dataclass
from typing import Protocol,Sequence

@dataclass(frozen=True)
class Objective:
    objective_id:str; expected_value:float; urgency:float; strategic_alignment:float; information_gain:float; cost:float; risk:float; opportunity_cost:float
class ObjectiveEcology:
    @staticmethod
    def priority(o:Objective)->float:return (o.expected_value*o.urgency*o.strategic_alignment*o.information_gain)/max(o.cost*o.risk*o.opportunity_cost,1e-9)
    def rank(self,objectives:Sequence[Objective]):return sorted(((self.priority(o),o) for o in objectives),key=lambda x:(x[0],x[1].objective_id),reverse=True)

@dataclass(frozen=True)
class PortfolioMission:
    mission_id:str; expected_value:float; resource_cost:float; unlock_value:float; blocking_count:int; risk:float
class PortfolioOptimizer:
    @staticmethod
    def score(m:PortfolioMission)->float:return (m.expected_value+m.unlock_value+m.blocking_count)/max(m.resource_cost*(1+m.risk),1e-9)
    def rank(self,missions:Sequence[PortfolioMission]):return sorted(((self.score(m),m) for m in missions),key=lambda x:(x[0],x[1].mission_id),reverse=True)

class CausalWorldModel(Protocol):
    def predict(self,state_id:str,action_id:str,horizon:int)->dict:...
    def update(self,observation:dict)->None:...
class InstitutionalDigitalTwin(Protocol):
    def snapshot(self)->str:...
    def fork(self,snapshot_id:str,scenario_id:str)->str:...
    def simulate(self,scenario_id:str,horizon:int)->dict:...
class CapabilityFoundry(Protocol):
    def specify(self,gap:dict)->dict:...
    def search_reuse_candidates(self,specification:dict)->list[dict]:...
    def build_candidate(self,specification:dict)->dict:...
    def validate_candidate(self,candidate:dict)->dict:...

@dataclass(frozen=True)
class ResourceBudget:
    money:float; tokens:int; compute_seconds:float; owner_attention_seconds:float; risk_budget:float
class InstitutionalMetabolism:
    @staticmethod
    def mission_roi(accepted_value:float,resource_consumption:float)->float:return accepted_value/max(resource_consumption,1e-9)
    @staticmethod
    def capability_roi(value_created:float,lifecycle_cost:float)->float:return value_created/max(lifecycle_cost,1e-9)
