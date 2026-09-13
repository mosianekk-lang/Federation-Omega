from __future__ import annotations

import ast, hashlib, json, math, re
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

TOK = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,127}")
GENSYM = re.compile(r"(?:class|def|function|interface|type|struct|enum|trait|fn|func)\s+([A-Za-z_][A-Za-z0-9_]*)")
PERMISSIVE = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"})


def _canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v)).hexdigest()


def _path(raw: str) -> str:
    p = PurePosixPath(raw)
    if p.is_absolute() or not p.parts or ".." in p.parts:
        raise ValueError(f"unsafe repository path: {raw}")
    return p.as_posix()


def _tokens(s: str) -> tuple[str, ...]:
    return tuple(x.lower() for x in TOK.findall(s))


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: str; sha256: str; language: str; symbols: tuple[str, ...]; imports: tuple[str, ...]; tokens: tuple[str, ...]
    text: str = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class RepositoryIndex:
    files: tuple[FileRecord, ...]; merkle_root: str
    def by_path(self) -> dict[str, FileRecord]: return {x.path: x for x in self.files}


@dataclass(frozen=True, slots=True)
class SearchHit:
    path: str; score: float; sha256: str; matched_symbols: tuple[str, ...]; excerpt: str


class RepositoryIntelligence:
    """Portable deterministic repo index; richer AST/LSP/embedding adapters may augment it."""
    LANG = {".py":"python",".ts":"typescript",".tsx":"typescript",".js":"javascript",".jsx":"javascript",".go":"go",".rs":"rust",".java":"java",".kt":"kotlin",".cs":"csharp",".rb":"ruby",".php":"php",".cpp":"cpp",".cc":"cpp",".c":"c",".h":"c-header",".md":"markdown",".json":"json",".yaml":"yaml",".yml":"yaml"}

    @classmethod
    def _record(cls, raw: str, text: str) -> FileRecord:
        path = _path(raw); lang = cls.LANG.get(PurePosixPath(path).suffix.lower(), "text")
        symbols: set[str] = set(); imports: set[str] = set()
        if lang == "python":
            try: tree = ast.parse(text)
            except SyntaxError: tree = None
            if tree:
                for n in ast.walk(tree):
                    if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)): symbols.add(n.name)
                    elif isinstance(n, ast.Import): imports.update(a.name for a in n.names)
                    elif isinstance(n, ast.ImportFrom) and n.module: imports.add(n.module)
        if not symbols: symbols.update(GENSYM.findall(text))
        return FileRecord(path, hashlib.sha256(text.encode()).hexdigest(), lang, tuple(sorted(symbols)), tuple(sorted(imports)), _tokens(text), text)

    @classmethod
    def _finish(cls, records: Iterable[FileRecord]) -> RepositoryIndex:
        files = tuple(sorted(records, key=lambda x: x.path))
        return RepositoryIndex(files, _hash([(x.path, x.sha256) for x in files]))

    def index(self, files: Mapping[str, str]) -> RepositoryIndex:
        return self._finish(self._record(p, t) for p, t in files.items())

    def update(self, previous: RepositoryIndex, *, changed_files: Mapping[str, str] | None = None, removed_paths: Iterable[str] = ()) -> RepositoryIndex:
        current = previous.by_path()
        for p in removed_paths: current.pop(_path(p), None)
        for p, text in (changed_files or {}).items():
            rec = self._record(p, text); current[rec.path] = rec
        return self._finish(current.values())

    @staticmethod
    def delta(before: RepositoryIndex, after: RepositoryIndex) -> dict[str, tuple[str, ...]]:
        a, b = before.by_path(), after.by_path(); common = set(a) & set(b)
        changed = {p for p in common if a[p].sha256 != b[p].sha256}
        return {"added":tuple(sorted(set(b)-set(a))),"changed":tuple(sorted(changed)),"removed":tuple(sorted(set(a)-set(b))),"unchanged":tuple(sorted(common-changed))}

    def search(self, index: RepositoryIndex, query: str, *, limit: int = 12) -> tuple[SearchHit, ...]:
        q = set(_tokens(query)); raw = query.strip().lower()
        if not q or limit <= 0: return ()
        df: Counter[str] = Counter(); n = max(len(index.files), 1)
        for f in index.files: df.update(set(f.tokens))
        out: list[SearchHit] = []
        for f in index.files:
            c = Counter(f.tokens); lexical = sum((1 + math.log(c[t])) * (math.log((n+1)/(df[t]+0.5))+1) for t in q if c[t])
            ms = tuple(sorted(s for s in f.symbols if raw in s.lower() or any(t in s.lower() for t in q)))
            score = lexical + 4*len(ms) + 2*len(q & set(_tokens(f.path))) + 1.5*sum(any(t in i.lower() for t in q) for i in f.imports)
            if score:
                lower=f.text.lower(); pos=min([lower.find(t) for t in q if lower.find(t)>=0] or [0]); start=max(pos-160,0)
                out.append(SearchHit(f.path, round(score,8), f.sha256, ms, f.text[start:start+640]))
        return tuple(sorted(out, key=lambda x:(-x.score,x.path))[:limit])

    def context_pack(self, index: RepositoryIndex, query: str, *, max_chars: int = 12000) -> str:
        if max_chars < 256: raise ValueError("max_chars must be >= 256")
        text="\n".join(f"# {h.path} sha256={h.sha256}\n{h.excerpt}" for h in self.search(index,query))
        return text[:max_chars]


