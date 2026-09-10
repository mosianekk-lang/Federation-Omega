from fastapi.testclient import TestClient
from aegis_omega.api import app
client=TestClient(app)

def test_health():
    r=client.get('/healthz'); assert r.status_code==200; assert r.json()['mode']=='defensive-only'

def test_assess_case():
    r=client.post('/v1/assess', json={'request_id':'api-test-001','events':[
        {'event_id':'event-api-1','device_id':'dev','event_class':'device_integrity','severity':.9,'source':'test','consent':True}
    ]})
    assert r.status_code==200; assert r.json()['requires_human_approval'] is True

def test_orchestration_profile_is_bounded_and_non_effectful_by_default():
    r=client.get('/v1/orchestration/profile'); assert r.status_code==200
    body=r.json(); assert body['selected_route_id']=='compose-sol62-formation-slos-fuse'; assert body['parallel_lanes']
    assert body['provider_effect_authorized'] is False and body['stable_promotion_authorized'] is False
    assert body['ai_bots_are_logical_roles'] is True and body['hidden_background_execution_claimed'] is False
    held={lane_id:reason for lane_id,reason in body['held_lanes']}; assert 'source-admission' in held and 'gcp-private-canary' in held

def test_adversarial_profile_is_defensive_and_non_promoting():
    r=client.get('/v1/adversarial/profile'); assert r.status_code==200; body=r.json()
    assert body['defensive_only'] is True and body['synthetic_scenarios_only'] is True
    assert body['neural_decision_authority'] is False and body['automatic_model_promotion'] is False

def test_adversarial_court_endpoint_has_no_provider_effect():
    r=client.post('/v1/adversarial/court'); assert r.status_code==200; body=r.json()
    assert body['scenario_pass_count']==body['scenario_count']==11; assert body['provider_effect_performed'] is False; assert body['auto_promotion_performed'] is False
