import pytest
from benchmarking.cfbe_omega.production_genesis_v1 import *
import benchmarking.cfbe_omega.production_genesis_v1 as pg

def contract(**kw):
    d=dict(product_id='p1',objective='build secure product',user_classes=('admin','user'),user_journeys=('signup','use'),required_outcomes=('value',),authority_ceiling='A1_INTERNAL',data_boundary='PRIVATE',owner_intent_hash='a'*64)
    d.update(kw); return ProductContract(**d)

def test_contract_and_determinism():
    c=contract(); assert c.validate() is c; assert c.fingerprint==contract().fingerprint
@pytest.mark.parametrize('field,value',[('product_id',''),('objective',''),('user_classes',()),('user_journeys',()),('required_outcomes',()),('owner_intent_hash','bad')])
def test_contract_fail_closed(field,value):
    with pytest.raises(ValueError): contract(**{field:value}).validate()

def test_genome_deterministic_and_complete():
    g=compile_production_genome(contract()); assert len(g.systems)==20; assert set(g.systems)==set(ComplementarySystem); assert g.fingerprint_sha256==compile_production_genome(contract()).fingerprint_sha256
@pytest.mark.parametrize('system', list(ComplementarySystem))
def test_all_complementary_systems(system): assert system in compile_production_genome(contract()).systems

def test_unknown_mutation_rejected():
    with pytest.raises(ValueError): compile_production_genome(contract(),allowed_mutations=('root_authority',))
@pytest.mark.parametrize('phase', list(BuildPhase))
def test_all_build_phases(phase): assert phase in compile_build_plan(compile_production_genome(contract())).phases
@pytest.mark.parametrize('tc', list(TestClass))
def test_all_test_classes(tc): assert tc in compile_test_matrix(compile_production_genome(contract()))
@pytest.mark.parametrize('proof', list(ProofKey))
def test_all_proof_keys_unique(proof): assert list(ProofKey).count(proof)==1

def test_28_proofs_and_20_systems_and_17_phases_and_14_tests():
    assert len(ProofKey)==28 and len(ComplementarySystem)==20 and len(BuildPhase)==17 and len(TestClass)==14
@pytest.mark.parametrize('stage', list(MaturityStage)[1:])
def test_stage_requires_exact_subset(stage):
    req=pg._STAGE_REQ[stage]; assert req
    r=evaluate_readiness(req); assert r.stage>=stage
    if len(req)>1:
        r2=evaluate_readiness(req[:-1]); assert r2.stage<stage

def test_provider_verified_not_deployed():
    r=evaluate_readiness(pg._STAGE_REQ[MaturityStage.PROVIDER_VERIFIED]); assert r.stage==MaturityStage.PROVIDER_VERIFIED

def test_go_live_holds_without_provider():
    d=evaluate_progressive_go_live(pg._STAGE_REQ[MaturityStage.DETERMINISTIC_TESTED],exact_effect_authority=True,rollback_verified=True,semantic_canary_defined=True); assert d.status=='HOLD'

def test_go_live_holds_authority_only():
    d=evaluate_progressive_go_live(pg._STAGE_REQ[MaturityStage.PROVIDER_VERIFIED],exact_effect_authority=False,rollback_verified=True,semantic_canary_defined=True); assert d.status=='HOLD_AUTHORITY'

def test_go_live_ready_only_when_all_current_gates():
    d=evaluate_progressive_go_live(pg._STAGE_REQ[MaturityStage.PROVIDER_VERIFIED],exact_effect_authority=True,rollback_verified=True,semantic_canary_defined=True); assert d.status=='READY_FOR_PROGRESSIVE_GO_LIVE'

def test_aocef_profile_preserves_envelope():
    g=compile_production_genome(contract()); p=compile_aocef_profile(g,objective='improve production',compute_budget=10); assert p.outer_envelope.owner_intent_hash==g.owner_intent_hash; assert p.outer_envelope.authority_ceiling==g.authority_ceiling; assert p.outer_envelope.no_production_self_mutation
@pytest.mark.parametrize('mutation,substrate', list(pg._MUTATION_MAP.items()))
def test_mutation_mapping(mutation,substrate):
    p=compile_aocef_profile(compile_production_genome(contract(),allowed_mutations=(mutation,)),objective='x',compute_budget=1); assert p.mutation_mapping[mutation]==substrate

def vec(**kw):
    d=dict(accepted_value=.9,quality=.95,security=.95,reliability=.95,maintainability=.95,observability=.95,deployability=.95,portability=.95,evolvability=.95,reuse=.95,owner_leverage=.95,cost=.2,wall_time=.2,owner_actions=.1,complexity=.2,defect_escape=.01,rollback_risk=.01); d.update(kw); return ProductionGenesisVector(**d)

def test_10x_design_only_rejected():
    c=vec(cost=0,wall_time=0,owner_actions=0,complexity=0,defect_escape=0,rollback_risk=0); f=vec(cost=100,wall_time=100,owner_actions=100,complexity=100,defect_escape=1,rollback_risk=1); r=evaluate_production_genesis_yield(c,f,maturity=MaturityStage.DETERMINISTIC_TESTED,provider_verified=False,forward_system_classes=1,no_benchmark_leakage=True,rollback_verified=True); assert not r.eligible_10x; assert 'OPERATIONAL_MATURITY_REQUIRED' in r.blockers

def test_10x_floor_regression_rejected():
    c=vec(quality=.8,cost=0,wall_time=0,owner_actions=0,complexity=0,defect_escape=0,rollback_risk=0); f=vec(cost=100,wall_time=100,owner_actions=100,complexity=100,defect_escape=1,rollback_risk=1); r=evaluate_production_genesis_yield(c,f,maturity=MaturityStage.OPERATIONAL_VERIFIED,provider_verified=True,forward_system_classes=3,no_benchmark_leakage=True,rollback_verified=True); assert not r.eligible_10x; assert 'FRONTIER_FLOOR_FAILED:quality' in r.blockers

def test_10x_valid_synthetic_math_fixture_only():
    c=vec(cost=0,wall_time=0,owner_actions=0,complexity=0,defect_escape=0,rollback_risk=0); f=vec(cost=100,wall_time=100,owner_actions=100,complexity=100,defect_escape=1,rollback_risk=1); r=evaluate_production_genesis_yield(c,f,maturity=MaturityStage.OPERATIONAL_VERIFIED,provider_verified=True,forward_system_classes=3,no_benchmark_leakage=True,rollback_verified=True); assert r.ratio>10 and r.eligible_10x
