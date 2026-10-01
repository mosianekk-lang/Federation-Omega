"""Real SQLite/process courts for atomic owner-scoped mission admission."""
from __future__ import annotations

import multiprocessing
from pathlib import Path
import sqlite3

import pytest

from services.sol62_client_runtime.sovereign_meta_intelligence import SovereignMetaIntelligence
from sol_61_runtime.sol_62 import GatewayPolicy, MissionSpec, Sol62Runtime, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_complete_client_runtime import Sol62CompleteClientRuntime
from sol_61_runtime.sol_62_frontier_primitives import ConstraintError


def _runtime(root):
    runtime = Sol62Runtime(
        root,
        gateway_policy=GatewayPolicy("test-gateway", "test-runtime"),
        identity_policy=WorkloadIdentityPolicy(allowed_issuers={"test"}, audience="test", subject_prefix="test:"),
    )
    return runtime, Sol62CompleteClientRuntime(runtime)


def _spec(objective="Atomic owner-scoped mission"):
    return MissionSpec("contended-mission", objective, {"state": "OPEN"}, {"state": "DONE"})


def _intent(spec, owner):
    return SovereignMetaIntelligence().build_owner_intent(
        owner_subject=owner, mission_id=spec.mission_id, objective=spec.objective,
        terminal_predicates={"target_state": dict(spec.target_state), "success_proofs": list(spec.success_proofs)},
        constraints=spec.constraints,
    )


def _snapshot(runtime):
    return {
        "state": [tuple(row) for row in runtime.control.db.execute("SELECT * FROM state ORDER BY namespace,item_key")],
        "events": [tuple(row) for row in runtime.control.db.execute("SELECT * FROM events ORDER BY seq")],
    }


def _contender(root, owner, start, result):
    runtime, client = _runtime(root)
    try:
        spec = _spec()
        start.wait(timeout=15)
        try:
            response = client.create_owned_mission(spec, owner_subject=owner, owner_intent=_intent(spec, owner))
            result.put(("OK", owner, response["client"]["owner_subject"]))
        except ConstraintError as error:
            result.put((str(error), owner, None))
    finally:
        runtime.close()


def _uncommitted_writer(root, ready, release, result):
    runtime, client = _runtime(root)
    try:
        with runtime.control.tx():
            spec = _spec()
            client.create_owned_mission(spec, owner_subject="test:writer", owner_intent=_intent(spec, "test:writer"))
            ready.set()
            if not release.wait(timeout=15):
                raise TimeoutError("reader never released the writer")
        result.put("COMMITTED")
    except BaseException as error:
        result.put(type(error).__name__)
        raise
    finally:
        runtime.close()


@pytest.fixture
def local(tmp_path):
    runtime, client = _runtime(tmp_path / "sol")
    try:
        yield runtime, client
    finally:
        runtime.close()


@pytest.mark.parametrize("owners", [("test:alice", "test:bob"), ("test:alice", "test:alice")])
def test_real_processes_admit_exactly_one_ownership_and_one_event_set(tmp_path, owners):
    root = tmp_path / "shared"
    initial, _ = _runtime(root)
    initial.close()
    context = multiprocessing.get_context("spawn")
    start = context.Barrier(2)
    results = context.Queue()
    processes = [context.Process(target=_contender, args=(str(root), owner, start, results)) for owner in owners]
    try:
        for process in processes:
            process.start()
        received = [results.get(timeout=25) for _ in processes]
        for process in processes:
            process.join(timeout=15)
            assert process.exitcode == 0
        runtime, _ = _runtime(root)
        try:
            bound = runtime.control.get_state("sol62.client.mission", _spec().mission_id)
            winner = bound["value"]["owner_subject"]
            if len(set(owners)) == 2:
                assert sorted(row[0] for row in received) == ["MISSION_ID_UNAVAILABLE", "OK"]
                assert [row[1] for row in received if row[0] == "OK"] == [winner]
            else:
                assert [row[0] for row in received] == ["OK", "OK"]
            assert runtime.control.get_state("sol62.owner.intent", _spec().mission_id)["value"]["owner_subject"] == winner
            events = runtime.control.db.execute("SELECT kind,COUNT(*) AS n FROM events WHERE aggregate=? GROUP BY kind", (_spec().mission_id,)).fetchall()
            assert {row["kind"]: row["n"] for row in events} == {
                "SOL62_MISSION_REGISTERED": 1,
                "SOL62_CLIENT_MISSION_BOUND": 1,
                "SOL62_SOVEREIGN_MISSION_ATTACHED": 1,
                "SOL62_INTELLIGENCE_PLAN_REFRESHED": 1,
                "SOL62_DURABILITY_POLICY_BOUND": 1,
                "SOL62_OWNER_INTENT_BOUND": 1,
            }
            assert runtime.control.verify_event_chain()
            assert bound["version"] == 1
        finally:
            runtime.close()
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
        results.close()


