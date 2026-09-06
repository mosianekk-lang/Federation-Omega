from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class OpportunitySignal:
    signal_id: str
    kind: str
    frequency: int
    shared_missions: int
    owner_minutes: float
    estimated_value: float
    confidence: float
    reversibility: float
    information_gain: float
    implementation_effort: float
    evidence_refs: tuple[str,...]=()

@dataclass(frozen=True)
class OpportunityCandidate:
    opportunity_id: str
    source_signal: str
    score: float
    experiment: tuple[str,...]
    state: str
    reason: str

class OpportunityAutopilot:
    ELIGIBLE={'REPEATED_MANUAL_PATTERN','SHARED_BOTTLENECK','NEW_CAPABILITY','RECURRING_CORRECTION','UNDERUSED_ASSET'}
    def discover(self,signals):
        out=[]; seen=set()
        for s in signals:
            if s.kind not in self.ELIGIBLE: continue
            if s.frequency<2 and s.shared_missions<2 and s.kind!='NEW_CAPABILITY': continue
            if not 0<=s.confidence<=1 or not 0<=s.reversibility<=1 or not 0<=s.information_gain<=1: raise ValueError('OPPORTUNITY_RATIO_RANGE')
            if s.implementation_effort<=0: raise ValueError('EFFORT_POSITIVE')
            raw=f'{s.kind}|{s.signal_id}|{s.evidence_refs}'; oid='OPP-'+sha256(raw.encode()).hexdigest()[:12]
            if oid in seen: continue
            seen.add(oid)
            score=(s.estimated_value*(.35+.65*s.confidence)+.03*s.owner_minutes+.2*s.information_gain+.15*s.reversibility+.08*min(5,s.shared_missions))/s.implementation_effort
            experiment=('BASELINE_CURRENT_PROCESS','BUILD_MINIMUM_REVERSIBLE_EXPERIMENT','RUN_PAIRED_COMPARISON','READBACK','KEEP_ONLY_IF_VALUE_POSITIVE')
            state='EXPERIMENT_READY' if s.confidence>=.35 else 'EVIDENCE_FIRST'
            out.append(OpportunityCandidate(oid,s.signal_id,round(score,6),experiment,state,'VALUE_INFORMATION_REUSE_RANK'))
        return tuple(sorted(out,key=lambda x:(-x.score,x.opportunity_id)))
