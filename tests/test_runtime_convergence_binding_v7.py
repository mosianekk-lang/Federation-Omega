from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from bubbles.mission_proof_passport import MissionProofPassport, PassportEventKind
from federation.f130_authoritative_snapshot_compiler_v1 import (
    F130AuthoritativeSnapshotCompiler,
)
from federation.mission_ir import MissionIR
from federation.runtime_convergence_binding_v6 import RuntimeConvergenceReceiptV6
from federation.runtime_convergence_binding_v7 import RuntimeConvergenceBinderV7
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import (
    ProofEntry,
    ProofStatus,
    WorkItem,
    WorkStatus,
)
from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
PROOFOS_POLICY = ROOT / "governance/proofos_omega_policy_v1.json"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
MISSION = "M-FRCB-V7-001"
OBJECTIVE = "compile durable mission truth into an authoritative F130 terminal snapshot"
SOURCE = "main@" + ("a" * 40)


def _stable(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=lambda item: item.value if hasattr(item, "value") else str(item),
    )


def _digest(value):
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def selected_for(path: str) -> tuple[set[str], set[str]]:
    policy = ProofPolicy.from_path(PROOFOS_POLICY)
    impact = ImpactCompiler(policy).assess([path])
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        impact=impact,
    )
    return set(impact.impacted_subsystems), {item.test_id for item in manifest.selected_tests}


def v6_receipt(mission_id: str = MISSION) -> RuntimeConvergenceReceiptV6:
    boundary = {
        "provider_dispatch_verified": True,
        "provider_execution_verified": True,
        "provider_native_readback_verified": True,
        "provider_semantic_readback_verified": True,
        "expected_semantic_state_verified": True,
        "fdof_event_chain_verified": True,
        "provider_authority_created": False,
        "f130_terminal_completion_verified": False,
    }
    seed = RuntimeConvergenceReceiptV6(
        schema="FUSE-RUNTIME-CONVERGENCE-BINDING-V6",
        version="6.0.0",
        capability_id="FUSE-FRCB-006",
        mission_id=mission_id,
        objective=OBJECTIVE,
        authority_ceiling="A1_INTERNAL",
        stages=(),
        v5_receipt_digest="sha256:" + ("1" * 64),
        fdof_activation_receipt_digest="sha256:" + ("2" * 64),
        provider_execution_receipt_digest="sha256:" + ("3" * 64),
        provider_execution_id="provider-exec-v7",
        provider="provider-v7",
        provider_target="runtime:v7",
        provider_semantic_state="RUNNING",
        provider_correlation_id="provider-correlation-v7",
        provider_verified_at_epoch=3000,
        of50_receipt_digest="sha256:" + ("4" * 64),
        of50_completion_verified=False,
        provider_execution_verified=True,
        provider_semantic_readback_verified=True,
        f130_terminal_completion_verified=False,
        receipt_digest="",
        truth_boundary=boundary,
    )
    return replace(seed, receipt_digest=_digest(seed.deterministic_payload()))


def mission() -> MissionIR:
    return MissionIR(
        mission_id=MISSION,
        objective=OBJECTIVE,
        domain="SYSTEMS",
        outcome_contract="Authoritative terminal snapshot is derivable from durable evidence.",
        source_frontier=SOURCE,
        privacy_class="P1_INTERNAL",
        rights_state="AUTHORIZED_INTERNAL",
        effect_class="READ_ONLY",
        rollback_required=False,
        proof_requirements=("source", "semantic_readback"),
        metadata={"authority_ceiling": "A1_INTERNAL"},
    ).normalized()


def build_ready_runtime(root: str):
    runtime = DurableMissionRuntimeV1(
        root,
        source_frontier=SOURCE,
        policy_sha256="policy-v7",
        environment_sha256="environment-v7",
    )
    item = mission()
    projection = runtime.open(
        item,
        required_proof_axes=("source",),
        trace_id="trace-v7",
    )
    runtime.bind_proof(
        MISSION,
        ProofEntry.create(
            axis="source",
            status=ProofStatus.PROVEN,
            evidence_refs=(SOURCE,),
            claim_limit="Source binding only.",
        ),
    )
    runtime.set_work_item(
        MISSION,
        WorkItem.create(
            work_id="WORK-V7",
            lane="convergence",
            objective="Close one durable convergence work item.",
            status=WorkStatus.READY,
        ),
    )
    runtime.update_work_status(
        MISSION,
        "WORK-V7",
        WorkStatus.VERIFIED,
        result_refs=("proof:work-v7",),
    )
    runtime.verify_success(
        MISSION,
        item.outcome_contract,
        evidence_refs=("proof:success-v7",),
    )

    passport = MissionProofPassport(runtime)
    passport.record(
        MISSION,
        PassportEventKind.SOURCE,
        state="VERIFIED",
        proof_refs=(SOURCE,),
        idempotency_key="passport-source-v7",
    )
    passport.record(
        MISSION,
        PassportEventKind.SEMANTIC_READBACK,
        state="PROVIDER_SEMANTIC_READBACK_VERIFIED",
        proof_refs=("provider:semantic-readback-v7",),
        data={"provider": "provider-v7"},
        idempotency_key="passport-readback-v7",
    )
    passport.record(
        MISSION,
        PassportEventKind.FINAL,
        state="VERIFIED",
        proof_refs=("proof:passport-final-v7",),
        idempotency_key="passport-final-v7",
    )
    return runtime, passport


