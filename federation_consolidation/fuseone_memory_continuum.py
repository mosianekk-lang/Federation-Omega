from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import tempfile
from typing import Any, Mapping, Sequence
from datetime import datetime, timezone

SCHEMA_VERSION = "FMC-MEMORY-1.0"
EXPORT_VERSION = "FMC-EXPORT-1.0"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(_canonical_json(record) + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    rows=[]
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip(): rows.append(json.loads(line))
    return rows


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name+".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(_canonical_json(value))
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class MemoryKind(str, Enum):
    INTENT="INTENT"; DECISION="DECISION"; FACT="FACT"; CLAIM="CLAIM"; HYPOTHESIS="HYPOTHESIS"; ASSUMPTION="ASSUMPTION"; CAPABILITY="CAPABILITY"; PROJECT="PROJECT"; SYSTEM="SYSTEM"; WORKFLOW="WORKFLOW"; PROCEDURE="PROCEDURE"; FAILURE="FAILURE"; NEGATIVE_KNOWLEDGE="NEGATIVE_KNOWLEDGE"; PROOF="PROOF"; ARTIFACT="ARTIFACT"; OPPORTUNITY="OPPORTUNITY"; DEPENDENCY="DEPENDENCY"; RELATIONSHIP="RELATIONSHIP"; EVENT="EVENT"; NEXT_ACTION="NEXT_ACTION"; POLICY="POLICY"; AUTHORITY="AUTHORITY"; CONTEXT_PACKAGE="CONTEXT_PACKAGE"; CONTINUATION_CAPSULE="CONTINUATION_CAPSULE"; PRESENT_TRUTH_CUT="PRESENT_TRUTH_CUT"; RECOVERY_MANIFEST="RECOVERY_MANIFEST"

class Canonicality(str, Enum):
    AUTHORITATIVE="AUTHORITATIVE"; DERIVED="DERIVED"; HISTORICAL="HISTORICAL"; EXPERIMENTAL="EXPERIMENTAL"; STALE="STALE"; QUARANTINED="QUARANTINED"

class SecurityClass(str, Enum):
    PUBLIC="PUBLIC"; INTERNAL="INTERNAL"; CONFIDENTIAL="CONFIDENTIAL"; SOVEREIGN="SOVEREIGN"; EPHEMERAL="EPHEMERAL"


@dataclass(frozen=True)
class MemoryObject:
    memory_id: str
    object_kind: MemoryKind
    payload: Mapping[str, Any]
    owner_scope: str = "KIM"
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=_now_iso)
    observed_at: str = field(default_factory=_now_iso)
    valid_from: str = field(default_factory=_now_iso)
    valid_until: str | None = None
    status: str = "ACTIVE"
    canonicality: Canonicality = Canonicality.DERIVED
    source_refs: tuple[str,...] = ()
    evidence_refs: tuple[str,...] = ()
    parent_ids: tuple[str,...] = ()
    supersedes: tuple[str,...] = ()
    superseded_by: tuple[str,...] = ()
    intent_ids: tuple[str,...] = ()
    project_ids: tuple[str,...] = ()
    security_class: SecurityClass = SecurityClass.INTERNAL
    retention_class: str = "STANDARD"
    authority_scope: str = "A1_INTERNAL"
    confidence: float = 1.0
    currentness_ttl_seconds: int | None = None
    last_verified_at: str | None = None

    def material(self) -> dict[str,Any]:
        d=asdict(self); d["object_kind"]=self.object_kind.value; d["canonicality"]=self.canonicality.value; d["security_class"]=self.security_class.value; d.pop("superseded_by",None); return d
    @property
    def content_hash(self)->str: return _digest(self.material())
    def to_dict(self)->dict[str,Any]:
        d=self.material(); d["superseded_by"]=list(self.superseded_by); d["content_hash"]=self.content_hash; return d
    @classmethod
    def from_dict(cls,d:Mapping[str,Any])->"MemoryObject":
        return cls(memory_id=str(d["memory_id"]),object_kind=MemoryKind(d["object_kind"]),payload=dict(d.get("payload",{})),owner_scope=str(d.get("owner_scope","KIM")),schema_version=str(d.get("schema_version",SCHEMA_VERSION)),created_at=str(d.get("created_at",_now_iso())),observed_at=str(d.get("observed_at",_now_iso())),valid_from=str(d.get("valid_from",_now_iso())),valid_until=d.get("valid_until"),status=str(d.get("status","ACTIVE")),canonicality=Canonicality(d.get("canonicality",Canonicality.DERIVED.value)),source_refs=tuple(d.get("source_refs",())),evidence_refs=tuple(d.get("evidence_refs",())),parent_ids=tuple(d.get("parent_ids",())),supersedes=tuple(d.get("supersedes",())),superseded_by=tuple(d.get("superseded_by",())),intent_ids=tuple(d.get("intent_ids",())),project_ids=tuple(d.get("project_ids",())),security_class=SecurityClass(d.get("security_class",SecurityClass.INTERNAL.value)),retention_class=str(d.get("retention_class","STANDARD")),authority_scope=str(d.get("authority_scope","A1_INTERNAL")),confidence=float(d.get("confidence",1.0)),currentness_ttl_seconds=d.get("currentness_ttl_seconds"),last_verified_at=d.get("last_verified_at"))

