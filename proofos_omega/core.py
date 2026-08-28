from __future__ import annotations

import fnmatch, hashlib, json, os, re, subprocess, sys, time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

class ProofOSError(RuntimeError): pass
class PolicyError(ProofOSError): pass
class ImpactError(ProofOSError): pass
class RunnerError(ProofOSError): pass

class RiskTier(IntEnum):
    R0_DOCS=0; R1_ISOLATED=1; R2_SHARED=2; R3_SECURITY_ABI=3; R4_CORE=4; R5_RELEASE=5
    @classmethod
    def parse(cls, value):
        if isinstance(value, cls): return value
        if isinstance(value, int): return cls(value)
        key=str(value).strip().upper()
        aliases={"R0":cls.R0_DOCS,"R1":cls.R1_ISOLATED,"R2":cls.R2_SHARED,"R3":cls.R3_SECURITY_ABI,"R4":cls.R4_CORE,"R5":cls.R5_RELEASE}
        if key in aliases: return aliases[key]
        try: return cls[key]
        except KeyError as e: raise PolicyError(f"unknown risk tier: {value!r}") from e

VALID_KINDS={"unittest_glob","unittest_module","compileall"}
VALID_SCOPES={"GLOBAL","SUBSYSTEM","SHADOW"}
VALID_FAILURES={"SECURITY_VIOLATION","AUTHORITY_EXPANSION","PROVENANCE_FAILURE","SOURCE_INTEGRITY_FAILURE","ABI_REGRESSION","SUBSYSTEM_REGRESSION","EXPORT_COMPATIBILITY","SELECTOR_ESCAPE","GENERAL_REGRESSION"}
SAFE_TARGET=re.compile(r"^[A-Za-z0-9_.*:/-]+(?:\.py)?$")
SAFE_MODULE=re.compile(r"^[A-Za-z0-9_.]+$")

def canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha256_bytes(b:bytes): return hashlib.sha256(b).hexdigest()
def sha256_json(v): return sha256_bytes(canonical_json(v).encode())
def stable_unique(xs:Iterable[str]): return sorted(set(xs))
def any_glob(path:str, patterns:Sequence[str]): return any(fnmatch.fnmatchcase(path,p) for p in patterns)
def normalize_path(path:str):
    raw=str(path).replace("\\","/").strip()
    while raw.startswith("./"): raw=raw[2:]
    out=str(PurePosixPath(raw))
    if out in {"","."} or out==".." or out.startswith("../") or "/../" in out: raise ImpactError(f"unsafe path: {path!r}")
    return out

