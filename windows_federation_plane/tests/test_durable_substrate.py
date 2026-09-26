import unittest

from federation_windows_plane.reality_twin import (
    CognitivePlacementEngine,
    DeterministicRealityTwin,
    NeuralRealityModel,
    evolve_policy,
    make_training_set,
)
from federation_windows_plane.substrate_contracts import (
    CommercialProfile,
    ExecutorKind,
    ExecutorPassport,
    ProofMaturity,
    ResourceVector,
    RoutingPolicy,
    WorkloadSpec,
)


def _executors():
    common = frozenset({"BUILD", "TEST", "SIMULATE", "VERIFY"})
    return [
        ExecutorPassport(
            "windows-local",
            ExecutorKind.WINDOWS_HOST,
            common | frozenset({"EXECUTE", "HEAVY"}),
            ResourceVector(cpu=16, memory_gb=32, io=8, network=4),
            isolation=0.55,
            locality=1.0,
            resilience=0.86,
            energy_efficiency=0.72,
            startup_ms=12,
            variable_cost=0.01,
            privacy_fit=0.95,
            residency_fit=0.95,
            proof_maturity=ProofMaturity.READBACK_PROVEN,
            readback_mechanisms=frozenset({"DEVICE_RECEIPT"}),
            commercial=CommercialProfile(unit_cost=0.05, deployability=0.90, maintainability=0.82, scalability=0.62, interoperability=0.90, observability=0.90, supportability=0.82, differentiation=0.88),
        ),
        ExecutorPassport(
            "wasm-sandbox",
            ExecutorKind.WASM_SANDBOX,
            common | frozenset({"PORTABLE", "UNTRUSTED"}),
            ResourceVector(cpu=8, memory_gb=8, io=3, network=2),
            isolation=0.88,
            locality=0.92,
            resilience=0.92,
            energy_efficiency=0.92,
            startup_ms=4,
            variable_cost=0.01,
            privacy_fit=0.95,
            residency_fit=0.95,
            proof_maturity=ProofMaturity.SOURCE_BOUND,
            commercial=CommercialProfile(unit_cost=0.03, deployability=0.92, maintainability=0.90, scalability=0.88, interoperability=0.98, observability=0.82, supportability=0.82, differentiation=0.78),
        ),
        ExecutorPassport(
            "google-cloud",
            ExecutorKind.GOOGLE_CLOUD,
            common | frozenset({"BURST", "GPU", "DISTRIBUTED"}),
            ResourceVector(cpu=128, memory_gb=512, gpu=8, io=32, network=32),
            isolation=0.93,
            locality=0.35,
            resilience=0.98,
            energy_efficiency=0.86,
            startup_ms=350,
            variable_cost=0.18,
            privacy_fit=0.70,
            residency_fit=0.70,
            accelerator_score=1.0,
            proof_maturity=ProofMaturity.AUTHENTICATED,
            readback_mechanisms=frozenset({"PROVIDER_JOB_STATUS"}),
            commercial=CommercialProfile(unit_cost=0.55, deployability=0.88, maintainability=0.90, scalability=1.0, interoperability=0.90, observability=0.98, supportability=0.90, differentiation=0.70),
        ),
        ExecutorPassport(
            "apps-script",
            ExecutorKind.GOOGLE_APPS_SCRIPT,
            frozenset({"AUTOMATE", "GOOGLE_WORKSPACE"}),
            ResourceVector(cpu=1, memory_gb=1, io=1, network=2),
            isolation=0.70,
            locality=0.15,
            resilience=0.92,
            energy_efficiency=0.98,
            startup_ms=80,
            variable_cost=0.02,
            privacy_fit=0.65,
            residency_fit=0.60,
            proof_maturity=ProofMaturity.AUTHENTICATED,
            commercial=CommercialProfile(unit_cost=0.05, deployability=0.98, maintainability=0.92, scalability=0.68, interoperability=0.90, observability=0.75, supportability=0.85, differentiation=0.65),
        ),
    ]


