from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, IntEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.cognitive_evolution_v1 import EvolutionSubstrate, OuterEnvelope, CognitiveGene, compile_genome

SCHEMA='CFBE_AO_PRODUCTION_GENESIS_PHASE1_V1'
PROVIDER_EFFECT_AUTHORIZED=False
PRODUCTION_DEPLOYMENT_AUTHORIZED=False
MODEL_TRAINING_AUTHORIZED=False

def _h(v): return sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,default=str).encode()).hexdigest()
def _norm(xs): return tuple(sorted({str(x).strip() for x in xs if str(x).strip()}))

@dataclass(frozen=True, slots=True)
class ProductContract:
    product_id:str; objective:str; user_classes:tuple[str,...]; user_journeys:tuple[str,...]; required_outcomes:tuple[str,...]; authority_ceiling:str; data_boundary:str; owner_intent_hash:str; quality_floor:float=.95; security_floor:float=.95; reliability_floor:float=.95
    def validate(self):
        if not all((self.product_id.strip(), self.objective.strip(), self.authority_ceiling.strip(), self.data_boundary.strip())): raise ValueError('PGC_CONTRACT_REQUIRED_FIELDS')
        if not self.user_classes or not self.user_journeys or not self.required_outcomes: raise ValueError('PGC_PRODUCT_OUTCOME_JOURNEY_REQUIRED')
        if len(self.owner_intent_hash)!=64: raise ValueError('PGC_OWNER_INTENT_HASH_REQUIRED')
        if any(not 0<=x<=1 for x in (self.quality_floor,self.security_floor,self.reliability_floor)): raise ValueError('PGC_FLOOR_RANGE_INVALID')
        return self
    @property
    def fingerprint(self):
        self.validate(); return _h((self.product_id,self.objective,_norm(self.user_classes),_norm(self.user_journeys),_norm(self.required_outcomes),self.authority_ceiling,self.data_boundary,self.owner_intent_hash,self.quality_floor,self.security_floor,self.reliability_floor))

class ComplementarySystem(str, Enum):
    INTENT_PRODUCT='INTENT_PRODUCT'; REQUIREMENTS_TELOS='REQUIREMENTS_TELOS'; CAPABILITY_REUSE='CAPABILITY_REUSE'; ARCHITECTURE_ADR='ARCHITECTURE_ADR'; DATA_API_CONTRACT='DATA_API_CONTRACT'; UX_DESIGN='UX_DESIGN'; BUILDER_SWARM='BUILDER_SWARM'; TEST_EVAL='TEST_EVAL'; DIGITAL_TWIN='DIGITAL_TWIN'; SECURITY_PRIVACY='SECURITY_PRIVACY'; SUPPLY_CHAIN='SUPPLY_CHAIN'; PLATFORM_IAC='PLATFORM_IAC'; RUNTIME_DURABILITY='RUNTIME_DURABILITY'; DEPLOY_CANARY_ROLLBACK='DEPLOY_CANARY_ROLLBACK'; OBSERVABILITY='OBSERVABILITY'; SRE_RELIABILITY_DR='SRE_RELIABILITY_DR'; FINOPS_PERFORMANCE='FINOPS_PERFORMANCE'; DOCS_RUNBOOK='DOCS_RUNBOOK'; USER_VALUE='USER_VALUE'; AOCEF_EVOLUTION='AOCEF_EVOLUTION'

@dataclass(frozen=True, slots=True)
class ComplementaryResolution:
    systems:tuple[ComplementarySystem,...]; reused:tuple[str,...]; residual:tuple[str,...]

def resolve_complementary_systems(*, reused:Iterable[str]=(), residual:Iterable[str]=()):
    return ComplementaryResolution(tuple(ComplementarySystem),_norm(reused),_norm(residual))