@dataclass(frozen=True)
class SubsystemRule: subsystem:str; patterns:tuple[str,...]; depends_on:tuple[str,...]=()
@dataclass(frozen=True)
class RiskRule: risk:RiskTier; patterns:tuple[str,...]; reason:str
@dataclass(frozen=True)
class HistoricalAssociation: patterns:tuple[str,...]; tests:tuple[str,...]; evidence:str
@dataclass(frozen=True)
class TestSpec:
    test_id:str; kind:str; target:str; patterns:tuple[str,...]; subsystems:tuple[str,...]; always:bool=False; min_risk:RiskTier|None=None; hard_always_run:bool=False; sentinel_eligible:bool=True; optional_if_missing:bool=False; failure_class:str="SUBSYSTEM_REGRESSION"; block_scope:str="SUBSYSTEM"; timeout_seconds:int=180
    def validate(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{1,100}",self.test_id): raise PolicyError(f"unsafe test id: {self.test_id}")
        if self.kind not in VALID_KINDS: raise PolicyError(f"unsupported test kind {self.kind}")
        if self.block_scope not in VALID_SCOPES or self.failure_class not in VALID_FAILURES: raise PolicyError(f"unsafe test contract: {self.test_id}")
        if not 1<=self.timeout_seconds<=3600: raise PolicyError(f"invalid timeout: {self.test_id}")
        safe=SAFE_MODULE if self.kind=="unittest_module" else SAFE_TARGET
        if not safe.fullmatch(self.target): raise PolicyError(f"unsafe test target: {self.target}")

@dataclass(frozen=True)
class ImpactAssessment:
    changed_paths:tuple[str,...]; risk:RiskTier; risk_reasons:tuple[str,...]; direct_subsystems:tuple[str,...]; impacted_subsystems:tuple[str,...]; unmapped_production_paths:tuple[str,...]; graph_sha256:str
    def to_dict(self): return {"changed_paths":list(self.changed_paths),"risk":self.risk.name,"risk_reasons":list(self.risk_reasons),"direct_subsystems":list(self.direct_subsystems),"impacted_subsystems":list(self.impacted_subsystems),"unmapped_production_paths":list(self.unmapped_production_paths),"graph_sha256":self.graph_sha256}
@dataclass(frozen=True)
class SelectedTest:
    test_id:str; reasons:tuple[str,...]; mode:str="BLOCKING"
    def to_dict(self): return {"test_id":self.test_id,"reasons":list(self.reasons),"mode":self.mode}
@dataclass(frozen=True)
class OmittedTest:
    test_id:str; reasons:tuple[str,...]
    def to_dict(self): return {"test_id":self.test_id,"reasons":list(self.reasons)}
@dataclass(frozen=True)
class ProofManifest:
    schema:str; version:str; base_sha:str; head_sha:str; policy_sha256:str; impact:ImpactAssessment; selected_tests:tuple[SelectedTest,...]; omitted_tests:tuple[OmittedTest,...]; selector_state:Mapping[str,Any]; manifest_sha256:str
    def deterministic_payload(self): return {"schema":self.schema,"version":self.version,"base_sha":self.base_sha,"head_sha":self.head_sha,"policy_sha256":self.policy_sha256,"impact":self.impact.to_dict(),"selected_tests":[x.to_dict() for x in self.selected_tests],"omitted_tests":[x.to_dict() for x in self.omitted_tests],"selector_state":dict(self.selector_state)}
    def to_dict(self): d=self.deterministic_payload(); d["manifest_sha256"]=self.manifest_sha256; return d
    def verify(self): return sha256_json(self.deterministic_payload())==self.manifest_sha256
@dataclass(frozen=True)
class TestExecutionResult:
    test_id:str; status:str; returncode:int; elapsed_seconds:float; proof_key:str; stdout_sha256:str; stderr_sha256:str; failure_class:str; block_scope:str; reused_from_cache:bool=False
    def to_dict(self): return {"test_id":self.test_id,"status":self.status,"returncode":self.returncode,"elapsed_seconds":round(self.elapsed_seconds,6),"proof_key":self.proof_key,"stdout_sha256":self.stdout_sha256,"stderr_sha256":self.stderr_sha256,"failure_class":self.failure_class,"block_scope":self.block_scope,"reused_from_cache":self.reused_from_cache}
@dataclass(frozen=True)
class AdmissionReport:
    manifest_sha256:str; results:tuple[TestExecutionResult,...]; blocking_failures:tuple[str,...]; scoped_failures:tuple[str,...]; status:str; report_sha256:str
    def deterministic_payload(self): return {"manifest_sha256":self.manifest_sha256,"results":[x.to_dict() for x in self.results],"blocking_failures":list(self.blocking_failures),"scoped_failures":list(self.scoped_failures),"status":self.status}
    def to_dict(self): d=self.deterministic_payload(); d["report_sha256"]=self.report_sha256; return d

class ProofPolicy:
    def __init__(self, raw:Mapping[str,Any]):
        self.raw=json.loads(json.dumps(raw)); self.schema=str(raw.get("schema","")); self.version=str(raw.get("version",""))
        if self.schema!="FEDERATION-PROOFOS-OMEGA-V1" or not re.fullmatch(r"\d+\.\d+\.\d+",self.version): raise PolicyError("unsupported ProofOS policy")
        if raw.get("authority_ceiling")!="A1_INTERNAL" or raw.get("external_effect_default") is not False: raise PolicyError("ProofOS may not expand authority or external effect")
        sel=raw.get("selector",{}); self.sentinel_percent=int(sel.get("sentinel_percent",0)); self.fallback_test_id=str(sel.get("fallback_full_suite_test_id","")); self.production_extensions=tuple(sel.get("production_extensions",[".py",".json",".yaml",".yml",".toml",".sh",".ps1",".js",".mjs",".ts"])); self.nonproduction_prefixes=tuple(sel.get("nonproduction_prefixes",["docs","tests"]))
        if not 0<=self.sentinel_percent<=100: raise PolicyError("invalid sentinel percent")
        self.risk_rules=tuple(RiskRule(RiskTier.parse(x["risk"]),tuple(x.get("patterns",[])),str(x.get("reason",""))) for x in raw.get("risk_rules",[]))
        self.subsystem_rules=tuple(SubsystemRule(str(x["subsystem"]),tuple(x.get("patterns",[])),tuple(x.get("depends_on",[]))) for x in raw.get("subsystem_rules",[]))
        self.subsystems={x.subsystem for x in self.subsystem_rules}; self._validate_graph()
        self.historical_associations=tuple(HistoricalAssociation(tuple(x.get("patterns",[])),tuple(x.get("tests",[])),str(x.get("evidence",""))) for x in raw.get("historical_associations",[]))
        self.tests={}
        for x in raw.get("tests",[]):
            t=TestSpec(test_id=str(x["id"]),kind=str(x["kind"]),target=str(x["target"]),patterns=tuple(x.get("patterns",[])),subsystems=tuple(x.get("subsystems",[])),always=bool(x.get("always",False)),min_risk=RiskTier.parse(x["min_risk"]) if x.get("min_risk") else None,hard_always_run=bool(x.get("hard_always_run",False)),sentinel_eligible=bool(x.get("sentinel_eligible",True)),optional_if_missing=bool(x.get("optional_if_missing",False)),failure_class=str(x.get("failure_class","SUBSYSTEM_REGRESSION")),block_scope=str(x.get("block_scope","SUBSYSTEM")),timeout_seconds=int(x.get("timeout_seconds",180))); t.validate()
            if t.test_id in self.tests: raise PolicyError(f"duplicate test: {t.test_id}")
            if any(s not in self.subsystems for s in t.subsystems): raise PolicyError(f"unknown subsystem in {t.test_id}")
            self.tests[t.test_id]=t
        if self.fallback_test_id not in self.tests or not any(t.always for t in self.tests.values()): raise PolicyError("missing fallback or P0 invariant")
        for a in self.historical_associations:
            if any(t not in self.tests for t in a.tests): raise PolicyError("historical association references unknown test")
        self.sha256=sha256_json(self.raw)
    @classmethod
    def from_path(cls,path): return cls(json.loads(Path(path).read_text(encoding="utf-8")))
    def _validate_graph(self):
        graph={r.subsystem:set(r.depends_on) for r in self.subsystem_rules}
        if any(d not in graph for ds in graph.values() for d in ds): raise PolicyError("unknown subsystem dependency")
        visiting=set(); done=set()
        def walk(n):
            if n in visiting: raise PolicyError("subsystem dependency cycle")
            if n in done: return
            visiting.add(n)
            for d in graph[n]: walk(d)
            visiting.remove(n); done.add(n)
        for n in graph: walk(n)
    def dependency_closure(self, direct:Iterable[str]):
        impacted=set(direct); changed=True
        while changed:
            changed=False
            for r in self.subsystem_rules:
                if r.subsystem not in impacted and any(d in impacted for d in r.depends_on): impacted.add(r.subsystem); changed=True
        return sorted(impacted)
    def is_production_path(self,path):
        first=path.split("/",1)[0]
        return not(first in self.nonproduction_prefixes or path.endswith(".md")) and any(path.endswith(x) for x in self.production_extensions)

class ImpactCompiler:
    def __init__(self,policy): self.policy=policy
    def assess(self,changed_paths:Sequence[str]):
        paths=tuple(stable_unique(normalize_path(x) for x in changed_paths)); reasons=[]; risk=RiskTier.R0_DOCS
        for p in paths:
            matched=False
            for r in self.policy.risk_rules:
                if any_glob(p,r.patterns): matched=True; risk=max(risk,r.risk); reasons.append(f"{p}:{r.reason}:{r.risk.name}")
            if not matched and self.policy.is_production_path(p): risk=max(risk,RiskTier.R1_ISOLATED); reasons.append(f"{p}:DEFAULT_PRODUCTION:R1_ISOLATED")
        direct=stable_unique(r.subsystem for r in self.policy.subsystem_rules if any(any_glob(p,r.patterns) for p in paths))
        impacted=self.policy.dependency_closure(direct)
        unmapped=stable_unique(p for p in paths if self.policy.is_production_path(p) and not any(any_glob(p,r.patterns) for r in self.policy.subsystem_rules))
        graph=sha256_json({"rules":[{"subsystem":r.subsystem,"patterns":r.patterns,"depends_on":r.depends_on} for r in self.policy.subsystem_rules],"direct":direct,"impacted":impacted})
        return ImpactAssessment(paths,risk,tuple(stable_unique(reasons)),tuple(direct),tuple(impacted),tuple(unmapped),graph)

class ProofSelector:
    def __init__(self,policy): self.policy=policy
    def compile_manifest(self,*,base_sha,head_sha,impact:ImpactAssessment):
        reasons={k:set() for k in self.policy.tests}
        for t in self.policy.tests.values():
            if t.always: reasons[t.test_id].add("P0_ALWAYS")
            if t.min_risk is not None and impact.risk>=t.min_risk: reasons[t.test_id].add(f"RISK_FLOOR:{t.min_risk.name}")
            if set(t.subsystems)&set(impact.impacted_subsystems): reasons[t.test_id].add("IMPACTED_SUBSYSTEM")
            if any(any_glob(p,t.patterns) for p in impact.changed_paths): reasons[t.test_id].add("DIRECT_PATH_MATCH")
        for a in self.policy.historical_associations:
            if any(any_glob(p,a.patterns) for p in impact.changed_paths):
                for tid in a.tests: reasons[tid].add(f"HISTORICAL_ASSOCIATION:{a.evidence}")
        fallback=bool(impact.unmapped_production_paths)
        if fallback: reasons[self.policy.fallback_test_id].add("FAIL_SAFE_UNMAPPED_PRODUCTION")
        candidates=sorted(t.test_id for t in self.policy.tests.values() if t.sentinel_eligible and not reasons[t.test_id])
        sentinel_count=(len(candidates)*self.policy.sentinel_percent+99)//100 if self.policy.sentinel_percent else 0
        seed=int(hashlib.sha256((base_sha+head_sha+self.policy.sha256).encode()).hexdigest(),16)
        sentinels=sorted(candidates,key=lambda x:hashlib.sha256(f"{seed}:{x}".encode()).hexdigest())[:sentinel_count]
        selected=[]; omitted=[]
        for tid in sorted(self.policy.tests):
            rs=set(reasons[tid]); mode="BLOCKING"
            if tid in sentinels: rs.add("SHADOW_SENTINEL"); mode="SHADOW_SENTINEL"
            if rs: selected.append(SelectedTest(tid,tuple(sorted(rs)),mode))
            else: omitted.append(OmittedTest(tid,("NO_GRAPH_PATH","NO_RISK_FLOOR","NO_HISTORICAL_ASSOCIATION","NOT_SELECTED_AS_SENTINEL")))
        state={"algorithm":"GRAPH_FLOOR_PLUS_EMPIRICAL_ASSOCIATION_V1","fallback_full_suite_activated":fallback,"sentinel_percent":self.policy.sentinel_percent,"deterministic_selector_floor_may_not_be_removed_by_prediction":True,"predictive_selector_may_only_add_tests":True,"omission_proof_complete":len(selected)+len(omitted)==len(self.policy.tests)}
        payload={"schema":"FEDERATION-PROOFOS-MANIFEST-V1","version":"1.0.0","base_sha":base_sha,"head_sha":head_sha,"policy_sha256":self.policy.sha256,"impact":impact.to_dict(),"selected_tests":[x.to_dict() for x in selected],"omitted_tests":[x.to_dict() for x in omitted],"selector_state":state}
        return ProofManifest(payload["schema"],payload["version"],base_sha,head_sha,self.policy.sha256,impact,tuple(selected),tuple(omitted),state,sha256_json(payload))

def _hash_paths(root:Path, paths:Iterable[Path]): return {p.relative_to(root).as_posix():sha256_bytes(p.read_bytes()) for p in paths}
def proof_key_for_test(*,repo_root,manifest,policy,spec,runtime_identity):
    root=Path(repo_root); source=[root/p for p in manifest.impact.changed_paths if (root/p).is_file()]; tests=[]
    if spec.kind=="unittest_glob": tests=list((root/"tests").glob(spec.target))
    elif spec.kind=="unittest_module":
        p=root/(spec.target.replace(".","/")+".py"); tests=[p] if p.is_file() else []
    return sha256_json({"manifest":manifest.manifest_sha256,"policy":policy.sha256,"test":spec.test_id,"kind":spec.kind,"target":spec.target,"source":_hash_paths(root,source),"test_source":_hash_paths(root,tests),"runtime":dict(runtime_identity)})

class ProofCache:
    def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def _path(self,key): return self.root/f"{key}.json"
    def load(self,key):
        p=self._path(key)
        if not p.is_file(): return None
        d=json.loads(p.read_text()); return d if d.get("status")=="PASS" and d.get("proof_key")==key else None
    def store(self,result):
        if result.status!="PASS": return
        p=self._path(result.proof_key); tmp=p.with_suffix(".tmp"); tmp.write_text(canonical_json(result.to_dict())+"\n"); os.replace(tmp,p)

class ProofRunner:
    def __init__(self,*,policy,repo_root,cache=None): self.policy=policy; self.repo_root=Path(repo_root); self.cache=cache
    def runtime_identity(self): return {"python":sys.version.split()[0],"platform":sys.platform,"policy":self.policy.version}
    def _present(self,t):
        if t.kind=="unittest_glob": return any((self.repo_root/"tests").glob(t.target))
        if t.kind=="unittest_module": return (self.repo_root/(t.target.replace(".","/")+".py")).is_file()
        return (self.repo_root/t.target).exists()
    def _argv(self,t):
        if t.kind=="unittest_glob": return [sys.executable,"-m","unittest","discover","-s","tests","-p",t.target,"-v"]
        if t.kind=="unittest_module": return [sys.executable,"-m","unittest",t.target,"-v"]
        if t.kind=="compileall": return [sys.executable,"-m","compileall","-q",t.target]
        raise RunnerError("unsupported test kind")
    def run(self,manifest):
        if not manifest.verify() or manifest.policy_sha256!=self.policy.sha256: raise RunnerError("manifest integrity failure")
        results=[]; blocking=[]; scoped=[]; runtime=self.runtime_identity()
        for sel in manifest.selected_tests:
            t=self.policy.tests[sel.test_id]; key=proof_key_for_test(repo_root=self.repo_root,manifest=manifest,policy=self.policy,spec=t,runtime_identity=runtime)
            cached=None if t.hard_always_run or self.cache is None else self.cache.load(key)
            if cached:
                r=TestExecutionResult(t.test_id,"PASS",0,0.0,key,cached["stdout_sha256"],cached["stderr_sha256"],t.failure_class,t.block_scope,True); results.append(r); continue
            if not self._present(t):
                status="SKIPPED_NOT_PRESENT" if t.optional_if_missing else "FAIL_NOT_PRESENT"; rc=0 if t.optional_if_missing else 2
                r=TestExecutionResult(t.test_id,status,rc,0.0,key,sha256_bytes(b""),sha256_bytes(b"required proof target not present" if rc else b""),t.failure_class,t.block_scope)
            else:
                start=time.monotonic()
                try:
                    p=subprocess.run(self._argv(t),cwd=self.repo_root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=t.timeout_seconds,check=False,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
                    r=TestExecutionResult(t.test_id,"PASS" if p.returncode==0 else "FAIL",p.returncode,time.monotonic()-start,key,sha256_bytes(p.stdout),sha256_bytes(p.stderr),t.failure_class,t.block_scope)
                except subprocess.TimeoutExpired as e:
                    r=TestExecutionResult(t.test_id,"FAIL_TIMEOUT",124,time.monotonic()-start,key,sha256_bytes(e.stdout or b""),sha256_bytes(e.stderr or b""),t.failure_class,t.block_scope)
            results.append(r)
            if r.status=="PASS" and self.cache: self.cache.store(r)
            elif not (r.status.startswith("PASS") or r.status.startswith("SKIPPED")):
                f=f"{t.test_id}:{'SELECTOR_ESCAPE' if sel.mode=='SHADOW_SENTINEL' else t.failure_class}"
                if sel.mode=="SHADOW_SENTINEL" or t.block_scope in {"GLOBAL","SUBSYSTEM"}: blocking.append(f)
                if t.block_scope!="GLOBAL": scoped.append(f)
        status="PASS" if not blocking else "FAIL"; payload={"manifest_sha256":manifest.manifest_sha256,"results":[x.to_dict() for x in results],"blocking_failures":sorted(blocking),"scoped_failures":sorted(scoped),"status":status}
        return AdmissionReport(manifest.manifest_sha256,tuple(results),tuple(sorted(blocking)),tuple(sorted(scoped)),status,sha256_json(payload))

def load_manifest(path):
    r=json.loads(Path(path).read_text()); i=r["impact"]; impact=ImpactAssessment(tuple(i["changed_paths"]),RiskTier.parse(i["risk"]),tuple(i["risk_reasons"]),tuple(i["direct_subsystems"]),tuple(i["impacted_subsystems"]),tuple(i["unmapped_production_paths"]),i["graph_sha256"])
    m=ProofManifest(r["schema"],r["version"],r["base_sha"],r["head_sha"],r["policy_sha256"],impact,tuple(SelectedTest(x["test_id"],tuple(x["reasons"]),x.get("mode","BLOCKING")) for x in r["selected_tests"]),tuple(OmittedTest(x["test_id"],tuple(x["reasons"])) for x in r["omitted_tests"]),dict(r["selector_state"]),r["manifest_sha256"])
    if not m.verify(): raise RunnerError("manifest digest mismatch")
    return m

def changed_paths_from_git(repo_root,base_sha,head_sha):
    for v,n in ((base_sha,"base"),(head_sha,"head")):
        if not re.fullmatch(r"[0-9a-f]{40,64}",v): raise ImpactError(f"invalid {n} sha")
    p=subprocess.run(["git","diff","--name-only","--diff-filter=ACMRTUXB",base_sha,head_sha],cwd=Path(repo_root),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if p.returncode: raise ImpactError("git diff failed")
    paths=[x.strip() for x in p.stdout.splitlines() if x.strip()]
    if not paths: raise ImpactError("git diff returned no changed paths")
    return paths
