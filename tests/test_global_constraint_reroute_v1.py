from federation.global_constraint_reroute_v1 import *


def test_exact_active_task_limit_classified():
    assert GlobalConstraintRerouter().classify("You've reached your limit of 20 active tasks. To schedule more tasks, consider pausing some tasks.") == ConstraintKind.ACTIVE_TASK_LIMIT


def test_too_many_automations_classified():
    assert GlobalConstraintRerouter().classify("too_many_active_automations") == ConstraintKind.ACTIVE_TASK_LIMIT


def test_rate_limit_classified():
    assert GlobalConstraintRerouter().classify("HTTP 429 Too Many Requests") == ConstraintKind.RATE_LIMIT


def test_quota_classified():
    assert GlobalConstraintRerouter().classify("Quota exceeded for project") == ConstraintKind.QUOTA_EXHAUSTED


def test_reuses_equivalent_existing_work_before_new_route():
    d=GlobalConstraintRerouter().decide(ConstraintEvent("limit reached","automations","create","m1"), MissionNeeds(scheduled=True), (), equivalent_existing_route_id="task-12", equivalent_existing_route_family="AUTOMATION")
    assert d.state==RerouteState.REUSE_EXISTING and d.owner_action_required is False


def test_never_consolidates_without_semantic_equivalence():
    d=GlobalConstraintRerouter().decide(ConstraintEvent("limit reached","automations","create","m1"), MissionNeeds(scheduled=True), (), safe_equivalent_consolidation=False)
    assert d.state==RerouteState.DURABLE_QUEUE


def test_scheduled_work_not_diluted_to_foreground():
    routes=(RouteOption("fg","IMMEDIATE_FOREGROUND",supports_immediate=True), RouteOption("sched","FUSE_INTERNAL_SCHEDULER",supports_schedule=True,supports_recurring=True,supports_condition_watch=True,supports_immediate=False))
    d=GlobalConstraintRerouter().decide(ConstraintEvent("too many active tasks","automations","create","m1"),MissionNeeds(scheduled=True,recurring=True),routes)
    assert d.selected_route_id=="sched"


def test_condition_watch_requires_equivalent_route():
    routes=(RouteOption("win","LOCAL_WINDOWS_SCHEDULER",supports_schedule=True,supports_recurring=True), RouteOption("fuse","FUSE_INTERNAL_SCHEDULER",supports_schedule=True,supports_recurring=True,supports_condition_watch=True))
    d=GlobalConstraintRerouter().decide(ConstraintEvent("limit reached","automations","create","m1"),MissionNeeds(scheduled=True,recurring=True,condition_watch=True),routes)
    assert d.selected_route_id=="fuse"


def test_external_effect_requires_authorized_route():
    routes=(RouteOption("a","ALT",external_effect_authorized=False),RouteOption("b","ALT2",external_effect_authorized=True))
    d=GlobalConstraintRerouter().decide(ConstraintEvent("quota exceeded","x","y","m1"),MissionNeeds(external_effect_required=True),routes)
    assert d.selected_route_id=="b"


def test_second_same_failure_forces_changed_family():
    routes=(RouteOption("same","A"),RouteOption("new","B",proof_strength=.8))
    d=GlobalConstraintRerouter().decide(ConstraintEvent("rate limit","x","y","m1",prior_route_family="A",recurrence=2),MissionNeeds(),routes)
    assert d.selected_route_id=="new"


def test_preserves_of50_friction_and_cycle_contract():
    d=GlobalConstraintRerouter().decide(ConstraintEvent("limit reached","x","y","m1"),MissionNeeds(),())
    assert d.of50_friction_class==FrictionClass.RATE_OR_QUOTA_PRESSURE
    assert d.cycle_decision==CycleDecision.CHANGED_ROUTE_REQUIRED
    assert d.preserve_mission is True


def test_no_live_route_durable_queue_not_owner_task():
    d=GlobalConstraintRerouter().decide(ConstraintEvent("capacity full","x","y","m1"),MissionNeeds(),())
    assert d.state==RerouteState.DURABLE_QUEUE and d.owner_action_required is False


def test_stale_or_uncallable_routes_rejected():
    routes=(RouteOption("stale","A",current=False),RouteOption("off","B",callable_now=False))
    assert GlobalConstraintRerouter().decide(ConstraintEvent("limit reached","x","y","m1"),MissionNeeds(),routes).state==RerouteState.DURABLE_QUEUE


def test_unknown_message_does_not_fake_absence():
    d=GlobalConstraintRerouter().decide(ConstraintEvent("mysterious refusal","x","y","m1"),MissionNeeds(),())
    assert d.constraint_kind==ConstraintKind.UNKNOWN and d.state==RerouteState.DURABLE_QUEUE


def test_default_routes_include_internal_scheduler_and_local_runtime():
    ids={r.route_id for r in default_constraint_routes()}
    assert {"fuse-internal-scheduler","local-fuse-runtime"}.issubset(ids)