@dataclass(frozen=True)
class ContextRelation:
    subject_id:str; predicate:str; object_id:str; evidence_refs:tuple[str,...]=(); created_at:str=field(default_factory=_now_iso)
    @property
    def relation_hash(self)->str:return _digest(asdict(self))

@dataclass(frozen=True)
class PresentTruthCut:
    cut_id:str; captured_at:str; source_main_sha:str; source_main_tree:str; fdof_state:str; mission_checkpoint:str; kdv_checkpoint:str; artifact_checkpoint:str; runtime_receipts:tuple[str,...]=(); provider_receipts:tuple[str,...]=(); active_intents:tuple[str,...]=(); contradictions:tuple[str,...]=()
    @property
    def digest(self)->str:return _digest(asdict(self))

@dataclass(frozen=True)
class ContinuationCapsule:
    capsule_id:str; intent_id:str; current_state_refs:tuple[str,...]; locked_decision_refs:tuple[str,...]; proven_claim_refs:tuple[str,...]; open_claim_refs:tuple[str,...]; blocker_refs:tuple[str,...]; source_runtime_refs:tuple[str,...]; artifact_refs:tuple[str,...]; authority_state_refs:tuple[str,...]; commercial_opportunity_refs:tuple[str,...]; exact_next_action:str; present_truth_cut_id:str; owner_action_required:str="NONE"; created_at:str=field(default_factory=_now_iso)
    @property
    def digest(self)->str:return _digest(asdict(self))

@dataclass(frozen=True)
class RecoveryManifest:
    manifest_id:str; latest_capsule_id:str; raw_archive_refs:tuple[str,...]; canonical_memory_refs:tuple[str,...]; source_refs:tuple[str,...]; kdv_refs:tuple[str,...]; artifact_vault_refs:tuple[str,...]; present_truth_cut_id:str; replica_refs:tuple[str,...]; index_schemas:tuple[str,...]; restore_procedure:tuple[str,...]; created_at:str=field(default_factory=_now_iso)
    @property
    def digest(self)->str:return _digest(asdict(self))

class MemoryConflict(RuntimeError): pass


