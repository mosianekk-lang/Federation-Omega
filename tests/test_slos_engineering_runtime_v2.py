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
    RepoGraph,
    ReadinessSignal,
    SLOSReadinessCourt,
    SpecialistRole,
    VerificationSupercourt,
)


class RepoGraphTests(unittest.TestCase):
    def test_python_symbol_dependency_and_impact(self):
        files = {
            "pkg/a.py": "def alpha():\n    return 1\n",
            "pkg/b.py": "from pkg.a import alpha\ndef beta():\n    return alpha()\n",
            "pkg/c.py": "from pkg.b import beta\ndef gamma():\n    return beta()\n",
        }
        graph = RepoGraph().build(files)
        self.assertTrue(graph.graph_sha256)
        impact = RepoGraph().impact(graph, ["pkg/a.py"], depth=3)
        self.assertEqual(set(impact.impacted_paths), set(files))
        self.assertIn("pkg/a.py", RepoGraph().ranked_context(graph, "alpha"))

    def test_graph_deterministic(self):
        files = {"z.py": "def z(): pass", "a.py": "def a(): pass"}
        self.assertEqual(RepoGraph().build(files).graph_sha256, RepoGraph().build(dict(reversed(list(files.items())))).graph_sha256)


class WorkspaceTests(unittest.TestCase):
    def test_content_addressed_and_rollback_bound(self):
        forge = PreparedWorkspaceForge()
        spec = forge.plan(
            base_revision="abc123",
            repo_graph_sha256="deadbeef",
            toolchain={"python": "3.12"},
            dependencies={"pytest": "8.4.1"},
            writable_paths=["superior_logic/new.py"],
        )
        receipt = forge.verify(spec, observed_base_revision="abc123", isolated=True, rollback_readback_ref="git:abc123", artifact_refs=["proof:1"])
        self.assertTrue(receipt.prepared)
        self.assertTrue(receipt.rollback_verified)


class FleetTests(unittest.TestCase):
    def test_conflicting_mutations_serialize(self):
        tasks = [
            FleetTask("a", SpecialistRole.IMPLEMENTER, ("pkg/a.py",), mutation=True),
            FleetTask("b", SpecialistRole.IMPLEMENTER, ("pkg/a.py",), mutation=True),
            FleetTask("c", SpecialistRole.TESTER, ("tests/",), depends_on=("a", "b"), mutation=False),
        ]
        plan = CodingFleetPlanner().plan(tasks)
        self.assertEqual(len(plan.serial_barriers), 1)
        self.assertEqual(plan.fan_in_order[-1], "lane-c")

    def test_disjoint_mutations_do_not_serialize(self):
        tasks = [
            FleetTask("a", SpecialistRole.IMPLEMENTER, ("pkg/a.py",), mutation=True),
            FleetTask("b", SpecialistRole.IMPLEMENTER, ("pkg/b.py",), mutation=True),
        ]
        self.assertEqual(CodingFleetPlanner().plan(tasks).serial_barriers, ())


class SupercourtTests(unittest.TestCase):
    def test_high_requires_independent_semantic_readback(self):
        required = VerificationSupercourt.POLICIES["HIGH"]
        rows = [CheckObservation(kind, True, f"proof:{kind.value}", independent=(kind == CheckKind.SEMANTIC_READBACK)) for kind in required]
        verdict = VerificationSupercourt().evaluate("HIGH", rows)
        self.assertEqual(verdict.status, "PROVEN")

    def test_hard_failure_rejects(self):
        rows = [
            CheckObservation(CheckKind.SYNTAX, True, "p:syntax"),
            CheckObservation(CheckKind.UNIT, False, "p:unit"),
            CheckObservation(CheckKind.SEMANTIC_READBACK, True, "p:read", independent=True),
        ]
        self.assertEqual(VerificationSupercourt().evaluate("LOW", rows).status, "REJECTED")


