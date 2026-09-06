from __future__ import annotations
from dataclasses import dataclass
from fnmatch import fnmatch

@dataclass(frozen=True)
class FailureSignal:
    signal_id: str
    trigger_type: str
    fingerprint: str
    route_id: str
    effect_class: str='NO_EFFECT'

@dataclass(frozen=True)
class ReflexDefinition:
    reflex_id: str
    trigger_type: str
    fingerprint_pattern: str
    action_chain: tuple[str,...]
    max_same_route_retries: int=1
    circuit_open_after: int=3
    allowed_effect_classes: tuple[str,...]=('NO_EFFECT','REVERSIBLE_INTERNAL')

@dataclass(frozen=True)
class ReflexDecision:
    state: str
    reflex_id: str
    actions: tuple[str,...]
    require_changed_route: bool
    circuit_open: bool
    reason: str

class TriggerRecoveryReflexes:
    def __init__(self,definitions=()):
        self.defs={d.reflex_id:d for d in definitions}; self.counts={}; self.route_counts={}; self.circuits=set()
    @classmethod
    def defaults(cls):
        return cls((
          ReflexDefinition('REFLEX-CI-DEPENDENCY','CI_FAIL','DEPENDENCY:*',('INSPECT_LOGS','CLASSIFY_DEPENDENCY','BUILD_MIN_REPAIR','RERUN_TESTS','READBACK')),
          ReflexDefinition('REFLEX-STALE-SOURCE','STALE_SOURCE','*',('FRESH_READ_SOURCE','INVALIDATE_STALE_PROOF','RECOMPILE_PLAN')),
          ReflexDefinition('REFLEX-PROVIDER-TIMEOUT','PROVIDER_TIMEOUT','*',('PROBE_PROVIDER_STATE','CHECK_EFFECT_UNKNOWN','TRY_ALTERNATE_ROUTE')),
          ReflexDefinition('REFLEX-DUPLICATE','DUPLICATE_WORK','*',('SELECT_CANONICAL_WORK','CANCEL_YOUNGER_DUPLICATE','MERGE_EVIDENCE')),
          ReflexDefinition('REFLEX-REPEAT','REPEATED_FAILURE','*',('OPEN_CIRCUIT','FORBID_UNCHANGED_RETRY','SEARCH_CHANGED_ROUTE'),max_same_route_retries=0,circuit_open_after=1),
        ))
    def register(self,d):
        if d.reflex_id in self.defs and self.defs[d.reflex_id]!=d: raise ValueError('REFLEX_COLLISION')
        self.defs[d.reflex_id]=d
    def decide(self,s:FailureSignal):
        if not all(x.strip() for x in (s.signal_id,s.trigger_type,s.fingerprint,s.route_id)): raise ValueError('SIGNAL_REQUIRED')
        matches=[d for d in self.defs.values() if d.trigger_type==s.trigger_type and fnmatch(s.fingerprint,d.fingerprint_pattern)]
        if not matches: return ReflexDecision('NO_REFLEX','',(),False,False,'NO_MATCHING_REFLEX')
        d=sorted(matches,key=lambda x:x.reflex_id)[0]
        if s.effect_class not in d.allowed_effect_classes: return ReflexDecision('HELD_EFFECT_CLASS',d.reflex_id,(),False,False,'EFFECT_CLASS_NOT_AUTOMATABLE')
        key=(d.reflex_id,s.fingerprint); self.counts[key]=self.counts.get(key,0)+1
        rkey=(key,s.route_id); self.route_counts[rkey]=self.route_counts.get(rkey,0)+1
        changed=self.route_counts[rkey]>d.max_same_route_retries
        opened=self.counts[key]>=d.circuit_open_after
        if opened: self.circuits.add(key)
        actions=d.action_chain
        if changed and 'FORBID_UNCHANGED_RETRY' not in actions: actions=actions+('FORBID_UNCHANGED_RETRY','SEARCH_CHANGED_ROUTE')
        return ReflexDecision('REFLEX_READY',d.reflex_id,actions,changed,opened,'MATCHED_BOUNDED_REFLEX')
    def reset(self,reflex_id,fingerprint): self.circuits.discard((reflex_id,fingerprint)); self.counts.pop((reflex_id,fingerprint),None)
