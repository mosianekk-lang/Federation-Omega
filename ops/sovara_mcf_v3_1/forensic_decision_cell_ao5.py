from __future__ import annotations

"""SOVARA-native JARVIS ΑΩ5 forensic decision-intelligence cell.

Portable/case-agnostic integration of the user-supplied ΑΩ5 specification.
SOVARA remains mission/route/effect-admission authority; JARVIS remains an
independent assurance/hold/challenge plane. This module has no provider-effect
executor and cannot mint provider authority.

Source specification SHA-256:
773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443
"""

from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
from hashlib import sha256
from math import prod
from typing import Any, Iterable, Mapping, Sequence
import json


class ExecutionState(IntEnum):
    S00_BOOT=0; S01_RESTORE=1; S02_VERIFY_RESTORE=2; S03_RECONCILE=3
    S04_OBJECTIVE_RESOLUTION=4; S05_ALPHA_DISCOVERY=5; S06_OMEGA_DEFINITION=6
    S07_PREFLIGHT=7; S08_DECOMPOSITION=8; S09_DAG_BUILD=9; S10_SCHEDULING=10
    S11_EXECUTION=11; S12_FAST_EVIDENCE_RELEASE=12; S13_DEEP_ANALYSIS=13
    S14_FAN_IN=14; S15_CONVERGENCE=15; S16_ADVERSARIAL_GATE=16
    S17_NEUTRAL_GATE=17; S18_SEMANTIC_QA=18; S19_PERSIST=19
    S20_READBACK_VERIFY=20; S21_RELEASE=21; S22_NEXT_ACTION=22
    S23_HANDOFF_PREP=23; S24_HANDOFF_READY=24; S25_CLOSED=25


class CapabilityRealityState(IntEnum):
    C0_CONCEPTUAL=0; C1_ACTIVE_TURN=1; C2_TOOL_BOUND=2
    C3_SCHEDULED=3; C4_PROVIDER_VERIFIED=4; C5_LIVE_RUNTIME=5


class ProofState(str, Enum):
    VERIFIED='VERIFIED'; PRELIMINARY='PRELIMINARY'; PARTIAL='PARTIAL'
    SUPPORTED_INFERENCE='SUPPORTED_INFERENCE'; GAP='GAP'
    CONTRADICTED='CONTRADICTED'; UNVERIFIED='UNVERIFIED'


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    name: str
    reality_state: CapabilityRealityState
    tool_binding: str|None=None
    required_input: tuple[str,...]=()
    execution_permission: str='NONE'
    last_verified: str|None=None
    limitations: tuple[str,...]=()

    def assert_claimable_as(self, claimed: CapabilityRealityState)->None:
        if claimed > self.reality_state:
            raise ValueError(
                f'CAPABILITY_REALITY_INFLATION:{self.capability_id}:'
                f'actual={self.reality_state.name}:claimed={claimed.name}'
            )


@dataclass(frozen=True)
class EvidenceQualityVector:
    authenticity: float; proximity: float; contemporaneity: float
    independence: float; completeness: float; specificity: float
    consistency: float; chain_of_custody: float
    admissibility_or_usability: float; decision_relevance: float
    def dimensions(self)->dict[str,float]: return asdict(self)


@dataclass(frozen=True)
class ConfidenceVector:
    source_confidence: float; fact_confidence: float; temporal_confidence: float
    actor_knowledge_confidence: float; authority_confidence: float
    causal_confidence: float; legal_fit_confidence: float
    policy_fit_confidence: float; theory_confidence: float
    remedy_confidence: float
    def dimensions(self)->dict[str,float]: return asdict(self)


@dataclass(frozen=True)
class AlphaRecord:
    alpha_id: str; alpha_type: str; date: str|None; source: str
    actor: str|None; event: str; proposition: str; authentication: str
    proof_state: ProofState; why_alpha: str; predecessor_check: str
    competing_alpha: tuple[str,...]=(); downstream_paths: tuple[str,...]=()