class MemoryStore:
    """Portable append-only JSONL memory. Indexes are derived and disposable."""
    def __init__(self, root:str|Path):
        self.root=Path(root); self.objects=self.root/"objects"; self.checkpoints=self.root/"checkpoints"; self.index_dir=self.root/"indexes"; self.root.mkdir(parents=True,exist_ok=True); self.objects.mkdir(exist_ok=True); self.checkpoints.mkdir(exist_ok=True); self.index_dir.mkdir(exist_ok=True)
        for p in (self.root/"relations.jsonl",self.root/"replicas.jsonl",self.root/"audit.jsonl"):
            if not p.exists(): p.touch()

    def _obj_path(self,memory_id:str)->Path:return self.objects/f"{_safe_id(memory_id)}.jsonl"
    def _audit(self,event_type:str,payload:Mapping[str,Any])->None:_append_jsonl(self.root/"audit.jsonl",{"event_id":f"fmc_evt_{_digest([event_type,payload,_now_iso()])[:24]}","event_type":event_type,"payload":dict(payload),"created_at":_now_iso()})

    def append(self,obj:MemoryObject)->dict[str,Any]:
        path=self._obj_path(obj.memory_id); rows=_read_jsonl(path)
        for row in rows:
            if row.get("content_hash")==obj.content_hash:return {"memory_id":obj.memory_id,"version":row["version"],"reused":True,"content_hash":obj.content_hash}
        version=len(rows)+1; rec={"version":version,**obj.to_dict()}; _append_jsonl(path,rec); self._audit("MEMORY_APPEND",{"memory_id":obj.memory_id,"version":version,"content_hash":obj.content_hash}); return {"memory_id":obj.memory_id,"version":version,"reused":False,"content_hash":obj.content_hash}

    def latest(self,memory_id:str)->MemoryObject|None:
        rows=_read_jsonl(self._obj_path(memory_id)); return MemoryObject.from_dict(rows[-1]) if rows else None
    def all_latest(self)->list[MemoryObject]:
        out=[]
        for p in sorted(self.objects.glob("*.jsonl")):
            rows=_read_jsonl(p)
            if rows: out.append(MemoryObject.from_dict(rows[-1]))
        return sorted(out,key=lambda o:o.memory_id)
    def version_count(self,memory_id:str)->int:return len(_read_jsonl(self._obj_path(memory_id)))

    def add_relation(self,rel:ContextRelation)->str:
        rows=_read_jsonl(self.root/"relations.jsonl")
        if not any(r.get("relation_hash")==rel.relation_hash for r in rows): _append_jsonl(self.root/"relations.jsonl",{"relation_hash":rel.relation_hash,**asdict(rel)}); self._audit("RELATION_APPEND",{"relation_hash":rel.relation_hash})
        return rel.relation_hash
    def relations_for(self,memory_id:str)->list[dict[str,Any]]:return [r for r in _read_jsonl(self.root/"relations.jsonl") if r["subject_id"]==memory_id or r["object_id"]==memory_id]

    def register_replica(self,memory_id:str,surface:str,locator:str,content_hash:str)->None:
        _append_jsonl(self.root/"replicas.jsonl",{"memory_id":memory_id,"surface":surface,"locator":locator,"content_hash":content_hash,"verified_at":_now_iso()})
    def orphaned(self,minimum_replicas:int=2)->list[str]:
        reps=_read_jsonl(self.root/"replicas.jsonl"); latest={}
        for r in reps:latest[(r["memory_id"],r["surface"],r["locator"])]=r
        counts={}
        for r in latest.values():counts[r["memory_id"]]=counts.get(r["memory_id"],0)+1
        return sorted([o.memory_id for o in self.all_latest() if counts.get(o.memory_id,0)<minimum_replicas])

    def rebuild_indexes(self)->dict[str,int]:
        idx={}
        for obj in self.all_latest():
            text=_canonical_json(obj.to_dict()).lower(); terms=sorted({t for t in re.findall(r"[a-z0-9_-]{3,}",text)}); idx[obj.memory_id]=terms
        _atomic_json(self.index_dir/"keyword-v1.json",{"schema":"FMC-KEYWORD-INDEX-V1","objects":idx})
        return {"memory_objects":len(idx),"terms_written":sum(len(v) for v in idx.values())}
    def search(self,query:str)->list[str]:
        p=self.index_dir/"keyword-v1.json"
        if not p.exists():return []
        idx=json.loads(p.read_text(encoding="utf-8"))["objects"]; terms=set(re.findall(r"[a-z0-9_-]{3,}",query.lower())); scored=[]
        for mid,vals in idx.items():
            score=len(terms & set(vals))
            if score:scored.append((-score,mid))
        return [m for _,m in sorted(scored)]

    def put_checkpoint(self,checkpoint_id:str,kind:str,payload:Mapping[str,Any])->str:
        digest=_digest(payload); path=self.checkpoints/f"{_safe_id(checkpoint_id)}.json"
        if path.exists():
            old=json.loads(path.read_text(encoding="utf-8"))
            if old["content_hash"]!=digest:raise MemoryConflict(f"checkpoint fork detected: {checkpoint_id}")
            return digest
        _atomic_json(path,{"checkpoint_id":checkpoint_id,"kind":kind,"payload":dict(payload),"content_hash":digest,"created_at":_now_iso()}); return digest
    def get_checkpoint(self,checkpoint_id:str)->dict[str,Any]|None:
        path=self.checkpoints/f"{_safe_id(checkpoint_id)}.json"; return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    def create_capsule(self,c:ContinuationCapsule)->str:return self.put_checkpoint(c.capsule_id,"CONTINUATION_CAPSULE",asdict(c))
    def create_manifest(self,m:RecoveryManifest)->str:return self.put_checkpoint(m.manifest_id,"RECOVERY_MANIFEST",asdict(m))
    def create_present_truth_cut(self,c:PresentTruthCut)->str:return self.put_checkpoint(c.cut_id,"PRESENT_TRUTH_CUT",asdict(c))

    def export_jsonl(self,path:str|Path,*,max_security:SecurityClass=SecurityClass.SOVEREIGN)->str:
        order=[SecurityClass.PUBLIC,SecurityClass.INTERNAL,SecurityClass.CONFIDENTIAL,SecurityClass.SOVEREIGN,SecurityClass.EPHEMERAL]; allowed=set(order[:order.index(max_security)+1]); records=[]
        for obj in self.all_latest():
            if obj.security_class==SecurityClass.EPHEMERAL or obj.security_class not in allowed:continue
            d=obj.to_dict(); d["payload"]=_sanitize_payload(d["payload"]); records.append({"record_type":"MEMORY_OBJECT","data":d})
        for r in _read_jsonl(self.root/"relations.jsonl"):records.append({"record_type":"RELATION","data":r})
        for p in sorted(self.checkpoints.glob("*.json")):
            d=json.loads(p.read_text(encoding="utf-8")); d["payload"]=_sanitize_payload(d["payload"]); records.append({"record_type":"CHECKPOINT","data":d})
        out=Path(path)
        with out.open("w",encoding="utf-8",newline="\n") as f:
            f.write(_canonical_json({"record_type":"EXPORT_HEADER","data":{"version":EXPORT_VERSION,"created_at":_now_iso()}})+"\n")
            for r in records:f.write(_canonical_json(r)+"\n")
        return sha256(out.read_bytes()).hexdigest()

    @classmethod
    def import_jsonl(cls,export_path:str|Path,root:str|Path)->"MemoryStore":
        store=cls(root); header=False
        for rec in _read_jsonl(Path(export_path)):
            typ=rec["record_type"]; data=rec["data"]
            if typ=="EXPORT_HEADER":
                if data["version"]!=EXPORT_VERSION:raise ValueError("unsupported export version")
                header=True
            elif typ=="MEMORY_OBJECT":store.append(MemoryObject.from_dict(data))
            elif typ=="RELATION":store.add_relation(ContextRelation(data["subject_id"],data["predicate"],data["object_id"],tuple(data.get("evidence_refs",())),data.get("created_at",_now_iso())))
            elif typ=="CHECKPOINT":store.put_checkpoint(data["checkpoint_id"],data["kind"],data["payload"])
        if not header:raise ValueError("missing export header")
        return store

    def context_projection(self,*,intent_ids:Sequence[str]=(),project_ids:Sequence[str]=(),max_security:SecurityClass=SecurityClass.INTERNAL)->list[dict[str,Any]]:
        order=[SecurityClass.PUBLIC,SecurityClass.INTERNAL,SecurityClass.CONFIDENTIAL,SecurityClass.SOVEREIGN]; max_idx=order.index(max_security); out=[]
        for obj in self.all_latest():
            if obj.security_class==SecurityClass.EPHEMERAL or order.index(obj.security_class)>max_idx:continue
            if intent_ids and not(set(obj.intent_ids)&set(intent_ids)):continue
            if project_ids and not(set(obj.project_ids)&set(project_ids)):continue
            d=obj.to_dict(); d["payload"]=_sanitize_payload(d["payload"]); out.append(d)
        return out

    def currentness_status(self,memory_id:str,now_epoch_seconds:float|None=None)->str:
        obj=self.latest(memory_id)
        if not obj:return "MISSING"
        if obj.canonicality in {Canonicality.STALE,Canonicality.QUARANTINED}:return obj.canonicality.value
        if obj.currentness_ttl_seconds is None or obj.last_verified_at is None:return "UNBOUNDED_HISTORY_ONLY"
        verified=datetime.fromisoformat(obj.last_verified_at.replace("Z","+00:00")).timestamp(); now=(datetime.now(timezone.utc).timestamp() if now_epoch_seconds is None else now_epoch_seconds); return "CURRENT" if now-verified<=obj.currentness_ttl_seconds else "STALE"


