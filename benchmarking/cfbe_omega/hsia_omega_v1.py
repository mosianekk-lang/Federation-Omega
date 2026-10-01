from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json,re
from typing import Mapping,Sequence

SCHEMA="FUSE-HSIA-OMEGA-V1"; VERSION="1.0.0"; DAILY_TARGET=100
CORPORA=("COMPANY","ALGORITHM","PATENT_PAPER","INTELLIGENCE_SOURCE")
FIVE_D=("DISCOVER","EXTRACT_MECHANISM","IDENTIFY_WHY_IT_WORKS","REMOVE_VENDOR_SPECIFIC_NOISE","COMPARE_COMPOSE")
PROPAGATION=("HARVEST_GENOME","OPPORTUNITY_RADAR","DESIRED_STATE","CAPABILITY_FEDERATION_MAP","ROUTE_MEMORY","LEARNING_LEDGER","SHARED_LEARNINGS","SYSTEM_RECEIVER_PROJECTIONS","GLOBAL_RECEIVER_BOOTSTRAP")

class Disposition(str,Enum):
    REUSE="REUSE"; EXTEND="EXTEND"; COMPOSE="COMPOSE"; REPURPOSE="REPURPOSE"; BUILD_RESIDUAL="BUILD_RESIDUAL"; REJECT="REJECT"
class Rights(str,Enum):
    CLEAR="CLEAR"; REVIEW_REQUIRED="REVIEW_REQUIRED"; RESTRICTED="RESTRICTED"; UNKNOWN="UNKNOWN"
class Proof(str,Enum):
    DISCOVERED="DISCOVERED"; SHADOW="SHADOW_VERIFIED"; NATURAL="NATURAL_EVIDENCE_VERIFIED"; RECEIVER="RECEIVER_LOCAL_VERIFIED"

@dataclass(frozen=True,slots=True)
class IntelligenceItem:
    item_id:str; corpus:str; title:str; mechanism:str; why:str; source_refs:tuple[str,...]
    tags:tuple[str,...]=(); vendor_terms:tuple[str,...]=(); required:tuple[str,...]=()
    rights:Rights=Rights.UNKNOWN; confidence:float=.5; freshness_days:int=0
    def validate(self):
        if not self.item_id or self.corpus not in CORPORA or not self.title or not self.mechanism or not self.why or not self.source_refs: raise ValueError("HSIA_INVALID_ITEM")
        if not 0<=self.confidence<=1 or self.freshness_days<0: raise ValueError("HSIA_INVALID_EVIDENCE")
        return self

@dataclass(frozen=True,slots=True)
class EstateCapability:
    capability_id:str; tokens:tuple[str,...]; primitives:tuple[str,...]=(); proof_refs:tuple[str,...]=()
    def validate(self):
        if not self.capability_id or (not self.tokens and not self.primitives): raise ValueError("HSIA_INVALID_CAPABILITY")
        return self

@dataclass(frozen=True,slots=True)
class Decision:
    item_id:str; disposition:Disposition; matches:tuple[str,...]; coverage:float; missing:tuple[str,...]
    source_work:bool; rights_review:bool; stable_promotion_allowed:bool=False

@dataclass(frozen=True,slots=True)
class DailyReceipt:
    schema:str; version:str; input_count:int; changed_count:int; unchanged_count:int
    corpus_counts:tuple[tuple[str,int],...]; decisions:tuple[Decision,...]; missions:tuple[dict[str,object],...]
    fingerprints:tuple[str,...]; corpus_floor_met:bool; external_effect_authorized:bool
    source_mutation_authorized:bool; stable_global_promotion_allowed:bool; receipt_sha256:str

def _canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)
def _hash(x): return sha256(_canon(x).encode()).hexdigest()
def _tokens(*xs):
    out=set()
    for x in xs:
        vals=x if isinstance(x,(tuple,list,set,frozenset)) else (x,)
        for v in vals: out.update(t for t in re.findall(r"[a-z0-9][a-z0-9_+-]{1,}",str(v).lower()) if len(t)>=3)
    return tuple(sorted(out))
def _ratio(a,b):
    a,b=set(a),set(b)
    return 0.0 if not a or not b else len(a&b)/len(a|b)

def fingerprint(item:IntelligenceItem)->str:
    item.validate(); return _hash(asdict(item))

def changed(items:Sequence[IntelligenceItem],previous:Mapping[str,str]|None=None):
    previous=dict(previous or {}); seen=set(); out=[]
    for x in items:
        x.validate()
        if x.item_id in seen: raise ValueError("HSIA_DUPLICATE_ITEM")
        seen.add(x.item_id)
        if previous.get(x.item_id)!=fingerprint(x): out.append(x)
    return tuple(out)

