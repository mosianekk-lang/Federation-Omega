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
from federation.runtime_convergence_binding_v6 import (
    RuntimeConvergenceBinderV6,
    StageStateV6,
)
from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector
from sol_61_runtime.fdof_frcb_activation_v1 import activate_for_frcb
from sol_61_runtime.fdof_frcb_provider_execution_v1 import execute_and_verify_for_frcb
from sol_61_runtime.fdof_provider_bridge_v1 import (
    DispatchReceipt,
    FederationProviderBridge,
    ProviderAdapter,
    ProviderExecutionRequest,
    ReadbackReceipt,
)
from sol_61_runtime.fdof_v1 import (
    ExecutorSpec,
    FederationDistributedOperatingFabric,
    HealthObservation,
    RouteRequest,
)
from sol_61_runtime.sol_62_runtime import Sol62Runtime


PROOFOS_POLICY = ROOT / "governance/proofos_omega_policy_v1.json"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
MISSION = "M-FRCB-V6-001"
OBJECTIVE = "bind provider execution plus native semantic readback into convergence truth"
NOW = 2000


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
            "ledger_head_hash": "learning-head-v6",
            "errors": [],
        },
        "evolution_chain": {
            "status": "PASSED",
            "event_count": 1,
            "ledger_head_hash": "evolution-head-v6",
            "errors": [],
        },
        "algorithm_result_receipts": ["b" * 64],
        "source_signal_count": 1,
        "learning_event_count": 1,
        "authority_ceiling": AUTHORITY_CEILING,
        "external_effect": False,
    }
    proof["proof_sha256"] = sha256(proof)
    return FoundryCycleResult(
        cycle_id="FC-FRCB-V6-001",
        status="PASSED",
        algorithm_results=(),
        opportunity_count=0,
        innovation_delta={"marker": "v6"},
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
                "score": 0.95,
                "falsifier": "provider-native readback does not bind",
                "capability_hypothesis": "build then execute one fenced provider route",
            },
            {
                "route_id": "R2",
                "route_family": "REPAIR",
                "score": 0.7,
                "falsifier": "repair cannot preserve execution identity",
                "capability_hypothesis": "repair existing provider route",
            },
        ),
        selected_route_id="R1",
        reuse_vs_build="PERMANENT_BUILD",
        selected_capability_hypothesis="build then execute one fenced provider route",
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


