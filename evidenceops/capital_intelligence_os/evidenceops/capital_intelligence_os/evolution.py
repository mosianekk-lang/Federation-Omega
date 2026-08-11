from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from typing import Iterable, Mapping, Sequence

@dataclass(frozen=True)
class ExperimentEvidence:
    experiment_id:str
    baseline_score:float
    candidate_score:float
    out_of_sample_score:float
    sample_size:int
    p_value:float
    tested_hypotheses:int=1
    safety_regression:bool=False
@dataclass(frozen=True)
class PromotionDecision:
    promoted:bool
    reasons:tuple[str,...]
    adjusted_alpha:float
class ExperimentCourt:
    """Governed promotion gate. Safety regressions veto statistical gains."""
    def decide(self,evidence:ExperimentEvidence,*,alpha:float=.05,min_sample:int=30,min_gain:float=.02)->PromotionDecision:
        adjusted=alpha/max(1,int(evidence.tested_hypotheses));reasons=[]
        if evidence.safety_regression:reasons.append('SAFETY_REGRESSION_VETO')
        if evidence.sample_size<min_sample:reasons.append('INSUFFICIENT_SAMPLE')
        if evidence.p_value>adjusted:reasons.append('MULTIPLE_TESTING_GATE_FAILED')
        if evidence.candidate_score-evidence.baseline_score<min_gain:reasons.append('INSUFFICIENT_IN_SAMPLE_GAIN')
        if evidence.out_of_sample_score-evidence.baseline_score<min_gain/2:reasons.append('OUT_OF_SAMPLE_GAIN_FAILED')
        return PromotionDecision(not reasons,tuple(reasons),adjusted)

@dataclass(frozen=True)
class CapabilityRecord:
    capability_id:str
    success_rate:float
    usefulness:float
    cost_efficiency:float
    evidence_quality:float
    observation_count:int
class CapabilityMortality:
    def state(self,r:CapabilityRecord)->str:
        if r.observation_count<10:return 'EXPERIMENTAL'
        score=.35*r.success_rate+.30*r.usefulness+.15*r.cost_efficiency+.20*r.evidence_quality
        if score>=.75:return 'PROVEN'
        if score>=.55:return 'PRODUCTION_MONITOR'
        if score>=.35:return 'DECLINING'
        return 'RETIRE_CANDIDATE'

@dataclass(frozen=True)
class CouncilOpinion:
    agent:str
    recommendation:str
    confidence:float
    evidence_quality:float
    rationale:str=''
@dataclass(frozen=True)
class CouncilDecision:
    recommendation:str
    support_weight:float
    dissent:tuple[str,...]
    ranking:tuple[tuple[str,float],...]
class EvidenceWeightedCouncil:
    def synthesize(self,opinions:Sequence[CouncilOpinion])->CouncilDecision:
        if not opinions:raise ValueError('at least one opinion required')
        weights={}
        for op in opinions:
            w=max(0,min(1,op.confidence))*max(0,min(1,op.evidence_quality));weights[op.recommendation]=weights.get(op.recommendation,0.0)+w
        ranking=tuple(sorted(((k,round(v,6)) for k,v in weights.items()),key=lambda kv:kv[1],reverse=True));winner=ranking[0][0];total=sum(weights.values()) or 1
        return CouncilDecision(winner,round(weights[winner]/total,6),tuple(op.agent for op in opinions if op.recommendation!=winner),ranking)

@dataclass(frozen=True)
class InnovationCandidate:
    fingerprint:str
    occurrence_count:int
    proposed_route:str
    lifecycle_state:str='EXPERIMENTAL_REQUIRES_COURT'
class FailureInnovationCompiler:
    def compile(self,failures:Iterable[Mapping[str,object]],*,threshold:int=3)->tuple[InnovationCandidate,...]:
        fps=[];routes={}
        for row in failures:
            fp=str(row.get('fingerprint','')).strip()
            if fp:fps.append(fp);routes.setdefault(fp,str(row.get('alternative_route','MATERIAL_DIFFERENT_ROUTE')))
        counts=Counter(fps);return tuple(InnovationCandidate(fp,n,routes[fp]) for fp,n in sorted(counts.items()) if n>=threshold)
