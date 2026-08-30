from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest

from omega_one.interop import EffectClass
from omega_one.work_engine import (
    LeaseReceipt,
    MissionEnvelope,
    OmegaCompletionEngine,
    ProofBundle,
    TaskEnvelope,
    TaskState,
    WorkerDescriptor,
    output_digest,
)


def mission(version=1, mission_id="M1"):
    return MissionEnvelope(mission_id, version, "Complete verified work", ("all fruit proven",))


def task(task_id, *, deps=(), tenant="alpha", authority="A0", privacy="P1", effect=EffectClass.READ, idem=None, max_attempts=3):
    return TaskEnvelope(
        task_id=task_id,
        mission_id="M1",
        dependencies=tuple(deps),
        capability="reason",
        input_digest=f"input-{task_id}",
        tenant_id=tenant,
        authority=authority,
        privacy=privacy,
        effect_class=effect,
        idempotency_key=idem,
        max_attempts=max_attempts,
    )


def worker(worker_id="W1", **kwargs):
    values = dict(worker_id=worker_id, capabilities=("reason",), authority_grants=("A0", "A1", "A2"), privacy_ceiling="P2", capacity=4)
    values.update(kwargs)
    return WorkerDescriptor(**values)


def proof(output, verifier="V1", **kwargs):
    values = dict(
        verifier_id=verifier,
        output_digest=output_digest(output),
        schema_valid=True,
        semantic_valid=True,
        policy_valid=True,
        readback_valid=True,
        evidence_refs=("urn:test:readback",),
    )
    values.update(kwargs)
    return ProofBundle(**values)


