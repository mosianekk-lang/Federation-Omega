import json
from pathlib import Path
import tempfile
import unittest

from federation.autonomic_completion_v5 import (
    AutonomicCompletionKernel,
    ExecutionContext,
    RuntimeMode,
    WorkPacket,
)
from federation.federation_learning_v1 import FederationLearningLedger
from federation.prompt_scientist_v2 import PromptGenome
from federation.run_store_v1 import RunStore
from federation.terminal_debt_v1 import (
    AutonomousDebtBurner,
    DebtOutcome,
    DebtState,
    TerminalDebtLedger,
    TerminalDebtSpec,
    specs_from_profile,
)


ROOT = Path(__file__).resolve().parents[1]


def genome():
    return PromptGenome(
        "FINALITY-V2",
        "V5",
        {
            "OWNER_AUTHORITY": "IMMUTABLE",
            "PROOF_FLOOR": "IMMUTABLE",
            "SECURITY_FLOOR": "IMMUTABLE",
            "PRIVACY_FLOOR": "IMMUTABLE",
            "OUTPUT_POLICY": "ZERO_MANDATORY_TERMINAL_DEBT",
        },
    )


class TerminalDebtV1Tests(unittest.TestCase):
    def test_terminal_debt_persists_and_requires_zero_open_debt(self):
        with tempfile.TemporaryDirectory() as td:
            store = RunStore(Path(td) / "run.db")
            ledger = TerminalDebtLedger(store)
            specs = (
                TerminalDebtSpec("A", "A", required_maturity=("SOURCE", "RUNTIME")),
                TerminalDebtSpec("B", "B", dependencies=("A",), required_maturity=("SEMANTIC",)),
            )
            items = ledger.reconcile("M1", specs, {"A": {"SOURCE": True}})
            assert {x.spec.debt_id for x in items} == {"A", "B"}
            assert ledger.terminal_zero("M1") is False
            rows = store.terminal_debts("M1")
            assert len(rows) == 2
            assert store.terminal_debt_counts("M1")["OPEN"] == 2
    
            ledger.reconcile("M1", specs, {"A": True, "B": True})
            assert ledger.terminal_zero("M1") is True
            assert store.terminal_debt_counts("M1")["CLOSED"] == 2
    
    
    def test_ready_plan_respects_dependencies_collisions_and_owner_authority(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = TerminalDebtLedger(RunStore(Path(td) / "run.db"))
            specs = (
                TerminalDebtSpec("A", "A", collision_keys=("source:x",), required_maturity=("SEMANTIC",), priority=100),
                TerminalDebtSpec("B", "B", collision_keys=("source:x",), required_maturity=("SEMANTIC",), priority=90),
                TerminalDebtSpec("C", "C", collision_keys=("source:y",), required_maturity=("SEMANTIC",), priority=80),
                TerminalDebtSpec("D", "D", dependencies=("A",), required_maturity=("SEMANTIC",), priority=100),
                TerminalDebtSpec("OWNER", "OWNER", owner_only=True, required_maturity=("SEMANTIC",), priority=1000),
            )
            ledger.reconcile("M2", specs, {})
            plan = ledger.burn_plan("M2", owner_authority=False, limit=8)
            ids = {x.spec.debt_id for x in plan}
            assert "OWNER" not in ids
            assert "D" not in ids
            assert "A" in ids
            assert "B" not in ids
            assert "C" in ids
    
    
    def test_debt_burner_closes_only_evidence_complete_debt(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = TerminalDebtLedger(RunStore(Path(td) / "run.db"))
            spec = TerminalDebtSpec("A", "A", family="TEST", required_maturity=("TEST", "SEMANTIC"))
            ledger.reconcile("M3", (spec,), {})
            burner = AutonomousDebtBurner(
                ledger,
                {
                    "TEST": lambda item: DebtOutcome(
                        True,
                        evidence_refs=("proof:test", "proof:semantic"),
                        passed_maturity=("TEST", "SEMANTIC"),
                    )
                },
            )
            result = burner.burn_wave("M3")
            assert len(result) == 1
            assert result[0].state is DebtState.CLOSED
            assert ledger.terminal_zero("M3") is True
    
    
    def test_autonomic_kernel_refuses_terminal_success_while_debt_open_then_auto_recompiles(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = {"PRODUCT": False}
            store = RunStore(Path(td) / "run.db")
            ledger = TerminalDebtLedger(store)
            learning = FederationLearningLedger(Path(td) / "learn.jsonl")
    
            def debt_specs(ctx):
                return (
                    TerminalDebtSpec(
                        "PRODUCT",
                        "PRODUCT",
                        family="PRODUCT",
                        required_maturity=("SEMANTIC",),
                        priority=100,
                    ),
                )
    
            def debt_evidence(ctx):
                return {"PRODUCT": evidence["PRODUCT"]}
    
            def recompiler(ctx, gaps):
                assert "PRODUCT" in gaps
                if any(p.packet_id == "PROVE-PRODUCT" for p in ctx.packets):
                    return ctx
                return ExecutionContext(
                    ctx.mission_id,
                    ctx.mission_class,
                    ctx.target_state,
                    ctx.runtime_mode,
                    ctx.prompt_genome,
                    ctx.packets + (
                        WorkPacket(
                            "PROVE-PRODUCT",
                            dependencies=tuple(p.packet_id for p in ctx.packets),
                        ),
                    ),
                    ctx.current_maturity,
                    ctx.owner_effect_authority,
                    ctx.maximum_parallelism,
                    dict(ctx.commercial_evidence),
                    ctx.commercial_applicable_gates,
                )
    
            def executor(packet):
                if packet.packet_id == "PROVE-PRODUCT":
                    evidence["PRODUCT"] = True
                    return True, "proof:product"
                return True, "proof:build"
    
            kernel = AutonomicCompletionKernel(
                store,
                learning,
                mission_recompiler=recompiler,
                terminal_debt_ledger=ledger,
                terminal_debt_spec_provider=debt_specs,
                terminal_debt_evidence_provider=debt_evidence,
            )
            ctx = ExecutionContext(
                "M4",
                "BUILD",
                "COMMERCIAL_READY_VERIFIED",
                RuntimeMode.CURRENT_RUN,
                genome(),
                (WorkPacket("BUILD"),),
                commercial_evidence={"FUNCTIONALITY": True},
                commercial_applicable_gates=("FUNCTIONALITY",),
            )
            results = kernel.execute_until_boundary(ctx, executor, max_cycles=5)
            assert results[0].terminal_state == ""
            assert results[0].recompile_required is True
            assert "PRODUCT" in results[0].maturity_gaps
            assert results[-1].terminal_state == "COMMERCIAL_READY_VERIFIED"
            assert ledger.terminal_zero("M4") is True
            checkpoint = store.read("M4")
            assert checkpoint is not None
            assert checkpoint.state["terminal_debt_zero"] is True
    
    
    def test_local_sovereign_ai_profile_is_dependency_closed_and_has_required_finality_predicates(self):
        profile = json.loads(
            (ROOT / "governance" / "fuse_local_sovereign_ai_finality_v2.json").read_text(encoding="utf-8")
        )
        specs = specs_from_profile(profile)
        ids = {x.debt_id for x in specs}
        required = {
            "FUSE_EXE_WINDOWS_PRODUCT",
            "LOCAL_CHAT",
            "OPENAI_DISABLED_VERIFIED",
            "OFFLINE_CORE_VERIFIED",
            "GOOGLE_DRIVE_RELEASE",
            "CROSS_PC_INSTALL",
            "UPDATE_ROLLBACK_LKG",
            "BACKUP_RESTORE",
            "SECURITY_PRIVACY_COURTS",
            "NATURAL_OWNER_WORKLOAD",
            "COMMERCIAL_READY_VERIFIED",
        }
        assert required <= ids
        for spec in specs:
            assert set(spec.dependencies) <= ids
    
        graph = {spec.debt_id: set(spec.dependencies) for spec in specs}
        visiting, visited = set(), set()
    
        def visit(node):
            if node in visiting:
                raise AssertionError(f"cycle:{node}")
            if node in visited:
                return
            visiting.add(node)
            for dep in graph[node]:
                visit(dep)
            visiting.remove(node)
            visited.add(node)
    
        for node in graph:
            visit(node)
    
        final = next(x for x in specs if x.debt_id == "COMMERCIAL_READY_VERIFIED")
        assert "COMMERCIAL_PRODUCT_UX" in final.dependencies
        assert "COMMERCIAL_RELEASE_ENGINEERING" in final.dependencies
    


if __name__ == "__main__":
    unittest.main()
