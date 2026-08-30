"""Fully Automated Elevation — Sovereign Solutions Foundry compiler v1.

Effect-free compiler for source-backed ideas. It converts an idea into a machine-readable
Project Genome and dependency/proof plan. It does not deploy, mutate providers, grant
authority, infer production maturity, or execute external effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import Iterable, Mapping, Sequence


class ValidationError(ValueError):
    pass


class BuildStage(str, Enum):
    IDEA_CAPTURED = "IDEA_CAPTURED"
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    GAP_DEFINED = "GAP_DEFINED"
    PROJECT_GENOME_COMPILED = "PROJECT_GENOME_COMPILED"
    FORMATION_SELECTED = "FORMATION_SELECTED"
    PREBUILD_ASSURANCE_PASSED = "PREBUILD_ASSURANCE_PASSED"
    DESIGN_PROVENANCE_CAPTURED = "DESIGN_PROVENANCE_CAPTURED"
    SOURCE_IMPLEMENTED = "SOURCE_IMPLEMENTED"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    CI_ADMITTED = "CI_ADMITTED"
    DEPLOYED = "DEPLOYED"
    PROVIDER_EXECUTED = "PROVIDER_EXECUTED"
    SEMANTIC_READBACK_VERIFIED = "SEMANTIC_READBACK_VERIFIED"
    REPEATED_SUCCESS = "REPEATED_SUCCESS"
    SOAKED = "SOAKED"
    VALUE_VERIFIED = "VALUE_VERIFIED"
    FULLY_ESTABLISHED = "FULLY_ESTABLISHED_SYSTEM_OR_SERVICE"


STAGE_ORDER = tuple(BuildStage)


@dataclass(frozen=True)
class AuthorityEnvelope:
    permitted: tuple[str, ...] = ()
    prohibited: tuple[str, ...] = (
        "SEND", "SHARE_EXTERNALLY", "PUBLISH", "PAY", "LEGAL_FILE",
        "DELETE_MATERIAL_EVIDENCE", "PRODUCTION_DEPLOY",
    )
    financial_limit: float = 0.0
    owner_release_required: bool = True

    def __post_init__(self) -> None:
        if self.financial_limit < 0:
            raise ValidationError("FINANCIAL_LIMIT_MUST_BE_NONNEGATIVE")
        overlap = set(self.permitted).intersection(self.prohibited)
        if overlap:
            raise ValidationError("AUTHORITY_CONTRADICTION:" + ",".join(sorted(overlap)))


@dataclass(frozen=True)
class CandidateRoute:
    route_id: str
    route_class: str
    description: str
    reuse_targets: tuple[str, ...] = ()
    complexity: float = 0.0
    reversibility: float = 1.0
    proofability: float = 1.0
    estimated_cost: float = 0.0
    risk: float = 0.0

    def __post_init__(self) -> None:
        if not self.route_id.strip() or not self.description.strip():
            raise ValidationError("ROUTE_ID_AND_DESCRIPTION_REQUIRED")
        for name, value in (("complexity", self.complexity), ("reversibility", self.reversibility), ("proofability", self.proofability), ("risk", self.risk)):
            if not 0.0 <= float(value) <= 1.0:
                raise ValidationError(f"ROUTE_{name.upper()}_OUT_OF_RANGE")
        if self.estimated_cost < 0:
            raise ValidationError("ROUTE_COST_MUST_BE_NONNEGATIVE")

    @property
    def score(self) -> float:
        cost_penalty = min(float(self.estimated_cost) / 10000.0, 1.0)
        return round(0.30*self.reversibility + 0.30*self.proofability + 0.15*(1-self.complexity) + 0.15*(1-self.risk) + 0.10*(1-cost_penalty), 6)


@dataclass(frozen=True)
class IdeaCandidate:
    idea_id: str
    title: str
    mission: str
    user_value: str
    source_refs: tuple[str, ...]
    exact_gap: str
    current_baseline: str
    protected_capabilities: tuple[str, ...] = ()
    reuse_candidates: tuple[str, ...] = ()
    candidate_routes: tuple[CandidateRoute, ...] = ()
    falsification_tests: tuple[str, ...] = ()
    authority: AuthorityEnvelope = field(default_factory=AuthorityEnvelope)
    value_metrics: tuple[str, ...] = ("quality","reliability","completion_rate","recovery_speed","latency","owner_burden","proof_strength","cost","reuse","complexity")


@dataclass(frozen=True)
class ProofGate:
    stage: BuildStage
    required_evidence: tuple[str, ...]
    owner_gate: bool = False
    provider_native: bool = False
    minimum_successes: int = 0
    minimum_soak_seconds: int = 0


@dataclass(frozen=True)
class StageState:
    stage: BuildStage
    state: str
    evidence_refs: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectGenome:
    project_id: str
    idea_id: str
    title: str
    mission: str
    user_value: str
    current_baseline: str
    exact_gap: str
    source_evidence: tuple[str, ...]
    protected_capabilities: tuple[str, ...]
    reuse_candidates: tuple[str, ...]
    candidate_routes: tuple[CandidateRoute, ...]
    selected_route: CandidateRoute
    falsification_tests: tuple[str, ...]
    authority_envelope: AuthorityEnvelope
    dependency_graph: tuple[tuple[str, str], ...]
    proof_gates: tuple[ProofGate, ...]
    value_metrics: tuple[str, ...]
    promotion_gate: str
    learning_contract: str
    compiler_version: str
    genome_sha256: str

    def as_dict(self) -> dict[str, object]:
        def rd(r):
            return {"route_id":r.route_id,"route_class":r.route_class,"description":r.description,"reuse_targets":list(r.reuse_targets),"complexity":r.complexity,"reversibility":r.reversibility,"proofability":r.proofability,"estimated_cost":r.estimated_cost,"risk":r.risk,"score":r.score}
        return {
            "schema":"FAE-PROJECT-GENOME-1","project_id":self.project_id,"idea_id":self.idea_id,"title":self.title,"mission":self.mission,"user_value":self.user_value,
            "current_baseline":self.current_baseline,"exact_gap":self.exact_gap,"source_evidence":list(self.source_evidence),"protected_capabilities":list(self.protected_capabilities),
            "reuse_candidates":list(self.reuse_candidates),"candidate_routes":[rd(r) for r in self.candidate_routes],"selected_route":rd(self.selected_route),
            "falsification_tests":list(self.falsification_tests),"authority_envelope":{"permitted":list(self.authority_envelope.permitted),"prohibited":list(self.authority_envelope.prohibited),"financial_limit":self.authority_envelope.financial_limit,"owner_release_required":self.authority_envelope.owner_release_required},
            "dependency_graph":[list(x) for x in self.dependency_graph],"proof_gates":[{"stage":g.stage.value,"required_evidence":list(g.required_evidence),"owner_gate":g.owner_gate,"provider_native":g.provider_native,"minimum_successes":g.minimum_successes,"minimum_soak_seconds":g.minimum_soak_seconds} for g in self.proof_gates],
            "value_metrics":list(self.value_metrics),"promotion_gate":self.promotion_gate,"learning_contract":self.learning_contract,"compiler_version":self.compiler_version,"genome_sha256":self.genome_sha256,
        }


class SovereignFoundryCompiler:
    VERSION = "FAE-SOVEREIGN-FOUNDRY-COMPILER-1.0.0"
    ROUTE_CLASS_ORDER = {"REUSE":0,"EXTEND":1,"SPECIALISE":2,"COMPOSE":3,"ADAPT":4,"REROUTE":5,"ENGINEER":6,"NEW_BUILD":7}

    @classmethod
    def _norm_refs(cls, refs: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted({str(r).strip() for r in refs if str(r).strip()}))

    @classmethod
    def _slug(cls, value: str) -> str:
        return (re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").upper()[:64] or "UNNAMED")

    @classmethod
    def _validate_candidate(cls, c: IdeaCandidate) -> None:
        req={"idea_id":c.idea_id,"title":c.title,"mission":c.mission,"user_value":c.user_value,"exact_gap":c.exact_gap,"current_baseline":c.current_baseline}
        missing=sorted(k for k,v in req.items() if not str(v).strip())
        if missing: raise ValidationError("MISSING_REQUIRED_FIELDS:"+",".join(missing))
        if not cls._norm_refs(c.source_refs): raise ValidationError("SOURCE_EVIDENCE_REQUIRED")
        if not c.candidate_routes: raise ValidationError("COMPETING_ROUTE_REQUIRED")
        ids=[r.route_id for r in c.candidate_routes]
        if len(ids)!=len(set(ids)): raise ValidationError("DUPLICATE_ROUTE_ID")
        if not c.falsification_tests: raise ValidationError("FALSIFICATION_TEST_REQUIRED")

    @classmethod
    def select_route(cls, routes: Sequence[CandidateRoute]) -> CandidateRoute:
        if not routes: raise ValidationError("COMPETING_ROUTE_REQUIRED")
        return sorted(routes,key=lambda r:(-r.score,cls.ROUTE_CLASS_ORDER.get(r.route_class.upper(),99),r.route_id))[0]

    @classmethod
    def default_proof_gates(cls):
        return (
            ProofGate(BuildStage.IDEA_CAPTURED,("idea_id","title","mission","user_value")),
            ProofGate(BuildStage.SOURCE_VERIFIED,("source_refs",)),
            ProofGate(BuildStage.GAP_DEFINED,("current_baseline","exact_gap")),
            ProofGate(BuildStage.PROJECT_GENOME_COMPILED,("genome_sha256","authority_envelope")),
            ProofGate(BuildStage.FORMATION_SELECTED,("candidate_routes>=1","selected_route","falsification_tests")),
            ProofGate(BuildStage.PREBUILD_ASSURANCE_PASSED,("RealityGuard/RCSG prebuild receipt","reuse-first estate check")),
            ProofGate(BuildStage.DESIGN_PROVENANCE_CAPTURED,("DPF material decision receipt",)),
            ProofGate(BuildStage.SOURCE_IMPLEMENTED,("source identity","implementation receipt")),
            ProofGate(BuildStage.DETERMINISTIC_TESTED,("test receipt","failure-first tests")),
            ProofGate(BuildStage.CI_ADMITTED,("exact-head CI/admission receipt",)),
            ProofGate(BuildStage.DEPLOYED,("provider deployment revision",),owner_gate=True,provider_native=True),
            ProofGate(BuildStage.PROVIDER_EXECUTED,("provider execution receipt",),provider_native=True),
            ProofGate(BuildStage.SEMANTIC_READBACK_VERIFIED,("independent semantic readback",),provider_native=True),
            ProofGate(BuildStage.REPEATED_SUCCESS,("distinct successful provider receipts",),provider_native=True,minimum_successes=3),
            ProofGate(BuildStage.SOAKED,("soak telemetry",),provider_native=True,minimum_successes=3,minimum_soak_seconds=300),
            ProofGate(BuildStage.VALUE_VERIFIED,("measured before/after value metrics","CFBE value verdict")),
            ProofGate(BuildStage.FULLY_ESTABLISHED,("operations runbook","support/rollback","SLO","VALUE_VERIFIED"),owner_gate=True),
        )

    @classmethod
    def dependency_graph(cls):
        return tuple((STAGE_ORDER[i].value,STAGE_ORDER[i+1].value) for i in range(len(STAGE_ORDER)-1))

    @classmethod
    def compile(cls,c:IdeaCandidate)->ProjectGenome:
        cls._validate_candidate(c); selected=cls.select_route(c.candidate_routes); refs=cls._norm_refs(c.source_refs); pid=f"FAE-PROJ-{cls._slug(c.idea_id)}"
        payload={"schema":"FAE-PROJECT-GENOME-1","project_id":pid,"idea_id":c.idea_id.strip(),"title":c.title.strip(),"mission":c.mission.strip(),"user_value":c.user_value.strip(),"current_baseline":c.current_baseline.strip(),"exact_gap":c.exact_gap.strip(),"source_evidence":refs,"protected_capabilities":tuple(sorted(set(c.protected_capabilities))),"reuse_candidates":tuple(sorted(set(c.reuse_candidates))),"candidate_routes":tuple((r.route_id,r.route_class,r.description,r.reuse_targets,r.complexity,r.reversibility,r.proofability,r.estimated_cost,r.risk,r.score) for r in c.candidate_routes),"selected_route":selected.route_id,"falsification_tests":tuple(c.falsification_tests),"authority":{"permitted":c.authority.permitted,"prohibited":c.authority.prohibited,"financial_limit":c.authority.financial_limit,"owner_release_required":c.authority.owner_release_required},"value_metrics":tuple(c.value_metrics),"compiler_version":cls.VERSION}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
        return ProjectGenome(pid,c.idea_id.strip(),c.title.strip(),c.mission.strip(),c.user_value.strip(),c.current_baseline.strip(),c.exact_gap.strip(),refs,tuple(sorted(set(c.protected_capabilities))),tuple(sorted(set(c.reuse_candidates))),tuple(c.candidate_routes),selected,tuple(c.falsification_tests),c.authority,cls.dependency_graph(),cls.default_proof_gates(),tuple(c.value_metrics),"NO_STAGE_PROMOTION_WITHOUT_MATCHING_TARGET_SPECIFIC_EVIDENCE","VERIFIED_OUTCOMES_MAY_FORM_RECEIVER_SPECIFIC_LEARNING; PROOF_AUTHORITY_AND_MATURITY_NEVER_INHERIT",cls.VERSION,digest)

    @classmethod
    def evaluate_progress(cls,genome:ProjectGenome,evidence_by_stage:Mapping[str,Sequence[str]],*,distinct_successes:int=0,soak_seconds:int=0,owner_release:bool=False):
        states=[]; prior=True
        for gate in genome.proof_gates:
            refs=cls._norm_refs(evidence_by_stage.get(gate.stage.value,())); blockers=[]
            if not prior: blockers.append("DEPENDENCY_NOT_PROVEN")
            if not refs: blockers.append("STAGE_EVIDENCE_REQUIRED")
            if gate.minimum_successes and distinct_successes<gate.minimum_successes: blockers.append(f"MINIMUM_SUCCESSES_REQUIRED:{gate.minimum_successes}")
            if gate.minimum_soak_seconds and soak_seconds<gate.minimum_soak_seconds: blockers.append(f"MINIMUM_SOAK_SECONDS_REQUIRED:{gate.minimum_soak_seconds}")
            if gate.owner_gate and not owner_release: blockers.append("OWNER_RELEASE_REQUIRED")
            state="PROVEN" if not blockers else "HELD"; states.append(StageState(gate.stage,state,refs,tuple(blockers))); prior=state=="PROVEN"
        return tuple(states)

    @classmethod
    def current_frontier(cls,states:Sequence[StageState]):
        passed=[s.stage for s in states if s.state=="PROVEN"]; return passed[-1] if passed else None
