from __future__ import annotations

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
from federation.oh50_producer_adapter_v1 import OH50ProducerAdapter
from federation.of50_ace_v1 import Authority, ExecutionProof, OF50CycleRequest, ProofTier
from federation.runtime_convergence_binding_v5 import (
    RuntimeConvergenceBinderV5,
    StageStateV5,
)
from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector
from sol_61_runtime.fdof_frcb_activation_v1 import activate_for_frcb
from sol_61_runtime.fdof_v1 import (
    ExecutorSpec,
    FederationDistributedOperatingFabric,
    HealthObservation,
    RouteRequest,
)
from sol_61_runtime.sol_62_frontier_primitives import ConstraintError
from sol_61_runtime.sol_62_runtime import Sol62Runtime


PROOFOS_POLICY = ROOT / "governance/proofos_omega_policy_v1.json"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
MISSION = "M-FRCB-V5-001"
OBJECTIVE = "bind fresh FDOF route and fence activation into convergence truth"
NOW = 1000


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
        cycle_id="FC-FRCB-V5-001",
        status="PASSED",
        algorithm_results=(),
        opportunity_count=0,
        innovation_delta={"marker": "v5"},
        learning_delta={"events_recorded": 1},
        maturity="LOCAL_DETERMINISTIC_FOUNDRY_EVOLUTION_AND_REPLICATION_CANARY_PASSED",
        proof=proof,
        authority_ceiling=AUTHORITY_CEILING,
        external_effect=False,
    )


def formation(foundry: FoundryCycleResult):
    return compile_of50_formation_decision(
        mission_id=MISSION,
        foundry_result=foundry,
        route_candidates=(
            {
                "route_id": "R1",
                "route_family": "BUILD",
                "score": 0.9,
                "falsifier": "build cannot preserve proof boundary",
                "capability_hypothesis": "build and activate verified local package",
            },
            {
                "route_id": "R2",
                "route_family": "REPAIR",
                "score": 0.7,
                "falsifier": "repair cannot close runtime route",
                "capability_hypothesis": "repair existing route",
            },
        ),
        selected_route_id="R1",
        reuse_vs_build="PERMANENT_BUILD",
        selected_capability_hypothesis="build and activate verified local package",
        implementation_required=True,
    )


def snapshot() -> MissionSnapshot:
    return MissionSnapshot(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
    )


