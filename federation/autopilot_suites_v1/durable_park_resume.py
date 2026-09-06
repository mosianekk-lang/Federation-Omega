from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class WaitPredicate:
    kind: str
    key: str
    expected_value: str = ''
    not_before: str = ''
    expires_at: str = ''
    def validate(self):
        if not self.kind.strip() or not self.key.strip(): raise ValueError('WAIT_PREDICATE_REQUIRED')

@dataclass
class ParkRecord:
    mission_id: str
    checkpoint_ref: str
    predicate: WaitPredicate
    parked_at: str
    status: str = 'PARKED'
    resume_count: int = 0
    last_resume_event: str = ''

class DurableParkResume:
    def __init__(self, path: str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        if not self.path.exists(): self._save({})
    def _load(self): return json.loads(self.path.read_text() or '{}')
    def _save(self,data):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2,sort_keys=True)); tmp.replace(self.path)
    def park(self, mission_id:str, checkpoint_ref:str, predicate:WaitPredicate, now:str|None=None):
        predicate.validate()
        if not mission_id.strip() or not checkpoint_ref.strip(): raise ValueError('MISSION_CHECKPOINT_REQUIRED')
        data=self._load(); now=now or datetime.now(timezone.utc).isoformat()
        existing=data.get(mission_id)
        payload={'mission_id':mission_id,'checkpoint_ref':checkpoint_ref,'predicate':asdict(predicate),'parked_at':now,'status':'PARKED','resume_count':existing.get('resume_count',0) if existing else 0,'last_resume_event':''}
        if existing and existing['status']=='PARKED' and existing['checkpoint_ref']==checkpoint_ref and existing['predicate']==payload['predicate']:
            return existing
        data[mission_id]=payload; self._save(data); return payload
    def active(self): return [v for v in self._load().values() if v['status']=='PARKED']
    @staticmethod
    def _matches(pred:dict[str,Any], event:dict[str,Any], now:datetime):
        if pred.get('not_before'):
            if now < datetime.fromisoformat(pred['not_before']): return False
        if event.get('kind') != pred.get('kind') or str(event.get('key')) != pred.get('key'): return False
        expected=pred.get('expected_value','')
        return not expected or str(event.get('value','')) == expected
    def resume_for_event(self,event:dict[str,Any],now:datetime|None=None):
        now=now or datetime.now(timezone.utc); data=self._load(); resumed=[]
        for mid,row in data.items():
            if row['status']!='PARKED': continue
            if self._matches(row['predicate'],event,now):
                row['status']='RESUMED'; row['resume_count']=int(row.get('resume_count',0))+1; row['last_resume_event']=str(event.get('event_id','')); resumed.append(mid)
        self._save(data); return tuple(resumed)
    def sweep_expired(self, now:datetime|None=None):
        now=now or datetime.now(timezone.utc); data=self._load(); expired=[]
        for mid,row in data.items():
            exp=row['predicate'].get('expires_at','')
            if row['status']=='PARKED' and exp and now >= datetime.fromisoformat(exp): row['status']='EXPIRED'; expired.append(mid)
        self._save(data); return tuple(expired)
    def cancel(self,mission_id:str):
        data=self._load();
        if mission_id in data: data[mission_id]['status']='CANCELLED'; self._save(data); return True
        return False
    def get(self,mission_id:str): return self._load().get(mission_id)
