from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .core import PolicyError, sha256_json

EVIDENCE_FACTORS = {
    "PROVIDER_LIVE_INDEPENDENT_READBACK": 1.00,
    "REPEATED_OPERATIONAL_SCOPED": 0.85,
    "DETERMINISTIC_CI_BOUNDED_RUNTIME": 0.70,
    "SOURCE_DESIGN_ONLY": 0.50,
    "PLANNED_CLAIMED_ONLY": 0.30,
}

@dataclass(frozen=True)
class BenchmarkObservation:
    evidence_state: str
    metrics: Mapping[str, float]
    proof_refs: tuple[str, ...] = ()

@dataclass(frozen=True)
class DimensionResult:
    metric: str
    raw_score: float
    effective_score: float
    target_met: bool
    safety_gate_met: bool
    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "raw_score": round(self.raw_score, 6), "effective_score": round(self.effective_score, 6), "target_met": self.target_met, "safety_gate_met": self.safety_gate_met}

@dataclass(frozen=True)
class CFBEAdmissionResult:
    status: str
    raw_weighted_score: float
    effective_weighted_score: float
    evidence_factor: float
    hard_gates_pass: bool
    ten_x_targets_pass: bool
    dimensions: tuple[DimensionResult, ...]
    receipt_sha256: str
    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "raw_weighted_score": round(self.raw_weighted_score, 4), "effective_weighted_score": round(self.effective_weighted_score, 4), "evidence_factor": self.evidence_factor, "hard_gates_pass": self.hard_gates_pass, "ten_x_targets_pass": self.ten_x_targets_pass, "dimensions": [x.to_dict() for x in self.dimensions], "receipt_sha256": self.receipt_sha256}

class CFBEAdmissionComparator:
    """Truth-bound incumbent/challenger comparator for admission systems."""
    def __init__(self, spec: Mapping[str, Any]):
        self.spec = json.loads(json.dumps(spec))
        if self.spec.get("schema") != "FEDERATION-PROOFOS-CFBE-V1": raise PolicyError("unsupported ProofOS CFBE spec")
        self.dimensions = list(self.spec.get("dimensions", []))
        self.total_weight = sum(float(x.get("weight", 0)) for x in self.dimensions)
        if not self.dimensions or self.total_weight <= 0: raise PolicyError("invalid CFBE dimensions")
        self.sha256 = sha256_json(self.spec)
    @classmethod
    def from_path(cls, path: str | Path): return cls(json.loads(Path(path).read_text(encoding="utf-8")))
    def compare(self, *, incumbent: BenchmarkObservation, challenger: BenchmarkObservation) -> CFBEAdmissionResult:
        if incumbent.evidence_state not in EVIDENCE_FACTORS or challenger.evidence_state not in EVIDENCE_FACTORS: raise PolicyError("unknown evidence state")
        ef = EVIDENCE_FACTORS[challenger.evidence_state]; results=[]; wr=0.0; we=0.0; hard=True; ten=True
        for d in self.dimensions:
            m=str(d["metric"]); w=float(d["weight"]); direction=str(d["direction"])
            if m not in incumbent.metrics or m not in challenger.metrics: raise PolicyError(f"missing metric observation: {m}")
            old=float(incumbent.metrics[m]); new=float(challenger.metrics[m])
            if old<0 or new<0: raise PolicyError(f"negative metric: {m}")
            target=self._target_met(d,old,new); safe=self._safety_gate_met(d,old,new); raw=self._dimension_score(direction,old,new,d); eff=raw*ef
            results.append(DimensionResult(m,raw,eff,target,safe)); wr+=raw*w; we+=eff*w
            if d.get("hard_gate") and not safe: hard=False
            if d.get("ten_x_target") and not target: ten=False
        raw_score=wr/self.total_weight; effective=we/self.total_weight
        operational=challenger.evidence_state in {"PROVIDER_LIVE_INDEPENDENT_READBACK","REPEATED_OPERATIONAL_SCOPED"}
        independent=bool(challenger.proof_refs) and challenger.evidence_state=="PROVIDER_LIVE_INDEPENDENT_READBACK"
        if not hard: status="REJECTED_SAFETY_OR_REGRESSION_GATE"
        elif not operational: status="HELD_NO_OPERATIONAL_EVIDENCE"
        elif ten and (not self.spec.get("frontier_leader_requires_independent_readback",True) or independent): status="TEN_X_FRONTIER_CANDIDATE"
        else: status="SAFE_IMPROVEMENT_CANDIDATE"
        payload={"spec_sha256":self.sha256,"status":status,"raw_weighted_score":round(raw_score,8),"effective_weighted_score":round(effective,8),"evidence_factor":ef,"hard_gates_pass":hard,"ten_x_targets_pass":ten,"dimensions":[x.to_dict() for x in results],"incumbent_evidence_state":incumbent.evidence_state,"challenger_evidence_state":challenger.evidence_state,"challenger_proof_refs":list(challenger.proof_refs)}
        return CFBEAdmissionResult(status,raw_score,effective,ef,hard,ten,tuple(results),sha256_json(payload))
    @staticmethod
    def _safety_gate_met(d,old,new):
        g=d.get("safety_gate")
        if not g: return True
        k=str(g.get("kind")); direction=str(d["direction"])
        if k=="NO_WORSE_THAN_INCUMBENT": return new<=old if direction=="LOWER_IS_BETTER" else new>=old
        if k=="AT_LEAST": return new>=float(g["value"])
        if k=="AT_MOST": return new<=float(g["value"])
        raise PolicyError(f"unsupported safety gate: {k}")
    @staticmethod
    def _target_met(d,old,new):
        t=d.get("target")
        if not t: return True
        k=str(t.get("kind")); v=float(t.get("value",0))
        if k=="RATIO_AT_MOST": return new==0 if old==0 else new/old<=v
        if k=="RATIO_AT_LEAST": return new>0 if old==0 else new/old>=v
        if k=="AT_LEAST": return new>=v
        if k=="AT_MOST": return new<=v
        raise PolicyError(f"unsupported target: {k}")
    @staticmethod
    def _dimension_score(direction,old,new,d):
        t=d.get("target") or {}; k=str(t.get("kind","")); v=t.get("value")
        if direction=="LOWER_IS_BETTER":
            if old==0: return 100.0 if new==0 else 0.0
            ratio=new/old; target=float(v) if k=="RATIO_AT_MOST" else .5
            if ratio<=target: return 100.0
            if ratio<=1: return 50+50*(1-ratio)/max(1e-9,1-target)
            return max(0.0,50/ratio)
        if direction=="HIGHER_IS_BETTER":
            if k=="AT_LEAST":
                target=float(v)
                return 100.0 if new>=target or target==0 else max(0,min(100,100*new/target))
            if old==0: return 100.0 if new>0 else 50.0
            ratio=new/old; target=float(v) if k=="RATIO_AT_LEAST" else 2.0
            if ratio>=target: return 100.0
            if ratio>=1: return 50+50*(ratio-1)/max(1e-9,target-1)
            return max(0,50*ratio)
        raise PolicyError(f"unsupported direction: {direction}")