_MUTATION_MAP={
'architecture':EvolutionSubstrate.ARCHITECTURE,'code':EvolutionSubstrate.CODE,'tests':EvolutionSubstrate.CODE,'tools':EvolutionSubstrate.ADAPTER,'skills':EvolutionSubstrate.SKILL,'routing':EvolutionSubstrate.ROUTING,'memory_policy':EvolutionSubstrate.MEMORY,'observability':EvolutionSubstrate.ADAPTER,'deployment_policy':EvolutionSubstrate.ALGORITHM,'performance_policy':EvolutionSubstrate.ALGORITHM,'docs':EvolutionSubstrate.CONTEXT,'ux':EvolutionSubstrate.CONTEXT,'model_choice':EvolutionSubstrate.ROUTING}

@dataclass(frozen=True, slots=True)
class ProductionGenome:
    genome_id:str; contract_fingerprint:str; systems:tuple[ComplementarySystem,...]; allowed_mutations:tuple[str,...]; authority_ceiling:str; data_boundary:str; owner_intent_hash:str; fingerprint_sha256:str
    def validate(self):
        if len(self.systems)!=20 or set(self.systems)!=set(ComplementarySystem): raise ValueError('PGC_COMPLEMENTARY_SYSTEM_SET_INCOMPLETE')
        if any(x not in _MUTATION_MAP for x in self.allowed_mutations): raise ValueError('PGC_MUTATION_CLASS_UNKNOWN')
        if len(self.owner_intent_hash)!=64 or len(self.fingerprint_sha256)!=64: raise ValueError('PGC_GENOME_FINGERPRINT_INVALID')
        return self

def compile_production_genome(contract:ProductContract, *, allowed_mutations:Iterable[str]=tuple(_MUTATION_MAP)):
    contract.validate(); muts=_norm(allowed_mutations)
    unknown=[x for x in muts if x not in _MUTATION_MAP]
    if unknown: raise ValueError('PGC_MUTATION_CLASS_UNKNOWN:'+','.join(unknown))
    systems=tuple(ComplementarySystem)
    payload={'schema':SCHEMA,'contract':contract.fingerprint,'systems':[x.value for x in systems],'mutations':muts,'authority':contract.authority_ceiling,'data_boundary':contract.data_boundary,'owner_intent_hash':contract.owner_intent_hash}
    d=_h(payload)
    return ProductionGenome('PG-'+d[:16].upper(),contract.fingerprint,systems,muts,contract.authority_ceiling,contract.data_boundary,contract.owner_intent_hash,d).validate()

class BuildPhase(str, Enum):
    CONTRACT='CONTRACT'; REUSE_CENSUS='REUSE_CENSUS'; ARCHITECTURE='ARCHITECTURE'; CONTRACTS='CONTRACTS'; UX='UX'; IMPLEMENT='IMPLEMENT'; TEST='TEST'; DIGITAL_TWIN='DIGITAL_TWIN'; SECURITY='SECURITY'; SUPPLY_CHAIN='SUPPLY_CHAIN'; PLATFORM='PLATFORM'; CANARY='CANARY'; PROGRESSIVE_ROLLOUT='PROGRESSIVE_ROLLOUT'; OPERATIONAL='OPERATIONAL'; USER_JOURNEY='USER_JOURNEY'; VALUE='VALUE'; EVOLVE='EVOLVE'
@dataclass(frozen=True, slots=True)
class BuildPlan:
    genome_id:str; phases:tuple[BuildPhase,...]; fingerprint_sha256:str

def compile_build_plan(genome:ProductionGenome):
    genome.validate(); phases=tuple(BuildPhase); return BuildPlan(genome.genome_id,phases,_h((genome.fingerprint_sha256,[p.value for p in phases])))

class TestClass(str, Enum):
    UNIT='UNIT'; INTEGRATION='INTEGRATION'; CONTRACT='CONTRACT'; PROPERTY='PROPERTY'; FAILURE='FAILURE'; SECURITY='SECURITY'; PRIVACY='PRIVACY'; PERFORMANCE='PERFORMANCE'; ACCESSIBILITY='ACCESSIBILITY'; UX='UX'; DATA_MIGRATION='DATA_MIGRATION'; DIGITAL_TWIN='DIGITAL_TWIN'; RECOVERY='RECOVERY'; REGRESSION='REGRESSION'
