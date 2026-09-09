import unittest
from dataclasses import dataclass
from enum import Enum, IntEnum
from types import SimpleNamespace

from benchmarking.cfbe_omega.fascg_aopgc_bridge_v1 import (
    MODEL_TRAINING_AUTHORIZED,
    PRODUCTION_DEPLOYMENT_AUTHORIZED,
    PRODUCTION_SELF_MUTATION_AUTHORIZED,
    PROVIDER_EFFECT_AUTHORIZED,
    TEN_X_VERIFIED,
    ProductContractSpec,
    compile_aopgc_production_evidence,
)


class E(Enum):
    def __str__(self): return self.value


class ProofKey(str, Enum):
    PRODUCT_CONTRACT='PRODUCT_CONTRACT'; SYSTEM_GENOME='SYSTEM_GENOME'; ARCHITECTURE='ARCHITECTURE'; SOURCE='SOURCE'; UNIT_TESTS='UNIT_TESTS'; INTEGRATION_TESTS='INTEGRATION_TESTS'; CONTRACT_TESTS='CONTRACT_TESTS'; SECURITY_TESTS='SECURITY_TESTS'; PERFORMANCE_TESTS='PERFORMANCE_TESTS'; TWIN_E2E='TWIN_E2E'; TWIN_FAILURE='TWIN_FAILURE'; SLSA_PROVENANCE='SLSA_PROVENANCE'; SBOM='SBOM'; ARTIFACT_DIGEST='ARTIFACT_DIGEST'; PROVIDER_IDENTITY='PROVIDER_IDENTITY'; CANARY_CONTRACT='CANARY_CONTRACT'; PROVIDER_EXECUTION='PROVIDER_EXECUTION'; PROVIDER_READBACK='PROVIDER_READBACK'; DEPLOYMENT_RECEIPT='DEPLOYMENT_RECEIPT'; READINESS='READINESS'; HEALTH='HEALTH'; PERSISTENCE='PERSISTENCE'; ROLLBACK='ROLLBACK'; OBSERVABILITY='OBSERVABILITY'; SLO='SLO'; DR_RECOVERY='DR_RECOVERY'; USER_JOURNEY='USER_JOURNEY'; VALUE_MEASUREMENT='VALUE_MEASUREMENT'

class MaturityStage(IntEnum):
    IDEA=0; PRODUCT_CONTRACTED=1; SYSTEM_GENOME_COMPILED=2; ARCHITECTURE_VERIFIED=3; SOURCE_IMPLEMENTED=4; DETERMINISTIC_TESTED=5; DIGITAL_TWIN_VERIFIED=6; SUPPLY_CHAIN_VERIFIED=7; PROVIDER_CANARY_READY=8; PROVIDER_VERIFIED=9; DEPLOYED=10; OPERATIONAL_VERIFIED=11; VALUE_VERIFIED=12

class ComplementarySystem(str, Enum):
    A0='A0'; A1='A1'; A2='A2'; A3='A3'; A4='A4'; A5='A5'; A6='A6'; A7='A7'; A8='A8'; A9='A9'; A10='A10'; A11='A11'; A12='A12'; A13='A13'; A14='A14'; A15='A15'; A16='A16'; A17='A17'; A18='A18'; A19='A19'
class BuildPhase(str, Enum):
    P0='P0'; P1='P1'; P2='P2'; P3='P3'; P4='P4'; P5='P5'; P6='P6'; P7='P7'; P8='P8'; P9='P9'; P10='P10'; P11='P11'; P12='P12'; P13='P13'; P14='P14'; P15='P15'; P16='P16'
class TestClass(str, Enum):
    T0='T0'; T1='T1'; T2='T2'; T3='T3'; T4='T4'; T5='T5'; T6='T6'; T7='T7'; T8='T8'; T9='T9'; T10='T10'; T11='T11'; T12='T12'; T13='T13'

@dataclass
class ProductContract:
    product_id:str; objective:str; user_classes:tuple; user_journeys:tuple; required_outcomes:tuple; authority_ceiling:str; data_boundary:str; owner_intent_hash:str; quality_floor:float=.95; security_floor:float=.95; reliability_floor:float=.95
    def validate(self): return self

@dataclass
class V:
    accepted_value:float=.9; quality:float=.95; security:float=.95; reliability:float=.95; maintainability:float=.95; observability:float=.95; deployability:float=.95; portability:float=.95; evolvability:float=.95; reuse:float=.95; owner_leverage:float=.95; cost:float=.1; wall_time:float=.1; owner_actions:float=.1; complexity:float=.1; defect_escape:float=.01; rollback_risk:float=.01
    def score(self): return (self.accepted_value+self.quality+self.security+self.reliability+self.maintainability+self.observability+self.deployability+self.portability+self.evolvability+self.reuse+self.owner_leverage)/11/(1+self.cost+self.wall_time+self.owner_actions+self.complexity+2*self.defect_escape+2*self.rollback_risk)

