from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from typing import Iterable
@dataclass(frozen=True)
class EBITDAAdjustment:
    adjustment_id:str; description:str; ebitda_effect:float; recurring:bool; evidence_confidence:float; category:str='OTHER'
class QualityOfEarningsEngine:
    def normalize_ebitda(self,reported_ebitda:float,adjustments:Iterable[EBITDAAdjustment],minimum_confidence:float=.5)->dict[str,object]:
        accepted=[]; excluded=[]
        for a in adjustments:
            if not 0<=a.evidence_confidence<=1: raise ValueError('confidence must be between 0 and 1')
            (accepted if a.evidence_confidence>=minimum_confidence else excluded).append(a)
        effect=sum(a.ebitda_effect for a in accepted); return {'reported_ebitda':reported_ebitda,'accepted_adjustment':effect,'normalized_ebitda':reported_ebitda+effect,'accepted_ids':[a.adjustment_id for a in accepted],'excluded_low_confidence_ids':[a.adjustment_id for a in excluded]}
    def recurring_quality_ratio(self,recurring_ebitda:float,normalized_ebitda:float)->float:
        if normalized_ebitda<=0: raise ValueError('normalized EBITDA must be positive')
        return max(0.0,min(1.0,recurring_ebitda/normalized_ebitda))
class WorkingCapitalNormalizer:
    def target(self,historical_working_capital:Iterable[float],method:str='median')->float:
        values=[float(x) for x in historical_working_capital]
        if not values: raise ValueError('history required')
        if method=='median': return float(median(values))
        if method=='mean': return sum(values)/len(values)
        raise ValueError('unsupported method')
    def adjustment(self,actual_at_close:float,target:float)->float: return actual_at_close-target
@dataclass(frozen=True)
class DebtLikeItem: item_id:str; amount:float; confidence:float; included:bool=True
class DebtLikeEngine:
    def total(self,items:Iterable[DebtLikeItem],minimum_confidence:float=.5)->dict[str,object]:
        accepted=[]; excluded=[]
        for item in items:
            if item.amount<0 or not 0<=item.confidence<=1: raise ValueError('invalid debt-like item')
            (accepted if item.included and item.confidence>=minimum_confidence else excluded).append(item)
        return {'total_debt_like':sum(i.amount for i in accepted),'accepted_ids':[i.item_id for i in accepted],'excluded_ids':[i.item_id for i in excluded]}