class EngineeringRisk(StrEnum): LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CRITICAL="CRITICAL"
class TaskKind(StrEnum): CONTEXT="CONTEXT"; DESIGN="DESIGN"; IMPLEMENT="IMPLEMENT"; TEST="TEST"; SECURITY="SECURITY"; REVIEW="REVIEW"; TERMINAL="TERMINAL"


@dataclass(frozen=True, slots=True)
class EngineeringTask:
    task_id: str; kind: TaskKind; purpose: str; depends_on: tuple[str,...]; target_paths: tuple[str,...]; effect_class: str; required_evidence: tuple[str,...]; specialist: str


@dataclass(frozen=True, slots=True)
class EngineeringSpec:
    mission_id: str; objective: str; success_condition: str; risk: EngineeringRisk; repository_merkle_root: str; constraints: tuple[str,...]; target_paths: tuple[str,...]; required_checks: tuple[str,...]; tasks: tuple[EngineeringTask,...]; compiled_digest: str


class EngineeringSpecCompiler:
    CHECKS={EngineeringRisk.LOW:("SYNTAX","UNIT"),EngineeringRisk.MEDIUM:("SYNTAX","UNIT","LINT","TYPE"),EngineeringRisk.HIGH:("SYNTAX","UNIT","LINT","TYPE","INTEGRATION","SECURITY"),EngineeringRisk.CRITICAL:("SYNTAX","UNIT","LINT","TYPE","INTEGRATION","SECURITY","PROPERTY_OR_FUZZ","ROLLBACK","REPRODUCIBLE_BUILD")}
    def __init__(self, repo: RepositoryIntelligence|None=None): self.repo=repo or RepositoryIntelligence()

    def compile(self, *, mission_id: str, objective: str, success_condition: str, repository: RepositoryIndex, query: str|None=None, risk: EngineeringRisk=EngineeringRisk.MEDIUM, constraints: Iterable[str]=(), required_checks: Iterable[str]=()) -> EngineeringSpec:
        if not mission_id.strip() or not objective.strip() or not success_condition.strip(): raise ValueError("mission fields required")
        risk=EngineeringRisk(risk); checks=tuple(sorted(set(required_checks) or set(self.CHECKS[risk]))); targets=tuple(h.path for h in self.repo.search(repository,query or objective,limit=8))
        tasks=[
          EngineeringTask("repo_context",TaskKind.CONTEXT,"retrieve bounded repository context",(),targets,"NO_EFFECT",("REPO_MERKLE_ROOT","CONTEXT_HIT_RECEIPTS"),"EXPLORER"),
          EngineeringTask("architecture",TaskKind.DESIGN,"form minimal architecture/change design",("repo_context",),targets,"NO_EFFECT",("DESIGN_RATIONALE","ALTERNATIVE_REJECTS"),"ARCHITECT"),
          EngineeringTask("implement",TaskKind.IMPLEMENT,"apply reversible source delta in isolated workspace",("architecture",),targets,"REVERSIBLE_INTERNAL",("PATCH_DIGEST","WORKSPACE_ID","BASE_REVISION"),"IMPLEMENTER"),
          EngineeringTask("test",TaskKind.TEST,"execute required engineering checks",("implement",),targets,"NO_EXTERNAL_EFFECT",checks,"TESTER")]
        prev="test"
        if risk in {EngineeringRisk.HIGH,EngineeringRisk.CRITICAL} or "SECURITY" in checks:
            tasks.append(EngineeringTask("security",TaskKind.SECURITY,"adversarial security and authority review",(prev,),targets,"NO_EFFECT",("SECURITY_REPORT","SECRET_SCAN","AUTHORITY_DIFF"),"SECURITY")); prev="security"
        tasks += [EngineeringTask("independent_review",TaskKind.REVIEW,"independent diff/regression review",(prev,),targets,"NO_EFFECT",("DIFF_REVIEW","REGRESSION_REVIEW"),"VERIFIER"),EngineeringTask("terminal_verify",TaskKind.TERMINAL,"compile semantic terminal truth",("independent_review",),targets,"NO_EFFECT",("SEMANTIC_ACCEPTANCE","PROOF_REFERENCES"),"TERMINAL_VERIFIER")]
        constraints=tuple(sorted(set(constraints))); body={"mission_id":mission_id,"objective":objective,"success_condition":success_condition,"risk":risk.value,"repo":repository.merkle_root,"constraints":constraints,"targets":targets,"checks":checks,"tasks":[asdict(t) for t in tasks]}
        return EngineeringSpec(mission_id,objective,success_condition,risk,repository.merkle_root,constraints,targets,checks,tuple(tasks),_hash(body))

    @staticmethod
    def to_mission_ir(spec: EngineeringSpec):
        from .mission_ir import LaneClass, MissionCompiler, MissionNode
        lanes={TaskKind.CONTEXT:LaneClass.EVIDENCE,TaskKind.DESIGN:LaneClass.COMPUTE,TaskKind.IMPLEMENT:LaneClass.COMPUTE,TaskKind.TEST:LaneClass.EVIDENCE,TaskKind.SECURITY:LaneClass.GOVERNANCE,TaskKind.REVIEW:LaneClass.GOVERNANCE,TaskKind.TERMINAL:LaneClass.CRITICAL}
        nodes=tuple(MissionNode(t.task_id,t.purpose,"CODEFORGE",lanes[t.kind],depends_on=t.depends_on,proof_obligations=t.required_evidence,context_keys=t.target_paths) for t in spec.tasks)
        return MissionCompiler().compile(mission_id=spec.mission_id,objective=spec.objective,success_condition=spec.success_condition,nodes=nodes,authoritative_sources=(f"repo-merkle:{spec.repository_merkle_root}",),constraints=spec.constraints,terminal_proofs=("SEMANTIC_ACCEPTANCE","PROOF_REFERENCES"))