@pytest.mark.parametrize("kind", [
    "SOL62_MISSION_REGISTERED", "SOL62_CLIENT_MISSION_BOUND", "SOL62_INTELLIGENCE_PLAN_REFRESHED",
    "SOL62_DURABILITY_POLICY_BOUND", "SOL62_OWNER_INTENT_BOUND",
])
def test_failure_after_each_written_stage_rolls_back_all_rows_and_events(local, monkeypatch, kind):
    runtime, client = local
    before = _snapshot(runtime)
    original = runtime.control.append_event
    def fail_after_event(aggregate, event_kind, payload):
        result = original(aggregate, event_kind, payload)
        if event_kind == kind:
            raise RuntimeError("injected after persisted stage")
        return result
    monkeypatch.setattr(runtime.control, "append_event", fail_after_event)
    spec = _spec()
    with pytest.raises(RuntimeError, match="injected"):
        client.create_owned_mission(spec, owner_subject="test:owner", owner_intent=_intent(spec, "test:owner"))
    assert _snapshot(runtime) == before
    assert not runtime.control.db.in_transaction
    assert runtime.control._tx_depth == 0
    assert runtime.control.verify_event_chain()
    # Failed admission must not poison subsequent healthy registration.
    monkeypatch.setattr(runtime.control, "append_event", original)
    response = client.create_owned_mission(spec, owner_subject="test:owner", owner_intent=_intent(spec, "test:owner"))
    assert response["client"]["owner_subject"] == "test:owner"


def test_another_process_reader_cannot_observe_partial_admission(tmp_path):
    root = tmp_path / "shared"
    reader, _ = _runtime(root)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    result = context.Queue()
    process = context.Process(target=_uncommitted_writer, args=(str(root), ready, release, result))
    before = _snapshot(reader)
    try:
        process.start()
        assert ready.wait(timeout=15)
        assert _snapshot(reader) == before
        release.set()
        assert result.get(timeout=15) == "COMMITTED"
        process.join(timeout=10)
        assert process.exitcode == 0
        assert reader.control.get_state("sol62.owner.intent", _spec().mission_id)["value"]["owner_subject"] == "test:writer"
        assert len(_snapshot(reader)["events"]) == 6
        assert reader.control.verify_event_chain()
    finally:
        release.set()
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        reader.close()
        result.close()


def test_same_owner_retry_does_not_reset_state_attempts_versions_or_events(local):
    runtime, client = local
    spec = _spec()
    client.create_owned_mission(spec, owner_subject="test:owner", owner_intent=_intent(spec, "test:owner"))
    current = client._get("sol62.client.mission", spec.mission_id)["value"]
    client._put("sol62.client.mission", spec.mission_id, {**current, "state": "WAITING_ROUTE", "total_attempts": 3})
    before = _snapshot(runtime)
    response = client.create_owned_mission(spec, owner_subject="test:owner", owner_intent=_intent(spec, "test:owner"))
    assert response["client"]["state"] == "WAITING_ROUTE"
    assert response["client"]["total_attempts"] == 3
    assert _snapshot(runtime) == before
    client.bind_mission(spec.mission_id, owner_subject="test:owner")
    assert _snapshot(runtime) == before


