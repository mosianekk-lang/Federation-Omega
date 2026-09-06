from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MissionCandidate:
    mission_id: str
    urgency: float
    deadline_pressure: float
    expected_value: float
    dependency_unlock: float
    information_gain: float
    completion_proximity: float
    owner_burden_reduction: float
    risk: float
    cost: float
    conflict_domain: str
    blocked: bool=False
    waiting: bool=False
    age_minutes: int=0

@dataclass(frozen=True)
class MissionSelection:
    selected: tuple[str,...]
    held: tuple[tuple[str,str],...]
    scores: tuple[tuple[str,float],...]

class MissionAirTrafficControl:
    def __init__(self,wip_limit:int=4,per_domain_limit:int=1):
        if wip_limit<1 or per_domain_limit<1: raise ValueError('WIP_LIMIT_INVALID')
        self.wip_limit=wip_limit; self.per_domain_limit=per_domain_limit
    @staticmethod
    def score(m:MissionCandidate):
        if not m.mission_id.strip(): raise ValueError('MISSION_ID_REQUIRED')
        vals=(m.urgency,m.deadline_pressure,m.expected_value,m.dependency_unlock,m.information_gain,m.completion_proximity,m.owner_burden_reduction,m.risk)
        if any(v<0 or v>1 for v in vals): raise ValueError('MISSION_RATIO_RANGE')
        if m.cost<0: raise ValueError('MISSION_COST_NONNEGATIVE')
        starvation=min(.25,max(0,m.age_minutes)/1440*.08)
        positive=(.18*m.urgency+.15*m.deadline_pressure+.2*m.expected_value+.15*m.dependency_unlock+.08*m.information_gain+.08*m.completion_proximity+.1*m.owner_burden_reduction+starvation)
        penalty=.12*m.risk+.06*min(1,m.cost)
        return round(positive-penalty,6)
    def select(self,missions):
        ranked=sorted(((self.score(m),m) for m in missions),key=lambda x:(-x[0],x[1].mission_id))
        selected=[]; held=[]; domains={}
        for score,m in ranked:
            if m.blocked: held.append((m.mission_id,'BLOCKED')); continue
            if m.waiting: held.append((m.mission_id,'WAITING')); continue
            if len(selected)>=self.wip_limit: held.append((m.mission_id,'WIP_LIMIT')); continue
            count=domains.get(m.conflict_domain,0)
            if m.conflict_domain and count>=self.per_domain_limit: held.append((m.mission_id,'CONFLICT_DOMAIN')); continue
            selected.append(m.mission_id); domains[m.conflict_domain]=count+1
        return MissionSelection(tuple(selected),tuple(held),tuple((m.mission_id,s) for s,m in ranked))