@dataclass(frozen=True, slots=True)
class VerificationObservation: check_id: str; passed: bool; evidence_ref: str; hard: bool=True
@dataclass(frozen=True, slots=True)
class VerificationVerdict: status: str; missing_checks: tuple[str,...]; failed_checks: tuple[str,...]; evidence_refs: tuple[str,...]; verdict_sha256: str


class VerificationCourt:
    def evaluate(self, *, required_checks: Iterable[str], observations: Iterable[VerificationObservation]) -> VerificationVerdict:
        req=tuple(sorted(set(required_checks))); by={o.check_id:o for o in observations}; missing=tuple(sorted(c for c in req if c not in by or not by[c].evidence_ref.strip())); failed=tuple(sorted(o.check_id for o in by.values() if o.hard and not o.passed))
        status="FAILED" if failed else "INCOMPLETE" if missing or not all(by[c].passed for c in req) else "PROVEN_LOCAL"; refs=tuple(sorted({o.evidence_ref for o in by.values() if o.evidence_ref.strip()})); body=(status,missing,failed,refs)
        return VerificationVerdict(status,missing,failed,refs,_hash(body))


@dataclass(frozen=True, slots=True)
class CapabilityGap: gap_id: str; semantic_operation: str; required_features: tuple[str,...]
@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    candidate_id: str; source_type: str; capabilities: tuple[str,...]; maturity: str; provenance_ref: str; license_id: str=""; source_available: bool=False; tests_present: bool=False; security_reviewed: bool=False
@dataclass(frozen=True, slots=True)
class AcquisitionPlan:
    action: str; candidate_id: str|None; direct_code_allowed: bool; residual_features: tuple[str,...]; proof_gates: tuple[str,...]; plan_sha256: str


