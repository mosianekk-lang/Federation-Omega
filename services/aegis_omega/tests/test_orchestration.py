import asyncio
import pytest
from aegis_omega.orchestration import AuthorityBoundaryError,AuthorizationContext,BotRole,EffectClass,FormationRouteTournament,RouteCandidate,RouteFamily,SafeBotSwarmExecutor,Sol62AlphaOmegaPlanner,WorkLane,aegis_current_mission_plan

def test_current_plan_has_all_four_route_families_and_selects_composed_route():
    plan=aegis_current_mission_plan(); assert plan.selected_route_id=='compose-sol62-formation-slos-fuse'; assert len(plan.route_ranking)==4

def test_parallel_lanes_are_safe_and_conflict_free():
    plan=aegis_current_mission_plan(); occupied=set(); assert plan.parallel_lanes
    for lane in plan.parallel_lanes:
        assert lane.effect_class in {EffectClass.NO_EFFECT,EffectClass.READ_ONLY}; assert not occupied.intersection(lane.conflict_domains); occupied.update(lane.conflict_domains)

def test_provider_and_mutating_lanes_fail_closed_without_authority():
    plan=aegis_current_mission_plan(); held=dict(plan.held_lanes); assert held['gemini-semantic-canary']=='PROVIDER_AUTHORITY_OR_IDENTITY_UNVERIFIED'; assert held['source-admission']=='PROVIDER_AUTHORITY_OR_IDENTITY_UNVERIFIED'; assert held['gcp-private-canary']=='PROVIDER_AUTHORITY_OR_IDENTITY_UNVERIFIED'; assert not plan.serial_lanes

def test_mutating_lanes_are_serial_even_when_fully_authorized():
    auth=AuthorizationContext(provider_authority_verified=True,provider_identity_current=True,cost_authorized=True,privacy_cleared=True,mutation_authorized=True,fdof_lease_owned=True); plan=aegis_current_mission_plan(auth); serial={lane.lane_id for lane in plan.serial_lanes}; assert {'gemini-semantic-canary','source-admission','gcp-private-canary'}.issubset(serial)

def test_mutation_stays_held_without_fdof_fence_even_with_provider_authority():
    auth=AuthorizationContext(provider_authority_verified=True,provider_identity_current=True,cost_authorized=True,privacy_cleared=True,mutation_authorized=True,fdof_lease_owned=False); plan=aegis_current_mission_plan(auth); held=dict(plan.held_lanes); assert held['source-admission']=='FDOF_FENCE_NOT_OWNED'; assert held['gcp-private-canary']=='FDOF_FENCE_NOT_OWNED'

def test_plan_digest_is_deterministic(): assert aegis_current_mission_plan().plan_sha256==aegis_current_mission_plan().plan_sha256

def test_formation_tournament_requires_all_route_families():
    routes=(RouteCandidate('a',RouteFamily.REUSE_OPTIMISE,'a',.5,.5,.5,.5,.5,.5,.5,.5,.5),)
    with pytest.raises(ValueError,match='ROUTE_FAMILIES_MISSING'): FormationRouteTournament.rank(routes)

def test_safe_bot_swarm_executes_only_parallel_safe_lanes_and_compiles_receipt():
    plan=aegis_current_mission_plan()
    async def handler(lane): return {'semantic_verified':True,'proof_valid':True,'provider_effect_performed':False,'evidence_ref':f'proof:{lane.lane_id}'}
    receipt=asyncio.run(SafeBotSwarmExecutor.execute(plan,{lane.lane_id:handler for lane in plan.parallel_lanes})); assert receipt.failed_lane_count==0; assert receipt.provider_effect_observed is False

def test_safe_bot_swarm_preserves_failure_without_faking_success():
    plan=aegis_current_mission_plan()
    async def handler(lane):
        if lane.lane_id==plan.parallel_lanes[0].lane_id: raise RuntimeError('seeded failure')
        return {'semantic_verified':True,'proof_valid':True,'evidence_ref':'proof'}
    receipt=asyncio.run(SafeBotSwarmExecutor.execute(plan,{lane.lane_id:handler for lane in plan.parallel_lanes})); assert receipt.failed_lane_count==1

def test_stable_promotion_never_inferred_from_execution_authority():
    auth=AuthorizationContext(provider_authority_verified=True,provider_identity_current=True,cost_authorized=True,privacy_cleared=True,mutation_authorized=True,fdof_lease_owned=True,stable_promotion_authorized=False); plan=aegis_current_mission_plan(auth); assert plan.provider_effect_authorized is True; assert plan.stable_promotion_authorized is False
