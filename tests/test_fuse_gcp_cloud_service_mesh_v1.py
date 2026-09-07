import pytest
from federation.fuse_gcp_cloud_service_mesh_v1 import *


def req(effect=EffectClass.A1_INTERNAL, **kw):
    base=dict(request_id="R1", mission_id="M1", requesting_organ="FUSE", capability="cloud.read", effect_class=effect)
    base.update(kw)
    return CloudServiceRequest(**base)


def route(route_id, **kw):
    base=dict(service="CloudRun", executor="operator", directness=5, maturity=5, health=1.0, reliability=1.0, latency_ms=100, cost=0, risk=0, effect_ceiling=EffectClass.A1_INTERNAL, evidence_refs=("proof",))
    base.update(kw)
    return CloudRoute(route_id=route_id, **base)


def effect_req():
    return req(EffectClass.A2_PROVIDER_MUTATION, project="p", target="svc", action="deploy", authority_ref="A", semantic_postcondition="rev2", idempotency_key="I")


def test_request_identity_required():
    with pytest.raises(ValueError, match="REQUEST_IDENTITY_REQUIRED"): req(request_id="").validate()


def test_effect_requires_exact_target_authority_readback_contract():
    with pytest.raises(ValueError, match="EFFECT_REQUEST_EXACT_TARGET_AUTHORITY_READBACK_REQUIRED"): req(EffectClass.A2_PROVIDER_MUTATION).validate()


def test_exact_effect_request_valid(): effect_req().validate()


def test_unhealthy_route_held(): assert FUSEGCPCloudServiceMesh().rank_routes(req(), [route("bad", health=.2)])[0].hold_reason == "UNHEALTHY_ROUTE"


def test_effect_ceiling_held(): assert FUSEGCPCloudServiceMesh().rank_routes(effect_req(), [route("read")])[0].hold_reason == "EFFECT_CEILING_INSUFFICIENT"


def test_direct_reuse_beats_build_last():
    ranked=FUSEGCPCloudServiceMesh().rank_routes(req(), [route("native"), route("build", directness=10, maturity=10, build_required=True)])
    assert ranked[0].route.route_id == "native"


def test_plan_selects_best_eligible_not_held(): assert FUSEGCPCloudServiceMesh().plan(req(), [route("held", health=.1), route("ok")]).selected_route_id == "ok"


def test_logical_bots_do_not_become_provider_workers():
    plan=FUSEGCPCloudServiceMesh().plan(req(), [route("ok")])
    assert plan.provider_native_worker_count == 0
    assert all(b.logical_only and not b.provider_native_worker and not b.may_self_certify for b in plan.logical_bots)


def test_alpha_omega_has_all_10_stages_in_order():
    packets=FUSEGCPCloudServiceMesh().alpha_omega_packets("M1")
    assert [p.stage for p in packets] == list(Stage) and len(packets) == 10


def test_alpha_omega_dependencies_are_monotonic_chain():
    packets=FUSEGCPCloudServiceMesh().alpha_omega_packets("M1")
    assert packets[0].dependencies == ()
    for i in range(1, len(packets)): assert packets[i].dependencies == (packets[i-1].packet_id,)


def test_receipt_read_only_transport_success_can_verify():
    receipt=CloudServiceReceipt("R1","M1","","","","status","operator","principal",True,False,"","",False,("proof",))
    assert receipt.verify(req())


def test_effect_receipt_requires_exact_target_match():
    receipt=CloudServiceReceipt("R1","M1","other","us","svc","deploy","operator","principal",True,True,"rev2","rev2",True,("proof",))
    assert not receipt.verify(effect_req())


def test_effect_receipt_requires_provider_identity():
    receipt=CloudServiceReceipt("R1","M1","p","us","svc","deploy","operator","",True,True,"rev2","rev2",True,("proof",))
    assert not receipt.verify(effect_req())


def test_effect_receipt_requires_semantic_readback():
    receipt=CloudServiceReceipt("R1","M1","p","us","svc","deploy","operator","principal",True,False,"rev2","rev2",True,("proof",))
    assert not receipt.verify(effect_req())


def test_effect_receipt_requires_postcondition_match():
    receipt=CloudServiceReceipt("R1","M1","p","us","svc","deploy","operator","principal",True,True,"rev2","rev1",True,("proof",))
    assert not receipt.verify(effect_req())


def test_effect_receipt_exact_semantic_proof_verifies():
    receipt=CloudServiceReceipt("R1","M1","p","us","svc","deploy","operator","principal",True,True,"rev2","rev2",True,("proof",))
    assert receipt.verify(effect_req())


def test_plan_digest_deterministic():
    mesh=FUSEGCPCloudServiceMesh(); p1=mesh.plan(req(), [route("b"), route("a")]); p2=mesh.plan(req(), [route("b"), route("a")])
    assert p1.plan_sha256 == p2.plan_sha256


def test_no_routes_fails_closed():
    with pytest.raises(ValueError, match="ROUTES_REQUIRED"): FUSEGCPCloudServiceMesh().plan(req(), [])


def test_all_routes_held_fails_closed():
    with pytest.raises(ValueError, match="NO_ELIGIBLE_CLOUD_ROUTE"): FUSEGCPCloudServiceMesh().plan(req(), [route("bad", health=.1)])


def test_custom_role_adds_without_dropping_core_swarm():
    roles={b.role for b in FUSEGCPCloudServiceMesh().formation_bots("M1", roles=["DATA_BIGQUERY_STORAGE_BOT"])}
    assert "DATA_BIGQUERY_STORAGE_BOT" in roles and "REDTEAM_PROOF_WITNESS_BOT" in roles
