from __future__ import annotations

import unittest

from federation.capability_truth_v1 import Maturity
from federation.cfbe_chat_hyperperformance_v1 import (
    EffectClass,
    PerformanceBudget,
    RouteProfile,
    WorkUnit,
)
from federation.execution_topology_compiler_v1 import (
    ExecutionTopologyCompiler,
    TopologyMode,
    TopologyTask,
)
from federation.live_worker_attestation_v1 import (
    CapabilityEpoch,
    WorkerAttestation,
    WorkerState,
)
from federation.mission_capability_admission_v1 import (
    Equivalence,
    MissionAdmissionReceipt,
    MissionCapabilityDecision,
)
from federation.mission_ir import MissionIR

NOW = "2026-09-06T22:30:00+02:00"


def mission() -> MissionIR:
    return MissionIR(
        mission_id="mission-topology-1",
        objective="compile a verified execution topology",
        domain="FEDERATION",
        outcome_contract="proof-bounded topology",
        source_frontier="signed-main",
        privacy_class="P1_INTERNAL",
        rights_state="OWNER_AUTHORIZED",
        effect_class="READ_ONLY",
        proof_requirements=("topology_receipt",),
    )


def admission(m: MissionIR, capability: str = "CAP_A") -> MissionAdmissionReceipt:
    decision = MissionCapabilityDecision(
        capability_id=capability,
        required_maturity=Maturity.PROVIDER_RUNNING,
        state="SATISFIED_DIRECT",
        selected_capability_id=capability,
        selected_maturity=Maturity.PROVIDER_RUNNING,
        equivalence=Equivalence.FULL,
        reasons=("PROVIDER_RUNNING_PROVEN",),
    )
    return MissionAdmissionReceipt(
        mission_id=m.mission_id,
        mission_digest=m.digest(),
        state="MISSION_ADMITTED",
        decisions=(decision,),
        blocking_capabilities=(),
        truth_index_digest="sha256:truth",
        receipt_digest="sha256:admission",
    )


def epoch(capability: str = "CAP_A") -> CapabilityEpoch:
    return CapabilityEpoch(
        epoch_id=f"epoch-{capability}",
        subject=capability,
        observed_at="2026-09-06T22:00:00+02:00",
        expires_at="2026-09-06T23:30:00+02:00",
        source_ref="provider:epoch-readback",
    )


def worker(
    worker_id: str,
    runtime_id: str,
    *,
    capability: str = "CAP_A",
    state: WorkerState = WorkerState.HEARTBEAT_VERIFIED,
    mission_id: str = "mission-topology-1",
) -> WorkerAttestation:
    kwargs = dict(
        attestation_id=f"att-{worker_id}",
        worker_id=worker_id,
        capability_id=capability,
        epoch_id=f"epoch-{capability}",
        state=state,
        observed_at="2026-09-06T22:20:00+02:00",
        expires_at="2026-09-06T23:00:00+02:00",
        source_ref="provider:worker-readback",
        runtime_id=runtime_id,
        mission_id=mission_id,
        tool_refs=("tool:read",) if state >= WorkerState.TOOL_BOUND else (),
        heartbeat_ref="provider:heartbeat" if state >= WorkerState.HEARTBEAT_VERIFIED else "",
        result_ref="provider:result" if state >= WorkerState.RESULT_VERIFIED else "",
        independently_verified=True,
    )
    return WorkerAttestation(**kwargs)


def task(unit_id: str, *, effect: EffectClass = EffectClass.READ_ONLY, domain: str = "") -> TopologyTask:
    return TopologyTask(
        WorkUnit(
            unit_id=unit_id,
            surface="github",
            operation="inspect",
            input_fingerprint=f"input-{unit_id}",
            effect_class=effect,
            cacheable=effect is not EffectClass.EXTERNAL_EFFECT,
        ),
        capability_id="CAP_A",
        mutation_domain=domain,
    )


def routes() -> tuple[RouteProfile, ...]:
    return (
        RouteProfile(
            route_id="github-direct",
            surface="github",
            available=True,
            fresh=True,
            direct=True,
            proof_refs=("provider:route-readback",),
        ),
    )


class ExecutionTopologyCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = mission()
        self.admission = admission(self.mission)
        self.compiler = ExecutionTopologyCompiler(PerformanceBudget(max_parallel=8))

    def compile(self, workers, tasks=(task("u1"),), require_swarm=False):
        return self.compiler.compile(
            mission=self.mission,
            admission=self.admission,
            tasks=tasks,
            routes=routes(),
            attestations=workers,
            epochs={"CAP_A": epoch()},
            now=NOW,
            require_swarm=require_swarm,
        )

    def test_agent_profiles_without_live_workers_cannot_create_swarm(self) -> None:
        result = self.compile((), require_swarm=True)
        self.assertEqual("TOPOLOGY_HELD_NO_LIVE_CAPACITY", result.state)
        self.assertEqual(TopologyMode.NONE, result.mode)
        self.assertFalse(result.executable)

    def test_registered_or_mission_assigned_worker_is_not_live_capacity(self) -> None:
        assigned = worker("w1", "runtime-1", state=WorkerState.MISSION_ASSIGNED)
        result = self.compile((assigned,))
        self.assertEqual("TOPOLOGY_HELD_NO_LIVE_CAPACITY", result.state)
        self.assertEqual((), result.assignments)

    def test_one_heartbeat_verified_worker_yields_single_worker_topology(self) -> None:
        result = self.compile((worker("w1", "runtime-1"),))
        self.assertEqual("TOPOLOGY_READY_SINGLE_WORKER", result.state)
        self.assertEqual(TopologyMode.SINGLE_WORKER, result.mode)
        self.assertEqual(("w1",), result.live_worker_ids)
        self.assertTrue(result.executable)

    def test_required_swarm_fails_closed_with_only_one_runtime(self) -> None:
        result = self.compile((worker("w1", "runtime-1"),), require_swarm=True)
        self.assertEqual("TOPOLOGY_HELD_SWARM_NOT_PROVEN", result.state)
        self.assertEqual(TopologyMode.NONE, result.mode)

    def test_two_worker_ids_on_same_runtime_do_not_prove_independent_swarm(self) -> None:
        result = self.compile(
            (worker("w1", "runtime-shared"), worker("w2", "runtime-shared")),
            tasks=(task("u1"), task("u2")),
            require_swarm=True,
        )
        self.assertEqual("TOPOLOGY_HELD_SWARM_NOT_PROVEN", result.state)

    def test_two_current_independent_runtimes_enable_parallel_swarm(self) -> None:
        result = self.compile(
            (worker("w1", "runtime-1"), worker("w2", "runtime-2")),
            tasks=(task("u1"), task("u2")),
            require_swarm=True,
        )
        self.assertEqual("TOPOLOGY_READY", result.state)
        self.assertEqual(TopologyMode.PARALLEL_SWARM, result.mode)
        self.assertEqual({"w1", "w2"}, {a.worker_id for a in result.assignments})

    def test_wrong_mission_worker_does_not_count_as_capacity(self) -> None:
        result = self.compile((worker("w1", "runtime-1", mission_id="other-mission"),))
        self.assertEqual("TOPOLOGY_HELD_NO_LIVE_CAPACITY", result.state)

    def test_same_mutation_domain_is_serialized_even_when_cfbe_can_parallelize(self) -> None:
        result = self.compile(
            (worker("w1", "runtime-1"), worker("w2", "runtime-2")),
            tasks=(
                task("u1", effect=EffectClass.INTERNAL_WRITE, domain="repo:main"),
                task("u2", effect=EffectClass.INTERNAL_WRITE, domain="repo:main"),
            ),
        )
        self.assertTrue(result.executable)
        self.assertEqual(2, len(result.waves))
        self.assertEqual(("repo:main",), result.waves[0].mutation_domains)
        self.assertEqual(("repo:main",), result.waves[1].mutation_domains)

    def test_different_mutation_domains_may_share_wave(self) -> None:
        result = self.compile(
            (worker("w1", "runtime-1"), worker("w2", "runtime-2")),
            tasks=(
                task("u1", effect=EffectClass.INTERNAL_WRITE, domain="repo:a"),
                task("u2", effect=EffectClass.INTERNAL_WRITE, domain="repo:b"),
            ),
        )
        self.assertTrue(result.executable)
        self.assertEqual(1, len(result.waves))
        self.assertEqual(("repo:a", "repo:b"), result.waves[0].mutation_domains)

    def test_unadmitted_mission_cannot_compile_topology(self) -> None:
        held = MissionAdmissionReceipt(
            mission_id=self.mission.mission_id,
            mission_digest=self.mission.digest(),
            state="MISSION_HELD_CAPABILITY_GAP",
            decisions=(),
            blocking_capabilities=("CAP_A",),
            truth_index_digest="sha256:truth",
            receipt_digest="sha256:held",
        )
        result = self.compiler.compile(
            mission=self.mission,
            admission=held,
            tasks=(task("u1"),),
            routes=routes(),
            attestations=(worker("w1", "runtime-1"),),
            epochs={"CAP_A": epoch()},
            now=NOW,
        )
        self.assertEqual("TOPOLOGY_HELD_MISSION_NOT_ADMITTED", result.state)

    def test_cfbe_route_gap_blocks_topology(self) -> None:
        result = self.compiler.compile(
            mission=self.mission,
            admission=self.admission,
            tasks=(task("u1"),),
            routes=(),
            attestations=(worker("w1", "runtime-1"),),
            epochs={"CAP_A": epoch()},
            now=NOW,
        )
        self.assertEqual("TOPOLOGY_HELD_CFBE_ROUTE_GAP", result.state)
        self.assertEqual(("u1",), result.blocked_units)


if __name__ == "__main__":
    unittest.main()