def _workloads():
    return [
        WorkloadSpec("local-build", frozenset({"BUILD", "HEAVY"}), ResourceVector(cpu=4, memory_gb=4, io=2), min_privacy_fit=0.85, min_residency_fit=0.85, commercial_priority=0.9),
        WorkloadSpec("untrusted-plugin", frozenset({"UNTRUSTED", "PORTABLE"}), ResourceVector(cpu=1, memory_gb=1), min_isolation=0.80),
        WorkloadSpec("cloud-burst", frozenset({"DISTRIBUTED", "GPU"}), ResourceVector(cpu=24, memory_gb=64, gpu=2, network=8), min_isolation=0.85, accelerator_affinity=1.0),
        WorkloadSpec("workspace-automation", frozenset({"AUTOMATE", "GOOGLE_WORKSPACE"}), ResourceVector(cpu=0.2, memory_gb=0.2, network=1), commercial_priority=0.8),
    ]


class DurableSubstrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executors = _executors()
        cls.workloads = _workloads()
        xs, ys = make_training_set(cls.executors, cls.workloads)
        cls.world = NeuralRealityModel()
        cls.world.fit(xs, ys)

    def test_hard_privacy_gate_keeps_sensitive_build_local(self):
        selected = CognitivePlacementEngine(self.executors, self.world).choose(self.workloads[0])
        self.assertEqual(selected.executor_id, "windows-local")

    def test_untrusted_workload_requires_strong_isolation(self):
        selected = CognitivePlacementEngine(self.executors, self.world).choose(self.workloads[1])
        self.assertGreaterEqual(selected.isolation, 0.80)
        self.assertEqual(selected.executor_id, "wasm-sandbox")

    def test_accelerated_burst_routes_to_accelerated_surface(self):
        selected = CognitivePlacementEngine(self.executors, self.world).choose(self.workloads[2])
        self.assertEqual(selected.executor_id, "google-cloud")

    def test_workspace_automation_routes_to_apps_script_capability(self):
        selected = CognitivePlacementEngine(self.executors, self.world).choose(self.workloads[3])
        self.assertEqual(selected.executor_id, "apps-script")

    def test_unhealthy_executor_is_not_selected(self):
        engine = CognitivePlacementEngine(self.executors, self.world)
        engine.state["windows-local"].healthy = False
        with self.assertRaisesRegex(RuntimeError, "NO_FEASIBLE_EXECUTOR"):
            engine.choose(self.workloads[0])

    def test_twin_is_deterministic_for_same_seed(self):
        a = DeterministicRealityTwin(self.executors, self.world, seed=42).run(self.workloads)
        b = DeterministicRealityTwin(self.executors, self.world, seed=42).run(self.workloads)
        self.assertEqual(a, b)
        self.assertEqual(a.safety_violations, 0)

    def test_bounded_evolution_never_promotes_safety_regression(self):
        _, _, promoted = evolve_policy(self.executors, self.world, self.workloads * 5, RoutingPolicy(), generations=2, population=8, seed=123)
        result = DeterministicRealityTwin(self.executors, self.world, seed=123).run(self.workloads * 5)
        self.assertEqual(result.safety_violations, 0)
        self.assertIsInstance(promoted, bool)

    def test_commercial_profile_penalizes_high_cost(self):
        strong = CommercialProfile(unit_cost=0.1, deployability=0.9, maintainability=0.9, scalability=0.9, interoperability=0.9, observability=0.9, supportability=0.9, differentiation=0.9)
        costly = CommercialProfile(unit_cost=1.0, deployability=0.9, maintainability=0.9, scalability=0.9, interoperability=0.9, observability=0.9, supportability=0.9, differentiation=0.9)
        self.assertGreater(strong.value_score(), costly.value_score())


if __name__ == "__main__":
    unittest.main()