@dataclass(frozen=True)
class OmegaRecord:
    omega_id: str; omega_class: str; desired_state: str; decision_maker: str
    decision_required: str; required_elements: tuple[str,...]; burden: str
    required_facts: tuple[str,...]; required_evidence: tuple[str,...]
    procedural_preconditions: tuple[str,...]; remedy: str
    minimum_success_state: str; blockers: tuple[str,...]=()
    distance_to_omega: str='UNKNOWN'; active_paths: tuple[str,...]=()
    fallback_paths: tuple[str,...]=()


@dataclass(frozen=True)
class PathRecord:
    path_id: str; omega_id: str; objective: str
    required_elements: tuple[str,...]; supporting_facts: tuple[str,...]
    adverse_facts: tuple[str,...]; dependencies: tuple[str,...]
    shared_dependencies: tuple[str,...]
    legal_viability: float; factual_strength: float; evidence_strength: float
    decision_impact: float; remedy_value: float; timeliness: float
    risk: float; dependency_factor: float; execution_cost: float

    def relative_value(self)->float:
        n=prod(max(v,1e-9) for v in (
            self.legal_viability,self.factual_strength,self.evidence_strength,
            self.decision_impact,self.remedy_value,self.timeliness))
        d=prod(max(v,1e-9) for v in (
            self.risk,self.dependency_factor,self.execution_cost))
        return n/d


@dataclass(frozen=True)
class PreflightInput:
    file_count:int=0; page_count:int=0; annexure_count:int=0; format_count:int=0
    nested_object_count:int=0; domain_count:int=0; expected_ocr_load:int=0
    expected_visual_load:int=0; legal_research_load:int=0; tool_complexity:int=0
    path_count:int=0; stream_count:int=0; context_risk:int=0; failure_risk:int=0


@dataclass(frozen=True)
class PreflightResult:
    preflight_id:str; complexity:str; auto_decompose:bool
    lane_plan:tuple[str,...]; path_plan:tuple[str,...]; stream_plan:tuple[str,...]
    budgets:Mapping[str,int]; first_output_target:str; persistence_target:str
    handoff_threshold:str; state:str='PASS'


@dataclass(frozen=True)
class HarmonizationContract:
    integration_id:str
    sovara_role:str='MISSION_ROUTE_EFFECT_ADMISSION_AND_ORCHESTRATION'
    ao5_role:str='FORENSIC_DECISION_INTELLIGENCE_METHOD_CELL'
    jarvis_assurance_role:str='INDEPENDENT_ASSURANCE_HOLD_CHALLENGE'
    cfbe_role:str='INDEPENDENT_BENCHMARK_VALUE_LEARNING'
    sentinel_role:str='HEALTH_FRESHNESS_DRIFT_OBSERVER'
    realityguard_role:str='TRUTH_AND_EXECUTION_RECEIPT_GUARD'
    provider_effect_authority:str='SOVARA_PROOF_BOUND_EFFECT_LANE_ONLY'
    cross_project_case_data_transfer:bool=False
    source_spec_sha256:str='773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443'
    zero_dilution:bool=True


@dataclass
class DecisionDAG:
    nodes:dict[str,str]=field(default_factory=dict)
    edges:list[tuple[str,str,str]]=field(default_factory=list)

    def add_node(self,node_id:str,node_type:str)->None: self.nodes[node_id]=node_type

    def add_edge(self,source:str,relation:str,target:str)->None:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError('UNKNOWN_DAG_NODE')
        self.edges.append((source,relation,target))

    def hidden_spofs(self,path_dependencies:Mapping[str,Iterable[str]])->dict[str,tuple[str,...]]:
        rev:dict[str,set[str]]={}
        for path,deps in path_dependencies.items():
            for dep in deps: rev.setdefault(dep,set()).add(path)
        return {d:tuple(sorted(p)) for d,p in sorted(rev.items()) if len(p)>=2}

    def acyclic(self)->bool:
        outgoing={n:set() for n in self.nodes}; indegree={n:0 for n in self.nodes}
        for source,_,target in self.edges:
            if target not in outgoing[source]:
                outgoing[source].add(target); indegree[target]+=1
        queue=[n for n,d in indegree.items() if d==0]; seen=0
        while queue:
            n=queue.pop(); seen+=1
            for target in outgoing[n]:
                indegree[target]-=1
                if indegree[target]==0: queue.append(target)
        return seen==len(self.nodes)