def compile_test_matrix(genome:ProductionGenome): genome.validate(); return tuple(TestClass)

class ProofKey(str, Enum):
    PRODUCT_CONTRACT='PRODUCT_CONTRACT'; SYSTEM_GENOME='SYSTEM_GENOME'; ARCHITECTURE='ARCHITECTURE'; SOURCE='SOURCE'; UNIT_TESTS='UNIT_TESTS'; INTEGRATION_TESTS='INTEGRATION_TESTS'; CONTRACT_TESTS='CONTRACT_TESTS'; SECURITY_TESTS='SECURITY_TESTS'; PERFORMANCE_TESTS='PERFORMANCE_TESTS'; TWIN_E2E='TWIN_E2E'; TWIN_FAILURE='TWIN_FAILURE'; SLSA_PROVENANCE='SLSA_PROVENANCE'; SBOM='SBOM'; ARTIFACT_DIGEST='ARTIFACT_DIGEST'; PROVIDER_IDENTITY='PROVIDER_IDENTITY'; CANARY_CONTRACT='CANARY_CONTRACT'; PROVIDER_EXECUTION='PROVIDER_EXECUTION'; PROVIDER_READBACK='PROVIDER_READBACK'; DEPLOYMENT_RECEIPT='DEPLOYMENT_RECEIPT'; READINESS='READINESS'; HEALTH='HEALTH'; PERSISTENCE='PERSISTENCE'; ROLLBACK='ROLLBACK'; OBSERVABILITY='OBSERVABILITY'; SLO='SLO'; DR_RECOVERY='DR_RECOVERY'; USER_JOURNEY='USER_JOURNEY'; VALUE_MEASUREMENT='VALUE_MEASUREMENT'

class MaturityStage(IntEnum):
    IDEA=0; PRODUCT_CONTRACTED=1; SYSTEM_GENOME_COMPILED=2; ARCHITECTURE_VERIFIED=3; SOURCE_IMPLEMENTED=4; DETERMINISTIC_TESTED=5; DIGITAL_TWIN_VERIFIED=6; SUPPLY_CHAIN_VERIFIED=7; PROVIDER_CANARY_READY=8; PROVIDER_VERIFIED=9; DEPLOYED=10; OPERATIONAL_VERIFIED=11; VALUE_VERIFIED=12

