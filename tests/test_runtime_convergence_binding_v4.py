from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ALPHA_SRC = ROOT / "systems" / "alpha-omega-turnkey" / "src"
if str(ALPHA_SRC) not in sys.path:
    sys.path.insert(0, str(ALPHA_SRC))

from alpha_omega import AlphaOmegaEngine
from alpha_omega.frcb_lifecycle_adapter import execute_local_build_for_frcb
from alpha_omega.of50_adapter import compile_of50_alpha_omega_packet

from evidenceops.innovation_engine.algorithms_common import AUTHORITY_CEILING, sha256
from evidenceops.innovation_engine.foundry_model import FoundryCycleResult
from evidenceops.innovation_engine.of50_adapter import compile_of50_formation_decision
from federation.aarek_v1 import MissionSnapshot
from federation.alpha_omega_lifecycle_binding_v1 import verify_local_artifacts
from federation.oh50_producer_adapter_v1 import OH50ProducerAdapter
from federation.of50_ace_v1 import (
    Authority,
    ExecutionProof,
    OF50CycleRequest,
    ProofTier,
)
from federation.runtime_convergence_binding_v4 import (
    RuntimeConvergenceBinderV4,
    StageStateV4,
)
from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


PROOFOS_POLICY = ROOT / "governance/proofos_omega_policy_v1.json"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
MISSION = "M-FRCB-V4-001"
OBJECTIVE = "bind actual Alpha-Omega local BUILD evidence into convergence truth"


def selected_for(path: str) -> tuple[set[str], set[str]]:
    policy = ProofPolicy.from_path(PROOFOS_POLICY)
    impact = ImpactCompiler(policy).assess([path])
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        impact=impact,
    )
    return set(impact.impacted_subsystems), {item.test_id for item in manifest.selected_tests}


def foundry_result() -> FoundryCycleResult:
    proof = {
        "registry_chain": "PASSED",
        "learning_chain": {
            "status": "PASSED",
            "event_count": 1,
            "ledger_head_hash": "learning-head",
            "errors": [],
        },
        "evolution_chain": {
            "status": "PASSED",
            "event_count": 1,
            "ledger_head_hash": "evolution-head",
            "errors": [],
        },
        "algorithm_result_receipts": ["a" * 64],
        "source_signal_count": 1,
        "learning_event_count": 1,
        "authority_ceiling": AUTHORITY_CEILING,
        "external_effect": False,
    }
    proof["proof_sha256"] = sha256(proof)
    return FoundryCycleResult(
        cycle_id="FC-FRCB-V4-001",
        status="PASSED",
        algorithm_results=(),
        opportunity_count=0,
        innovation_delta={"marker": "v4"},
        learning_delta={"events_recorded": 1},
        maturity="LOCAL_DETERMINISTIC_FOUNDRY_EVOLUTION_AND_REPLICATION_CANARY_PASSED",
        proof=proof,
        authority_ceiling=AUTHORITY_CEILING,
        external_effect=False,
    )


def formation(foundry: FoundryCycleResult, *, implementation_required: bool = True):
    return compile_of50_formation_decision(
        mission_id=MISSION,
        foundry_result=foundry,
        route_candidates=(
            {
                "route_id": "R1",
                "route_family": "BUILD",
                "score": 0.9,
                "falsifier": "build does not satisfy proof gates",
                "capability_hypothesis": "local build can close source implementation debt",
            },
            {
                "route_id": "R2",
                "route_family": "REPAIR",
                "score": 0.7,
                "falsifier": "repair cannot preserve rollback",
                "capability_hypothesis": "repair existing artifacts",
            },
        ),
        selected_route_id="R1",
        reuse_vs_build="PERMANENT_BUILD" if implementation_required else "REUSE",
        selected_capability_hypothesis="local build can close source implementation debt",
        implementation_required=implementation_required,
    )


def snapshot() -> MissionSnapshot:
    return MissionSnapshot(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
    )


def request(manifest, decision, packet, **overrides) -> OF50CycleRequest:
    base = dict(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
        owner_protection_decision="CONTINUE_AUTOMATICALLY",
        owner_protection_violations=(),
        aarek_receipt_ref="",
        swarm_manifest=manifest,
        formation_decision=decision,
        alpha_omega_packet=packet,
        execution_proof=ExecutionProof(executed=False, proof_tier=ProofTier.SOURCE),
        required_outcomes=("O1",),
        proven_outcomes=(),
        completion_requested=False,
    )
    base.update(overrides)
    return OF50CycleRequest(**base)