class WorkEngineTests(unittest.TestCase):
    def engine(self, directory):
        return OmegaCompletionEngine(Path(directory) / "state")

    def test_graph_rejects_cycles_and_dangling_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            with self.assertRaisesRegex(ValueError, "CYCLIC_DAG"):
                engine.submit_mission(mission(), (task("A", deps=("B",)), task("B", deps=("A",))))
            with self.assertRaisesRegex(ValueError, "DANGLING_DEPENDENCY"):
                engine.submit_mission(mission(), (task("A", deps=("missing",)),))

    def test_hard_policy_match_precedes_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker("cheap", authority_grants=("A0",), unit_cost=0))
            engine.register_worker(worker("costly", authority_grants=("A0", "A2"), unit_cost=1))
            engine.submit_mission(mission(), (task("A", authority="A2"),))
            self.assertIsNone(engine.schedule_next())

    def test_load_aware_worker_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker("slow", capacity=1, predicted_latency_ms=10000))
            engine.register_worker(worker("fast", capacity=1, predicted_latency_ms=10))
            engine.submit_mission(mission(), (task("A"),))
            self.assertEqual(engine.schedule_next().worker_id, "fast")

    def test_dag_join_and_independent_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            engine.submit_mission(mission(), (task("A"), task("B", deps=("A",))))
            lease_a = engine.schedule_next()
            self.assertIsNotNone(lease_a)
            with self.assertRaisesRegex(ValueError, "SELF_VERIFICATION"):
                engine.submit_candidate(lease_a, {"fruit": "A"}, proof({"fruit": "A"}, verifier="W1"))
            engine.submit_candidate(lease_a, {"fruit": "A"}, proof({"fruit": "A"}))
            lease_b = engine.schedule_next()
            self.assertTrue(lease_b.task_key.endswith(":B"))
            engine.submit_candidate(lease_b, {"fruit": "B"}, proof({"fruit": "B"}))
            status = engine.mission_status("M1")
            self.assertEqual(status["state"], "PROVEN")
            self.assertTrue(status["terminal"])
            self.assertTrue(engine.verify_integrity())

    def test_failed_proof_does_not_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            engine.submit_mission(mission(), (task("A"),))
            lease = engine.schedule_next()
            with self.assertRaisesRegex(ValueError, "INDEPENDENT_PROOF_FAILED"):
                engine.submit_candidate(lease, "wrong", proof("wrong", semantic_valid=False))
            self.assertEqual(engine.mission_status("M1")["tasks"][lease.task_key], TaskState.RUNNING.value)

    def test_proof_publication_replays_exactly_once_after_crash_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            armed = {"value": True}

            def fault(point):
                if armed["value"] and point == "after_proof_publication":
                    armed["value"] = False
                    raise RuntimeError("INJECTED_PROOF_PUBLICATION_CRASH")

            root = Path(directory) / "state"
            engine = OmegaCompletionEngine(root, fault_injector=fault)
            engine.register_worker(worker())
            engine.submit_mission(mission(), (task("A"),))
            lease = engine.schedule_next()
            with self.assertRaisesRegex(RuntimeError, "INJECTED_PROOF_PUBLICATION_CRASH"):
                engine.submit_candidate(lease, {"fruit": "A"}, proof({"fruit": "A"}))

            recovered = OmegaCompletionEngine(root)
            self.assertEqual(recovered.mission_status("M1")["state"], "PROVEN")
            events = recovered.sol._events()
            result_events = [
                row for row in events
                if row["event_type"] == "RECEIPT_RECORDED"
                and row["payload"]["workstream_id"] == lease.task_key
                and row["payload"]["receipt_type"] == "RESULT"
            ]
            proof_events = [
                row for row in events
                if row["event_type"] == "RECEIPT_RECORDED"
                and row["payload"]["workstream_id"] == lease.task_key
                and row["payload"]["receipt_type"] == "INDEPENDENT_PROOF"
            ]
            evaluation_events = [
                row for row in events
                if row["event_type"] == "COMPLETION_EVALUATED"
                and row["payload"]["workstream_id"] == lease.task_key
            ]
            reliability_events = [
                row for row in events
                if row["event_type"] == "RELIABILITY_UPDATED"
                and row["payload"].get("omega_publication_id") == f"proof-finalize:{lease.task_key}"
            ]
            self.assertEqual(len(result_events), 1)
            self.assertEqual(len(proof_events), 1)
            self.assertEqual(len(evaluation_events), 1)
            self.assertEqual(len(reliability_events), 1)
            self.assertEqual(recovered.persistence_status()["pending_transition_outbox"], 0)
            self.assertTrue(recovered.verify_integrity())

    def test_sol_receipt_publication_id_rejects_changed_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.submit_mission(mission(), (task("A"),))
            publication_id = "proof-finalize:M1:v1:A"
            first = engine._record_sol_receipt_once(
                workstream_id="M1:v1:A",
                receipt_type="RESULT",
                body={"output_digest": "first"},
                publication_id=publication_id,
            )
            same = engine._record_sol_receipt_once(
                workstream_id="M1:v1:A",
                receipt_type="RESULT",
                body={"output_digest": "first"},
                publication_id=publication_id,
            )
            self.assertEqual(first, same)
            with self.assertRaisesRegex(RuntimeError, "SOL_RECEIPT_IDEMPOTENCY_CONFLICT"):
                engine._record_sol_receipt_once(
                    workstream_id="M1:v1:A",
                    receipt_type="RESULT",
                    body={"output_digest": "changed"},
                    publication_id=publication_id,
                )
            raw = [
                row for row in engine.sol._events()
                if row["event_type"] == "RECEIPT_RECORDED"
                and row["payload"]["body"].get("omega_publication_id") == publication_id
            ]
            self.assertEqual(len(raw), 1)

    def test_bounded_retry_reaches_dead_letter(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            engine.submit_mission(mission(), (task("A", max_attempts=2),))
            first = engine.schedule_next()
            self.assertEqual(engine.fail_task(first, "TRANSIENT", "one"), TaskState.RETRY_WAIT.value)
            second = engine.schedule_next()
            self.assertEqual(engine.fail_task(second, "TRANSIENT", "two"), TaskState.DEAD_LETTER.value)

    def test_supersession_rejects_stale_result(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            engine.submit_mission(mission(), (task("A"),))
            stale = engine.schedule_next()
            engine.submit_mission(mission(version=2), (replace(task("A"), mission_id="M1"),))
            with self.assertRaisesRegex(ValueError, "STALE"):
                engine.submit_candidate(stale, "late", proof("late"))

    def test_cancellation_revokes_lease_and_late_result(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            engine.submit_mission(mission(), (task("A"), task("B", deps=("A",))))
            lease = engine.schedule_next()
            status = engine.cancel_mission("M1")
            self.assertEqual(status["state"], "CANCELLED")
            self.assertEqual(engine.state["workers"]["W1"]["running"], 0)
            with self.assertRaisesRegex(ValueError, "STALE"):
                engine.submit_candidate(lease, "late", proof("late"))

    def test_effect_permit_is_bound_single_use_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            effect_task = task("A", authority="A2", effect=EffectClass.WRITE, idem="idem-A")
            engine.submit_mission(mission(), (effect_task,))
            lease = engine.schedule_next()
            payload = {"operation": "local-simulation"}
            action = output_digest(payload)
            with self.assertRaisesRegex(PermissionError, "OWNER_AUTHORITY_REQUIRED"):
                engine.issue_effect_permit(lease, action)
            permit = engine.issue_effect_permit(lease, action, owner_authorized=True)
            receipt = engine.record_simulated_effect(lease, permit["permit_id"], payload)
            self.assertFalse(receipt["external_effect"])
            # Same logical effect returns its original receipt and never duplicates fruit.
            self.assertEqual(engine.record_simulated_effect(lease, permit["permit_id"], payload), receipt)
            engine.submit_candidate(lease, "done", proof("done"), effect_receipt=receipt)
            self.assertEqual(engine.mission_status("M1")["state"], "PROVEN")

    def test_duplicate_idempotency_key_rejects_mission_before_any_plane_mutates(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            event_count = len(engine.state["events"])
            tasks = (
                task("A", authority="A2", effect=EffectClass.WRITE, idem="shared-key"),
                task("B", authority="A2", effect=EffectClass.WRITE, idem="shared-key"),
            )
            with self.assertRaisesRegex(ValueError, "DUPLICATE_IDEMPOTENCY_KEY"):
                engine.submit_mission(mission(), tasks)
            self.assertNotIn("M1", engine.state["missions"])
            self.assertEqual(engine.state["tasks"], {})
            self.assertEqual(engine.worker_plane.state.jobs, {})
            self.assertEqual(engine.worker_plane.state.idempotency, {})
            self.assertEqual(len(engine.state["events"]), event_count)
            self.assertTrue(engine.verify_integrity())

    def test_existing_idempotency_key_conflict_rejects_second_mission(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            first = task("A", authority="A2", effect=EffectClass.WRITE, idem="shared-key")
            engine.submit_mission(mission(), (first,))
            event_count = len(engine.state["events"])
            job_keys = set(engine.worker_plane.state.jobs)
            second = replace(
                task("B", authority="A2", effect=EffectClass.WRITE, idem="shared-key"),
                mission_id="M2",
            )
            with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
                engine.submit_mission(mission(mission_id="M2"), (second,))
            self.assertNotIn("M2", engine.state["missions"])
            self.assertFalse(any(row["spec"]["mission_id"] == "M2" for row in engine.state["tasks"].values()))
            self.assertEqual(set(engine.worker_plane.state.jobs), job_keys)
            self.assertEqual(len(engine.state["events"]), event_count)
            self.assertTrue(engine.verify_integrity())

    def test_integrity_reconciles_control_and_worker_planes(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            engine.submit_mission(mission(), (task("A"),))
            self.assertTrue(engine.verify_integrity())
            key = next(iter(engine.state["tasks"]))
            del engine.worker_plane.state.jobs[key]
            self.assertFalse(engine.verify_integrity())

    def test_weighted_fair_flow_prevents_starvation(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker(capacity=6))
            tasks = (
                replace(task("A1", tenant="alpha"), flow_weight=1),
                replace(task("A2", tenant="alpha"), flow_weight=1),
                replace(task("B1", tenant="beta"), flow_weight=1),
                replace(task("B2", tenant="beta"), flow_weight=1),
            )
            engine.submit_mission(mission(), tasks)
            first = engine.schedule_next()
            second = engine.schedule_next()
            tenants = {engine.state["tasks"][item.task_key]["spec"]["tenant_id"] for item in (first, second)}
            self.assertEqual(tenants, {"alpha", "beta"})

    def test_state_recovers_from_disk_with_valid_chains(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.engine(directory)
            first.register_worker(worker())
            first.submit_mission(mission(), (task("A"),))
            lease = first.schedule_next()
            first.submit_candidate(lease, "fruit", proof("fruit"))
            second = self.engine(directory)
            self.assertEqual(second.mission_status("M1")["state"], "PROVEN")
            self.assertTrue(second.verify_integrity())

    def test_incremental_sqlite_backend_is_default_and_observable(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker())
            status = engine.persistence_status()
            self.assertEqual(status["backend"], "SQLITE_WAL_INCREMENTAL")
            self.assertEqual(status["journal_mode"], "WAL")
            self.assertEqual(status["schema_version"], 2)
            self.assertGreaterEqual(status["revision"], 1)
            self.assertEqual(status["pending_outbox"], 0)
            self.assertFalse(status["legacy_snapshot_present"])
            self.assertTrue(engine.control_file.exists())
            self.assertEqual(engine.control_file.suffix, ".sqlite3")
            self.assertEqual(status["last_commit"]["rows_upserted"], 1)

    def test_empty_schedule_probe_does_not_advance_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker(capacity=1))
            engine.submit_mission(mission(), (task("A"), task("B", deps=("A",))))
            engine.schedule_next()
            before = engine.persistence_status()["revision"]
            self.assertIsNone(engine.schedule_next())
            self.assertEqual(engine.persistence_status()["revision"], before)

    def test_concurrency_plan_tracks_topology_and_spare_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker(capacity=4))
            engine.submit_mission(mission(), (task("A"), task("B"), task("C", deps=("A", "B"))))
            plan = engine.concurrency_plan(max_concurrency=8)
            self.assertEqual(plan.mode, "PARALLEL_FRONTIER")
            self.assertEqual(plan.target_parallelism, 2)
            leases = engine.schedule_wave(max_concurrency=8)
            self.assertEqual(len(leases), 2)
            plan = engine.concurrency_plan(max_concurrency=8)
            self.assertEqual(plan.target_parallelism, 0)

    def test_schedule_wave_coalesces_control_revision_and_preserves_fairness(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker(capacity=6))
            tasks = (
                replace(task("A1", tenant="alpha"), flow_weight=1),
                replace(task("A2", tenant="alpha"), flow_weight=1),
                replace(task("B1", tenant="beta"), flow_weight=1),
                replace(task("B2", tenant="beta"), flow_weight=1),
            )
            engine.submit_mission(mission(), tasks)
            before = engine.persistence_status()["revision"]
            leases = engine.schedule_wave(max_concurrency=4)
            after = engine.persistence_status()["revision"]
            self.assertEqual(len(leases), 4)
            self.assertEqual(after - before, 1)
            self.assertEqual(engine.persistence_status()["pending_transition_outbox"], 0)
            first_two = [engine.state["tasks"][item.task_key]["spec"]["tenant_id"] for item in leases[:2]]
            self.assertEqual(set(first_two), {"alpha", "beta"})
            self.assertTrue(engine.verify_integrity())

    def test_schedule_wave_serializes_effectful_frontier(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.register_worker(worker(capacity=4))
            tasks = (
                task("W1", authority="A2", effect=EffectClass.WRITE, idem="wave-effect-1"),
                task("W2", authority="A2", effect=EffectClass.WRITE, idem="wave-effect-2"),
            )
            engine.submit_mission(mission(), tasks)
            leases = engine.schedule_wave(max_concurrency=4)
            effect_leases = [
                item for item in leases
                if engine.state["tasks"][item.task_key]["spec"]["effect_class"] != EffectClass.READ.value
            ]
            self.assertEqual(len(effect_leases), 1)
            self.assertEqual(len(leases), 1)
            self.assertEqual(engine.concurrency_plan(max_concurrency=4).effect_slots, 0)

    def test_committed_dispatch_wave_recovers_after_injected_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"

            def crash(point):
                if point == "after_dispatch_wave_commit":
                    raise RuntimeError("INJECTED_DISPATCH_CRASH")

            first = OmegaCompletionEngine(state_dir, fault_injector=crash)
            first.register_worker(worker(capacity=4))
            first.submit_mission(mission(), (task("A"), task("B")))
            with self.assertRaisesRegex(RuntimeError, "INJECTED_DISPATCH_CRASH"):
                first.schedule_wave(max_concurrency=2)
            self.assertEqual(first.persistence_status()["pending_transition_outbox"], 1)
            self.assertTrue(all(job["status"] == "QUEUED" for job in first.worker_plane.state.jobs.values()))

            recovered = OmegaCompletionEngine(state_dir)
            self.assertEqual(recovered.persistence_status()["pending_transition_outbox"], 0)
            self.assertTrue(all(job["status"] == "LEASED" for job in recovered.worker_plane.state.jobs.values()))
            self.assertTrue(recovered.verify_integrity())

    def test_partial_dispatch_materialization_replays_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            engine = OmegaCompletionEngine(state_dir)
            engine.register_worker(worker(capacity=4))
            engine.submit_mission(mission(), (task("A"), task("B"), task("C")))
            original_lease = engine.worker_plane.lease
            calls = 0

            def fail_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("INJECTED_PARTIAL_MATERIALIZATION")
                return original_lease(*args, **kwargs)

            engine.worker_plane.lease = fail_second
            with self.assertRaisesRegex(RuntimeError, "INJECTED_PARTIAL_MATERIALIZATION"):
                engine.schedule_wave(max_concurrency=3)
            self.assertEqual(engine.persistence_status()["pending_transition_outbox"], 1)
            self.assertEqual(sum(job["status"] == "LEASED" for job in engine.worker_plane.state.jobs.values()), 1)

            recovered = OmegaCompletionEngine(state_dir)
            self.assertEqual(recovered.persistence_status()["pending_transition_outbox"], 0)
            self.assertTrue(all(job["status"] == "LEASED" for job in recovered.worker_plane.state.jobs.values()))
            self.assertTrue(recovered.verify_integrity())

    def test_cross_instance_dispatch_wave_has_one_committer_and_no_duplicate_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            first = OmegaCompletionEngine(state_dir)
            first.register_worker(worker(capacity=4))
            first.submit_mission(mission(), (task("A"), task("B")))
            second = OmegaCompletionEngine(state_dir)
            barrier = threading.Barrier(2)
            outcomes = []
            outcomes_lock = threading.Lock()

            def dispatch(engine):
                barrier.wait()
                try:
                    outcome = ("COMMITTED", len(engine.schedule_wave(max_concurrency=2)))
                except Exception as exc:
                    outcome = (type(exc).__name__, 0)
                with outcomes_lock:
                    outcomes.append(outcome)

            threads = [threading.Thread(target=dispatch, args=(item,)) for item in (first, second)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sum(item[0] == "COMMITTED" and item[1] == 2 for item in outcomes), 1)
            recovered = OmegaCompletionEngine(state_dir)
            self.assertEqual(recovered.persistence_status()["pending_outbox"], 0)
            self.assertEqual(sum(job["status"] == "LEASED" for job in recovered.worker_plane.state.jobs.values()), 2)
            self.assertTrue(recovered.verify_integrity())

    def test_committed_admission_recovers_after_injected_crash_before_materialization(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"

            def crash(point):
                if point == "after_admission_commit":
                    raise RuntimeError("INJECTED_PROCESS_CRASH")

            first = OmegaCompletionEngine(state_dir, fault_injector=crash)
            first.register_worker(worker())
            with self.assertRaisesRegex(RuntimeError, "INJECTED_PROCESS_CRASH"):
                first.submit_mission(mission(), (task("A"),))
            self.assertEqual(first.persistence_status()["pending_outbox"], 1)
            self.assertEqual(first.worker_plane.state.jobs, {})
            self.assertFalse(first.verify_integrity())

            recovered = OmegaCompletionEngine(state_dir)
            self.assertEqual(recovered.persistence_status()["pending_outbox"], 0)
            self.assertIn("M1:v1:A", recovered.worker_plane.state.jobs)
            self.assertEqual(recovered.mission_status("M1")["tasks"]["M1:v1:A"], "READY")
            self.assertTrue(recovered.verify_integrity())

    def test_cross_instance_contention_admits_exactly_one_shared_idempotency_key(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            first = OmegaCompletionEngine(state_dir)
            first.register_worker(worker())
            second = OmegaCompletionEngine(state_dir)
            barrier = threading.Barrier(2)
            outcomes = []
            outcomes_lock = threading.Lock()

            def submit(engine, mission_id, task_id):
                candidate = replace(
                    task(task_id, authority="A2", effect=EffectClass.WRITE, idem="shared-cross-instance"),
                    mission_id=mission_id,
                )
                barrier.wait()
                try:
                    engine.submit_mission(mission(mission_id=mission_id), (candidate,))
                    outcome = "ADMITTED"
                except ValueError as exc:
                    outcome = str(exc)
                with outcomes_lock:
                    outcomes.append(outcome)

            threads = [
                threading.Thread(target=submit, args=(first, "M1", "A")),
                threading.Thread(target=submit, args=(second, "M2", "B")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(outcomes.count("ADMITTED"), 1)
            self.assertEqual(outcomes.count("IDEMPOTENCY_KEY_CONFLICT"), 1)

            readback = OmegaCompletionEngine(state_dir)
            self.assertEqual(len(readback.state["missions"]), 1)
            self.assertEqual(len(readback.state["tasks"]), 1)
            self.assertEqual(len(readback.worker_plane.state.jobs), 1)
            self.assertEqual(readback.worker_plane.state.idempotency["shared-cross-instance"], next(iter(readback.state["tasks"])))
            self.assertTrue(readback.verify_integrity())

    def test_legacy_json_migrates_once_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "state"
            state_dir.mkdir(parents=True)
            legacy = OmegaCompletionEngine._blank()
            row = {"type": "LEGACY_CHECKPOINT", "body": {"version": 1}, "at": "2026-08-30T00:00:00Z", "previous": "GENESIS"}
            row["hash"] = output_digest(row)
            legacy["events"].append(row)
            legacy["dispatch_counts"]["alpha"] = 4
            source = state_dir / "control-state.json"
            source.write_text(json.dumps(legacy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            original = source.read_bytes()

            engine = OmegaCompletionEngine(state_dir)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(engine.state["dispatch_counts"], {"alpha": 4})
            self.assertEqual(len(engine.persistence_status()["migrations"]), 1)
            self.assertTrue(engine.persistence_status()["legacy_snapshot_present"])
            self.assertTrue(engine.verify_integrity())

            reopened = OmegaCompletionEngine(state_dir)
            self.assertEqual(len(reopened.persistence_status()["migrations"]), 1)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
