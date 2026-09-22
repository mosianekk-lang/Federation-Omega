from datetime import datetime, timezone, timedelta
import pytest
from federation.durable_scheduler_bus_v1 import *
from scheduler.github_issue_bus import parse_mission, make_issue_body

def mission(**kwargs):
    values = dict(
        mission_id="m1", idempotency_key="idem1", task_type="NO_EFFECT_CANARY",
        objective="prove no-effect durable scheduling",
    )
    values.update(kwargs)
    return DurableMission(**values)

def test_immediate_due():
    assert due(mission(), now=datetime.now(timezone.utc))

def test_once_future_not_due():
    timestamp = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert not due(mission(schedule_kind=ScheduleKind.ONCE, not_before=timestamp), now=datetime.now(timezone.utc))

def test_once_past_due():
    timestamp = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert due(mission(schedule_kind=ScheduleKind.ONCE, not_before=timestamp), now=datetime.now(timezone.utc))

def test_interval_floor():
    with pytest.raises(ValueError, match="MINIMUM_ONE_HOUR"):
        mission(schedule_kind=ScheduleKind.INTERVAL, not_before=datetime.now(timezone.utc).isoformat(), interval_seconds=60).validate()

def test_handler_canary_no_effect():
    result = default_handlers().run(mission())
    assert result["status"] == "PASS" and result["effects"] == "NONE"

def test_unknown_handler_rejected():
    with pytest.raises(KeyError):
        default_handlers().run(mission(task_type="NOPE"))

def test_changed_route_after_second_failure():
    assert next_route_family("A", 2, ("A", "B")) == "B"

def test_first_failure_may_use_first_route():
    assert next_route_family("A", 1, ("A", "B")) == "A"

def test_no_routes_durable_queue():
    assert next_route_family("A", 2, ()) == "DURABLE_QUEUE"

def test_issue_roundtrip():
    item = mission(
        schedule_kind=ScheduleKind.CONDITION_WATCH,
        not_before=datetime.now(timezone.utc).isoformat(),
        payload={"x": 1},
    )
    decoded = parse_mission(make_issue_body(item))
    assert decoded.mission_id == item.mission_id and decoded.payload["x"] == 1

def test_issue_requires_schema():
    with pytest.raises(ValueError):
        parse_mission("nothing")

def test_digest_stable():
    assert mission().digest == mission().digest

def test_effect_class_preserved():
    item = mission(effect_class="EXTERNAL_WRITE")
    assert parse_mission(make_issue_body(item)).effect_class == "EXTERNAL_WRITE"

def test_condition_watch_due_after_not_before():
    timestamp = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert due(
        mission(schedule_kind=ScheduleKind.CONDITION_WATCH, not_before=timestamp),
        now=datetime.now(timezone.utc),
    )

def test_required_identity():
    with pytest.raises(ValueError):
        mission(mission_id="").validate()