REQ={
    MaturityStage.IDEA:(),
    MaturityStage.PRODUCT_CONTRACTED:(ProofKey.PRODUCT_CONTRACT,),
    MaturityStage.SYSTEM_GENOME_COMPILED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME),
    MaturityStage.ARCHITECTURE_VERIFIED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE),
    MaturityStage.SOURCE_IMPLEMENTED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE),
    MaturityStage.DETERMINISTIC_TESTED:(ProofKey.PRODUCT_CONTRACT,ProofKey.SYSTEM_GENOME,ProofKey.ARCHITECTURE,ProofKey.SOURCE,ProofKey.UNIT_TESTS,ProofKey.INTEGRATION_TESTS,ProofKey.CONTRACT_TESTS,ProofKey.SECURITY_TESTS,ProofKey.PERFORMANCE_TESTS),
    MaturityStage.DIGITAL_TWIN_VERIFIED:tuple(list(ProofKey)[:11]),
    MaturityStage.SUPPLY_CHAIN_VERIFIED:tuple(list(ProofKey)[:14]),
    MaturityStage.PROVIDER_CANARY_READY:tuple(list(ProofKey)[:16]),
    MaturityStage.PROVIDER_VERIFIED:tuple(list(ProofKey)[:18]),
    MaturityStage.DEPLOYED:tuple(list(ProofKey)[:23]),
    MaturityStage.OPERATIONAL_VERIFIED:tuple(list(ProofKey)[:27]),
    MaturityStage.VALUE_VERIFIED:tuple(ProofKey),
}

def readiness(proofs):
    obs=set(proofs); stage=MaturityStage.IDEA
    for s in MaturityStage:
        if set(REQ[s]).issubset(obs): stage=s
        else: break
    next_stage=MaturityStage(stage+1) if stage<MaturityStage.VALUE_VERIFIED else stage
    return SimpleNamespace(stage=stage, observed=tuple(p for p in ProofKey if p in obs), missing_to_next=tuple(p for p in REQ[next_stage] if p not in obs))

def fake_pg(schema="CFBE_AO_PRODUCTION_GENESIS_PHASE1_V1", bad_shape=False, self_mutation=False):
    def genome(c, **kwargs): return SimpleNamespace(genome_id='PG-123', systems=tuple(ComplementarySystem), fingerprint_sha256='a'*64, authority_ceiling=c.authority_ceiling, data_boundary=c.data_boundary, owner_intent_hash=c.owner_intent_hash)
    def build(g): return SimpleNamespace(fingerprint_sha256='b'*64)
    def ao(g, **kwargs): return SimpleNamespace(fingerprint_sha256='c'*64, cognitive_genome_id='CEG-123', outer_envelope=SimpleNamespace(no_production_self_mutation=not self_mutation, owner_intent_hash=g.owner_intent_hash, authority_ceiling=g.authority_ceiling))
    def go(proofs, exact_effect_authority, rollback_verified, semantic_canary_defined):
        r=readiness(proofs); b=[]
        if r.stage<MaturityStage.PROVIDER_VERIFIED: b.append('PROVIDER_VERIFICATION_REQUIRED')
        if not exact_effect_authority: b.append('EXACT_EFFECT_AUTHORITY_REQUIRED')
        if not rollback_verified: b.append('ROLLBACK_REQUIRED')
        if not semantic_canary_defined: b.append('SEMANTIC_CANARY_REQUIRED')
        return SimpleNamespace(status='READY_FOR_PROGRESSIVE_GO_LIVE' if not b else 'HOLD', blockers=tuple(sorted(b)), readiness_stage=r.stage)
    def pgy(c, f, maturity, provider_verified, forward_system_classes, no_benchmark_leakage, rollback_verified):
        ratio=c.score()/max(f.score(),1e-12); ok=maturity>=MaturityStage.OPERATIONAL_VERIFIED and provider_verified and forward_system_classes>=3 and no_benchmark_leakage and rollback_verified and ratio>=10
        return SimpleNamespace(ratio=ratio, eligible_10x=ok, blockers=())
    systems=ComplementarySystem if not bad_shape else tuple(list(ComplementarySystem)[:-1])
    return SimpleNamespace(
        SCHEMA=schema, PROVIDER_EFFECT_AUTHORIZED=False, PRODUCTION_DEPLOYMENT_AUTHORIZED=False, MODEL_TRAINING_AUTHORIZED=False,
        ProductContract=ProductContract, ComplementarySystem=systems, BuildPhase=BuildPhase, TestClass=TestClass, ProofKey=ProofKey, MaturityStage=MaturityStage,
        ProductionGenesisVector=V, compile_production_genome=genome, compile_build_plan=build, compile_test_matrix=lambda g: tuple(TestClass),
        compile_aocef_profile=ao, evaluate_readiness=readiness, evaluate_progressive_go_live=go, evaluate_production_genesis_yield=pgy,
    )