_STAGE_REQ={
MaturityStage.IDEA:(),
MaturityStage.PRODUCT_CONTRACTED:(ProofKey.PRODUCT_CONTRACT,),
MaturityStage.SYSTEM_GENOME_COMPILED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME),
MaturityStage.ARCHITECTURE_VERIFIED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE),
MaturityStage.SOURCE_IMPLEMENTED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE),
MaturityStage.DETERMINISTIC_TESTED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE,ProofKey.UNIT_TESTS,ProofKey.INTEGRATION_TESTS,ProofKey.CONTRACT_TESTS,ProofKey.SECURITY_TESTS,ProofKey.PERFORMANCE_TESTS),
MaturityStage.DIGITAL_TWIN_VERIFIED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE,ProofKey.UNIT_TESTS,ProofKey.INTEGRATION_TESTS,ProofKey.CONTRACT_TESTS,ProofKey.SECURITY_TESTS,ProofKey.PERFORMANCE_TESTS,ProofKey.TWIN_E2E,ProofKey.TWIN_FAILURE),
MaturityStage.SUPPLY_CHAIN_VERIFIED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE,ProofKey.UNIT_TESTS,ProofKey.INTEGRATION_TESTS,ProofKey.CONTRACT_TESTS,ProofKey.SECURITY_TESTS,ProofKey.PERFORMANCE_TESTS,ProofKey.TWIN_E2E,ProofKey.TWIN_FAILURE,ProofKey.SLSA_PROVENANCE,ProofKey.SBOM,ProofKey.ARTIFACT_DIGEST),
MaturityStage.PROVIDER_CANARY_READY:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE,ProofKey.UNIT_TESTS,ProofKey.INTEGRATION_TESTS,ProofKey.CONTRACT_TESTS,ProofKey.SECURITY_TESTS,ProofKey.PERFORMANCE_TESTS,ProofKey.TWIN_E2E,ProofKey.TWIN_FAILURE,ProofKey.SLSA_PROVENANCE,ProofKey.SBOM,ProofKey.ARTIFACT_DIGEST,ProofKey.PROVIDER_IDENTITY,ProofKey.CANARY_CONTRACT),
MaturityStage.PROVIDER_VERIFIED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE,ProofKey.UNIT_TESTS,ProofKey.INTEGRATION_TESTS,ProofKey.CONTRACT_TESTS,ProofKey.SECURITY_TESTS,ProofKey.PERFORMANCE_TESTS,ProofKey.TWIN_E2E,ProofKey.TWIN_FAILURE,ProofKey.SLSA_PROVENANCE,ProofKey.SBOM,ProofKey.ARTIFACT_DIGEST,ProofKey.PROVIDER_IDENTITY,ProofKey.CANARY_CONTRACT,ProofKey.PROVIDER_EXECUTION,ProofKey.PROVIDER_READBACK),
MaturityStage.DEPLOYED:tuple(ProofKey)[:23],
MaturityStage.OPERATIONAL_VERIFIED:tuple(ProofKey)[:27],
MaturityStage.VALUE_VERIFIED:tuple(ProofKey),
}

@dataclass(frozen=True, slots=True)
class ReadinessReceipt:
    stage:MaturityStage; observed:tuple[ProofKey,...]; missing_to_next:tuple[ProofKey,...]; fingerprint_sha256:str

def evaluate_readiness(proofs:Iterable[ProofKey]):
    observed=set(proofs); stage=MaturityStage.IDEA
    for s in MaturityStage:
        if set(_STAGE_REQ[s]).issubset(observed): stage=s
        else: break
    next_stage=MaturityStage(stage+1) if stage<MaturityStage.VALUE_VERIFIED else stage
    missing=tuple(p for p in _STAGE_REQ[next_stage] if p not in observed)
    ordered=tuple(p for p in ProofKey if p in observed)
    return ReadinessReceipt(stage,ordered,missing,_h((stage.name,[p.value for p in ordered],[p.value for p in missing])))

@dataclass(frozen=True, slots=True)
class GoLiveDecision:
    status:str; blockers:tuple[str,...]; readiness_stage:MaturityStage; fingerprint_sha256:str

def evaluate_progressive_go_live(proofs:Iterable[ProofKey], *, exact_effect_authority:bool, rollback_verified:bool, semantic_canary_defined:bool):
    r=evaluate_readiness(proofs); b=[]
    if r.stage<MaturityStage.PROVIDER_VERIFIED: b.append('PROVIDER_VERIFICATION_REQUIRED')
    if not exact_effect_authority: b.append('EXACT_EFFECT_AUTHORITY_REQUIRED')
    if not rollback_verified: b.append('ROLLBACK_REQUIRED')
    if not semantic_canary_defined: b.append('SEMANTIC_CANARY_REQUIRED')
    status='READY_FOR_PROGRESSIVE_GO_LIVE' if not b else ('HOLD_AUTHORITY' if b==['EXACT_EFFECT_AUTHORITY_REQUIRED'] else 'HOLD')
    return GoLiveDecision(status,tuple(sorted(b)),r.stage,_h((status,sorted(b),r.stage.name)))

@dataclass(frozen=True, slots=True)
class AOCEFProfile:
    production_genome_id:str; outer_envelope:OuterEnvelope; cognitive_genome_id:str; mutation_mapping:Mapping[str,EvolutionSubstrate]; fingerprint_sha256:str

