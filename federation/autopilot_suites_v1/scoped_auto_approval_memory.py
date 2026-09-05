from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from fnmatch import fnmatch
import json
from pathlib import Path

@dataclass(frozen=True)
class ApprovalGrant:
    grant_id: str
    mission_id: str
    effect_classes: tuple[str,...]
    target_patterns: tuple[str,...]
    authorization_ref: str
    expires_at: str=''
    max_uses: int=1
    reversible_required: bool=True
    readback_required: bool=True

@dataclass(frozen=True)
class ApprovalRequest:
    mission_id: str
    effect_class: str
    target: str
    reversible: bool
    readback_available: bool

@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    grant_id: str
    authorization_ref: str
    reason: str
    remaining_uses: int

class ScopedApprovalMemory:
    def __init__(self,path:str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        if not self.path.exists(): self._save({'grants':{},'uses':{},'revoked':[]})
    def _load(self): return json.loads(self.path.read_text())
    def _save(self,d):
        t=self.path.with_suffix('.tmp'); t.write_text(json.dumps(d,indent=2,sort_keys=True)); t.replace(self.path)
    def add(self,g:ApprovalGrant):
        if not all(x.strip() for x in (g.grant_id,g.mission_id,g.authorization_ref)): raise ValueError('GRANT_REQUIRED')
        if g.max_uses<1: raise ValueError('GRANT_MAX_USES')
        d=self._load(); existing=d['grants'].get(g.grant_id); payload=asdict(g)
        if existing and existing!=payload: raise ValueError('GRANT_COLLISION')
        d['grants'][g.grant_id]=payload; d['uses'].setdefault(g.grant_id,0); self._save(d)
    def revoke(self,grant_id:str):
        d=self._load();
        if grant_id not in d['revoked']: d['revoked'].append(grant_id); self._save(d)
    def authorize(self,r:ApprovalRequest,now:datetime|None=None,consume:bool=True):
        now=now or datetime.now(timezone.utc); d=self._load(); candidates=[]
        for gid,g in d['grants'].items():
            if gid in d['revoked'] or g['mission_id']!=r.mission_id: continue
            if r.effect_class not in g['effect_classes']: continue
            if not any(fnmatch(r.target,p) for p in g['target_patterns']): continue
            if g['expires_at'] and now>=datetime.fromisoformat(g['expires_at']): continue
            used=int(d['uses'].get(gid,0)); remaining=int(g['max_uses'])-used
            if remaining<=0: continue
            if g['reversible_required'] and not r.reversible: continue
            if g['readback_required'] and not r.readback_available: continue
            specificity=max(len(p.replace('*','')) for p in g['target_patterns'])
            candidates.append((specificity,gid,g,remaining))
        if not candidates: return ApprovalDecision(False,'','','NO_MATCHING_SCOPED_GRANT',0)
        _,gid,g,remaining=sorted(candidates,key=lambda x:(-x[0],x[1]))[0]
        if consume:
            d['uses'][gid]=int(d['uses'].get(gid,0))+1; self._save(d); remaining-=1
        return ApprovalDecision(True,gid,g['authorization_ref'],'SCOPED_PREAUTHORIZATION_MATCH',remaining)