class AOPGCBridgeTests(unittest.TestCase):
    def contract(self):
        return ProductContractSpec('fascg','production FASCG',('owner',),('operate',),('verified value',),'A1_INTERNAL','PRIVATE','a'*64)
    def names(self, stage=MaturityStage.DETERMINISTIC_TESTED): return tuple(p.value for p in REQ[stage])
    def test_truth_flags(self):
        self.assertFalse(PROVIDER_EFFECT_AUTHORIZED); self.assertFalse(PRODUCTION_DEPLOYMENT_AUTHORIZED)
        self.assertFalse(MODEL_TRAINING_AUTHORIZED); self.assertFalse(PRODUCTION_SELF_MUTATION_AUTHORIZED); self.assertFalse(TEN_X_VERIFIED)
    def test_deterministic_evidence_preserves_lower_maturity(self):
        e=compile_aopgc_production_evidence(self.contract(), observed_proof_keys=self.names(), exact_effect_authority=False, rollback_verified=True, semantic_canary_defined=True, compute_budget=10, pg_module=fake_pg())
        self.assertEqual(e.readiness_stage,'DETERMINISTIC_TESTED'); self.assertEqual(e.go_live_status,'HOLD')
        self.assertFalse(e.provider_bound); self.assertFalse(e.operational_verified); self.assertFalse(e.fascg_ten_x_verified)
        self.assertEqual((e.complementary_system_count,e.build_phase_count,e.test_class_count,e.proof_key_count),(20,17,14,28))
    def test_provider_verified_can_be_go_live_candidate_with_exact_authority(self):
        e=compile_aopgc_production_evidence(self.contract(), observed_proof_keys=self.names(MaturityStage.PROVIDER_VERIFIED), exact_effect_authority=True, rollback_verified=True, semantic_canary_defined=True, compute_budget=10, pg_module=fake_pg())
        self.assertTrue(e.progressive_go_live_candidate); self.assertTrue(e.provider_bound); self.assertFalse(e.operational_verified)
    def test_operational_can_be_retained_without_tenx_inheritance(self):
        e=compile_aopgc_production_evidence(self.contract(), observed_proof_keys=self.names(MaturityStage.OPERATIONAL_VERIFIED), exact_effect_authority=True, rollback_verified=True, semantic_canary_defined=True, compute_budget=10, pg_module=fake_pg())
        self.assertTrue(e.operational_verified); self.assertFalse(e.fascg_ten_x_verified)
    def test_aopgc_10x_never_becomes_fascg_10x(self):
        cand=dict(cost=0,wall_time=0,owner_actions=0,complexity=0,defect_escape=0,rollback_risk=0)
        front=dict(cost=100,wall_time=100,owner_actions=100,complexity=100,defect_escape=1,rollback_risk=1)
        e=compile_aopgc_production_evidence(self.contract(), observed_proof_keys=self.names(MaturityStage.OPERATIONAL_VERIFIED), exact_effect_authority=True, rollback_verified=True, semantic_canary_defined=True, compute_budget=10, candidate_vector=cand, frontier_vector=front, pgy_provider_verified=True, forward_system_classes=3, pg_module=fake_pg())
        self.assertTrue(e.aopgc_eligible_10x); self.assertGreater(e.aopgc_pgy_ratio,10); self.assertFalse(e.fascg_ten_x_verified)
    def test_unknown_proof_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'UNKNOWN_PROOF_KEY'):
            compile_aopgc_production_evidence(self.contract(), observed_proof_keys=('NOT_A_PROOF',), exact_effect_authority=False, rollback_verified=False, semantic_canary_defined=False, compute_budget=1, pg_module=fake_pg())
    def test_upstream_schema_drift_rejected(self):
        with self.assertRaisesRegex(ValueError,'SCHEMA_MISMATCH'):
            compile_aopgc_production_evidence(self.contract(), observed_proof_keys=self.names(), exact_effect_authority=False, rollback_verified=False, semantic_canary_defined=False, compute_budget=1, pg_module=fake_pg(schema='WRONG'))
    def test_self_mutation_boundary_required(self):
        with self.assertRaisesRegex(ValueError,'SELF_MUTATION_BOUNDARY'):
            compile_aopgc_production_evidence(self.contract(), observed_proof_keys=self.names(), exact_effect_authority=False, rollback_verified=False, semantic_canary_defined=False, compute_budget=1, pg_module=fake_pg(self_mutation=True))
    def test_pgy_vectors_must_be_paired(self):
        with self.assertRaisesRegex(ValueError,'VECTORS_MUST_BE_PAIRED'):
            compile_aopgc_production_evidence(self.contract(), observed_proof_keys=self.names(), exact_effect_authority=False, rollback_verified=False, semantic_canary_defined=False, compute_budget=1, candidate_vector={}, pg_module=fake_pg())

if __name__=='__main__': unittest.main()
