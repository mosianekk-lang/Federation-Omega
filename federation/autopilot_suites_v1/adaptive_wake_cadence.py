from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class CadenceInputs:
    mission_id: str
    current_interval_s: int = 3600
    deadline_seconds: int|None = None
    change_probability: float = 0.2
    material_change_rate: float = 0.1
    failure_count: int = 0
    stable_cycles: int = 0
    urgency: float = 0.2
    cost_pressure: float = 0.0
    provider_rate_pressure: float = 0.0

@dataclass(frozen=True)
class CadenceDecision:
    mission_id: str
    next_interval_s: int
    mode: str
    reasons: tuple[str,...]
    jitter_s: int

class AdaptiveWakeCadence:
    def __init__(self,min_s:int=60,max_s:int=86400):
        if min_s<=0 or max_s<min_s: raise ValueError('CADENCE_BOUNDS_INVALID')
        self.min_s=min_s; self.max_s=max_s
    def decide(self,x:CadenceInputs):
        if not x.mission_id.strip(): raise ValueError('MISSION_ID_REQUIRED')
        for v in (x.change_probability,x.material_change_rate,x.urgency,x.cost_pressure,x.provider_rate_pressure):
            if not 0<=float(v)<=1: raise ValueError('CADENCE_RATIO_RANGE')
        interval=float(max(self.min_s,min(self.max_s,x.current_interval_s))); reasons=[]
        if x.deadline_seconds is not None:
            if x.deadline_seconds <= 3600: interval=min(interval,300); reasons.append('DEADLINE_WITHIN_HOUR')
            elif x.deadline_seconds <= 86400: interval=min(interval,900); reasons.append('DEADLINE_WITHIN_DAY')
        activity=max(x.change_probability,x.material_change_rate,x.urgency)
        if activity >= .75: interval*=.35; reasons.append('HIGH_ACTIVITY')
        elif activity >= .45: interval*=.6; reasons.append('MEDIUM_ACTIVITY')
        if x.failure_count>0: interval*=max(.35,1-.12*min(x.failure_count,4)); reasons.append('RECOVERY_TIGHTEN')
        if x.stable_cycles>=3: interval*=min(8,2**min(3,x.stable_cycles//3)); reasons.append('STABLE_BACKOFF')
        pressure=max(x.cost_pressure,x.provider_rate_pressure)
        if pressure>.5: interval*=1+pressure; reasons.append('COST_RATE_BACKOFF')
        raw=int(max(self.min_s,min(self.max_s,round(interval))))
        h=int(sha256(x.mission_id.encode()).hexdigest()[:8],16); span=max(1,min(30,raw//20)); jitter=(h%(2*span+1))-span
        final=max(self.min_s,min(self.max_s,raw+jitter))
        mode='FAST' if final<=300 else 'ACTIVE' if final<=1800 else 'NORMAL' if final<=7200 else 'BACKOFF'
        return CadenceDecision(x.mission_id,final,mode,tuple(reasons or ['BASELINE']),jitter)