def _sanitize_payload(value:Any)->Any:
    secret_keys={"password","passwd","secret","secret_value","api_key","token","refresh_token","private_key","credential"}
    if isinstance(value,Mapping):return {k:("<REDACTED:SECRET_REF_REQUIRED>" if str(k).lower() in secret_keys else _sanitize_payload(v)) for k,v in value.items()}
    if isinstance(value,list):return [_sanitize_payload(v) for v in value]
    if isinstance(value,tuple):return tuple(_sanitize_payload(v) for v in value)
    return value


def migrate_memory_dict(raw:Mapping[str,Any],target_version:str=SCHEMA_VERSION)->dict[str,Any]:
    data=dict(raw); current=str(data.get("schema_version","FMC-MEMORY-0.9"))
    if current==target_version:return data
    if current=="FMC-MEMORY-0.9" and target_version==SCHEMA_VERSION:
        data.setdefault("owner_scope","KIM"); data.setdefault("canonicality",Canonicality.DERIVED.value); data.setdefault("security_class",SecurityClass.INTERNAL.value); data.setdefault("retention_class","STANDARD"); data.setdefault("authority_scope","A1_INTERNAL"); data.setdefault("confidence",1.0); data.setdefault("source_refs",[]); data.setdefault("evidence_refs",[]); data.setdefault("parent_ids",[]); data.setdefault("supersedes",[]); data.setdefault("superseded_by",[]); data.setdefault("intent_ids",[]); data.setdefault("project_ids",[]); data.setdefault("status","ACTIVE"); data.setdefault("created_at",_now_iso()); data.setdefault("observed_at",data["created_at"]); data.setdefault("valid_from",data["created_at"]); data.setdefault("valid_until",None); data["schema_version"]=SCHEMA_VERSION; return data
    raise ValueError(f"unsupported migration {current} -> {target_version}")
