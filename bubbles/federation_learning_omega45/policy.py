from __future__ import annotations
import math, statistics
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from .store import LearningStore

@dataclass(frozen=True)
class AdaptivePolicy:
    project_id: str
    mission_type: str
    retrieval_budget: int
    hot1_max_bytes: int
    stall_seconds: int
    tool_result_token_budget: int
    sample_count: int
    confidence: float
    source: str = "OMEGA45_OPERATIONAL_LEARNING"

def _percentile(xs: List[float], q: float) -> float:
    if not xs: raise ValueError("empty")
    ys=sorted(xs); pos=(len(ys)-1)*q; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return ys[lo]
    return ys[lo] + (ys[hi]-ys[lo])*(pos-lo)

class PolicyLearner:
    """Conservative learner: insufficient evidence never promotes a learned policy."""
    def __init__(self, store: LearningStore, *, min_samples: int = 12, promote_confidence: float = 0.72): self.store=store; self.min_samples=min_samples; self.promote_confidence=promote_confidence
    def propose(self, project_id: str, mission_type: str) -> AdaptivePolicy:
        retrieval=self.store.values(project_id=project_id,mission_type=mission_type,metric="retrieval.calls"); context=self.store.values(project_id=project_id,mission_type=mission_type,metric="context.hot1_bytes"); stall=self.store.values(project_id=project_id,mission_type=mission_type,metric="stall.seconds_to_progress"); payload=self.store.values(project_id=project_id,mission_type=mission_type,metric="retrieval.result_tokens")
        n=min([len(x) for x in (retrieval,context,stall,payload)] or [0]); confidence=min(0.95,n/max(self.min_samples,1)*0.72) if n else 0.0
        r=max(2,min(8,int(round(_percentile(retrieval,0.75) if retrieval else 3)))); c=max(8000,min(32000,int(round((_percentile(context,0.90) if context else 16000)*1.10)))); s=max(180,min(1800,int(round((_percentile(stall,0.75) if stall else 1080)*1.15)))); t=max(2000,min(10000,int(round((_percentile(payload,0.90) if payload else 4000)*1.05))))
        return AdaptivePolicy(project_id,mission_type,r,c,s,t,n,confidence)
    def candidate(self, project_id: str, mission_type: str) -> Dict[str,Any]:
        p=self.propose(project_id,mission_type); eligible=p.sample_count>=self.min_samples and p.confidence>=self.promote_confidence; key=f"{project_id}:{mission_type}"; state="CANDIDATE_ELIGIBLE" if eligible else "SHADOW_INSUFFICIENT_EVIDENCE"; self.store.save_policy(key,asdict(p),state,p.sample_count,p.confidence,False); return {"policy":asdict(p),"eligible":eligible,"state":state}

class ShadowPolicyEvaluator:
    """Compares baseline vs candidate on observed outcomes; does not self-promote."""
    def __init__(self, store: LearningStore): self.store=store
    def evaluate(self, project_id: str, mission_type: str, candidate: AdaptivePolicy) -> Dict[str,Any]:
        lat=self.store.values(project_id=project_id,mission_type=mission_type,metric="latency.total_ms"); proof=self.store.values(project_id=project_id,mission_type=mission_type,metric="proof.completed"); dup=self.store.values(project_id=project_id,mission_type=mission_type,metric="reuse.prevented_call")
        if not lat: return {"qualified":False,"reason":"NO_LATENCY_OBSERVATIONS"}
        p_rate=sum(proof)/len(proof) if proof else 0.0; d_rate=sum(dup)/len(dup) if dup else 0.0; p95=_percentile(lat,0.95); qualified=candidate.sample_count>=12 and p_rate>=0.80 and p95>0 and candidate.confidence>=0.72
        return {"qualified":qualified,"observed_p95_latency_ms":round(p95,2),"proof_completion_rate":round(p_rate,3),"prevented_call_rate":round(d_rate,3),"sample_count":candidate.sample_count,"rule":"candidate cannot promote without >=12 samples, >=0.80 proof completion, >=0.72 confidence"}
