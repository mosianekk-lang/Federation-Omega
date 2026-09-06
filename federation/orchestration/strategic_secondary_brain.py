"""Strategic FUSE Secondary Brain compiler.

Provider-neutral and effect-free. Converts strategic signals into proof-carrying
StrategicPackets; external effects remain behind Federation authority gates.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from hashlib import sha256
import json, math, time
from typing import Iterable, Sequence

class AuthorityClass(str, Enum):
    A0="A0"; A1="A1"; A2="A2"
class StrategicTemperature(str, Enum):
    COLD="COLD"; WARM="WARM"; HOT="HOT"; CRITICAL="CRITICAL"
class ActionDisposition(str, Enum):
    ARCHIVE="ARCHIVE"; RESEARCH="RESEARCH"; QUEUE_SAFE="QUEUE_SAFE"; HOLD_AUTHORITY="HOLD_AUTHORITY"

@dataclass(frozen=True)
class StrategicSignal:
    signal_id:str; source:str; observed_at:float; summary:str
    credibility:float; surprise:float; impact:float; horizon_days:int=90; tags:tuple[str,...]=()
    def __post_init__(self):
        for n in ("credibility","surprise","impact"):
            if not 0<=getattr(self,n)<=1: raise ValueError(f"{n} must be 0..1")
        if self.horizon_days<=0: raise ValueError("horizon_days must be positive")
    @property
    def significance(self)->float:
        return round(self.impact*(0.55+0.25*self.surprise+0.20*self.credibility),6)
    @property
    def fingerprint(self)->str:
        raw="|".join((self.source.strip().lower(),self.summary.strip().lower(),",".join(sorted(t.lower() for t in self.tags))))
        return sha256(raw.encode()).hexdigest()

@dataclass(frozen=True)
class StrategicHypothesis:
    hypothesis_id:str; statement:str; probability:float; falsifiers:tuple[str,...]; evidence_signal_ids:tuple[str,...]; horizon_days:int
    def __post_init__(self):
        if not 0<=self.probability<=1: raise ValueError("probability must be 0..1")
        if not self.falsifiers or not self.evidence_signal_ids: raise ValueError("falsifier and evidence required")

@dataclass(frozen=True)
class StrategicOption:
    option_id:str; title:str; expected_value:float; option_value:float; information_value:float; cost:float
    irreversibility:float; ip_exposure:float; competitor_attention:float; authority:AuthorityClass
    preferred_route:str; fallback_route:str; proof_contract:str; rollback_contract:str
    @property
    def score(self)->float:
        risk=1+2*self.irreversibility+1.5*self.ip_exposure+self.competitor_attention
        return round((self.expected_value+self.option_value+self.information_value)/(risk*(1+self.cost)),6)

@dataclass(frozen=True)
class StrategicPacket:
    packet_id:str; created_at:float; temperature:StrategicTemperature; disposition:ActionDisposition
    signal_ids:tuple[str,...]; hypothesis_ids:tuple[str,...]; selected_option_id:str|None; authority:AuthorityClass
    preferred_route:str|None; fallback_route:str|None; proof_contract:str; rollback_contract:str; rationale:str; fingerprint:str
    def as_dict(self): return asdict(self)

class StrategicCompiler:
    def __init__(self,min_material_significance=.35,critical_threshold=.82,hot_threshold=.62,warm_threshold=.35):
        self.min_material_significance=min_material_significance; self.critical_threshold=critical_threshold
        self.hot_threshold=hot_threshold; self.warm_threshold=warm_threshold
    def deduplicate(self,signals:Iterable[StrategicSignal])->tuple[StrategicSignal,...]:
        out={}
        for s in signals:
            if s.fingerprint not in out or s.credibility>out[s.fingerprint].credibility: out[s.fingerprint]=s
        return tuple(sorted(out.values(),key=lambda x:(x.observed_at,x.signal_id)))
    def temperature(self,signals:Sequence[StrategicSignal])->StrategicTemperature:
        peak=max((s.significance for s in signals),default=0)
        if peak>=self.critical_threshold:return StrategicTemperature.CRITICAL
        if peak>=self.hot_threshold:return StrategicTemperature.HOT
        if peak>=self.warm_threshold:return StrategicTemperature.WARM
        return StrategicTemperature.COLD
    def compile(self,*,signals:Sequence[StrategicSignal],hypotheses:Sequence[StrategicHypothesis],options:Sequence[StrategicOption],now:float|None=None)->StrategicPacket:
        now=time.time() if now is None else now
        material=tuple(s for s in self.deduplicate(signals) if s.significance>=self.min_material_significance)
        ids={s.signal_id for s in material}
        hs=tuple(h for h in hypotheses if set(h.evidence_signal_ids).issubset(ids))
        selected=None; disposition=ActionDisposition.ARCHIVE; rationale="No material strategic signal met escalation threshold."; authority=AuthorityClass.A0
        if material and not hs:
            disposition=ActionDisposition.RESEARCH; rationale="Material signals exist but no falsifiable evidence-bound hypothesis is ready."
        elif hs and options:
            selected=max(options,key=lambda o:(o.score,o.option_id)); authority=selected.authority
            disposition=ActionDisposition.QUEUE_SAFE if authority in (AuthorityClass.A0,AuthorityClass.A1) else ActionDisposition.HOLD_AUTHORITY
            rationale="Highest-value proof-carrying option selected." if disposition is ActionDisposition.QUEUE_SAFE else "Selected option requires consequential external authority."
        proof=selected.proof_contract if selected else "Evidence-bound archive/readback receipt"
        rollback=selected.rollback_contract if selected else "No external effect; no rollback required"
        basis={"signals":[s.fingerprint for s in material],"hypotheses":[h.hypothesis_id for h in hs],"selected":selected.option_id if selected else None,"disposition":disposition.value,"authority":authority.value,"proof":proof}
        fp=sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest()
        return StrategicPacket("SCEC-"+fp[:16].upper(),now,self.temperature(material),disposition,tuple(s.signal_id for s in material),tuple(h.hypothesis_id for h in hs),selected.option_id if selected else None,authority,selected.preferred_route if selected else None,selected.fallback_route if selected else None,proof,rollback,rationale,fp)

def brier_score(probability:float,outcome:bool)->float:
    if not 0<=probability<=1: raise ValueError("probability must be 0..1")
    return (probability-(1.0 if outcome else 0.0))**2

def surprise_score(probability:float,outcome:bool,floor:float=1e-9)->float:
    if not 0<=probability<=1: raise ValueError("probability must be 0..1")
    p=probability if outcome else 1-probability
    return -math.log2(max(p,floor))