def compile_aocef_profile(genome:ProductionGenome, *, objective:str, compute_budget:float, safety_floor:float=.95, reliability_floor:float=.95):
    genome.validate(); mapping={m:_MUTATION_MAP[m] for m in genome.allowed_mutations}; allowed=tuple(sorted(set(mapping.values()),key=lambda x:x.value))
    envelope=OuterEnvelope(objective=objective,allowed_substrates=allowed,authority_ceiling=genome.authority_ceiling,data_boundary=genome.data_boundary,owner_intent_hash=genome.owner_intent_hash,compute_budget=compute_budget,safety_floor=safety_floor,reliability_floor=reliability_floor,no_production_self_mutation=True).validate()
    genes=[CognitiveGene('PG-'+m.upper(),sub, 'improve '+m, (m,), ('preserve_owner_intent','preserve_authority','independent_verifier','rollback','provenance')) for m,sub in sorted(mapping.items())]
    ceg=compile_genome(envelope,genes,lineage_proof_refs=(genome.fingerprint_sha256,))
    return AOCEFProfile(genome.genome_id,envelope,ceg.genome_id,mapping,_h((genome.genome_id,envelope.fingerprint,ceg.fingerprint_sha256,sorted((k,v.value) for k,v in mapping.items()))))

@dataclass(frozen=True, slots=True)
class ProductionGenesisVector:
    accepted_value:float; quality:float; security:float; reliability:float; maintainability:float; observability:float; deployability:float; portability:float; evolvability:float; reuse:float; owner_leverage:float; cost:float; wall_time:float; owner_actions:float; complexity:float; defect_escape:float; rollback_risk:float
    def score(self):
        for x in (self.accepted_value,self.quality,self.security,self.reliability,self.maintainability,self.observability,self.deployability,self.portability,self.evolvability,self.reuse,self.owner_leverage):
            if not 0<=x<=1: raise ValueError('PGC_VECTOR_UNIT_RANGE')
        if any(x<0 for x in (self.cost,self.wall_time,self.owner_actions,self.complexity,self.defect_escape,self.rollback_risk)): raise ValueError('PGC_VECTOR_COST_NEGATIVE')
        q=(self.accepted_value+self.quality+self.security+self.reliability+self.maintainability+self.observability+self.deployability+self.portability+self.evolvability+self.reuse+self.owner_leverage)/11
        burden=1+self.cost+self.wall_time+self.owner_actions+self.complexity+2*self.defect_escape+2*self.rollback_risk
        return q/burden

@dataclass(frozen=True, slots=True)
class ProductionGenesisYieldCourt:
    ratio:float; eligible_10x:bool; blockers:tuple[str,...]; fingerprint_sha256:str

def evaluate_production_genesis_yield(candidate:ProductionGenesisVector, frontier:ProductionGenesisVector, *, maturity:MaturityStage, provider_verified:bool, forward_system_classes:int, no_benchmark_leakage:bool, rollback_verified:bool):
    cs=candidate.score(); fs=frontier.score(); ratio=cs/max(fs,1e-12); b=[]
    if maturity<MaturityStage.OPERATIONAL_VERIFIED: b.append('OPERATIONAL_MATURITY_REQUIRED')
    if not provider_verified: b.append('PROVIDER_VERIFICATION_REQUIRED')
    if forward_system_classes<3: b.append('THREE_FORWARD_SYSTEM_CLASSES_REQUIRED')
    if not no_benchmark_leakage: b.append('BENCHMARK_LEAKAGE_FORBIDDEN')
    if not rollback_verified: b.append('ROLLBACK_REQUIRED')
    for name in ('quality','security','reliability','maintainability','observability','deployability','portability'):
        if getattr(candidate,name)<getattr(frontier,name): b.append('FRONTIER_FLOOR_FAILED:'+name)
    if ratio<10: b.append('TEN_X_RATIO_NOT_MET')
    b=tuple(sorted(set(b))); return ProductionGenesisYieldCourt(ratio,not b,b,_h((ratio,b,maturity.name,provider_verified,forward_system_classes,no_benchmark_leakage,rollback_verified)))
