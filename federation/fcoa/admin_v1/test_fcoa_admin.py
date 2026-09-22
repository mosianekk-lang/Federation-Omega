from fcoa_admin import *


def reg():
    return FCOAAdminRegistry([
        CapabilityRecord("alpha_omega.schedule", "alpha-omega", Scope.FUSE_OWNED, frozenset({"FUSE_INTERNAL_ADMIN"})),
        CapabilityRecord("formation.compose", "formation", Scope.FUSE_OWNED, frozenset({"FUSE_INTERNAL_ADMIN"})),
        CapabilityRecord("hypercube.harvest", "hypercube", Scope.FUSE_OWNED, frozenset({"FUSE_INTERNAL_ADMIN"})),
        CapabilityRecord("localllm.model.admin", "localllm", Scope.FUSE_OWNED, frozenset({"FUSE_INTERNAL_ADMIN"})),
        CapabilityRecord("github.source.write", "github", Scope.PROVIDER, frozenset({"PROVIDER_WRITE"}), requires_credentials=True),
    ])


def mission(**kw):
    d = dict(mission_id="m1", allowed_effects=frozenset({"READ_ONLY"}))
    d.update(kw)
    return MissionAuthority(**d)


def test_all_internal_admin_actions_authorized():
    a = FCOASuperAdmin(reg())
    for cap in ["alpha_omega.schedule", "formation.compose", "hypercube.harvest", "localllm.model.admin"]:
        for action in AdminAction:
            assert a.authorize(cap, action, mission(), requested_effect="FUSE_INTERNAL_ADMIN").state == "AUTHORIZED"


def test_future_fuse_capability_inherited_dynamically():
    r = reg(); a = FCOASuperAdmin(r)
    r.register(CapabilityRecord("future.quantum.router", "future-router", Scope.FUSE_OWNED, frozenset({"FUSE_INTERNAL_ADMIN"})))
    assert a.authorize("future.quantum.router", AdminAction.CONFIGURE, mission(), requested_effect="FUSE_INTERNAL_ADMIN").state == "AUTHORIZED"


def test_foreign_fence_cannot_be_overwritten():
    a = FCOASuperAdmin(reg())
    d = a.authorize("hypercube.harvest", AdminAction.DEPLOY, mission(), requested_effect="FUSE_INTERNAL_ADMIN",
                    lease=LeaseState("x", True, "OTHER", True))
    assert d.state == "JOIN_OR_WAIT"


def test_provider_requires_real_credential_and_authority():
    a = FCOASuperAdmin(reg())
    m = mission(allowed_effects=frozenset({"PROVIDER_WRITE"}))
    assert a.authorize("github.source.write", AdminAction.DEPLOY, m, requested_effect="PROVIDER_WRITE").state == "REBIND_REQUIRED"
    m2 = mission(allowed_effects=frozenset({"PROVIDER_WRITE"}), provider_credentials_bound=frozenset({"github"}))
    assert a.authorize("github.source.write", AdminAction.DEPLOY, m2, requested_effect="PROVIDER_WRITE").state == "AUTHORITY_REQUIRED"
    m3 = mission(allowed_effects=frozenset({"PROVIDER_WRITE"}), provider_credentials_bound=frozenset({"github"}),
                 provider_authorities=frozenset({"github"}))
    assert a.authorize("github.source.write", AdminAction.DEPLOY, m3, requested_effect="PROVIDER_WRITE").state == "AUTHORIZED"


def test_external_message_stays_gated():
    r = reg(); r.register(CapabilityRecord("fuse.messaging.bridge", "msg", Scope.FUSE_OWNED, frozenset({"EXTERNAL_MESSAGE"})))
    a = FCOASuperAdmin(r)
    assert a.authorize("fuse.messaging.bridge", AdminAction.ROUTE, mission(), requested_effect="EXTERNAL_MESSAGE").state == "BLOCKED_EFFECT_GATE"
    m = mission(allowed_effects=frozenset({"EXTERNAL_MESSAGE"}))
    assert a.authorize("fuse.messaging.bridge", AdminAction.ROUTE, m, requested_effect="EXTERNAL_MESSAGE").state == "AUTHORIZED"


def test_missing_capability_harvest_or_build():
    a = FCOASuperAdmin(reg())
    assert a.authorize("missing.capability", AdminAction.ROUTE, mission()).state == "HARVEST_OR_BUILD"


def test_stale_and_unhealthy_do_not_false_authorize():
    r = FCOAAdminRegistry([
        CapabilityRecord("stale", "x", Scope.FUSE_OWNED, current=False),
        CapabilityRecord("bad", "y", Scope.FUSE_OWNED, healthy=False)
    ])
    a = FCOASuperAdmin(r)
    assert a.authorize("stale", AdminAction.ROUTE, mission()).state == "REBIND_OR_REQUALIFY"
    assert a.authorize("bad", AdminAction.ROUTE, mission()).state == "REPAIR_OR_FAILOVER"


def test_same_mechanism_failure_changes_route():
    a = FCOASuperAdmin(reg())
    assert a.next_route(0) == "AUTO_ROUTE"
    assert a.next_route(2) == "CHANGED_MECHANISM_RECOMPILE"
