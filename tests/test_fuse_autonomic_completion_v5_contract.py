from pathlib import Path
import tempfile
import unittest

from federation.autonomic_completion_v5 import (
    AutonomicCompletionKernel,
    ExecutionContext,
    OutputClass,
    RuntimeMode,
    WorkPacket,
)
from federation.commercial_maturity_v1 import CommercialMaturityController
from federation.federation_learning_v1 import FederationLearningLedger
from federation.prompt_scientist_v2 import PromptGenome
from federation.run_store_v1 import RunStore


def genome():
    return PromptGenome("V5.0.1", "V4.0.0", {
        "OWNER_AUTHORITY":"IMMUTABLE",
        "PROOF_FLOOR":"IMMUTABLE",
        "SECURITY_FLOOR":"IMMUTABLE",
        "PRIVACY_FLOOR":"IMMUTABLE",
        "TRUTH_BOUNDARIES":"IMMUTABLE",
        "PROVIDER_NATIVE_PROOF":"IMMUTABLE",
        "ROLLBACK_REQUIREMENTS":"IMMUTABLE",
        "OUTPUT_POLICY":"NON_TERMINAL_PROGRESS_CONTINUES",
        "RUNTIME_REENTRY":"PERSIST_OR_RESUME_CAPSULE",
        "LEARNING_CALLBACK":"EACH_MATERIAL_CYCLE",
        "MATURITY_POLICY":"COMMERCIAL_READY_VERIFIED",
    })


class FuseAutonomicCompletionV5ContractTests(unittest.TestCase):
    def test_progress_is_nonterminal_and_exact_cycles_continue(self):
        with tempfile.TemporaryDirectory() as td:
            store=RunStore(Path(td)/"run.db")
            ledger=FederationLearningLedger(Path(td)/"learn.jsonl")
            kernel=AutonomicCompletionKernel(store, ledger)
            packets=tuple(WorkPacket(f"P{i}", (() if i == 0 else (f"P{i-1}",))) for i in range(4))
            ctx=ExecutionContext(
                "V5-CONTRACT", "BUILD", "COMMERCIAL_READY_VERIFIED",
                RuntimeMode.CURRENT_RUN, genome(), packets,
                current_maturity="LOCAL_TESTED",
                commercial_evidence={"FUNCTIONALITY": True},
                commercial_applicable_gates=("FUNCTIONALITY",),
            )
            results=kernel.execute_until_boundary(ctx, lambda p: (True, f"proof:{p.packet_id}"))
            self.assertEqual(len(results), 4)
            self.assertTrue(all(r.telemetry.output_class == OutputClass.PROGRESS_UPDATE.value for r in results[:-1]))
            self.assertEqual(results[-1].terminal_state, "COMMERCIAL_READY_VERIFIED")
            self.assertEqual(ledger.verify(), (True, 4))

    def test_packet_completion_cannot_fake_commercial_maturity(self):
        with tempfile.TemporaryDirectory() as td:
            kernel=AutonomicCompletionKernel(
                RunStore(Path(td)/"run.db"),
                FederationLearningLedger(Path(td)/"learn.jsonl"),
            )
            ctx=ExecutionContext(
                "V5-MATURITY", "BUILD", "COMMERCIAL_READY_VERIFIED",
                RuntimeMode.CURRENT_RUN, genome(), (WorkPacket("BUILD"),),
                current_maturity="LOCAL_TESTED",
                commercial_evidence={"FUNCTIONALITY": True},
                commercial_applicable_gates=("FUNCTIONALITY", "SECURITY", "RELIABILITY"),
            )
            result=kernel.run_cycle(ctx, cycle=1, packet_executor=lambda p: (True, "proof:build"))
            self.assertEqual(result.terminal_state, "")
            self.assertTrue(result.recompile_required)
            self.assertEqual(result.maturity_gaps, ("SECURITY", "RELIABILITY"))
            self.assertEqual(result.context.current_maturity, "LOCAL_TESTED")

    def test_commercial_court_is_explicit_and_complete(self):
        court=CommercialMaturityController(("FUNCTIONALITY","SECURITY","RELIABILITY"))
        self.assertEqual(
            court.evaluate({"FUNCTIONALITY":True,"SECURITY":True}).state,
            "COMMERCIAL_MATURITY_OPEN",
        )
        self.assertEqual(
            court.evaluate({"FUNCTIONALITY":True,"SECURITY":True,"RELIABILITY":True}).state,
            "COMMERCIAL_READY_VERIFIED",
        )

    def test_owner_reserved_effect_remains_held(self):
        with tempfile.TemporaryDirectory() as td:
            kernel=AutonomicCompletionKernel(
                RunStore(Path(td)/"run.db"),
                FederationLearningLedger(Path(td)/"learn.jsonl"),
            )
            ctx=ExecutionContext(
                "V5-AUTH", "DEPLOY", "PRODUCTION_VERIFIED",
                RuntimeMode.CURRENT_RUN, genome(),
                (WorkPacket("SAFE"), WorkPacket("EFFECT", effect_class="EXTERNAL_EFFECT", owner_reserved=True)),
                owner_effect_authority=False,
            )
            result=kernel.run_cycle(ctx, cycle=1, packet_executor=lambda p: (True, p.packet_id))
            states={p.packet_id:p.done for p in result.context.packets}
            self.assertTrue(states["SAFE"])
            self.assertFalse(states["EFFECT"])


if __name__ == "__main__":
    unittest.main()
