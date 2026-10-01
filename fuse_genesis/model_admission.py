from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json,math,re

HEX64=re.compile(r"^[0-9a-f]{64}$")
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"))

@dataclass(frozen=True)
class ModelArtifact:
    model_id:str
    family:str
    format:str
    sha256:str
    size_bytes:int
    quantization:str
    context_tokens:int
    license_id:str
    source_ref:str
    capabilities:tuple[str,...]

    def validate(self):
        if self.format.upper() not in {"GGUF","SAFETENSORS","ONNX"}: raise ValueError("format")
        if not HEX64.fullmatch(self.sha256): raise ValueError("sha")
        if self.size_bytes<=0: raise ValueError("size")
        if self.context_tokens<=0: raise ValueError("context")
        if not self.license_id.strip() or not self.source_ref.strip(): raise ValueError("license/source")
        if not self.capabilities: raise ValueError("capabilities")
        return self

@dataclass(frozen=True)
class HardwareDescriptor:
    host_id:str
    ram_total_bytes:int
    ram_available_bytes:int
    vram_total_bytes:int
    vram_available_bytes:int
    cpu_threads:int
    gpu_name:str
    disk_free_bytes:int

    def validate(self):
        if min(self.ram_total_bytes,self.ram_available_bytes,self.disk_free_bytes,self.cpu_threads)<=0: raise ValueError("hardware")
        if self.ram_available_bytes>self.ram_total_bytes: raise ValueError("ram")
        if self.vram_available_bytes>self.vram_total_bytes: raise ValueError("vram")
        return self

@dataclass(frozen=True)
class FitPolicy:
    ram_reserve_bytes:int=2*1024**3
    disk_multiplier:float=1.5
    runtime_overhead_bytes:int=768*1024**2
    kv_bytes_per_token:float=32768
    gpu_offload_optional:bool=True

@dataclass(frozen=True)
class FitDecision:
    admitted:bool
    route:str
    required_ram_bytes:int
    required_disk_bytes:int
    estimated_kv_bytes:int
    reasons:tuple[str,...]

def evaluate_fit(m:ModelArtifact,h:HardwareDescriptor,p:FitPolicy=FitPolicy()):
    m.validate(); h.validate()
    kv=int(m.context_tokens*p.kv_bytes_per_token)
    required_ram=int(m.size_bytes*1.10 + kv + p.runtime_overhead_bytes)
    required_disk=int(m.size_bytes*p.disk_multiplier)
    usable_ram=max(0,h.ram_available_bytes-p.ram_reserve_bytes)
    reasons=[]
    if required_disk>h.disk_free_bytes: reasons.append("INSUFFICIENT_DISK")
    if required_ram>usable_ram: reasons.append("INSUFFICIENT_RAM")
    gpu_possible=h.vram_available_bytes>=min(m.size_bytes,required_ram)
    if not reasons:
        route="GPU_FULL" if gpu_possible else ("CPU_OR_PARTIAL_GPU" if p.gpu_offload_optional else "CPU")
        return FitDecision(True,route,required_ram,required_disk,kv,())
    return FitDecision(False,"REJECT",required_ram,required_disk,kv,tuple(reasons))

@dataclass(frozen=True)
class RuntimeProbe:
    model_id:str
    artifact_sha256:str
    runtime:str
    runtime_version:str
    host_id:str
    loaded:bool
    api_ok:bool
    cold_start_ms:int|None
    first_token_ms:int|None
    tokens_per_second:float|None
    observed_at:str

    def qualifies(self):
        return self.loaded and self.api_ok and self.artifact_sha256 and bool(self.runtime_version) and bool(self.host_id)

@dataclass(frozen=True)
class BenchmarkContext:
    task_id:str
    dataset_sha256:str
    hardware_id:str
    runtime_version:str
    model_sha256:str
    cache_state:str

    def comparable(self,other):
        fields=("task_id","dataset_sha256","hardware_id","runtime_version","cache_state")
        return all(getattr(self,f)==getattr(other,f) for f in fields)

@dataclass(frozen=True)
class BenchmarkResult:
    context:BenchmarkContext
    accepted:bool
    correctness:float
    latency_ms:int
    tokens_per_second:float
    owner_interventions:int

def winner(inc:BenchmarkResult,chal:BenchmarkResult):
    if not inc.context.comparable(chal.context): return "NOT_COMPARABLE"
    if not chal.accepted: return "INCUMBENT"
    if not inc.accepted: return "CHALLENGER"
    if chal.correctness < inc.correctness: return "INCUMBENT"
    chal_better=(chal.latency_ms<inc.latency_ms and chal.tokens_per_second>=inc.tokens_per_second)
    return "CHALLENGER" if chal_better else "INCUMBENT"

@dataclass(frozen=True)
class LoadPolicy:
    max_resident_models:int=1
    unload_idle_seconds:int=300
    prewarm_priority:tuple[str,...]=()

    def choose_resident(self,candidates:list[tuple[str,int,float]]):
        return tuple(x[0] for x in sorted(candidates,key=lambda x:(-x[1],-x[2],x[0]))[:self.max_resident_models])

def admission_receipt(model:ModelArtifact,hardware:HardwareDescriptor,fit:FitDecision,probe:RuntimeProbe|None):
    return {
      "schema":"FUSE-LOCAL-MODEL-ADMISSION-RECEIPT-V1",
      "model":asdict(model),
      "hardware":asdict(hardware),
      "fit":asdict(fit),
      "runtime_probe":asdict(probe) if probe else None,
      "artifact_admitted":model.validate() is model,
      "hardware_admitted":fit.admitted,
      "runtime_qualified":bool(probe and probe.qualifies()),
      "complete":bool(fit.admitted and probe and probe.qualifies())
    }
