from __future__ import annotations
import hashlib,json,re
from dataclasses import dataclass
from typing import Iterable

def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def _slug(name): return re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-')

@dataclass(frozen=True,slots=True)
class TrajectoryLesson:
 mission_id:str; steps:tuple[str,...]; evidence_refs:tuple[str,...]; accepted:bool; regression_free:bool; owner_interventions:int=0

@dataclass(frozen=True,slots=True)
class SkillCandidate:
 name:str; description:str; steps:tuple[str,...]; source_missions:tuple[str,...]; evidence_refs:tuple[str,...]; status:str; skill_sha256:str

@dataclass(frozen=True,slots=True)
class SkillReplay:
 replay_id:str; passed:bool; independent:bool; regression_free:bool; evidence_ref:str

class SkillForge:
 """Form portable Agent-Skills-style procedures only from repeated proven trajectories."""
 def propose(self,*,name:str,description:str,lessons:Iterable[TrajectoryLesson],min_lessons:int=3)->SkillCandidate:
  good=[x for x in lessons if x.accepted and x.regression_free and x.evidence_refs]
  if len(good)<min_lessons: raise ValueError('INSUFFICIENT_PROVEN_TRAJECTORIES')
  base=list(good[0].steps); common=set(base)
  for x in good[1:]: common &= set(x.steps)
  steps=tuple(s for s in base if s in common)
  if not steps: raise ValueError('NO_STABLE_COMMON_PROCEDURE')
  missions=tuple(sorted(x.mission_id for x in good)); refs=tuple(sorted({r for x in good for r in x.evidence_refs})); body=(name,description,steps,missions,refs)
  return SkillCandidate(_slug(name),description.strip(),steps,missions,refs,'CANDIDATE',_hash(body))

 def evaluate(self,skill:SkillCandidate,replays:Iterable[SkillReplay],*,min_independent:int=2)->str:
  rows=list(replays); good=[r for r in rows if r.passed and r.independent and r.regression_free and r.evidence_ref]
  if any(not r.regression_free for r in rows): return 'REJECT_REGRESSION'
  return 'ADOPT_CANDIDATE' if len(good)>=min_independent else 'HOLD_MORE_REPLAY'

 def render_skill_md(self,skill:SkillCandidate,*,checks:tuple[str,...]=(),forbidden:tuple[str,...]=())->str:
  lines=['---',f'name: {skill.name}',f'description: {skill.description}','---','',f'# {skill.name}','', '## Procedure']
  lines += [f'{i}. {step}' for i,step in enumerate(skill.steps,1)]
  if checks: lines += ['','## Verification',*[f'- {x}' for x in checks]]
  if forbidden: lines += ['','## Forbidden actions',*[f'- {x}' for x in forbidden]]
  lines += ['','## Provenance',f'- Skill candidate SHA-256: `{skill.skill_sha256}`',f'- Source missions: {", ".join(skill.source_missions)}']
  return '\n'.join(lines)+'\n'
