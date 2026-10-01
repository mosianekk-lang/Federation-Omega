from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

@dataclass(frozen=True,slots=True)
class ArchitecturePattern:
 pattern_id:str; capabilities:tuple[str,...]; proof_strength:float; risk:float; complexity:float; reversibility:float; failure_domains:tuple[str,...]=(); incompatible_with:tuple[str,...]=(); source_refs:tuple[str,...]=()
 def validate(self):
  if not self.pattern_id or not self.capabilities: raise ValueError('pattern identity/capabilities required')
  for n in ('proof_strength','risk','complexity','reversibility'):
   if not 0<=getattr(self,n)<=1: raise ValueError(f'{n} outside [0,1]')

@dataclass(frozen=True,slots=True)
class ArchitectureRequirement:
 required_capabilities:tuple[str,...]; optional_capabilities:tuple[str,...]=(); max_risk:float=.5; min_proof_strength:float=.5; max_components:int=4

@dataclass(frozen=True,slots=True)
class ArchitectureOption:
 pattern_ids:tuple[str,...]; coverage:float; optional_coverage:float; score:float; residual_gaps:tuple[str,...]; failure_domains:tuple[str,...]; option_sha256:str

class ArchitectureGenome:
 """Bounded proof-aware architecture composition; novelty never outranks mission fit."""
 def rank(self,req:ArchitectureRequirement,patterns:Iterable[ArchitecturePattern],*,limit:int=10)->tuple[ArchitectureOption,...]:
  required=set(req.required_capabilities); optional=set(req.optional_capabilities)
  if not required or req.max_components<1: raise ValueError('required capabilities/max_components invalid')
  pool=[]
  for p in patterns:
   p.validate()
   if p.risk<=req.max_risk and p.proof_strength>=req.min_proof_strength: pool.append(p)
  options=[]
  max_k=min(req.max_components,len(pool))
  for k in range(1,max_k+1):
   for group in combinations(pool,k):
    ids={p.pattern_id for p in group}
    if any(set(p.incompatible_with)&ids for p in group): continue
    caps=set().union(*(set(p.capabilities) for p in group)); hit=len(required&caps); cov=hit/len(required); opt=len(optional&caps)/max(len(optional),1) if optional else 0.0
    proof=min(p.proof_strength for p in group); risk=max(p.risk for p in group); rev=sum(p.reversibility for p in group)/k; complexity=sum(p.complexity for p in group)/k; domains=set().union(*(set(p.failure_domains) for p in group)); diversity=min(len(domains),3)/3
    score=10*cov+2*opt+2*proof+1.5*rev+diversity-2*risk-1.5*complexity-.35*(k-1)
    residual=tuple(sorted(required-caps)); pids=tuple(sorted(ids)); body=(pids,round(cov,6),round(opt,6),tuple(sorted(domains)),residual)
    options.append(ArchitectureOption(pids,round(cov,6),round(opt,6),round(score,6),residual,tuple(sorted(domains)),_hash(body)))
  return tuple(sorted(options,key=lambda o:(len(o.residual_gaps),-o.score,o.pattern_ids))[:limit])

 def challenge(self,champion:ArchitectureOption,challenger:ArchitectureOption)->str:
  if challenger.residual_gaps and not champion.residual_gaps: return 'HOLD_CHALLENGER'
  if len(challenger.residual_gaps)<len(champion.residual_gaps): return 'CHALLENGER_ADVANCES'
  return 'CHALLENGER_ADVANCES' if challenger.score>=champion.score+0.5 else 'KEEP_CHAMPION'


def core_ai_patterns()->tuple[ArchitecturePattern,...]:
 """Provider-neutral starting genome; evidence/runtime proof remains receiver-local."""
 return (
  ArchitecturePattern('HYBRID_RETRIEVAL',('retrieval','semantic_context','citation'),.75,.15,.35,.95,('INDEX','EMBEDDING')),
  ArchitecturePattern('MISSION_DAG_AGENTS',('agents','planning','parallelism','proof_obligations'),.9,.2,.45,.9,('SCHEDULER','MODEL')),
  ArchitecturePattern('DURABLE_EVENT_WORKFLOW',('durability','resume','replay','idempotency'),.9,.2,.55,.85,('STATE','QUEUE')),
  ArchitecturePattern('CQRS_EVENT_SOURCING',('audit','as_of_state','recovery','read_write_separation'),.85,.25,.65,.75,('EVENT_LOG','PROJECTION')),
  ArchitecturePattern('MODEL_ROUTER_CHALLENGER',('model_routing','evaluation','fallback','cost_control'),.8,.25,.45,.95,('ROUTER','MODEL_PROVIDER')),
  ArchitecturePattern('MCP_TOOL_GATEWAY',('tools','capability_discovery','typed_contracts'),.9,.2,.35,.95,('TOOL_GATEWAY',)),
  ArchitecturePattern('A2A_AGENT_MESH',('agent_interop','delegation','capability_discovery'),.75,.3,.5,.9,('AGENT_PEER',)),
  ArchitecturePattern('INDEPENDENT_PROOF_SIDECAR',('verification','semantic_readback','provenance'),.95,.1,.35,.95,('ASSURANCE',)),
  ArchitecturePattern('LOCAL_FIRST_DEGRADED_CORE',('sovereignty','offline','recovery','provider_exit'),.85,.15,.55,.9,('LOCAL_RUNTIME','ARCHIVE')),
  ArchitecturePattern('SANDBOXED_CODE_CELLS',('code_execution','isolation','artifact_readback','rollback'),.85,.2,.45,.95,('SANDBOX',)),
 )