def test_conflicting_definition_and_direct_foreign_binding_are_denied_without_writes(local):
    runtime, client = local
    spec = _spec()
    client.create_owned_mission(spec, owner_subject="test:owner", owner_intent=_intent(spec, "test:owner"))
    before = _snapshot(runtime)
    changed = _spec("Changed objective")
    with pytest.raises(ConstraintError, match="MISSION_ID_CONFLICT"):
        client.create_owned_mission(changed, owner_subject="test:owner", owner_intent=_intent(changed, "test:owner"))
    with pytest.raises(ConstraintError, match="MISSION_ID_UNAVAILABLE"):
        client.bind_mission(spec.mission_id, owner_subject="test:intruder")
    assert _snapshot(runtime) == before


def test_orphan_state_is_not_adopted_or_erased(local):
    runtime, client = local
    runtime.control.cas_put("sol62.owner.intent", _spec().mission_id, {"owner_subject": "test:legacy"}, expected_version=0)
    before = _snapshot(runtime)
    with pytest.raises(ConstraintError, match="MISSION_ID_UNAVAILABLE"):
        client.create_owned_mission(_spec(), owner_subject="test:owner", owner_intent=_intent(_spec(), "test:owner"))
    assert _snapshot(runtime) == before


def test_intent_cannot_disagree_with_authenticated_owner(local):
    runtime, client = local
    before = _snapshot(runtime)
    with pytest.raises(ConstraintError, match="MISSION_OWNER_INTENT_MISMATCH"):
        client.create_owned_mission(_spec(), owner_subject="test:owner", owner_intent=_intent(_spec(), "test:other"))
    assert _snapshot(runtime) == before


def test_caught_nested_failure_rolls_back_only_savepoint_and_outer_commit_remains_valid(local):
    runtime, _ = local
    control = runtime.control
    with control.tx():
        control.cas_put("test", "outer", {"value": 1}, expected_version=0)
        with pytest.raises(RuntimeError):
            with control.tx():
                control.cas_put("test", "inner", {"value": 2}, expected_version=0)
                control.append_event("test", "INNER", {})
                raise RuntimeError("rollback savepoint")
        control.append_event("test", "OUTER", {})
    assert control.get_state("test", "outer") is not None
    assert control.get_state("test", "inner") is None
    assert [row[0] for row in control.db.execute("SELECT kind FROM events")] == ["OUTER"]
    assert control.verify_event_chain()
    assert control._tx_depth == 0


def test_baseexception_rolls_back_outer_admission_and_thread_guard_remains_default(local):
    runtime, client = local
    class Interrupted(BaseException):
        pass
    with pytest.raises(Interrupted):
        with runtime.control.tx():
            client.create_owned_mission(_spec(), owner_subject="test:owner", owner_intent=_intent(_spec(), "test:owner"))
            raise Interrupted()
    assert _snapshot(runtime) == {"state": [], "events": []}
    assert runtime.control._tx_depth == 0
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(sqlite3.ProgrammingError, match="same thread"):
            pool.submit(runtime.control.get_state, "sol62.mission", _spec().mission_id).result()


def test_process_exit_before_outer_commit_leaves_no_admission_and_allows_recovery(tmp_path):
    root = tmp_path / "shared-crash"
    reader, client = _runtime(root)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    result = context.Queue()
    process = context.Process(target=_uncommitted_writer, args=(str(root), ready, release, result))
    before = _snapshot(reader)
    try:
        process.start()
        assert ready.wait(timeout=15)
        process.terminate()
        process.join(timeout=10)
        assert process.exitcode != 0
        assert _snapshot(reader) == before
        spec = _spec()
        response = client.create_owned_mission(spec, owner_subject="test:recovery", owner_intent=_intent(spec, "test:recovery"))
        assert response["client"]["owner_subject"] == "test:recovery"
        assert reader.control.verify_event_chain()
        assert len(_snapshot(reader)["events"]) == 6
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        reader.close()
        result.close()