class CapabilityAcquirer:
    """Reuse internal capability first; third-party code remains provenance/licence/security gated."""
    def plan(self,gap:CapabilityGap,*,internal_candidates:Sequence[CapabilityCandidate]=(),external_candidates:Sequence[CapabilityCandidate]=())->AcquisitionPlan:
        req=set(gap.required_features)
        def rank(xs): return sorted(xs,key=lambda c:(-len(req&set(c.capabilities)),c.candidate_id))
        for c in rank(internal_candidates):
            hit=req&set(c.capabilities)
            if hit:
                residual=tuple(sorted(req-hit)); return self._out("REUSE_INTERNAL" if not residual else "COMPOSE_INTERNAL",c,False,residual,("CURRENT_SOURCE_READBACK","REGRESSION","SEMANTIC_ACCEPTANCE"))
        for c in rank(external_candidates):
            hit=req&set(c.capabilities)
            if not hit: continue
            residual=tuple(sorted(req-hit)); code=c.source_type=="OPEN_SOURCE" and c.license_id in PERMISSIVE and c.source_available and c.tests_present and c.security_reviewed and bool(c.provenance_ref.strip())
            if code: return self._out("CODE_GRAFT_CANDIDATE",c,True,residual,("LICENSE","PROVENANCE","SUPPLY_CHAIN","SANDBOX","TESTS","SECRET_SCAN","ROLLBACK","INDEPENDENT_READBACK"))
            return self._out("HARVEST_MECHANISM",c,False,residual,("PRIMARY_TECHNICAL_EVIDENCE","CLEAN_ROOM_ABSTRACTION","LOCAL_IMPLEMENTATION_TESTS","CFBE_CHALLENGER","ROLLBACK"))
        return self._out("BUILD_SMALLEST_GAP",None,False,tuple(sorted(req)),("SPEC","FALSIFICATION_TEST","UNIT","INTEGRATION","SECURITY","ROLLBACK","CFBE_CHALLENGER"))
    @staticmethod
    def _out(action,c,direct,residual,gates):
        cid=c.candidate_id if c else None; body=(action,cid,direct,residual,gates); return AcquisitionPlan(action,cid,direct,residual,gates,_hash(body))


@dataclass(frozen=True, slots=True)
class EngineeringMetrics:
    task_set_id: str; acceptance_hash: str; accepted_task_rate: float; median_wall_seconds: float; owner_interventions: float; tool_round_trips: float; regression_escape_rate: float; verified_readback_rate: float; sample_size: int=1; median_cost: float=0.0
    def validate(self):
        if not self.task_set_id or not self.acceptance_hash or self.median_wall_seconds<=0 or self.sample_size<1: raise ValueError("invalid experiment identity/size/time")
        if any(not 0<=x<=1 for x in (self.accepted_task_rate,self.regression_escape_rate,self.verified_readback_rate)): raise ValueError("rate outside [0,1]")
        if min(self.owner_interventions,self.tool_round_trips,self.median_cost)<0: raise ValueError("negative burden/cost")


@dataclass(frozen=True, slots=True)
class TenXVerdict: multiplier: float; target_met: bool; hard_regression: bool; reason: str


class TenXEngineeringCourt:
    """10x requires >=30 matched observations per side and no quality/readback regression."""
    @staticmethod
    def vet(m:EngineeringMetrics)->float:
        m.validate(); quality=m.accepted_task_rate*m.verified_readback_rate*(1-m.regression_escape_rate); return quality*(3600/m.median_wall_seconds)/(1+m.owner_interventions)/math.sqrt(1+m.tool_round_trips)/(1+m.median_cost)
    def compare(self,b:EngineeringMetrics,c:EngineeringMetrics)->TenXVerdict:
        b.validate(); c.validate()
        if (b.task_set_id,b.acceptance_hash)!=(c.task_set_id,c.acceptance_hash): raise ValueError("TENX_EXPERIMENT_IDENTITY_MISMATCH")
        mult=self.vet(c)/self.vet(b) if self.vet(b)>0 else math.inf; reg=c.accepted_task_rate<b.accepted_task_rate or c.verified_readback_rate<b.verified_readback_rate or c.regression_escape_rate>b.regression_escape_rate; sample=b.sample_size>=30 and c.sample_size>=30; ok=mult>=10 and not reg and sample
        reason="HARD_QUALITY_REGRESSION" if reg else "INSUFFICIENT_PAIRED_SAMPLE" if not sample else "TENX_VERIFIED" if ok else "TENX_NOT_YET_PROVEN"
        return TenXVerdict(round(mult,6),ok,reg,reason)


__all__=["AcquisitionPlan","CapabilityAcquirer","CapabilityCandidate","CapabilityGap","EngineeringMetrics","EngineeringRisk","EngineeringSpec","EngineeringSpecCompiler","EngineeringTask","FileRecord","RepositoryIndex","RepositoryIntelligence","SearchHit","TaskKind","TenXEngineeringCourt","TenXVerdict","VerificationCourt","VerificationObservation","VerificationVerdict"]