class ClosureTests(unittest.TestCase):
    def test_internal_composition_precedes_external(self):
        engine = AutonomousCapabilityClosure()
        decision = engine.decide(
            gap_id="gap-1",
            required=("graph", "workspace"),
            internal=(
                ClosureCandidate("i1", "internal", ("graph",), .9, .1, "git:i1"),
                ClosureCandidate("i2", "internal", ("workspace",), .9, .1, "git:i2"),
            ),
            external=(ClosureCandidate("e1", "external", ("graph", "workspace"), .9, .1, "spec:e1"),),
        )
        self.assertEqual(decision.action, ClosureAction.COMPOSE_INTERNAL)
        self.assertEqual(decision.residual, ())

    def test_external_harvest_not_direct_authority(self):
        decision = AutonomousCapabilityClosure().decide(
            gap_id="gap-2",
            required=("newcap",),
            external=(ClosureCandidate("e1", "external", ("newcap",), .9, .1, "paper:e1"),),
        )
        self.assertEqual(decision.action, ClosureAction.HARVEST_MECHANISM)


class ReadinessTests(unittest.TestCase):
    def test_complete_requires_two_receivers(self):
        signals = []
        for i, signal in enumerate(SLOSReadinessCourt.REQUIRED):
            signals.append(ReadinessSignal(signal, True, f"proof:{signal}", "runtime-a" if i % 2 == 0 else "runtime-b"))
        verdict = SLOSReadinessCourt().evaluate(signals)
        self.assertEqual(verdict.status, "SLOS_ENGINEERING_RUNTIME_READY")

    def test_missing_signal_holds(self):
        signals = [ReadinessSignal("SOURCE_ADMISSION", True, "proof:x", "a")]
        self.assertEqual(SLOSReadinessCourt().evaluate(signals).status, "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()

class RuntimeBridgeTests(unittest.TestCase):
    def test_runtime_bridge_requires_prepared_workspace(self):
        import sys, types
        from superior_logic.engineering_runtime import WorkspaceReceipt
        from superior_logic.runtime_bridge import FederationRuntimeBridge, SandboxExecutionRequest
        forge = PreparedWorkspaceForge()
        spec = forge.plan(base_revision='a', repo_graph_sha256='b', toolchain={}, dependencies={}, writable_paths=['out.txt'])
        bad = WorkspaceReceipt(spec.workspace_id, False, True, True, True, (), 'x')
        with self.assertRaises(PermissionError):
            FederationRuntimeBridge().execute_disposable(spec, bad, SandboxExecutionRequest('t', ('python',), {'out.txt':'x'}), ledger_path='x')

    def test_runtime_bridge_uses_admitted_interface_contract(self):
        import sys, types
        from superior_logic.runtime_bridge import FederationRuntimeBridge, SandboxExecutionRequest
        calls = {}
        fake = types.ModuleType('alpha_omega_v30.sandbox_fleet')
        class SandboxPolicy:
            def __init__(self, **kwargs): calls['policy'] = kwargs
        class ReceiptLedger:
            def __init__(self, path): calls['ledger'] = path
        class SandboxTask:
            def __init__(self, **kwargs): self.kwargs=kwargs
        class OperationalSandbox:
            def __init__(self, policy, ledger): pass
            def run(self, task):
                calls['task'] = task.kwargs
                return {'status':'PASS','execution_verified':True,'readback_verified':True,'rollback_verified':True,'persistence_verified':True,'result_hash':'rh','ledger_entry_hash':'lh'}
        fake.SandboxPolicy=SandboxPolicy; fake.ReceiptLedger=ReceiptLedger; fake.SandboxTask=SandboxTask; fake.OperationalSandbox=OperationalSandbox
        parent = types.ModuleType('alpha_omega_v30')
        sys.modules['alpha_omega_v30']=parent
        sys.modules['alpha_omega_v30.sandbox_fleet']=fake
        forge=PreparedWorkspaceForge()
        spec=forge.plan(base_revision='a',repo_graph_sha256='b',toolchain={},dependencies={},writable_paths=['out.txt'])
        receipt=forge.verify(spec,observed_base_revision='a',isolated=True,rollback_readback_ref='git:a')
        result=FederationRuntimeBridge().execute_disposable(spec,receipt,SandboxExecutionRequest('t',('python',),{'out.txt':'x'},('out.txt',),('python',),2),ledger_path='/tmp/l')
        self.assertEqual(result.status,'PASS')
        self.assertTrue(result.rollback_verified)
        self.assertEqual(calls['task']['export_paths'],('out.txt',))