class SemanticRegressionFirewall:
    FORBIDDEN_ESCALATIONS={
        ('MAY','DID'),('RISK','FINDING'),('ALLEGATION','FACT'),
        ('ACCESS','KNOWLEDGE'),('CHRONOLOGY','CAUSATION'),
        ('REFERRAL','ACCEPTANCE'),('PARTIAL','COMPLETE'),
        ('INSTITUTIONAL_FAILURE','PERSONAL_CULPABILITY'),('POSSIBILITY','INTENT')}

    @classmethod
    def check(cls,transitions:Iterable[tuple[str,str]])->tuple[str,...]:
        out=[]
        for before,after in transitions:
            key=(before.upper(),after.upper())
            if key in cls.FORBIDDEN_ESCALATIONS: out.append(f'{key[0]}->{key[1]}')
        return tuple(sorted(out))


class EvidenceIndependenceEngine:
    @staticmethod
    def classify(origin_ids:Sequence[str],actor_ids:Sequence[str]=())->dict[str,Any]:
        total=len(origin_ids); independent=len(set(origin_ids)); derivative=max(total-independent,0)
        ratio=(independent/total) if total else 0
        if independent<=1: cls='EIS-E SINGLE_ORIGIN'
        elif ratio<.5: cls='EIS-D DERIVATIVE_HEAVY'
        elif ratio<.8: cls='EIS-C MIXED'
        elif derivative: cls='EIS-B SUBSTANTIALLY_INDEPENDENT'
        else: cls='EIS-A STRONGLY_INDEPENDENT'
        return {'origin_count':total,'derivative_count':derivative,
                'independent_source_count':independent,
                'actor_independence':len(set(actor_ids)) if actor_ids else None,
                'class':cls}


class FailureLearningModel:
    @staticmethod
    def recurrence_action(n:int)->str:
        if n<=0:return 'NO_FAILURE'
        if n==1:return 'STRENGTHEN_CONTROL'
        if n==2:return 'OMEGA_SCIENTIST_ARCHITECTURE_REVIEW'
        return 'EXISTING_FIX_FAILED_REDESIGN_OR_ROLLBACK'

    @staticmethod
    def promotion_state(*,fixed:bool,tested_control:bool,regression_survived:bool)->str:
        if fixed and tested_control and regression_survived:return 'CAPABILITY'
        if fixed and tested_control:return 'LEARNING'
        if fixed:return 'INCIDENT'
        return 'OPEN_FAILURE'


class PathBudgetGovernor:
    def __init__(self,active_max:int=3,shadow_max:int=3):
        self.active_max=active_max; self.shadow_max=shadow_max

    def allocate(self,paths:Sequence[PathRecord])->dict[str,tuple[str,...]]:
        ranked=sorted(paths,key=lambda p:(-p.relative_value(),p.path_id))
        return {
            'ACTIVE':tuple(p.path_id for p in ranked[:self.active_max]),
            'SHADOW':tuple(p.path_id for p in ranked[self.active_max:self.active_max+self.shadow_max]),
            'ARCHIVED':tuple(p.path_id for p in ranked[self.active_max+self.shadow_max:])}


