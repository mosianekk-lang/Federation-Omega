from __future__ import annotations
from dataclasses import dataclass,field
from typing import Iterable
@dataclass
class SynergyCommitment:
    synergy_id:str; category:str; expected_value:float; realized_value:float=0.0; confidence:float=.5; owner:str|None=None; evidence_ids:list[str]=field(default_factory=list)
class SynergyLedger:
    def realization(self,items:Iterable[SynergyCommitment])->dict[str,float]:
        items=list(items); expected=sum(i.expected_value for i in items); realized=sum(i.realized_value for i in items); return {'expected':expected,'realized':realized,'realization_ratio':1.0 if expected==0 else realized/expected,'value_gap':expected-realized}
@dataclass(frozen=True)
class IntegrationMilestone: milestone_id:str; due_day:int; critical:bool; completed:bool=False
class DayOneReadiness:
    def score(self,milestones:Iterable[IntegrationMilestone])->float:
        ms=list(milestones)
        if not ms: return 1.0
        weights=[2 if m.critical else 1 for m in ms]; return sum(w for m,w in zip(ms,weights) if m.completed)/sum(weights)
class ValueLeakageDetector:
    def detect(self,baseline_value:float,current_value:float,approved_investment:float=0.0)->dict[str,float|bool]:
        expected=baseline_value+approved_investment; leakage=max(0.0,expected-current_value); return {'expected_value':expected,'current_value':current_value,'leakage':leakage,'leakage_ratio':0.0 if expected==0 else leakage/abs(expected),'flag':leakage>0}
