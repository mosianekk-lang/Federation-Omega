from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Iterable,Mapping
import hashlib,json,re

HEX64=re.compile(r"^[0-9a-f]{64}$")
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))
def sha_bytes(b): return hashlib.sha256(b).hexdigest()

@dataclass(frozen=True)
class CreativeIntent:
    intent_id:str
    modalities:tuple[str,...]
    editable_master_required:bool
    provenance_required:bool
    target_fidelity:str
    dimensions:tuple[int,int]|None=None
    duration_s:float|None=None

    def validate(self):
        if not self.intent_id or not self.modalities: raise ValueError("intent")
        if self.target_fidelity not in {"DRAFT","STANDARD","HIGH","MASTER"}: raise ValueError("fidelity")
        if self.dimensions and min(self.dimensions)<=0: raise ValueError("dimensions")
        if self.duration_s is not None and self.duration_s<=0: raise ValueError("duration")
        return self

@dataclass(frozen=True)
class CreativeCellDescriptor:
    cell_id:str
    engine_class:str
    executable_ref:str
    version:str
    local:bool
    modalities:tuple[str,...]
    editable_outputs:bool
    deterministic_seed:bool
    offline_capable:bool
    provenance_capable:bool
    max_width:int|None=None
    max_height:int|None=None
    max_duration_s:float|None=None
    license_id:str=""
    source_ref:str=""

    def validate(self):
        if not self.cell_id or not self.version or not self.executable_ref: raise ValueError("cell")
        if not self.modalities: raise ValueError("modalities")
        if not self.license_id or not self.source_ref: raise ValueError("license/source")
        return self

@dataclass(frozen=True)
class CellDecision:
    eligible:bool
    reasons:tuple[str,...]
    score:int

def qualify_cell(intent:CreativeIntent,cell:CreativeCellDescriptor):
    intent.validate(); cell.validate()
    reasons=[]; req=set(intent.modalities)
    if not req<=set(cell.modalities): reasons.append("MODALITY_GAP")
    if intent.editable_master_required and not cell.editable_outputs: reasons.append("EDITABLE_MASTER_GAP")
    if intent.provenance_required and not cell.provenance_capable: reasons.append("PROVENANCE_GAP")
    if intent.dimensions:
        w,h=intent.dimensions
        if cell.max_width and w>cell.max_width: reasons.append("WIDTH_LIMIT")
        if cell.max_height and h>cell.max_height: reasons.append("HEIGHT_LIMIT")
    if intent.duration_s is not None and cell.max_duration_s and intent.duration_s>cell.max_duration_s:
        reasons.append("DURATION_LIMIT")
    score=0
    if cell.local: score+=5
    if cell.offline_capable: score+=4
    if cell.editable_outputs: score+=3
    if cell.provenance_capable: score+=2
    if cell.deterministic_seed: score+=1
    return CellDecision(not reasons,tuple(reasons),score)

def choose_cell(intent,cells):
    decisions=[(c,qualify_cell(intent,c)) for c in cells]
    eligible=[x for x in decisions if x[1].eligible]
    if not eligible: return None,decisions
    eligible.sort(key=lambda x:(-x[1].score,x[0].cell_id))
    return eligible[0][0],decisions

@dataclass(frozen=True)
class ArtifactReceipt:
    artifact_id:str
    logical_role:str
    media_type:str
    sha256:str
    editable:bool
    provenance_ref:str
    source_asset_refs:tuple[str,...]
    engine_cell_id:str
    engine_version:str
    intent_id:str

    def validate(self,intent:CreativeIntent):
        if not HEX64.fullmatch(self.sha256): raise ValueError("sha")
        if intent.editable_master_required and not self.editable: raise ValueError("editable")
        if intent.provenance_required and not self.provenance_ref: raise ValueError("provenance")
        if not self.engine_cell_id or not self.engine_version or self.intent_id!=intent.intent_id: raise ValueError("binding")
        return self

@dataclass(frozen=True)
class Defect:
    defect_id:str
    region:str
    defect_class:str
    severity:int
    mutable_component:str

@dataclass(frozen=True)
class DefectMap:
    artifact_id:str
    defects:tuple[Defect,...]
    def targeted_components(self):
        return tuple(sorted({d.mutable_component for d in self.defects if d.severity>0}))

@dataclass(frozen=True)
class RerenderPlan:
    preserve_artifact_id:str
    components:tuple[str,...]
    full_rerender:bool

def compile_rerender(defects:DefectMap,full_threshold=5):
    comps=defects.targeted_components()
    severe=sum(d.severity for d in defects.defects)
    return RerenderPlan(defects.artifact_id,comps,severe>=full_threshold)

@dataclass(frozen=True)
class QCResult:
    artifact_id:str
    fidelity:float
    editability:bool
    provenance:bool
    technical_valid:bool
    accepted:bool

def qc(intent:CreativeIntent,receipt:ArtifactReceipt,*,fidelity,technical_valid):
    receipt.validate(intent)
    threshold={"DRAFT":.60,"STANDARD":.75,"HIGH":.90,"MASTER":.97}[intent.target_fidelity]
    ok=fidelity>=threshold and technical_valid and (receipt.editable or not intent.editable_master_required) and (bool(receipt.provenance_ref) or not intent.provenance_required)
    return QCResult(receipt.artifact_id,fidelity,receipt.editable,bool(receipt.provenance_ref),technical_valid,ok)

@dataclass(frozen=True)
class RuntimeProbe:
    cell_id:str
    version:str
    executable_sha256:str
    host_id:str
    callable:bool
    offline_tested:bool
    observed_at:str
    def qualifies(self):
        return self.callable and HEX64.fullmatch(self.executable_sha256) and bool(self.version) and bool(self.host_id)

def admission_receipt(cell:CreativeCellDescriptor,probe:RuntimeProbe|None):
    return {"cell":asdict(cell),"runtime_probe":asdict(probe) if probe else None,
            "source_admitted":cell.validate() is cell,
            "runtime_qualified":bool(probe and probe.qualifies())}