class ForensicDecisionCellAO5:
    SOURCE_SPEC_SHA256='773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443'

    def __init__(self)->None:
        self.state=ExecutionState.S00_BOOT; self.preflight_passed=False
        self.release_gates={'ADVERSARIAL_GATE':False,'NEUTRAL_GATE':False,'SEMANTIC_QA':False}
        self.dag=DecisionDAG(); self.events:list[dict[str,Any]]=[]

    @staticmethod
    def harmonization_contract()->HarmonizationContract:
        return HarmonizationContract('SOVARA-AO5-FORENSIC-DECISION-CELL-V1')

    def transition(self,target:ExecutionState)->None:
        if target==ExecutionState.S11_EXECUTION and not self.preflight_passed:
            raise ValueError('EXECUTION_REQUIRES_PREFLIGHT_PASS')
        if target==ExecutionState.S21_RELEASE and not all(self.release_gates.values()):
            raise ValueError('RELEASE_REQUIRES_ADVERSARIAL_NEUTRAL_SEMANTIC_GATES')
        if target<self.state and target not in {ExecutionState.S03_RECONCILE,ExecutionState.S07_PREFLIGHT,ExecutionState.S16_ADVERSARIAL_GATE}:
            raise ValueError('INVALID_BACKWARD_TRANSITION')
        self.state=target; self.events.append({'type':'STATE_TRANSITION','state':target.name})

    def preflight(self,i:PreflightInput)->PreflightResult:
        auto=any((i.page_count>50,i.file_count>8,i.annexure_count>8,i.domain_count>3,
                  i.expected_ocr_load>=3,i.expected_visual_load>=3))
        score=sum((i.file_count>2,i.page_count>10,i.annexure_count>3,i.domain_count>1,
                   i.tool_complexity>2,i.path_count>3,i.stream_count>8,i.context_risk>2,i.failure_risk>2))
        complexity='C5 EXTREME' if auto or score>=7 else 'C4 VERY_LARGE' if score>=5 else 'C3 LARGE' if score>=3 else 'C2 MODERATE' if score>=1 else 'C1 SMALL'
        digest=sha256(json.dumps(asdict(i),sort_keys=True).encode()).hexdigest()[:16]
        r=PreflightResult(
            f'AO5-PREFLIGHT-{digest}',complexity,auto,
            ('DECISION_RELEVANT_UNIT','CHILD_LANES' if auto else 'SINGLE_LANE'),
            ('MAX_3_ACTIVE','MAX_3_SHADOW'),('ACTIVATE_RELEVANT_ONLY',),
            {'MAX_ACTIVE_PATHS':3,'MAX_SHADOW_PATHS':3,'MAX_ACTIVE_STREAMS':12,'MAX_UNPERSISTED_FINDINGS':50},
            'DECISION_CHANGING_VERIFIED_FINDING','SOVARA_EVENT_AND_PROOF_LEDGER','BEFORE_CONTEXT_DEGRADATION')
        self.preflight_passed=True; self.events.append({'type':'PREFLIGHT',**asdict(r)}); return r

    def set_release_gate(self,gate:str,passed:bool=True)->None:
        if gate not in self.release_gates:raise KeyError('UNKNOWN_RELEASE_GATE')
        self.release_gates[gate]=passed

    @staticmethod
    def consequence_gate(*,owner_approval:bool,provider_authority:bool)->str:
        if not owner_approval:return 'BLOCK_OWNER_APPROVAL_REQUIRED'
        if not provider_authority:return 'BLOCK_PROVIDER_AUTHORITY_REQUIRED'
        return 'ADMISSIBLE_FOR_SEPARATE_EFFECT_EXECUTOR'

    def receipt(self)->dict[str,Any]:
        p={'integration_id':self.harmonization_contract().integration_id,'state':self.state.name,
           'preflight_passed':self.preflight_passed,'release_gates':dict(self.release_gates),
           'events':self.events,'external_effects':0}
        digest=sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return {**p,'receipt_sha256':digest}