def of50_request(manifest, decision, packet) -> OF50CycleRequest:
    return OF50CycleRequest(
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


class RuntimeConvergenceBindingV5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.engine = AlphaOmegaEngine(self.root / "alpha")
        self.foundry = foundry_result()
        self.formation = formation(self.foundry)
        self.oh50 = OH50ProducerAdapter().produce(
            mission_id=MISSION,
            objective=OBJECTIVE,
            required_capabilities=("build", "activation", "proof"),
        )
        self.alpha = compile_of50_alpha_omega_packet(
            self.engine,
            mission_id=MISSION,
            objective=OBJECTIVE,
            formation_decision=self.formation,
            rollback_ref="rollback:local:v5",
            runtime_target="runtime:local-package",
            terminal_criteria=("local build", "capability activation", "provider readback"),
        )
        assert self.alpha is not None
        self.build_receipt = execute_local_build_for_frcb(self.engine, self.alpha)

        self.runtime = Sol62Runtime(self.root / "fdof")
        self.fdof = FederationDistributedOperatingFabric(self.runtime)
        self.fdof.register_executor(ExecutorSpec(
            executor_id="exec-v5",
            provider="local-executor",
            capabilities=("RUN_LOCAL_PACKAGE",),
            target_prefixes=("runtime:",),
            authority_ceiling="A1_INTERNAL",
            cost_class="C0_INCLUDED_FREE",
            readback_modes=("SEMANTIC",),
            rollback_modes=("REVERT",),
            max_parallel=1,
        ))
        self.fdof.record_health(HealthObservation(
            observation_id="health-v5",
            executor_id="exec-v5",
            observed_at_epoch=NOW,
            ttl_seconds=300,
            process="HEALTHY",
            authentication="HEALTHY",
            target_access="HEALTHY",
            semantic_capability="HEALTHY",
            readback="HEALTHY",
            capacity_available=1,
            provider_state="AVAILABLE",
            proof_id="proof:fdof-health:v5",
            evidence_class="DETERMINISTIC_TEST",
        ))
        self.route_request = RouteRequest(
            route_id="route-v5",
            mission_id=MISSION,
            transition_id="transition-v5",
            operation="RUN_LOCAL_PACKAGE",
            target="runtime:local-package",
            required_capabilities=("RUN_LOCAL_PACKAGE",),
            authority_ceiling="A1_INTERNAL",
            allowed_cost_classes=("C0_INCLUDED_FREE",),
            require_readback=True,
            require_rollback=False,
            consequential=False,
        )
        self.activation = activate_for_frcb(
            self.fdof,
            self.route_request,
            now_epoch=NOW,
            lease_ttl_seconds=120,
        )
        self.binder = RuntimeConvergenceBinderV5()

    def tearDown(self) -> None:
        self.runtime.close()
        self.temp.cleanup()

    def request(self):
        return of50_request(self.oh50.manifest, self.formation, self.alpha.packet)

    def test_activation_receipt_proves_route_fence_not_provider_execution(self):
        self.assertTrue(self.activation.verify(now_epoch=NOW))
        self.assertTrue(self.activation.truth_boundary["fdof_route_selected"])
        self.assertTrue(self.activation.truth_boundary["transition_fence_active"])
        self.assertTrue(self.activation.truth_boundary["sol62_event_chain_verified"])
        self.assertFalse(self.activation.truth_boundary["provider_dispatch_verified"])
        self.assertFalse(self.activation.truth_boundary["provider_effect_verified"])
        self.assertFalse(self.activation.truth_boundary["provider_semantic_readback_verified"])

    def test_v5_appends_capability_activation_without_inflating_runtime_truth(self):
        result = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=self.request(),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
            alpha_omega_build_receipt=self.build_receipt,
            fdof_activation_receipt=self.activation,
            now_epoch=NOW,
        )
        stages = {item.stage: item for item in result.convergence_receipt.stages}
        self.assertEqual(
            StageStateV5.CAPABILITY_ROUTE_FENCE_VERIFIED,
            stages["CAPABILITY_ACTIVATION"].state,
        )
        self.assertEqual("exec-v5", result.convergence_receipt.fdof_executor_id)
        self.assertEqual("local-executor", result.convergence_receipt.fdof_provider)
        self.assertEqual("runtime:local-package", result.convergence_receipt.fdof_target)
        self.assertFalse(result.convergence_receipt.provider_execution_verified)
        self.assertFalse(result.convergence_receipt.provider_semantic_readback_verified)
        self.assertFalse(result.convergence_receipt.f130_terminal_completion_verified)
        self.assertFalse(result.convergence_receipt.completion_verified)
        self.assertTrue(result.convergence_receipt.verify())

    def test_expired_activation_cannot_enter_v5(self):
        self.assertFalse(self.activation.verify(now_epoch=NOW + 121))
        with self.assertRaisesRegex(
            ValueError,
            "FDOF_CAPABILITY_ACTIVATION_RECEIPT_INVALID_OR_STALE",
        ):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=self.request(),
                oh50_producer_receipt=self.oh50.receipt,
                foundry_result=self.foundry,
                alpha_omega_build_receipt=self.build_receipt,
                fdof_activation_receipt=self.activation,
                now_epoch=NOW + 121,
            )

    def test_alpha_runtime_target_mismatch_is_rejected(self):
        other_request = RouteRequest(
            route_id="route-v5-other",
            mission_id=MISSION,
            transition_id="transition-v5-other",
            operation="RUN_LOCAL_PACKAGE",
            target="runtime:other-package",
            required_capabilities=("RUN_LOCAL_PACKAGE",),
            authority_ceiling="A1_INTERNAL",
            allowed_cost_classes=("C0_INCLUDED_FREE",),
            require_readback=True,
            require_rollback=False,
            consequential=False,
        )
        other = activate_for_frcb(
            self.fdof,
            other_request,
            now_epoch=NOW,
            lease_ttl_seconds=120,
        )
        with self.assertRaisesRegex(
            ValueError,
            "FDOF_CAPABILITY_ACTIVATION_TARGET_MISMATCH",
        ):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=self.request(),
                oh50_producer_receipt=self.oh50.receipt,
                foundry_result=self.foundry,
                alpha_omega_build_receipt=self.build_receipt,
                fdof_activation_receipt=other,
                now_epoch=NOW,
            )

    def test_stale_health_cannot_create_activation(self):
        stale_runtime = Sol62Runtime(self.root / "stale-fdof")
        try:
            stale_fdof = FederationDistributedOperatingFabric(stale_runtime)
            stale_fdof.register_executor(ExecutorSpec(
                executor_id="exec-stale-v5",
                provider="local-executor",
                capabilities=("RUN_LOCAL_PACKAGE",),
                target_prefixes=("runtime:",),
                authority_ceiling="A1_INTERNAL",
                cost_class="C0_INCLUDED_FREE",
                readback_modes=("SEMANTIC",),
                rollback_modes=("REVERT",),
            ))
            stale_fdof.record_health(HealthObservation(
                observation_id="health-stale-v5",
                executor_id="exec-stale-v5",
                observed_at_epoch=NOW - 1000,
                ttl_seconds=60,
                process="HEALTHY",
                authentication="HEALTHY",
                target_access="HEALTHY",
                semantic_capability="HEALTHY",
                readback="HEALTHY",
                capacity_available=1,
                provider_state="AVAILABLE",
                proof_id="proof:stale",
                evidence_class="DETERMINISTIC_TEST",
            ))
            with self.assertRaises(ConstraintError):
                activate_for_frcb(
                    stale_fdof,
                    RouteRequest(
                        route_id="route-stale-v5",
                        mission_id=MISSION,
                        transition_id="transition-stale-v5",
                        operation="RUN_LOCAL_PACKAGE",
                        target="runtime:local-package",
                        required_capabilities=("RUN_LOCAL_PACKAGE",),
                        authority_ceiling="A1_INTERNAL",
                        allowed_cost_classes=("C0_INCLUDED_FREE",),
                        require_readback=True,
                        require_rollback=False,
                        consequential=False,
                    ),
                    now_epoch=NOW,
                )
        finally:
            stale_runtime.close()

    def test_v5_receipt_is_deterministic_for_same_bound_evidence(self):
        kwargs = dict(
            aarek_snapshot=snapshot(),
            of50_request=self.request(),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
            alpha_omega_build_receipt=self.build_receipt,
            fdof_activation_receipt=self.activation,
            now_epoch=NOW,
        )
        left = self.binder.evaluate(**kwargs)
        right = self.binder.evaluate(**kwargs)
        self.assertEqual(
            left.convergence_receipt.receipt_digest,
            right.convergence_receipt.receipt_digest,
        )


class RuntimeConvergenceBindingV5ProofOSTests(unittest.TestCase):
    def test_v4_change_impacts_v5(self):
        impacted, selected = selected_for("federation/runtime_convergence_binding_v4.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V5", impacted)
        self.assertIn("runtime_convergence_binding_v5", selected)

    def test_fdof_change_impacts_v5(self):
        impacted, selected = selected_for("sol_61_runtime/fdof_v1.py")
        self.assertIn("FUSE_FDOF_CAPABILITY_ACTIVATION_V1", impacted)
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V5", impacted)
        self.assertIn("runtime_convergence_binding_v5", selected)

    def test_sol62_fence_change_impacts_v5(self):
        impacted, selected = selected_for("sol_61_runtime/sol_62_frontier_primitives.py")
        self.assertIn("FUSE_FDOF_CAPABILITY_ACTIVATION_V1", impacted)
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V5", impacted)
        self.assertIn("runtime_convergence_binding_v5", selected)


if __name__ == "__main__":
    unittest.main()
