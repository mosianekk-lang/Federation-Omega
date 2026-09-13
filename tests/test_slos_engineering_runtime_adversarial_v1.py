import unittest

from superior_logic.engineering_runtime import (
    AutonomousCapabilityClosure,
    CheckKind,
    CheckObservation,
    ClosureAction,
    ClosureCandidate,
    CodingFleetPlanner,
    FleetTask,
    PreparedWorkspaceForge,
    ReadinessSignal,
    RepoGraph,
    SLOSReadinessCourt,
    SpecialistRole,
    VerificationSupercourt,
)
from superior_logic.finalization_kernel import FinalizationDirective, SLOSFinalizationKernel
from superior_logic.runtime_bridge import FederationRuntimeBridge, SandboxExecutionRequest


class PathBoundaryAdversarialTests(unittest.TestCase):
    def test_repograph_rejects_parent_escape(self):
        with self.assertRaises(ValueError):
            RepoGraph().build({"../escape.py": "x=1"})

    def test_workspace_rejects_absolute_write_path(self):
        with self.assertRaises(ValueError):
            PreparedWorkspaceForge().plan(
                base_revision="abc",
                repo_graph_sha256="graph",
                toolchain={},
                dependencies={},
                writable_paths=["/tmp/escape"],
            )

    def test_runtime_rejects_input_outside_write_set_before_executor_import(self):
        forge = PreparedWorkspaceForge()
        spec = forge.plan(
            base_revision="abc",
            repo_graph_sha256="graph",
            toolchain={},
            dependencies={},
            writable_paths=["allowed/"],
        )
        receipt = forge.verify(spec, observed_base_revision="abc", isolated=True, rollback_readback_ref="git:abc")
        with self.assertRaises(PermissionError):
            FederationRuntimeBridge().execute_disposable(
                spec,
                receipt,
                SandboxExecutionRequest("t", ("python", "-c", "print(1)"), {"other/x.py": "x=1"}, allowed_executables=("python",)),
                ledger_path="/tmp/never-created-ledger",
            )

    def test_runtime_rejects_unallowlisted_executable_before_executor_import(self):
        forge = PreparedWorkspaceForge()
        spec = forge.plan(
            base_revision="abc",
            repo_graph_sha256="graph",
            toolchain={},
            dependencies={},
            writable_paths=["allowed/x.txt"],
        )
        receipt = forge.verify(spec, observed_base_revision="abc", isolated=True, rollback_readback_ref="git:abc")
        with self.assertRaises(PermissionError):
            FederationRuntimeBridge().execute_disposable(
                spec,
                receipt,
                SandboxExecutionRequest("t", ("bash", "-lc", "echo x"), {"allowed/x.txt": "x"}, allowed_executables=("python",)),
                ledger_path="/tmp/never-created-ledger",
            )


class CoordinationAdversarialTests(unittest.TestCase):
    def test_fleet_dependency_cycle_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            CodingFleetPlanner().plan((
                FleetTask("a", SpecialistRole.IMPLEMENTER, ("a.py",), depends_on=("b",), mutation=True),
                FleetTask("b", SpecialistRole.TESTER, (), depends_on=("a",), mutation=False),
            ))

    def test_nested_mutation_domains_serialize(self):
        plan = CodingFleetPlanner().plan((
            FleetTask("parent", SpecialistRole.IMPLEMENTER, ("pkg/",), mutation=True),
            FleetTask("child", SpecialistRole.IMPLEMENTER, ("pkg/sub/x.py",), mutation=True),
        ))
        self.assertEqual(plan.serial_barriers, (("lane-child", "lane-parent"),))


class ProofAdversarialTests(unittest.TestCase):
    def test_high_court_cannot_inherit_independence_from_unrelated_check(self):
        required = VerificationSupercourt.POLICIES["HIGH"]
        rows = [CheckObservation(kind, True, f"proof:{kind.value}", independent=False) for kind in required]
        rows.append(CheckObservation(CheckKind.PERFORMANCE, True, "proof:perf", independent=True))
        verdict = VerificationSupercourt().evaluate("HIGH", rows)
        self.assertEqual(verdict.status, "INCOMPLETE_INDEPENDENCE")

    def test_readiness_cannot_promote_from_one_receiver(self):
        signals = [ReadinessSignal(signal, True, f"proof:{signal}", "same-runtime") for signal in SLOSReadinessCourt.REQUIRED]
        self.assertEqual(SLOSReadinessCourt().evaluate(signals).status, "INCOMPLETE_INDEPENDENT_RECEIVER")

    def test_any_failed_readiness_signal_rejects_even_when_all_present(self):
        signals = [
            ReadinessSignal(signal, signal != "ROLLBACK", f"proof:{signal}", "runtime-a" if i % 2 == 0 else "runtime-b")
            for i, signal in enumerate(SLOSReadinessCourt.REQUIRED)
        ]
        verdict = SLOSReadinessCourt().evaluate(signals)
        self.assertEqual(verdict.status, "REJECTED")
        self.assertEqual(verdict.failed, ("ROLLBACK",))


class CapabilityClosureAdversarialTests(unittest.TestCase):
    def test_high_risk_external_candidate_is_not_harvested(self):
        decision = AutonomousCapabilityClosure().decide(
            gap_id="gap-risk",
            required=("cap",),
            external=(ClosureCandidate("unsafe", "external", ("cap",), .99, .9, "spec:unsafe"),),
        )
        self.assertEqual(decision.action, ClosureAction.BUILD_SMALLEST_GAP)
        self.assertEqual(decision.selected, ())

    def test_unproven_external_candidate_is_not_harvested(self):
        decision = AutonomousCapabilityClosure().decide(
            gap_id="gap-proof",
            required=("cap",),
            external=(ClosureCandidate("weak", "external", ("cap",), .1, .1, "spec:weak"),),
        )
        self.assertEqual(decision.action, ClosureAction.BUILD_SMALLEST_GAP)


class DeterminismAdversarialTests(unittest.TestCase):
    def test_impact_depth_is_bounded(self):
        files = {
            "a.py": "def a(): return 1\n",
            "b.py": "from a import a\ndef b(): return a()\n",
            "c.py": "from b import b\ndef c(): return b()\n",
        }
        graph = RepoGraph().build(files)
        impact = RepoGraph().impact(graph, ["a.py"], depth=1)
        self.assertEqual(set(impact.impacted_paths), {"a.py", "b.py"})

    def test_finalization_blueprint_is_order_invariant(self):
        directive = FinalizationDirective(
            mission_id="deterministic",
            base_revision="abc",
            objective="verified coding runtime",
            required_capabilities=("repository_intelligence", "prepared_workspace", "coding_fleet", "verification_supercourt", "capability_closure"),
            optional_capabilities=("semantic_readback", "rollback"),
        )
        files_a = {"z.py": "def z(): pass\n", "a.py": "def a(): pass\n"}
        files_b = dict(reversed(list(files_a.items())))
        kwargs = dict(toolchain={"python": "3.12"}, dependencies={"pytest": "8.4.1"})
        one = SLOSFinalizationKernel().compile(directive, repository_files=files_a, **kwargs)
        two = SLOSFinalizationKernel().compile(directive, repository_files=files_b, **kwargs)
        self.assertEqual(one.blueprint_sha256, two.blueprint_sha256)
        self.assertEqual(one.repo_graph_sha256, two.repo_graph_sha256)


if __name__ == "__main__":
    unittest.main()
