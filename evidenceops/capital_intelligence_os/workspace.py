from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable,Mapping
@dataclass(frozen=True)
class ReadinessDimension: name:str; score:float; weight:float; explanation:str
@dataclass(frozen=True)
class ReadinessResult: score:float; top_issues:tuple[str,...]; strengths:tuple[str,...]; owner_summary:str
class SaleReadinessEngine:
    def assess(self,dimensions:Iterable[ReadinessDimension])->ReadinessResult:
        dims=list(dimensions)
        if not dims: raise ValueError('readiness dimensions required')
        for d in dims:
            if not 0<=d.score<=1 or d.weight<0: raise ValueError('invalid readiness dimension')
        total=sum(d.weight for d in dims)
        if total<=0: raise ValueError('positive readiness weight required')
        score=sum(d.score*d.weight for d in dims)/total; issues=tuple(d.name for d in sorted(dims,key=lambda x:(x.score,-x.weight,x.name)) if d.score<.65)[:5]; strengths=tuple(d.name for d in sorted(dims,key=lambda x:(-x.score,-x.weight,x.name)) if d.score>=.8)[:5]; summary=f'Your business is {round(score*100)}% transaction-ready. '+(f'The highest-priority improvement area is {issues[0]}.' if issues else 'No major readiness gap is currently identified by this model.'); return ReadinessResult(score,issues,strengths,summary)
@dataclass(frozen=True)
class NextAction:
    action_id:str; title:str; expected_impact:float; confidence:float; effort:float; urgency:float; reversible:bool=True
class NextBestActionEngine:
    def rank(self,actions:Iterable[NextAction])->list[tuple[NextAction,float]]:
        ranked=[]
        for a in actions:
            if any(not 0<=x<=1 for x in (a.expected_impact,a.confidence,a.effort,a.urgency)): raise ValueError('action dimensions must be between 0 and 1')
            score=(.5*a.expected_impact+.25*a.urgency+.25*a.confidence)*(1-.55*a.effort)*(1.05 if a.reversible else .9); ranked.append((a,score))
        return sorted(ranked,key=lambda x:(-x[1],x[0].action_id))
class DecisionBriefBuilder:
    def build(self,*,title:str,verified_facts:Iterable[str],assumptions:Iterable[str],risks:Iterable[str],alternatives:Iterable[str],recommendation:str)->Mapping[str,object]:
        return {'title':title,'verified_facts':list(verified_facts),'assumptions':list(assumptions),'risks':list(risks),'alternatives':list(alternatives),'recommendation':recommendation,'requires_human_decision':True}
