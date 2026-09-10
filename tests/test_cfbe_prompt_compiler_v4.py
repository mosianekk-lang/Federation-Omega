from __future__ import annotations

import importlib.util
import unittest

try:
    _HAS_CFBE_VNEXT = importlib.util.find_spec("benchmarking.cfbe_omega.mission_execution_kernel_vnext.multistream") is not None
except ModuleNotFoundError:
    _HAS_CFBE_VNEXT = False

from federation.cfbe_prompt_compiler_v4 import (
    CompilerError,
    EffectClass,
    FailureCircuitBreaker,
    MissionCompiler,
    MissionTask,
    PacketDisposition,
    ProofLadder,
    ProofReceipt,
    PropagationTarget,
    plan_version_propagation,
)


class MissionCompilerV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = MissionCompiler()

    def compile(self, tasks):
        return self.compiler.compile(
            objective="ship verified prompt fabric",
            current_verified_state="SOURCE_BASELINE",
            target_state="ADMITTED",
            deliverables=(item for item in ["compiler", "scientist"]),
            acceptance_tests=(item for item in ["unit", "airlock"]),
            proof_requirements=(item for item in ["test", "readback"]),
            tasks=tasks,
            mission_id="MISSION-PROMPT-V4",
        )

    def test_parallel_reads_then_serialized_internal_write(self):
        tasks = (
            MissionTask("read-a", "inspect source", "LANE-A-REPOSITORY_SOURCE_INTELLIGENCE", collision_keys=("repo:a",), priority=95),
            MissionTask("read-b", "inspect benchmark", "LANE-G-CFBE_FRONTIER_BENCHMARK", collision_keys=("web:b",), priority=90),
            MissionTask("write", "form canonical candidate", "LANE-B-ARCHITECTURE_IMPLEMENTATION", depends_on=("read-a", "read-b"), effect_class=EffectClass.INTERNAL_A1, canonical_write=True, priority=100),
        )
        graph = self.compile(tasks)
        graph.validate_hash()
        self.assertEqual(graph.deliverables, ("compiler", "scientist"))
        waves = self.compiler.schedule_waves(graph, max_parallel=8)
        self.assertEqual(set(waves[0].packet_ids), {"PKT-read-a", "PKT-read-b"})
        self.assertEqual(waves[1].packet_ids, ("PKT-write",))
        self.assertIn("SERIALIZED", waves[1].reason)

    def test_collision_key_splits_read_waves(self):
        graph = self.compile(
            (
                MissionTask("r1", "read one", "LANE-A-REPOSITORY_SOURCE_INTELLIGENCE", collision_keys=("repo",)),
                MissionTask("r2", "read two", "LANE-A-REPOSITORY_SOURCE_INTELLIGENCE", collision_keys=("repo",)),
            )
        )
        waves = self.compiler.schedule_waves(graph)
        self.assertEqual(len(waves), 2)
        self.assertTrue(all(len(w.packet_ids) == 1 for w in waves))

    def test_provider_and_dependent_packets_are_held(self):
        graph = self.compile(
            (
                MissionTask("provider", "mutate provider", "LANE-F-PROVIDER_DEPLOYMENT_READINESS", effect_class=EffectClass.PROVIDER_MUTATION),
                MissionTask("after", "read provider receipt", "LANE-H-DOCUMENTATION_PROOF_LEARNING", depends_on=("provider",)),
            )
        )
        by_id = {p.task_id: p for p in graph.packets}
        self.assertIs(by_id["provider"].disposition, PacketDisposition.HELD_EXTERNAL_AUTHORITY)
        self.assertIs(by_id["after"].disposition, PacketDisposition.HELD_DEPENDENCY)
        self.assertEqual(self.compiler.schedule_waves(graph), ())

    def test_cycle_fails_closed(self):
        with self.assertRaisesRegex(CompilerError, "MISSION_GRAPH_CYCLE"):
            self.compile(
                (
                    MissionTask("a", "a", "LANE-A-REPOSITORY_SOURCE_INTELLIGENCE", depends_on=("b",)),
                    MissionTask("b", "b", "LANE-D-TEST_SIMULATION", depends_on=("a",)),
                )
            )

    def test_repeated_failure_opens_circuit_on_second_identical_fingerprint(self):
        breaker = FailureCircuitBreaker(threshold=2)
        first = breaker.record("F-1")
        second = breaker.record("F-1")
        self.assertFalse(first.circuit_open)
        self.assertEqual(first.required_route, "BOUNDED_RETRY_OR_SAFE_REPAIR_ALLOWED")
        self.assertTrue(second.circuit_open)
        self.assertEqual(second.required_route, "MATERIALLY_DIFFERENT_ROUTE_REQUIRED")

    def test_proof_ladder_requires_native_runtime_and_rollback_proof(self):
        ladder = ProofLadder()
        with self.assertRaisesRegex(CompilerError, "RUNTIME_VERIFIED_REQUIRES_PROVIDER_READBACK"):
            ladder.promote(
                ProofReceipt("TESTED", evidence_refs=("tests",)),
                ProofReceipt("RUNTIME_VERIFIED", evidence_refs=("runtime",), runtime_receipt_ref="run-1"),
            )
        runtime = ProofReceipt(
            "RUNTIME_VERIFIED",
            evidence_refs=("runtime",),
            runtime_receipt_ref="run-1",
            provider_readback_ref="provider-1",
        )
        self.assertEqual(ladder.promote(ProofReceipt("TESTED", evidence_refs=("tests",)), runtime).state, "RUNTIME_VERIFIED")
        with self.assertRaisesRegex(CompilerError, "PRODUCTION_VERIFIED_REQUIRES_ROLLBACK_PROOF"):
            ladder.promote(runtime, ProofReceipt("PRODUCTION_VERIFIED", evidence_refs=("prod",), runtime_receipt_ref="run-2", provider_readback_ref="provider-2"))

    def test_version_propagation_is_receiver_specific(self):
        decisions = plan_version_propagation(
            (
                PropagationTarget("receiver-green", compatible=True, regression_green=True, rollback_ref="rb-1"),
                PropagationTarget("receiver-bad", compatible=True, regression_green=False, rollback_ref="rb-2"),
                PropagationTarget("receiver-unknown", compatible=False, regression_green=True, rollback_ref="rb-3"),
            )
        )
        actions = {d.target_id: (d.action, d.reason) for d in decisions}
        self.assertEqual(actions["receiver-green"], ("ELIGIBLE", "COMPATIBLE_REGRESSION_GREEN"))
        self.assertEqual(actions["receiver-bad"], ("HOLD", "RECEIVER_REGRESSION_NOT_GREEN"))
        self.assertEqual(actions["receiver-unknown"], ("HOLD", "INCOMPATIBLE_RECEIVER"))

    @unittest.skipUnless(
        _HAS_CFBE_VNEXT,
        "existing repository CFBE vNext package not available in isolated local candidate",
    )
    def test_adapter_reuses_existing_effect_free_multistream_graph(self):
        graph = self.compile(
            (
                MissionTask("r1", "read one", "LANE-A-REPOSITORY_SOURCE_INTELLIGENCE"),
                MissionTask("r2", "read two", "LANE-D-TEST_SIMULATION", depends_on=("r1",)),
                MissionTask("m1", "internal mutation", "LANE-B-ARCHITECTURE_IMPLEMENTATION", effect_class=EffectClass.INTERNAL_A1),
            )
        )
        adapted = self.compiler.to_cfbe_vnext_execution_graph(graph)
        self.assertEqual({p.path_id for p in adapted.paths}, {"PATH-r1", "PATH-r2"})


if __name__ == "__main__":
    unittest.main()