def harvest(item:IntelligenceItem):
    item.validate(); clean=item.mechanism
    for term in sorted(set(item.vendor_terms),key=len,reverse=True):
        clean=re.sub(re.escape(term),"provider",clean,flags=re.I)
    clean=re.sub(r"\s+"," ",clean).strip()
    body={"item_id":item.item_id,"corpus":item.corpus,"mechanism":clean,"why":item.why,"tokens":_tokens(clean,item.tags),"required":_tokens(item.required),"sources":sorted(item.source_refs),"rights":item.rights.value,"five_d":FIVE_D}
    body["fingerprint"]=_hash(body); return body

def classify(h:Mapping[str,object],estate:Sequence[EstateCapability])->Decision:
    if h["rights"]==Rights.RESTRICTED.value:
        return Decision(str(h["item_id"]),Disposition.REJECT,(),0.0,tuple(h["required"]),False,True)
    ht=set(h["tokens"])|set(h["required"]); scored=[]
    for c in estate:
        ct=_tokens(c.validate().tokens,c.primitives); s=_ratio(ht,ct)
        if s>0: scored.append((s,c,ct))
    scored.sort(key=lambda z:(-z[0],z[1].capability_id)); top=scored[0] if scored else None
    matches=tuple(x[1].capability_id for x in scored[:4]); covered=set()
    for _,_,ct in scored[:4]: covered|=set(ct)
    missing=tuple(sorted(set(h["required"])-covered)); coverage=len(ht&covered)/len(ht) if ht else 1.0; top_score=top[0] if top else 0.0
    if top and top_score>=.82 and not missing: d=Disposition.REUSE; work=False
    elif top and top_score>=.55: d=Disposition.EXTEND; work=bool(missing)
    elif len(scored)>=2 and coverage>=.70: d=Disposition.COMPOSE; work=bool(missing)
    elif h["required"] and not (set(h["required"])&covered): d=Disposition.BUILD_RESIDUAL; work=True
    elif top and top_score>=.25: d=Disposition.REPURPOSE; work=True
    else: d=Disposition.BUILD_RESIDUAL; work=True
    review=h["rights"] in (Rights.REVIEW_REQUIRED.value,Rights.UNKNOWN.value)
    return Decision(str(h["item_id"]),d,matches,round(coverage,6),missing,work,review)

def compile_daily(*,items:Sequence[IntelligenceItem],estate:Sequence[EstateCapability],previous:Mapping[str,str]|None=None,target:int=DAILY_TARGET)->DailyReceipt:
    if target<1: raise ValueError("HSIA_BAD_TARGET")
    all_items=tuple(x.validate() for x in items); delta=changed(all_items,previous); hs=tuple(harvest(x) for x in delta); ds=tuple(classify(h,estate) for h in hs)
    missions=[]
    for h,d in zip(hs,ds):
        if d.disposition in (Disposition.REUSE,Disposition.REJECT): continue
        idem=f"HSIA:{h['item_id']}:{h['fingerprint'][:16]}:{d.disposition.value}"
        missions.append({"mission_id":"MISSION-HSIA-"+_hash(idem)[:16].upper(),"item_id":h["item_id"],"disposition":d.disposition.value,"idempotency_key":idem,"dependencies":tuple(sorted(set(d.matches)|set(d.missing))),"proof_requirements":("SOURCE_INDEPENDENT_COURT","NON_REGRESSION","PROVENANCE_RIGHTS","RECEIVER_LOCAL_PROOF","NATURAL_EVIDENCE_WHEN_PROMOTING"),"authority_ceiling":"A1_INTERNAL","effect_ceiling":"NO_NEW_EXTERNAL_EFFECT","source_serialized_by_fdof":True,"owner_action_required":False})
    counts=tuple((k,sum(x.corpus==k for x in all_items)) for k in CORPORA); fps=tuple(sorted(str(h["fingerprint"]) for h in hs))
    body={"schema":SCHEMA,"version":VERSION,"input":len(all_items),"changed":len(delta),"counts":counts,"decisions":[asdict(d) for d in ds],"missions":missions,"fingerprints":fps,"corpus_floor_met":all(n>=target for _,n in counts),"external_effect_authorized":False,"source_mutation_authorized":False,"stable_global_promotion_allowed":False}
    return DailyReceipt(SCHEMA,VERSION,len(all_items),len(delta),len(all_items)-len(delta),counts,ds,tuple(missions),fps,body["corpus_floor_met"],False,False,False,_hash(body))

def propagation_targets(*,decision:Decision,proof:Proof,rights:Rights):
    if decision.disposition is Disposition.REJECT or rights in (Rights.RESTRICTED,Rights.UNKNOWN): return ()
    return PROPAGATION if proof in (Proof.NATURAL,Proof.RECEIVER) else ()
