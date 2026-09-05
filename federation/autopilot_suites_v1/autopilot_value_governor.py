from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from pathlib import Path

@dataclass(frozen=True)
class RunObservation:
    automation_id: str
    mission_id: str
    material_progress: bool
    calls: int
    latency_s: float
    owner_minutes_saved: float
    false_alerts: int
    duplicate_work: int
    cost_units: float
    outcome_value: float
    interventions: int=0

@dataclass(frozen=True)
class ValueDecision:
    automation_id: str
    recommendation: str
    value_density: float
    no_progress_rate: float
    false_alert_rate: float
    duplicate_rate: float
    reason: str

class AutopilotValueGovernor:
    def __init__(self,path:str|Path|None=None): self.path=Path(path) if path else None; self.rows=[]; self._load()
    def _load(self):
        if self.path and self.path.exists(): self.rows=[RunObservation(**r) for r in json.loads(self.path.read_text())]
    def _save(self):
        if self.path: self.path.parent.mkdir(parents=True,exist_ok=True); self.path.write_text(json.dumps([asdict(r) for r in self.rows],indent=2,sort_keys=True))
    def record(self,r:RunObservation):
        if not r.automation_id.strip() or r.calls<0 or r.latency_s<0 or r.cost_units<0: raise ValueError('OBSERVATION_INVALID')
        self.rows.append(r); self._save()
    def evaluate(self,automation_id:str,min_samples:int=3):
        rows=[r for r in self.rows if r.automation_id==automation_id]
        if len(rows)<min_samples: return ValueDecision(automation_id,'HOLD_FOR_DATA',0,0,0,0,'INSUFFICIENT_SAMPLES')
        n=len(rows); no=sum(not r.material_progress for r in rows)/n; false=sum(r.false_alerts for r in rows)/max(1,n); dup=sum(r.duplicate_work for r in rows)/max(1,n)
        benefit=sum(r.outcome_value+.2*r.owner_minutes_saved for r in rows)
        burden=sum(.02*r.calls+.002*r.latency_s+r.cost_units+.3*r.interventions for r in rows)
        density=benefit/max(.1,burden)
        if no>=.85 and density<.5: rec='SUSPEND'; reason='HIGH_NO_PROGRESS_LOW_VALUE'
        elif false>=.5 or dup>=.5: rec='BACKOFF'; reason='NOISE_OR_DUPLICATION'
        elif density>=3 and no<=.5: rec='PROMOTE'; reason='HIGH_VALUE_DENSITY'
        elif density<1: rec='BACKOFF'; reason='LOW_VALUE_DENSITY'
        else: rec='KEEP'; reason='POSITIVE_BUT_NOT_PROMOTION_GRADE'
        return ValueDecision(automation_id,rec,round(density,6),round(no,6),round(false,6),round(dup,6),reason)
    @staticmethod
    def overlap_score(a:set[str],b:set[str]): return 0 if not (a or b) else len(a&b)/len(a|b)
    def merge_candidate(self,a_id,b_id,a_scope:set[str],b_scope:set[str],threshold=.75): return self.overlap_score(a_scope,b_scope)>=threshold