def run_synthetic_canary()->dict[str,Any]:
    c=ForensicDecisionCellAO5()
    for s in (ExecutionState.S01_RESTORE,ExecutionState.S02_VERIFY_RESTORE,ExecutionState.S03_RECONCILE,
              ExecutionState.S04_OBJECTIVE_RESOLUTION,ExecutionState.S05_ALPHA_DISCOVERY,
              ExecutionState.S06_OMEGA_DEFINITION,ExecutionState.S07_PREFLIGHT): c.transition(s)
    pf=c.preflight(PreflightInput(file_count=4,page_count=28,domain_count=2,path_count=5,stream_count=7))
    for node,kind in {'SRC-A':'SOURCE_NODE','FACT-X':'FACT_NODE','FACT-Y':'FACT_NODE','OMEGA':'OMEGA_NODE'}.items(): c.dag.add_node(node,kind)
    c.dag.add_edge('SRC-A','SUPPORTS','FACT-X'); c.dag.add_edge('FACT-X','REQUIRES','OMEGA'); c.dag.add_edge('FACT-Y','SUPPORTS','OMEGA')
    spofs=c.dag.hidden_spofs({'PATH-A':{'FACT-X'},'PATH-B':{'FACT-X'},'PATH-C':{'FACT-Y'}})
    paths=[
        PathRecord('P1','OMEGA','primary',(),(),(),('FACT-X',),(),.9,.9,.9,.9,.9,.9,.3,.4,.4),
        PathRecord('P2','OMEGA','protective',(),(),(),('FACT-X',),(),.8,.8,.8,.8,.8,.9,.2,.4,.3),
        PathRecord('P3','OMEGA','evidence',(),(),(),('FACT-Y',),(),.95,.95,.95,.7,.7,.7,.2,.2,.2),
        PathRecord('P4','OMEGA','fallback',(),(),(),(),(),.6,.6,.6,.6,.6,.6,.5,.5,.5),
        PathRecord('P5','OMEGA','contingency',(),(),(),(),(),.5,.5,.5,.5,.5,.5,.7,.7,.7)]
    allocation=PathBudgetGovernor().allocate(paths)
    independence=EvidenceIndependenceEngine.classify(['EMAIL-1','EMAIL-1','EMAIL-1','MEETING-2'])
    violations=SemanticRegressionFirewall.check([('MAY','DID'),('FACT','FACT')])
    for s in (ExecutionState.S08_DECOMPOSITION,ExecutionState.S09_DAG_BUILD,ExecutionState.S10_SCHEDULING,
              ExecutionState.S11_EXECUTION,ExecutionState.S14_FAN_IN,ExecutionState.S15_CONVERGENCE,
              ExecutionState.S16_ADVERSARIAL_GATE): c.transition(s)
    c.set_release_gate('ADVERSARIAL_GATE'); c.transition(ExecutionState.S17_NEUTRAL_GATE)
    c.set_release_gate('NEUTRAL_GATE'); c.transition(ExecutionState.S18_SEMANTIC_QA)
    c.set_release_gate('SEMANTIC_QA'); c.transition(ExecutionState.S19_PERSIST)
    c.transition(ExecutionState.S20_READBACK_VERIFY); c.transition(ExecutionState.S21_RELEASE)
    receipt=c.receipt(); h=c.harmonization_contract()
    checks={
        'preflight_pass':pf.state=='PASS','dag_acyclic':c.dag.acyclic(),
        'hidden_spof_detected':spofs.get('FACT-X')==('PATH-A','PATH-B'),
        'active_path_budget_enforced':len(allocation['ACTIVE'])<=3,
        'shadow_path_budget_enforced':len(allocation['SHADOW'])<=3,
        'derivative_repetition_not_independent':independence['independent_source_count']==2,
        'semantic_inflation_detected':'MAY->DID' in violations,
        'consequence_gate_fail_closed':c.consequence_gate(owner_approval=False,provider_authority=True)=='BLOCK_OWNER_APPROVAL_REQUIRED',
        'sovara_effect_authority_preserved':'SOVARA' in h.provider_effect_authority,
        'cross_project_case_data_transfer_disabled':not h.cross_project_case_data_transfer,
        'external_effects_zero':receipt['external_effects']==0,
        'release_reached_after_three_gates':receipt['state']=='S21_RELEASE' and all(receipt['release_gates'].values())}
    return {'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'preflight':asdict(pf),
            'spofs':spofs,'path_allocation':allocation,'evidence_independence':independence,
            'semantic_violations':violations,'harmonization':asdict(h),'receipt':receipt}


if __name__=='__main__':
    print(json.dumps(run_synthetic_canary(),indent=2,sort_keys=True))
