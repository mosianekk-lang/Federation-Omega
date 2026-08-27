from pathlib import Path
import tempfile
import unittest

from formation_omega.mission_convergence import (
    ClosureLock,
    ConvergenceLedger,
    FailureResolver,
    FailureStatus,
    IdeaDisposition,
    IdeaPriority,
    MissionConvergenceEngine,
    MissionSpec,
    ProofEntry,
    ProofStatus,
    WorkItem,
    WorkStatus,
)


def mission(required_axes=("design", "source", "rollback")):
    return MissionSpec.create(
        mission_id="MISSION-MCE-TEST-001",
        objective="Converge one mission to independently verified closure",
        success_criteria=("Source admitted", "Runtime canary verified"),
        authority_ceiling="A2",
        constraints=("No false completion",),
        required_proof_axes=required_axes,
        rollback_required=True,
    )


class FormationOmegaMissionConvergenceTests(unittest.TestCase):
    def test_mission_spec_can_reuse_legacy_contract_identity(self):
        legacy = {
            "mission_id": "MISSION-LEGACY-001",
            "objective": "Close the legacy mission without semantic drift",
            "success_criteria": ["Verified closure"],
            "authority_ceiling": "A1",
            "contract_sha256": "abc123",
            "constraints": ["proof before claim"],
            "rollback_required": True,
        }
        spec = MissionSpec.from_legacy_contract(legacy, required_proof_axes=("source", "rollback"))
        self.assertEqual(spec.mission_id, legacy["mission_id"])
        self.assertEqual(spec.source_contract_sha256, "abc123")
        self.assertEqual(spec.source_contract_ref, "FEDERATION_OMEGA_V2_MISSION_CONTRACT")
        self.assertTrue(spec.mission_sha256)

    def test_public_safe_mission_rejects_secret_fields_via_ledger(self):
        ledger = ConvergenceLedger()
        with self.assertRaisesRegex(ValueError, "secret-bearing"):
            ledger.append(mission_id="MISSION-X", event_type="TEST", payload={"api_key": "do-not-store"})

    def test_jsonl_ledger_is_idempotent_and_restart_verifiable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "mce.jsonl"
            ledger = ConvergenceLedger(path)
            one = ledger.append(
                mission_id="MISSION-X",
                event_type="TEST",
                payload={"state": "A"},
                idempotency_key="same",
                occurred_at="2026-08-27T08:00:00+00:00",
            )
            replay = ledger.append(
                mission_id="MISSION-X",
                event_type="TEST",
                payload={"state": "A"},
                idempotency_key="same",
                occurred_at="2026-08-27T08:01:00+00:00",
            )
            self.assertEqual(one.event_id, replay.event_id)
            self.assertEqual(len(ledger.events()), 1)
            reopened = ConvergenceLedger(path)
            result = reopened.verify()
            self.assertEqual(result["state"], "VERIFIED")
            self.assertEqual(result["event_count"], 1)
            self.assertEqual(result["head_hash"], one.event_hash)

    def test_dependency_wave_runs_independent_lanes_and_serializes_shared_state(self):
        engine = MissionConvergenceEngine()
        engine.open_mission(mission())
        engine.set_work_item("MISSION-MCE-TEST-001", WorkItem.create(work_id="A", lane="design", objective="Verify design"))
        engine.set_work_item(
            "MISSION-MCE-TEST-001",
            WorkItem.create(work_id="B", lane="source", objective="Build source candidate", dependencies=("A",), shared_state_key="github-main"),
        )
        engine.set_work_item(
            "MISSION-MCE-TEST-001",
            WorkItem.create(work_id="C", lane="source", objective="Build another source candidate", dependencies=("A",), shared_state_key="github-main"),
        )
        engine.set_work_item(
            "MISSION-MCE-TEST-001",
            WorkItem.create(work_id="D", lane="proof", objective="Prepare independent proof harness", dependencies=("A",)),
        )
        first = engine.project("MISSION-MCE-TEST-001").ready_work_wave()
        self.assertEqual([item.work_id for item in first], ["A"])
        engine.update_work_status("MISSION-MCE-TEST-001", "A", WorkStatus.VERIFIED)
        second = engine.project("MISSION-MCE-TEST-001").ready_work_wave()
        ids = {item.work_id for item in second}
        self.assertIn("D", ids)
        self.assertEqual(len({"B", "C"} & ids), 1)

    def test_closure_lock_only_p0_interrupts_implementation(self):
        lock = ClosureLock(active=True, target="Close live canary")
        self.assertEqual(lock.disposition(IdeaPriority.P0), IdeaDisposition.INTERRUPT_CLOSURE)
        self.assertEqual(lock.disposition(IdeaPriority.P1), IdeaDisposition.PARALLEL_CHALLENGER)
        self.assertEqual(lock.disposition(IdeaPriority.P2), IdeaDisposition.IMPROVEMENT_INBOX)
        self.assertEqual(lock.disposition(IdeaPriority.P3), IdeaDisposition.FUTURE_BACKLOG)

    def test_failure_fingerprint_reuses_one_resolver_record(self):
        engine = MissionConvergenceEngine()
        engine.open_mission(mission())
        resolver = FailureResolver.create(
            fingerprint="stale github base after concurrent main merge",
            exact_gap="Candidate ancestry is stale",
            diagnosis="Main advanced independently",
            immediate_workaround="Classify path overlap",
            permanent_fix="Use source convergence lane",
            alternate_route="Reanchor exact candidate blobs",
            retry_condition="Fresh signed main observed",
            proof_test="Exact-head checks pass",
            closure_test="Candidate merged and signed main read back",
            evidence_refs=("PR-628",),
        )
        engine.record_failure("MISSION-MCE-TEST-001", resolver)
        projection = engine.record_failure("MISSION-MCE-TEST-001", resolver)
        self.assertEqual(len(projection.resolvers), 1)
        self.assertEqual(projection.resolvers[resolver.resolver_id].occurrence_count, 2)

    def test_closure_requires_success_proof_axes_work_and_closed_failures(self):
        engine = MissionConvergenceEngine()
        engine.open_mission(mission())
        engine.set_work_item("MISSION-MCE-TEST-001", WorkItem.create(work_id="A", lane="source", objective="Admit source"))
        resolver = FailureResolver.create(
            fingerprint="temporary stale base",
            exact_gap="Base moved",
            diagnosis="Concurrent merge",
            immediate_workaround="Reclassify",
            permanent_fix="Convergence lane",
            alternate_route="Overlay candidate blobs",
            retry_condition="Fresh main",
            proof_test="Checks pass",
            closure_test="Readback passes",
        )
        engine.record_failure("MISSION-MCE-TEST-001", resolver)
        self.assertFalse(engine.project("MISSION-MCE-TEST-001").closable)
        engine.update_work_status("MISSION-MCE-TEST-001", "A", WorkStatus.VERIFIED, result_refs=("MERGE-1",))
        for axis in ("design", "source", "rollback"):
            engine.update_proof(
                "MISSION-MCE-TEST-001",
                ProofEntry.create(axis=axis, status=ProofStatus.PROVEN, evidence_refs=(f"PROOF-{axis}",)),
            )
        for criterion in mission().success_criteria:
            engine.verify_success("MISSION-MCE-TEST-001", criterion, evidence_refs=(f"EVIDENCE:{criterion}",))
        engine.set_failure_status("MISSION-MCE-TEST-001", resolver.resolver_id, FailureStatus.CLOSED, evidence_refs=("CLOSURE-TEST-PASS",))
        self.assertTrue(engine.project("MISSION-MCE-TEST-001").closable)
        receipt = engine.close_mission("MISSION-MCE-TEST-001", receipt_refs=("JARVIS-READBACK",))
        self.assertEqual(receipt["state"], "CLOSED_VERIFIED")
        self.assertTrue(receipt["closure_receipt_sha256"])
        self.assertEqual(engine.project("MISSION-MCE-TEST-001").status, "CLOSED_VERIFIED")

    def test_proven_axis_requires_evidence(self):
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            ProofEntry.create(axis="source", status=ProofStatus.PROVEN)

    def test_event_projection_preserves_append_only_history(self):
        engine = MissionConvergenceEngine()
        engine.open_mission(mission())
        engine.update_proof("MISSION-MCE-TEST-001", ProofEntry.create(axis="source", status=ProofStatus.PARTIAL, evidence_refs=("PR-1",)))
        engine.update_proof("MISSION-MCE-TEST-001", ProofEntry.create(axis="source", status=ProofStatus.PROVEN, evidence_refs=("MERGE-1",)))
        projection = engine.project("MISSION-MCE-TEST-001")
        self.assertEqual(projection.proof_vector["source"].status, ProofStatus.PROVEN)
        self.assertGreaterEqual(len(engine.ledger.events("MISSION-MCE-TEST-001")), 4)
        self.assertEqual(engine.ledger.verify()["state"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
