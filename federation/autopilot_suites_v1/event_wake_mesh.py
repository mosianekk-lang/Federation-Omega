from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    source: str
    event_type: str
    subject: str
    occurred_at: str
    payload_hash: str = ''
    labels: tuple[str, ...] = ()
    materiality: float = 0.5
    idempotency_key: str = ''
    def validate(self):
        if not all(x.strip() for x in (self.event_id,self.source,self.event_type,self.subject,self.occurred_at)):
            raise ValueError('EVENT_REQUIRED_FIELD_MISSING')
        if not 0 <= float(self.materiality) <= 1: raise ValueError('EVENT_MATERIALITY_RANGE')
    @property
    def dedupe_key(self): return self.idempotency_key.strip() or self.event_id

@dataclass(frozen=True)
class Subscription:
    subscription_id: str
    mission_id: str
    sources: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    required_labels: tuple[str, ...] = ()
    min_materiality: float = 0.0
    enabled: bool = True
    debounce_seconds: int = 0
    def validate(self):
        if not self.subscription_id.strip() or not self.mission_id.strip(): raise ValueError('SUBSCRIPTION_ID_REQUIRED')
        if not 0 <= float(self.min_materiality) <= 1: raise ValueError('SUBSCRIPTION_MATERIALITY_RANGE')
        if self.debounce_seconds < 0: raise ValueError('DEBOUNCE_NON_NEGATIVE')

@dataclass(frozen=True)
class WakeReceipt:
    event_id: str
    event_dedupe_key: str
    matched_missions: tuple[str, ...]
    matched_subscriptions: tuple[str, ...]
    invalidation_keys: tuple[str, ...]
    duplicate_suppressed: bool
    debounce_suppressed: tuple[str, ...]
    authority_delta: str = 'NONE'
    external_effect: bool = False

class EventWakeMesh:
    def __init__(self):
        self._subs: dict[str, Subscription] = {}
        self._seen: set[str] = set()
        self._last_wake: dict[str, datetime] = {}
    def register(self, sub: Subscription):
        sub.validate()
        if sub.subscription_id in self._subs and self._subs[sub.subscription_id] != sub:
            raise ValueError('SUBSCRIPTION_COLLISION')
        self._subs[sub.subscription_id] = sub
    def unregister(self, subscription_id: str): self._subs.pop(subscription_id, None)
    def _matches(self, e: EventEnvelope, s: Subscription):
        if not s.enabled or e.materiality < s.min_materiality: return False
        if s.sources and e.source not in s.sources: return False
        if s.event_types and e.event_type not in s.event_types: return False
        if s.subjects and e.subject not in s.subjects: return False
        if s.required_labels and not set(s.required_labels).issubset(set(e.labels)): return False
        return True
    def ingest(self, e: EventEnvelope, now: datetime|None=None):
        e.validate(); now = now or datetime.now(timezone.utc)
        if e.dedupe_key in self._seen:
            return WakeReceipt(e.event_id,e.dedupe_key,(),(),(),True,())
        self._seen.add(e.dedupe_key)
        missions=[]; subs=[]; debounced=[]
        for sid,s in sorted(self._subs.items()):
            if not self._matches(e,s): continue
            last=self._last_wake.get(sid)
            if last and (now-last).total_seconds() < s.debounce_seconds:
                debounced.append(sid); continue
            self._last_wake[sid]=now; subs.append(sid); missions.append(s.mission_id)
        inv=tuple(sorted({f'source:{e.source}',f'subject:{e.subject}',f'event_type:{e.event_type}'}))
        return WakeReceipt(e.event_id,e.dedupe_key,tuple(dict.fromkeys(missions)),tuple(subs),inv,False,tuple(debounced))
    def subscription_count(self): return len(self._subs)
    def seen_count(self): return len(self._seen)
