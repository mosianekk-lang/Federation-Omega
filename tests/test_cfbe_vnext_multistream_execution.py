from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
import tempfile
import threading
import unittest

from benchmarking.cfbe_omega.mission_execution_kernel_vnext.core import (
    CFBEKernelError,
    EvidenceProof,
    FruitCriterion,
    IdempotencyConflict,
    MissionContract,
    MissionExecutionKernel,
    Requirement,
)
from benchmarking.cfbe_omega.mission_execution_kernel_vnext.multistream import (
    AGENT_ROLES,
    BenchmarkMode,
    CapabilityAttestation,
    CapabilitySnapshot,
    ExecutionGraph,
    MATURITY,
    MultiStreamExecutionBridge,
    PathCandidate,
    PathResult,
    PathResultState,
    PairedBenchmarkObservation,
    StreamNode,
    evaluate_throughput_claim,
    execute_logical_wave,
)


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def mission(*, version: int = 1) -> MissionContract:
    return MissionContract.create(
        mission_id="MISSION-MULTISTREAM-TEST",
        mission_version=version,
        owner_outcome="Deliver one deterministic multi-stream local result",
        terminal_fruit=(FruitCriterion("F1", "Independent multi-stream witness proves completion"),),
        requirements=(
            Requirement("R1", "Build independent candidate paths in parallel"),
            Requirement("R2", "Converge candidates through sovereign verified fan in"),
        ),
        critical_path=("R1", "R2"),
    )


def graph(
    contract: MissionContract,
    *,
    streams: tuple[StreamNode, ...] | None = None,
    paths: tuple[PathCandidate, ...] | None = None,
    graph_id: str = "GRAPH-1",
    max_parallel: int = 4,
    maximum_total_cost: float = 10,
    baseline_quality: float = 0.8,
) -> ExecutionGraph:
    streams = streams or (
        StreamNode("DISCOVER", ("R1",), effect_group_key="shared:artifact"),
        StreamNode("VERIFY", ("R2",), depends_on=("DISCOVER",)),
    )
    paths = paths or (
        PathCandidate("path-a", "DISCOVER", "REUSE", "group-a", ("python",), expected_quality=0.9, estimated_cost=1, priority=2),
        PathCandidate("path-b", "DISCOVER", "INNOVATE", "group-b", ("python",), expected_quality=0.85, estimated_cost=1, priority=1),
        PathCandidate("path-v", "VERIFY", "FALSIFY", "group-v", ("python",), expected_quality=0.9, estimated_cost=1),
    )
    return ExecutionGraph.create(
        graph_id=graph_id,
        mission_id=contract.mission_id,
        mission_version=contract.mission_version,
        contract_sha256=contract.contract_sha256,
        formation_plan_sha256="f" * 64,
        streams=streams,
        paths=paths,
        max_parallel=max_parallel,
        maximum_total_cost=maximum_total_cost,
        baseline_quality=baseline_quality,
    )


class MultiStreamExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "mission.sqlite3"
        self.kernel = MissionExecutionKernel(self.db)
        self.contract = mission()
        self.kernel.open_mission(self.contract)
        self.bridge = MultiStreamExecutionBridge(self.kernel)
        self.graph = graph(self.contract)
        self.bridge.register_graph(self.graph)
        self.snapshot = CapabilitySnapshot.create(
            "CAPS-1", ("python", "sqlite"), observed_at=NOW.isoformat()
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def bind_path_proof(self, path_id: str, proof_id: str, *, independence: int = 1) -> None:
        self.kernel.bind_proof(
            EvidenceProof(
                proof_id=proof_id,
                claim_id=f"path:{path_id}",
                mission_id=self.contract.mission_id,
                mission_version=self.contract.mission_version,
                artifact_hashes=(f"sha256:{path_id}",),
                dependency_hashes={"graph": self.graph.graph_sha256},
                environment_fingerprint="python-local",
                authority_fingerprint=f"verifier-{path_id}",
                created_at=NOW.isoformat(),
                max_age_seconds=3600,
                invalidation_predicates=("graph changed",),
                independence_level=independence,
            )
        )

    def claim_and_verify(self, path_id: str, proof_id: str, quality: float = 0.9) -> None:
        claim = self.bridge.claim_path(
            self.graph.graph_id, path_id, f"worker-{path_id}", self.snapshot,
            now=NOW.isoformat(),
        )
        self.bind_path_proof(path_id, proof_id)
        self.bridge.submit_path_result(
            self.graph.graph_id,
            PathResult(
                path_id, claim.claim_id, claim.fence, PathResultState.VERIFIED,
                (proof_id,), quality, BenchmarkMode.SIMULATED,
                producer_identity=f"worker-{path_id}", verifier_identity=f"verifier-{path_id}",
            ),
            now=(NOW + timedelta(seconds=1)).isoformat(),
        )

    def test_cycle_and_unknown_dependency_fail_closed(self) -> None:
        with self.assertRaisesRegex(CFBEKernelError, "CYCLE"):
            graph(
                self.contract,
                streams=(StreamNode("A", ("R1",), ("B",)), StreamNode("B", ("R2",), ("A",))),
                paths=(PathCandidate("a", "A", "X", "a"), PathCandidate("b", "B", "X", "b")),
                graph_id="CYCLE",
            )
        with self.assertRaisesRegex(CFBEKernelError, "DEPENDENCY_INVALID"):
            graph(
                self.contract,
                streams=(StreamNode("A", ("R1", "R2"), ("MISSING",)),),
                paths=(PathCandidate("a", "A", "X", "a"),),
                graph_id="UNKNOWN",
            )

    def test_graph_is_bound_to_exact_mission_contract(self) -> None:
        wrong = replace(self.graph, graph_id="GRAPH-WRONG", contract_sha256="0" * 64)
        wrong = replace(wrong, graph_sha256="")
        wrong = replace(wrong, graph_sha256=ExecutionGraph.create(
            graph_id=wrong.graph_id, mission_id=wrong.mission_id,
            mission_version=wrong.mission_version, contract_sha256=wrong.contract_sha256,
            formation_plan_sha256=wrong.formation_plan_sha256, streams=wrong.streams,
            paths=wrong.paths, max_parallel=wrong.max_parallel,
            maximum_total_cost=wrong.maximum_total_cost, baseline_quality=wrong.baseline_quality,
        ).graph_sha256)
        with self.assertRaisesRegex(CFBEKernelError, "CONTRACT_HASH_MISMATCH"):
            self.bridge.register_graph(wrong)

    def test_capability_snapshot_filters_paths_and_rejects_tampering(self) -> None:
        missing = CapabilitySnapshot.create("CAPS-2", ("sqlite",), observed_at=NOW.isoformat())
        self.assertEqual((), self.bridge.ready_wave(self.graph.graph_id, missing, now=NOW.isoformat()))
        tampered = replace(self.snapshot, capabilities=("python", "provider-admin"))
        with self.assertRaisesRegex(CFBEKernelError, "SNAPSHOT_HASH_MISMATCH"):
            self.bridge.ready_wave(self.graph.graph_id, tampered, now=NOW.isoformat())

    def test_capability_attestations_admit_only_verified_live_resources(self) -> None:
        snapshot = CapabilitySnapshot.from_attestations(
            "CAPS-ATTESTED",
            (
                CapabilityAttestation("python", "VERIFIED_LIVE", "probe:python"),
                CapabilityAttestation("provider-admin", "BLOCKED_OR_UNVERIFIED", "probe:admin"),
            ),
            observed_at=NOW.isoformat(),
        )
        self.assertEqual(("python",), snapshot.capabilities)

    def test_dag_ready_wave_blocks_descendant_until_fan_in(self) -> None:
        first = self.bridge.ready_wave(self.graph.graph_id, self.snapshot, now=NOW.isoformat())
        self.assertEqual({"path-a", "path-b"}, {item.path_id for item in first})
        self.assertNotIn("path-v", {item.path_id for item in first})
        self.claim_and_verify("path-a", "PROOF-A")
        self.bridge.sovereign_fan_in(self.graph.graph_id, "DISCOVER", now=(NOW + timedelta(seconds=2)).isoformat())
        second = self.bridge.ready_wave(self.graph.graph_id, self.snapshot, now=(NOW + timedelta(seconds=3)).isoformat())
        self.assertEqual(("path-v",), tuple(item.path_id for item in second))

    def test_collision_keys_and_parallel_bound_are_enforced(self) -> None:
        streams = (
            StreamNode("A", ("R1",), collision_keys=("shared",)),
            StreamNode("B", ("R2",), collision_keys=("shared",)),
        )
        paths = (
            PathCandidate("a", "A", "X", "a", expected_quality=0.9),
            PathCandidate("b", "B", "X", "b", expected_quality=0.8),
        )
        other = graph(self.contract, graph_id="GRAPH-COLLISION", streams=streams, paths=paths, max_parallel=2)
        self.bridge.register_graph(other)
        wave = self.bridge.ready_wave(other.graph_id, self.snapshot, now=NOW.isoformat())
        self.assertEqual(1, len(wave))

    def test_total_cost_is_reserved_across_waves(self) -> None:
        costly = graph(self.contract, graph_id="GRAPH-COST", max_parallel=1, maximum_total_cost=1)
        self.bridge.register_graph(costly)
        first = self.bridge.ready_wave(costly.graph_id, self.snapshot, now=NOW.isoformat())
        claim = self.bridge.claim_path(costly.graph_id, first[0].path_id, "worker", self.snapshot, now=NOW.isoformat())
        self.assertEqual(1, claim.fence)
        self.assertEqual((), self.bridge.ready_wave(costly.graph_id, self.snapshot, now=(NOW + timedelta(seconds=1)).isoformat()))

    def test_logical_agent_envelopes_cannot_self_certify_or_execute_effects(self) -> None:
        packet = self.bridge.ready_wave(self.graph.graph_id, self.snapshot, now=NOW.isoformat())[0]
        envelopes = self.bridge.logical_agent_envelopes(packet)
        self.assertEqual(set(AGENT_ROLES), {item.role for item in envelopes})
        self.assertTrue(all(item.logical_only and not item.may_self_certify for item in envelopes))
        self.assertFalse(packet.external_effect_authorized)

    def test_claim_is_single_owner_and_expiry_takeover_increments_fence(self) -> None:
        first = self.bridge.claim_path(
            self.graph.graph_id, "path-a", "worker-a", self.snapshot,
            ttl_seconds=2, now=NOW.isoformat(),
        )
        replay = self.bridge.claim_path(
            self.graph.graph_id, "path-a", "worker-a", self.snapshot,
            now=(NOW + timedelta(seconds=1)).isoformat(),
        )
        self.assertEqual(first.claim_id, replay.claim_id)
        with self.assertRaisesRegex(CFBEKernelError, "ALREADY_CLAIMED"):
            self.bridge.claim_path(
                self.graph.graph_id, "path-a", "worker-b", self.snapshot,
                now=(NOW + timedelta(seconds=1)).isoformat(),
            )
        second = self.bridge.claim_path(
            self.graph.graph_id, "path-a", "worker-b", self.snapshot,
            now=(NOW + timedelta(seconds=3)).isoformat(),
        )
        self.assertEqual(first.fence + 1, second.fence)

    def test_cancelled_path_rejects_late_result_and_cascade_cancels_descendants(self) -> None:
        claim = self.bridge.claim_path(
            self.graph.graph_id, "path-a", "worker-a", self.snapshot, now=NOW.isoformat()
        )
        cancelled = self.bridge.cancel_stream(self.graph.graph_id, "DISCOVER", "route superseded")
        self.assertEqual({"path-a", "path-b", "path-v"}, set(cancelled))
        self.bind_path_proof("path-a", "PROOF-LATE")
        with self.assertRaisesRegex(CFBEKernelError, "CANCELLED_PATH_RESULT"):
            self.bridge.submit_path_result(
                self.graph.graph_id,
                PathResult("path-a", claim.claim_id, claim.fence, PathResultState.VERIFIED, ("PROOF-LATE",), 1, producer_identity="worker-a", verifier_identity="verifier-path-a"),
                now=(NOW + timedelta(seconds=1)).isoformat(),
            )

    def test_verified_result_requires_current_independent_path_scoped_proof(self) -> None:
        claim = self.bridge.claim_path(
            self.graph.graph_id, "path-a", "worker-a", self.snapshot, now=NOW.isoformat()
        )
        self.bind_path_proof("path-b", "PROOF-WRONG")
        with self.assertRaisesRegex(CFBEKernelError, "SCOPE_MISMATCH"):
            self.bridge.submit_path_result(
                self.graph.graph_id,
                PathResult("path-a", claim.claim_id, claim.fence, PathResultState.VERIFIED, ("PROOF-WRONG",), 1, producer_identity="worker-a", verifier_identity="verifier-path-a"),
                now=(NOW + timedelta(seconds=1)).isoformat(),
            )

    def test_equal_quality_benchmark_gate_rejects_regression(self) -> None:
        claim = self.bridge.claim_path(
            self.graph.graph_id, "path-a", "worker-a", self.snapshot, now=NOW.isoformat()
        )
        self.bind_path_proof("path-a", "PROOF-LOW")
        with self.assertRaisesRegex(CFBEKernelError, "QUALITY_REGRESSION"):
            self.bridge.submit_path_result(
                self.graph.graph_id,
                PathResult("path-a", claim.claim_id, claim.fence, PathResultState.VERIFIED, ("PROOF-LOW",), 0.79, BenchmarkMode.EQUAL_QUALITY, producer_identity="worker-a", verifier_identity="verifier-path-a"),
                now=(NOW + timedelta(seconds=1)).isoformat(),
            )

    def test_fan_in_selects_deterministic_winner_and_cancels_loser(self) -> None:
        self.claim_and_verify("path-a", "PROOF-A", 0.9)
        self.claim_and_verify("path-b", "PROOF-B", 0.95)
        receipt = self.bridge.sovereign_fan_in(
            self.graph.graph_id, "DISCOVER", now=(NOW + timedelta(seconds=2)).isoformat()
        )
        self.assertEqual("path-b", receipt.selected_path_id)
        self.assertEqual("SIMULATED_EQUAL_OR_BETTER", receipt.benchmark_state)
        self.assertFalse(receipt.external_effect_executed)
        projection = self.bridge.projection(self.graph.graph_id)
        self.assertIn("path-a", projection["cancelled_paths"])
        self.assertEqual((("shared:artifact", "path-b"),), projection["effect_winners"])

    def test_fan_in_requires_independent_corroborating_groups(self) -> None:
        streams = (StreamNode("A", ("R1", "R2"), minimum_verified_paths=2),)
        paths = (
            PathCandidate("a", "A", "X", "same"),
            PathCandidate("b", "A", "Y", "same"),
        )
        other = graph(self.contract, graph_id="GRAPH-CORROBORATE", streams=streams, paths=paths)
        self.bridge.register_graph(other)
        for path_id, proof_id in (("a", "PA"), ("b", "PB")):
            claim = self.bridge.claim_path(other.graph_id, path_id, f"w-{path_id}", self.snapshot, now=NOW.isoformat())
            self.kernel.bind_proof(EvidenceProof(
                proof_id, f"path:{path_id}", self.contract.mission_id, 1, ("artifact",),
                {"graph": other.graph_sha256}, "local", f"v-{path_id}", NOW.isoformat(), 3600, (), 1,
            ))
            self.bridge.submit_path_result(other.graph_id, PathResult(path_id, claim.claim_id, claim.fence, PathResultState.VERIFIED, (proof_id,), 1, producer_identity=f"w-{path_id}", verifier_identity=f"v-{path_id}"), now=(NOW + timedelta(seconds=1)).isoformat())
        with self.assertRaisesRegex(CFBEKernelError, "CORROBORATION_INCOMPLETE"):
            self.bridge.sovereign_fan_in(other.graph_id, "A", now=(NOW + timedelta(seconds=2)).isoformat())

    def test_concurrent_fan_in_creates_one_effect_winner(self) -> None:
        self.claim_and_verify("path-a", "PROOF-A", 1)
        self.claim_and_verify("path-b", "PROOF-B", 1)
        receipts: list[str] = []
        errors: list[str] = []
        barrier = threading.Barrier(2)

        def converge() -> None:
            barrier.wait()
            try:
                receipt = self.bridge.sovereign_fan_in(
                    self.graph.graph_id, "DISCOVER", now=(NOW + timedelta(seconds=2)).isoformat()
                )
                receipts.append(receipt.decision_sha256)
            except Exception as exc:  # pragma: no cover - failure is asserted below
                errors.append(str(exc))

        threads = (threading.Thread(target=converge), threading.Thread(target=converge))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual([], errors)
        self.assertEqual(1, len(set(receipts)))
        self.assertEqual(1, len(self.bridge.projection(self.graph.graph_id)["effect_winners"]))

    def test_restart_rehydrates_claim_results_shared_proof_and_fan_in(self) -> None:
        self.claim_and_verify("path-a", "PROOF-A")
        first = self.bridge.sovereign_fan_in(
            self.graph.graph_id, "DISCOVER", now=(NOW + timedelta(seconds=2)).isoformat()
        )
        restarted = MultiStreamExecutionBridge(MissionExecutionKernel(self.db))
        state = restarted.projection(self.graph.graph_id)
        self.assertEqual(("DISCOVER",), state["fanin_streams"])
        self.assertEqual(("PROOF-A",), state["shared_proofs"]["path-a"])
        self.assertEqual(first.decision_sha256, restarted.sovereign_fan_in(self.graph.graph_id, "DISCOVER").decision_sha256)
        self.assertEqual(MATURITY, state["maturity"])

    def test_mission_revision_fences_old_graph(self) -> None:
        self.kernel.revise_mission(mission(version=2))
        with self.assertRaisesRegex(CFBEKernelError, "STALE_EXECUTION_GRAPH"):
            self.bridge.ready_wave(self.graph.graph_id, self.snapshot)

    def test_verified_result_requires_distinct_claim_bound_producer_and_verifier(self) -> None:
        claim = self.bridge.claim_path(
            self.graph.graph_id, "path-a", "worker-a", self.snapshot, now=NOW.isoformat()
        )
        self.bind_path_proof("path-a", "PROOF-IDENTITY")
        with self.assertRaisesRegex(CFBEKernelError, "PRODUCER_CLAIM_MISMATCH"):
            self.bridge.submit_path_result(
                self.graph.graph_id,
                PathResult("path-a", claim.claim_id, claim.fence, PathResultState.VERIFIED,
                           ("PROOF-IDENTITY",), 1, producer_identity="worker-b", verifier_identity="verifier-path-a"),
                now=(NOW + timedelta(seconds=1)).isoformat(),
            )
        with self.assertRaisesRegex(CFBEKernelError, "INDEPENDENT_VERIFIER_REQUIRED"):
            self.bridge.submit_path_result(
                self.graph.graph_id,
                PathResult("path-a", claim.claim_id, claim.fence, PathResultState.VERIFIED,
                           ("PROOF-IDENTITY",), 1, producer_identity="worker-a", verifier_identity="worker-a"),
                now=(NOW + timedelta(seconds=1)).isoformat(),
            )

    def test_atomic_claims_cannot_jointly_exceed_total_budget(self) -> None:
        streams = (StreamNode("A", ("R1", "R2")),)
        paths = (
            PathCandidate("a", "A", "X", "a", estimated_cost=1),
            PathCandidate("b", "A", "Y", "b", estimated_cost=1),
        )
        bounded = graph(
            self.contract, graph_id="GRAPH-ATOMIC-COST", streams=streams, paths=paths,
            max_parallel=2, maximum_total_cost=1,
        )
        self.bridge.register_graph(bounded)
        barrier = threading.Barrier(2)
        successes: list[str] = []
        failures: list[str] = []

        def claim(path_id: str) -> None:
            barrier.wait()
            try:
                self.bridge.claim_path(
                    bounded.graph_id, path_id, f"worker-{path_id}", self.snapshot,
                    now=NOW.isoformat(),
                )
                successes.append(path_id)
            except CFBEKernelError as exc:
                failures.append(str(exc))

        threads = [threading.Thread(target=claim, args=(path_id,)) for path_id in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(1, len(successes))
        self.assertEqual(1, len(failures))
        self.assertTrue(
            "GRAPH_TOTAL_COST_EXHAUSTED" in failures[0]
            or "PATH_NOT_READY_OR_CAPABLE" in failures[0]
        )

    def test_logical_wave_contains_failed_path_and_completes_healthy_siblings(self) -> None:
        packets = self.bridge.ready_wave(self.graph.graph_id, self.snapshot, now=NOW.isoformat())

        async def worker(packet):
            await asyncio.sleep(0.01)
            if packet.path_id == "path-a":
                raise RuntimeError("bounded failure")
            return f"ok:{packet.path_id}"

        outcomes = asyncio.run(execute_logical_wave(packets, worker, max_parallel=2))
        by_path = {item.path_id: item for item in outcomes}
        self.assertEqual("FAILED", by_path["path-a"].state)
        self.assertTrue(by_path["path-a"].failure_fingerprint)
        self.assertEqual("SUCCEEDED", by_path["path-b"].state)
        self.assertEqual("ok:path-b", by_path["path-b"].value)

    def test_throughput_claim_requires_sample_strength_and_equal_quality(self) -> None:
        observations = tuple(
            PairedBenchmarkObservation(3.2 + index / 1000, 1.0, 1.0, 1.0)
            for index in range(30)
        )
        receipt = evaluate_throughput_claim(observations)
        self.assertEqual("SIMULATED_SCHEDULING_SPEEDUP_ONLY", receipt.state)
        self.assertGreaterEqual(receipt.one_sided_95_lower_bound, 2)
        real = tuple(replace(item, measurement_scope="REAL_MISSION") for item in observations)
        self.assertEqual(
            "MEASURED_CAPABILITY_UPGRADE_GE_2X", evaluate_throughput_claim(real).state
        )
        degraded = list(observations)
        degraded[-1] = replace(degraded[-1], parallel_quality=0.9)
        self.assertEqual(
            "MEASURED_NOT_PROVEN_GE_2X", evaluate_throughput_claim(tuple(degraded)).state
        )
        with self.assertRaisesRegex(CFBEKernelError, "SAMPLE_COUNT_INSUFFICIENT"):
            evaluate_throughput_claim(observations[:29])

    def test_active_execution_graph_blocks_core_terminality(self) -> None:
        for requirement_id in ("R1", "R2"):
            proof_id = f"PROOF-{requirement_id}"
            self.kernel.bind_proof(EvidenceProof(
                proof_id, f"requirement:{requirement_id}", self.contract.mission_id, 1,
                ("artifact",), {"graph": self.graph.graph_sha256}, "local", "A1",
                NOW.isoformat(), 3600, (), 1,
            ))
            self.kernel.prove_requirement(self.contract.mission_id, 1, requirement_id, proof_id)
        self.kernel.bind_proof(EvidenceProof(
            "PROOF-F1", "fruit:F1", self.contract.mission_id, 1, ("artifact",),
            {"graph": self.graph.graph_sha256}, "local", "A1", NOW.isoformat(), 3600, (), 1,
        ))
        self.kernel.prove_fruit(self.contract.mission_id, 1, "F1", "PROOF-F1")
        report = self.kernel.terminality_report(self.contract.mission_id, now=NOW.isoformat())
        self.assertEqual(("EXECUTION_GRAPH:GRAPH-1:ACTIVE",), report.gaps)


if __name__ == "__main__":
    unittest.main()