class RuntimeConvergenceBindingV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.engine = AlphaOmegaEngine(self.temp.name)
        self.foundry = foundry_result()
        self.formation = formation(self.foundry, implementation_required=True)
        self.oh50 = OH50ProducerAdapter().produce(
            mission_id=MISSION,
            objective=OBJECTIVE,
            required_capabilities=("build", "proof", "rollback"),
        )
        self.alpha = compile_of50_alpha_omega_packet(
            self.engine,
            mission_id=MISSION,
            objective=OBJECTIVE,
            formation_decision=self.formation,
            rollback_ref="rollback:local:v4",
            runtime_target="local-package",
            terminal_criteria=("build artifacts", "tests", "provider readback"),
        )
        assert self.alpha is not None
        self.build_receipt = execute_local_build_for_frcb(self.engine, self.alpha)
        self.binder = RuntimeConvergenceBinderV4()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_local_build_receipt_reads_back_current_artifacts(self):
        self.assertTrue(self.build_receipt.verify())
        self.assertTrue(verify_local_artifacts(self.build_receipt))
        self.assertTrue(self.build_receipt.truth_boundary["local_build_execution_verified"])
        self.assertTrue(self.build_receipt.truth_boundary["local_artifact_readback_verified"])
        self.assertFalse(self.build_receipt.truth_boundary["test_stage_verified"])
        self.assertFalse(self.build_receipt.truth_boundary["provider_deployment_verified"])

    def test_v4_promotes_only_alpha_local_build_stage(self):
        result = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=request(self.oh50.manifest, self.formation, self.alpha.packet),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
            alpha_omega_build_receipt=self.build_receipt,
        )
        stages = {item.stage: item for item in result.convergence_receipt.stages}
        self.assertEqual(StageStateV4.PRODUCER_INVOCATION_VERIFIED, stages["AAREK"].state)
        self.assertEqual(StageStateV4.PRODUCER_INVOCATION_VERIFIED, stages["OH50"].state)
        self.assertEqual(
            StageStateV4.FOUNDRY_CYCLE_RECEIPT_VERIFIED,
            stages["FORMATION_INNOVATION"].state,
        )
        self.assertEqual(
            StageStateV4.LOCAL_BUILD_RECEIPT_VERIFIED,
            stages["ALPHA_OMEGA_IF_REQUIRED"].state,
        )
        self.assertTrue(result.convergence_receipt.alpha_omega_local_build_verified)
        self.assertFalse(
            result.convergence_receipt.truth_boundary["alpha_omega_test_stage_verified"]
        )
        self.assertFalse(result.convergence_receipt.provider_execution_verified)
        self.assertFalse(result.convergence_receipt.f130_terminal_completion_verified)
        self.assertFalse(result.convergence_receipt.completion_verified)
        self.assertTrue(result.convergence_receipt.verify())

    def test_current_artifact_tamper_blocks_v4(self):
        target = Path(self.build_receipt.build_dir) / "README.md"
        target.write_text(target.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")
        self.assertFalse(verify_local_artifacts(self.build_receipt))
        with self.assertRaisesRegex(ValueError, "ALPHA_OMEGA_LOCAL_BUILD_RECEIPT_INVALID"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(self.oh50.manifest, self.formation, self.alpha.packet),
                oh50_producer_receipt=self.oh50.receipt,
                foundry_result=self.foundry,
                alpha_omega_build_receipt=self.build_receipt,
            )

    def test_packet_substitution_is_rejected(self):
        substituted = replace(self.alpha.packet, rollback_ref="rollback:other")
        with self.assertRaisesRegex(ValueError, "ALPHA_OMEGA_LOCAL_BUILD_PACKET_DIGEST_MISMATCH"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(self.oh50.manifest, self.formation, substituted),
                oh50_producer_receipt=self.oh50.receipt,
                foundry_result=self.foundry,
                alpha_omega_build_receipt=self.build_receipt,
            )

    def test_required_build_without_receipt_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ALPHA_OMEGA_LOCAL_BUILD_RECEIPT_REQUIRED"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(self.oh50.manifest, self.formation, self.alpha.packet),
                oh50_producer_receipt=self.oh50.receipt,
                foundry_result=self.foundry,
            )

    def test_v4_receipt_is_deterministic_for_same_bound_evidence(self):
        kwargs = dict(
            aarek_snapshot=snapshot(),
            of50_request=request(self.oh50.manifest, self.formation, self.alpha.packet),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
            alpha_omega_build_receipt=self.build_receipt,
        )
        left = self.binder.evaluate(**kwargs)
        right = self.binder.evaluate(**kwargs)
        self.assertEqual(
            left.convergence_receipt.receipt_digest,
            right.convergence_receipt.receipt_digest,
        )


class RuntimeConvergenceBindingV4ProofOSTests(unittest.TestCase):
    def test_v3_change_impacts_v4(self):
        impacted, selected = selected_for("federation/runtime_convergence_binding_v3.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V4", impacted)
        self.assertIn("runtime_convergence_binding_v4", selected)

    def test_alpha_engine_change_impacts_v4(self):
        impacted, selected = selected_for(
            "systems/alpha-omega-turnkey/src/alpha_omega/engine.py"
        )
        self.assertIn("FUSE_ALPHA_OMEGA_TURNKEY_LOCAL_BUILD_V1", impacted)
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V4", impacted)
        self.assertIn("runtime_convergence_binding_v4", selected)

    def test_alpha_of50_adapter_change_impacts_v4(self):
        impacted, selected = selected_for(
            "systems/alpha-omega-turnkey/src/alpha_omega/of50_adapter.py"
        )
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V4", impacted)
        self.assertIn("runtime_convergence_binding_v4", selected)


if __name__ == "__main__":
    unittest.main()