class F130AuthoritativeSnapshotCompilerTests(unittest.TestCase):
    def test_compiler_derives_terminal_truth_from_durable_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            compiled = F130AuthoritativeSnapshotCompiler().compile(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=v6_receipt(),
            )
            self.assertTrue(compiled.receipt.verify())
            self.assertTrue(compiled.receipt.objective_satisfied)
            self.assertTrue(compiled.snapshot.objective_satisfied)
            self.assertEqual(MISSION, compiled.snapshot.current_mission_id)
            self.assertEqual(
                runtime.ledger.verify()["head_hash"],
                compiled.receipt.ledger_head_hash,
            )
            required_done = [
                task
                for task in compiled.snapshot.tasks
                if task.required and task.state.value == "DONE"
            ]
            self.assertTrue(required_done)
            self.assertTrue(
                all(task.required_proof_ids for task in required_done)
            )
            self.assertFalse(
                compiled.receipt.truth_boundary["caller_terminal_booleans_accepted"]
            )

    def test_pending_request_blocks_authoritative_terminality(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            runtime.request(
                MISSION,
                step_id="approval",
                request_type="BOUNDED_INPUT",
                target="provider:v7",
                reason="One bounded current input remains.",
                input_identity={"need": "bounded-input"},
                continuation_key="continue-v7",
            )
            compiled = F130AuthoritativeSnapshotCompiler().compile(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=v6_receipt(),
            )
            self.assertFalse(compiled.snapshot.objective_satisfied)
            self.assertIn(
                "PENDING_REQUEST:",
                "|".join(compiled.receipt.compiler_gaps),
            )
            pending = [
                task
                for task in compiled.snapshot.tasks
                if task.task_id.startswith("PENDING_REQUEST::")
            ]
            self.assertEqual(1, len(pending))
            self.assertTrue(pending[0].required)
            self.assertEqual("BLOCKED", pending[0].state.value)

    def test_verified_work_without_result_proof_is_not_done(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            runtime.set_work_item(
                MISSION,
                WorkItem.create(
                    work_id="WORK-NO-PROOF",
                    lane="verify",
                    objective="This work must not become DONE without evidence.",
                    status=WorkStatus.VERIFIED,
                ),
            )
            compiled = F130AuthoritativeSnapshotCompiler().compile(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=v6_receipt(),
            )
            task = next(
                item
                for item in compiled.snapshot.tasks
                if item.task_id == "WORK-NO-PROOF"
            )
            self.assertEqual("BLOCKED", task.state.value)
            self.assertFalse(compiled.snapshot.objective_satisfied)
            self.assertIn(
                "WORK_RESULT_PROOF:WORK-NO-PROOF",
                compiled.receipt.compiler_gaps,
            )

    def test_incomplete_passport_blocks_authoritative_terminality(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, _passport = build_ready_runtime(td)
            incomplete = MissionProofPassport(runtime)
            # A new passport projects the same durable ledger, so remove the FINAL
            # evidence by constructing a fresh mission instead.
        with tempfile.TemporaryDirectory() as td:
            runtime = DurableMissionRuntimeV1(
                td,
                source_frontier=SOURCE,
                policy_sha256="policy-v7",
                environment_sha256="environment-v7",
            )
            item = mission()
            runtime.open(item, required_proof_axes=("source",))
            runtime.bind_proof(
                MISSION,
                ProofEntry.create(
                    axis="source",
                    status=ProofStatus.PROVEN,
                    evidence_refs=(SOURCE,),
                ),
            )
            runtime.verify_success(
                MISSION,
                item.outcome_contract,
                evidence_refs=("proof:success-v7",),
            )
            passport = MissionProofPassport(runtime)
            passport.record(
                MISSION,
                PassportEventKind.SEMANTIC_READBACK,
                state="PROVIDER_SEMANTIC_READBACK_VERIFIED",
                proof_refs=("provider:readback",),
            )
            compiled = F130AuthoritativeSnapshotCompiler().compile(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=v6_receipt(),
            )
            self.assertFalse(compiled.snapshot.objective_satisfied)
            self.assertIn(
                "MISSION_PROOF_PASSPORT_NOT_COMPLETE",
                compiled.receipt.compiler_gaps,
            )

    def test_v6_mission_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            with self.assertRaisesRegex(
                ValueError,
                "F130_AUTHORITATIVE_V6_MISSION_MISMATCH",
            ):
                F130AuthoritativeSnapshotCompiler().compile(
                    runtime=runtime,
                    passport=passport,
                    mission_id=MISSION,
                    v6_receipt=v6_receipt("OTHER-MISSION"),
                )


class RuntimeConvergenceBindingV7Tests(unittest.TestCase):
    def test_v7_snapshot_receipt_stays_nonterminal_before_f130_commit(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            result = RuntimeConvergenceBinderV7().evaluate(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=v6_receipt(),
            )
            self.assertTrue(result.convergence_receipt.verify())
            self.assertTrue(
                result.convergence_receipt.authoritative_snapshot_verified
            )
            self.assertTrue(result.convergence_receipt.provider_execution_verified)
            self.assertTrue(
                result.convergence_receipt.provider_semantic_readback_verified
            )
            self.assertFalse(
                result.convergence_receipt.f130_terminal_completion_verified
            )
            self.assertFalse(result.convergence_receipt.completion_verified)

    def test_f130_prepare_and_commit_reach_complete_verified_on_unchanged_state(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            binder = RuntimeConvergenceBinderV7()
            provider = v6_receipt()
            prepared = binder.prepare_terminal(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=provider,
                now_epoch=4000.0,
            )
            self.assertTrue(prepared.verify())
            result = binder.commit_terminal(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=provider,
                prepared=prepared,
                now_epoch=4001.0,
            )
            self.assertEqual("COMPLETE_VERIFIED", result.f130_action)
            self.assertTrue(result.completion_verified)
            self.assertTrue(result.f130_receipt_digest.startswith("sha256:"))
            self.assertTrue(result.terminal_receipt_digest.startswith("sha256:"))

    def test_durable_state_change_after_prepare_blocks_replayed_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            binder = RuntimeConvergenceBinderV7()
            provider = v6_receipt()
            prepared = binder.prepare_terminal(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=provider,
                now_epoch=4000.0,
            )
            runtime.engine.record_source_decision(
                MISSION,
                {"decision": "current durable state changed after terminal prepare"},
            )
            with self.assertRaisesRegex(
                ValueError,
                "F130_AUTHORITATIVE_SNAPSHOT_DRIFT",
            ):
                binder.commit_terminal(
                    runtime=runtime,
                    passport=passport,
                    mission_id=MISSION,
                    v6_receipt=provider,
                    prepared=prepared,
                    now_epoch=4001.0,
                )

    def test_new_pending_request_after_prepare_blocks_replay(self):
        with tempfile.TemporaryDirectory() as td:
            runtime, passport = build_ready_runtime(td)
            binder = RuntimeConvergenceBinderV7()
            provider = v6_receipt()
            prepared = binder.prepare_terminal(
                runtime=runtime,
                passport=passport,
                mission_id=MISSION,
                v6_receipt=provider,
                now_epoch=4000.0,
            )
            runtime.request(
                MISSION,
                step_id="late-input",
                request_type="INPUT",
                target="provider:v7",
                reason="New current dependency appeared.",
                input_identity={"late": True},
                continuation_key="late-v7",
            )
            with self.assertRaisesRegex(
                ValueError,
                "F130_AUTHORITATIVE_SNAPSHOT_DRIFT",
            ):
                binder.commit_terminal(
                    runtime=runtime,
                    passport=passport,
                    mission_id=MISSION,
                    v6_receipt=provider,
                    prepared=prepared,
                    now_epoch=4001.0,
                )


class RuntimeConvergenceBindingV7ProofOSTests(unittest.TestCase):
    def test_v6_change_impacts_v7(self):
        impacted, selected = selected_for("federation/runtime_convergence_binding_v6.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V7", impacted)
        self.assertIn("runtime_convergence_binding_v7", selected)

    def test_durable_runtime_change_impacts_v7(self):
        impacted, selected = selected_for(
            "formation_omega/durable_mission_runtime_v1.py"
        )
        self.assertIn("FUSE_F130_AUTHORITATIVE_SNAPSHOT_V1", impacted)
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V7", impacted)
        self.assertIn("runtime_convergence_binding_v7", selected)

    def test_passport_change_impacts_v7(self):
        impacted, selected = selected_for("bubbles/mission_proof_passport.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V7", impacted)
        self.assertIn("runtime_convergence_binding_v7", selected)

    def test_f130_interlock_change_impacts_v7(self):
        impacted, selected = selected_for(
            "federation/fuse_mission_runtime_interlock_v1.py"
        )
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V7", impacted)
        self.assertIn("runtime_convergence_binding_v7", selected)


if __name__ == "__main__":
    unittest.main()
