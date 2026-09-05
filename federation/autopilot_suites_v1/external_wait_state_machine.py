from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

WAIT_STATES={'WAITING_FOR_EMAIL','WAITING_FOR_CI','WAITING_FOR_APPROVAL','WAITING_FOR_PROVIDER','WAITING_FOR_LOCK','WAITING_FOR_DEADLINE'}
TERMINAL={'COMPLETED','CANCELLED'}
@dataclass(frozen=True)
class WaitCondition:
    state: str
    key: str
    expected_value: str=''
    not_before: str=''
    expires_at: str=''

@dataclass
class MissionWait:
    mission_id: str
    state: str='ACTIVE'
    condition: WaitCondition|None=None
    resume_count: int=0
    last_event_id: str=''

class ExternalWaitStateMachine:
    def __init__(self): self.missions={}
    def create(self,mission_id):
        if not mission_id.strip(): raise ValueError('MISSION_ID_REQUIRED')
        self.missions.setdefault(mission_id,MissionWait(mission_id)); return self.missions[mission_id]
    def wait(self,mission_id,condition:WaitCondition):
        if condition.state not in WAIT_STATES: raise ValueError('INVALID_WAIT_STATE')
        m=self.create(mission_id)
        if m.state in TERMINAL: raise ValueError('TERMINAL_MISSION')
        m.state=condition.state; m.condition=condition; return m
    def on_event(self,event:dict,now:datetime|None=None):
        now=now or datetime.now(timezone.utc); resumed=[]
        for m in self.missions.values():
            c=m.condition
            if not c or m.state not in WAIT_STATES: continue
            if c.not_before and now<datetime.fromisoformat(c.not_before): continue
            if str(event.get('wait_state',''))!=c.state or str(event.get('key',''))!=c.key: continue
            if c.expected_value and str(event.get('value',''))!=c.expected_value: continue
            m.state='ACTIVE'; m.condition=None; m.resume_count+=1; m.last_event_id=str(event.get('event_id','')); resumed.append(m.mission_id)
        return tuple(resumed)
    def timeout(self,now:datetime|None=None):
        now=now or datetime.now(timezone.utc); expired=[]
        for m in self.missions.values():
            c=m.condition
            if c and c.expires_at and now>=datetime.fromisoformat(c.expires_at): m.state='ACTIVE'; m.condition=None; expired.append(m.mission_id)
        return tuple(expired)
    def complete(self,mission_id): m=self.create(mission_id); m.state='COMPLETED'; m.condition=None
    def cancel(self,mission_id): m=self.create(mission_id); m.state='CANCELLED'; m.condition=None