class RuntimeConvergenceBindingV6Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.engine = AlphaOmegaEngine(self.root / "alpha")
        self.foundry = foundry_result()
        self.formation = formation(self.foundry)
        self.oh50 = OH50ProducerAdapter().produce(
            mission_id=MISSION,
            objective=OBJECTIVE,
            required_capabilities=("build", "activation", "provider-readback"),
        )
        self.alpha = compile_of50_alpha_omega_packet(
            self.engine,
            mission_id=MISSION,
            objective=OBJECTIVE,
            formation_decision=self.formation,
            rollback_ref="rollback:local:v6",
            runtime_target="runtime:local-package",
            terminal_criteria=(
                "local build",
                "capability activation",
                "provider-native semantic readback",
            ),
        )
        assert self.alpha is not None
        self.build_receipt = execute_local_build_for_frcb(self.engine, self.alpha)

        self.runtime = Sol62Runtime(self.root / "fdof")
        self.fdof = FederationDistributedOperatingFabric(self.runtime)
        self.fdof.register_executor(ExecutorSpec(
            executor_id="exec-v6",
            provider="local-executor",
            capabilities=("RUN_LOCAL_PACKAGE",),
            target_prefixes=("runtime:",),
            authority_ceiling="A1_INTERNAL",
            cost_class="C0_INCLUDED_FREE",
            readback_modes=("PROVIDER_NATIVE",),
            rollback_modes=("REVERT",),
            max_parallel=1,
        ))
        self.fdof.record_health(HealthObservation(
            observation_id="health-v6",
            executor_id="exec-v6",
            observed_at_epoch=NOW,
            ttl_seconds=300,
            process="HEALTHY",
            authentication="HEALTHY",
            target_access="HEALTHY",
            semantic_capability="HEALTHY",
            readback="HEALTHY",
            capacity_available=1,
            provider_state="AVAILABLE",
            proof_id="proof:fdof-health:v6",
            evidence_class="PROVIDER_NATIVE",
        ))
        self.route_request = RouteRequest(
            route_id="route-v6",
            mission_id=MISSION,
            transition_id="transition-v6",
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
        self.bridge = FederationProviderBridge(self.fdof)
        self.dispatch_calls = 0
        self.readback_calls = 0
        self.binder = RuntimeConvergenceBinderV6()

    def tearDown(self) -> None:
        self.runtime.close()
        self.temp.cleanup()

    def request(self) -> OF50CycleRequest:
        return of50_request(self.oh50.manifest, self.formation, self.alpha.packet)

    def provider_request(self, *, target: str = "runtime:local-package") -> ProviderExecutionRequest:
        return ProviderExecutionRequest(
            execution_id="provider-exec-v6",
            mission_id=MISSION,
            transition_id="transition-v6",
            route_id="route-v6",
            executor_id="exec-v6",
            provider="local-executor",
            operation="RUN_LOCAL_PACKAGE",
            target=target,
            payload={"package": "alpha-v6"},
            idempotency_key="idem-v6",
            semantics="IDEMPOTENT",
            consequential=False,
            expected_readback={"state": "RUNNING"},
            metadata={"frcb_stage": "V6"},
        )

    def register_adapter(
        self,
        *,
        accepted: bool = True,
        effect_uncertain: bool = False,
        readback_verified: bool = True,
        provider_native: bool = True,
        semantic_state: str = "RUNNING",
        correlation: str = "provider-request-v6",
    ) -> None:
        def dispatch(req):
            self.dispatch_calls += 1
            return DispatchReceipt(
                execution_id=req.execution_id,
                provider=req.provider,
                provider_request_id="provider-request-v6",
                accepted=accepted,
                effect_uncertain=effect_uncertain,
                summary={"accepted": accepted},
            )

        def readback(req, dispatch_receipt):
            self.readback_calls += 1
            return ReadbackReceipt(
                execution_id=req.execution_id,
                provider=req.provider,
                semantic_state=semantic_state,
                verified=readback_verified,
                provider_correlation_id=correlation,
                evidence={
                    "provider_native": provider_native,
                    "runtime_state": semantic_state,
                },
            )

        self.bridge.register_adapter(ProviderAdapter(
            adapter_id="local-executor-v6",
            provider="local-executor",
            dispatch=dispatch,
            readback=readback,
            rollback=None,
            version=1,
        ))

    def execute_provider(self):
        return execute_and_verify_for_frcb(
            self.bridge,
            self.activation,
            self.provider_request(),
            now_epoch=NOW + 1,
        )

    def test_provider_execution_receipt_binds_exact_v5_activation(self):
        self.register_adapter()
        receipt = self.execute_provider()
        self.assertTrue(receipt.verify())
        self.assertEqual(self.activation.receipt_digest, receipt.activation_receipt_digest)
        self.assertEqual("provider-exec-v6", receipt.execution_id)
        self.assertEqual("local-executor", receipt.provider)
        self.assertEqual("RUNNING", receipt.semantic_state)
        self.assertTrue(receipt.truth_boundary["provider_execution_verified"])
        self.assertTrue(receipt.truth_boundary["provider_native_readback_verified"])
        self.assertTrue(receipt.truth_boundary["expected_semantic_state_verified"])
        self.assertFalse(receipt.truth_boundary["f130_terminal_completion_verified"])

    def test_v6_promotes_provider_execution_but_not_terminal_completion(self):
        self.register_adapter()
        provider = self.execute_provider()
        result = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=self.request(),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
            alpha_omega_build_receipt=self.build_receipt,
            fdof_activation_receipt=self.activation,
            provider_execution_receipt=provider,
            now_epoch=NOW + 10,
        )
        stages = {item.stage: item for item in result.convergence_receipt.stages}
        self.assertEqual(
            StageStateV6.PROVIDER_EXECUTION_READBACK_VERIFIED,
            stages["PROVIDER_EXECUTION_READBACK"].state,
        )
        self.assertTrue(result.convergence_receipt.provider_execution_verified)
        self.assertTrue(result.convergence_receipt.provider_semantic_readback_verified)
        self.assertFalse(result.convergence_receipt.f130_terminal_completion_verified)
        self.assertFalse(result.convergence_receipt.completion_verified)
        self.assertTrue(result.convergence_receipt.verify())

    def test_verified_boolean_without_provider_native_evidence_cannot_promote(self):
        self.register_adapter(provider_native=False)
        with self.assertRaisesRegex(
            ValueError,
            "FDOF_PROVIDER_SEMANTIC_READBACK_NOT_VERIFIED",
        ):
            self.execute_provider()
        state = self.bridge._state("provider-exec-v6")
        self.assertEqual("EFFECT_UNKNOWN", state["state"])
        self.assertFalse(state["readback_provider_native"])

    def test_expected_semantic_state_mismatch_cannot_promote(self):
        self.register_adapter(semantic_state="STOPPED")
        with self.assertRaisesRegex(
            ValueError,
            "FDOF_PROVIDER_SEMANTIC_READBACK_NOT_VERIFIED",
        ):
            self.execute_provider()
        state = self.bridge._state("provider-exec-v6")
        self.assertFalse(state["readback_expected_match"])

    def test_rejected_dispatch_is_not_execution_and_never_read_back(self):
        self.register_adapter(accepted=False)
        with self.assertRaisesRegex(ValueError, "FDOF_PROVIDER_DISPATCH_REJECTED"):
            self.execute_provider()
        state = self.bridge._state("provider-exec-v6")
        self.assertEqual("DISPATCH_REJECTED", state["state"])
        self.assertEqual(1, self.dispatch_calls)
        self.assertEqual(0, self.readback_calls)

    def test_request_target_substitution_fails_before_provider_dispatch(self):
        self.register_adapter()
        with self.assertRaisesRegex(
            ValueError,
            "FDOF_PROVIDER_REQUEST_TARGET_MISMATCH",
        ):
            execute_and_verify_for_frcb(
                self.bridge,
                self.activation,
                self.provider_request(target="runtime:other-package"),
                now_epoch=NOW + 1,
            )
        self.assertEqual(0, self.dispatch_calls)

    def test_same_execution_is_not_blindly_dispatched_twice(self):
        self.register_adapter()
        first = self.execute_provider()
        second = self.execute_provider()
        self.assertEqual(first.receipt_digest, second.receipt_digest)
        self.assertEqual(1, self.dispatch_calls)
        self.assertEqual(1, self.readback_calls)

    def test_provider_execution_from_future_is_rejected_by_v6(self):
        self.register_adapter()
        provider = self.execute_provider()
        with self.assertRaisesRegex(
            ValueError,
            "FDOF_PROVIDER_EXECUTION_VERIFICATION_FROM_FUTURE",
        ):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=self.request(),
                oh50_producer_receipt=self.oh50.receipt,
                foundry_result=self.foundry,
                alpha_omega_build_receipt=self.build_receipt,
                fdof_activation_receipt=self.activation,
                provider_execution_receipt=provider,
                now_epoch=NOW,
            )


class RuntimeConvergenceBindingV6ProofOSTests(unittest.TestCase):
    def test_v5_change_impacts_v6(self):
        impacted, selected = selected_for("federation/runtime_convergence_binding_v5.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V6", impacted)
        self.assertIn("runtime_convergence_binding_v6", selected)

    def test_fdof_provider_bridge_change_impacts_v6(self):
        impacted, selected = selected_for("sol_61_runtime/fdof_provider_bridge_v1.py")
        self.assertIn("FUSE_FDOF_PROVIDER_EXECUTION_READBACK_V1", impacted)
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V6", impacted)
        self.assertIn("runtime_convergence_binding_v6", selected)

    def test_provider_execution_adapter_change_impacts_v6(self):
        impacted, selected = selected_for(
            "sol_61_runtime/fdof_frcb_provider_execution_v1.py"
        )
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V6", impacted)
        self.assertIn("runtime_convergence_binding_v6", selected)


if __name__ == "__main__":
    unittest.main()
