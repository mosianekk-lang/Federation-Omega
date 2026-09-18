from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from evidenceops.innovation_engine.algorithms_common import AUTHORITY_CEILING, sha256
from evidenceops.innovation_engine.foundry_model import FoundryCycleResult
from evidenceops.innovation_engine.of50_adapter import compile_of50_formation_decision
from federation.aarek_v1 import MissionSnapshot
from federation.oh50_producer_adapter_v1 import OH50ProducerAdapter
from federation.of50_ace_v1 import (
    Authority,
    ExecutionProof,
    OF50CycleRequest,
    ProofTier,
)
from federation.runtime_convergence_binding_v3 import (
    RuntimeConvergenceBinderV3,
    StageStateV3,
)
from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
PROOFOS_POLICY = ROOT / "governance/proofos_omega_policy_v1.json"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40

MISSION = "M-FRCB-V3-001"
OBJECTIVE = "bind exact Formation foundry-cycle receipt into convergence truth"


def selected_for(path: str) -> tuple[set[str], set[str]]:
    policy = ProofPolicy.from_path(PROOFOS_POLICY)
    impact = ImpactCompiler(policy).assess([path])
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        impact=impact,
    )
    return set(impact.impacted_subsystems), {item.test_id for item in manifest.selected_tests}


def foundry_result(
    *,
    cycle_id: str = "FC-FRCB-V3-001",
    status: str = "PASSED",
    innovation_marker: str = "baseline",
) -> FoundryCycleResult:
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
        cycle_id=cycle_id,
        status=status,
        algorithm_results=(),
        opportunity_count=0,
        innovation_delta={"marker": innovation_marker},
        learning_delta={"events_recorded": 1},
        maturity="LOCAL_DETERMINISTIC_FOUNDRY_EVOLUTION_AND_REPLICATION_CANARY_PASSED",
        proof=proof,
        authority_ceiling=AUTHORITY_CEILING,
        external_effect=False,
    )


def formation(result: FoundryCycleResult):
    return compile_of50_formation_decision(
        mission_id=MISSION,
        foundry_result=result,
        route_candidates=(
            {
                "route_id": "R1",
                "route_family": "REUSE",
                "score": 0.9,
                "falsifier": "falsify-r1",
                "capability_hypothesis": "reuse existing",
            },
            {
                "route_id": "R2",
                "route_family": "REPAIR",
                "score": 0.7,
                "falsifier": "falsify-r2",
                "capability_hypothesis": "repair existing",
            },
        ),
        selected_route_id="R1",
        reuse_vs_build="REUSE",
        selected_capability_hypothesis="reuse existing",
        implementation_required=False,
    )


def snapshot() -> MissionSnapshot:
    return MissionSnapshot(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
    )


def request(manifest, decision, **overrides) -> OF50CycleRequest:
    base = dict(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
        owner_protection_decision="CONTINUE_AUTOMATICALLY",
        owner_protection_violations=(),
        aarek_receipt_ref="",
        swarm_manifest=manifest,
        formation_decision=decision,
        alpha_omega_packet=None,
        execution_proof=ExecutionProof(executed=False, proof_tier=ProofTier.SOURCE),
        required_outcomes=("O1",),
        proven_outcomes=(),
        completion_requested=False,
    )
    base.update(overrides)
    return OF50CycleRequest(**base)


class FormationFoundryBindingTests(unittest.TestCase):
    def test_of50_adapter_prefers_exact_foundry_receipt_digest(self):
        result = foundry_result()
        decision = formation(result)
        self.assertEqual(result.as_dict()["receipt_sha256"], decision.foundry_cycle_ref)
        self.assertNotEqual(result.cycle_id, decision.foundry_cycle_ref)

    def test_cycle_with_held_gates_cannot_promote(self):
        held = foundry_result(status="PASSED_WITH_HELD_GATES")
        produced = OH50ProducerAdapter().produce(mission_id=MISSION, objective=OBJECTIVE)
        with self.assertRaisesRegex(ValueError, "FORMATION_FOUNDRY_CYCLE_NOT_PASSED"):
            RuntimeConvergenceBinderV3().evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(produced.manifest, formation(held)),
                oh50_producer_receipt=produced.receipt,
                foundry_result=held,
            )

    def test_foundry_proof_hash_tamper_is_rejected(self):
        result = foundry_result()
        tampered = replace(
            result,
            proof={**dict(result.proof), "proof_sha256": "0" * 64},
        )
        produced = OH50ProducerAdapter().produce(mission_id=MISSION, objective=OBJECTIVE)
        with self.assertRaisesRegex(ValueError, "FORMATION_FOUNDRY_PROOF_SHA256_MISMATCH"):
            RuntimeConvergenceBinderV3().evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(produced.manifest, formation(tampered)),
                oh50_producer_receipt=produced.receipt,
                foundry_result=tampered,
            )

    def test_chain_failure_cannot_promote(self):
        result = foundry_result()
        bad_proof = dict(result.proof)
        bad_proof["registry_chain"] = "FAILED"
        bad_proof["proof_sha256"] = sha256({
            key: value for key, value in bad_proof.items() if key != "proof_sha256"
        })
        bad = replace(result, proof=bad_proof)
        produced = OH50ProducerAdapter().produce(mission_id=MISSION, objective=OBJECTIVE)
        with self.assertRaisesRegex(ValueError, "FORMATION_FOUNDRY_REGISTRY_CHAIN_NOT_VERIFIED"):
            RuntimeConvergenceBinderV3().evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(produced.manifest, formation(bad)),
                oh50_producer_receipt=produced.receipt,
                foundry_result=bad,
            )


class RuntimeConvergenceBindingV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundry = foundry_result()
        self.formation = formation(self.foundry)
        self.oh50 = OH50ProducerAdapter().produce(
            mission_id=MISSION,
            objective=OBJECTIVE,
            required_capabilities=("foundry", "proof"),
        )
        self.binder = RuntimeConvergenceBinderV3()

    def test_v3_promotes_formation_only_after_foundry_receipt_binding(self):
        result = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=request(self.oh50.manifest, self.formation),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
        )
        stages = {item.stage: item for item in result.convergence_receipt.stages}
        self.assertEqual(StageStateV3.PRODUCER_INVOCATION_VERIFIED, stages["AAREK"].state)
        self.assertEqual(StageStateV3.PRODUCER_INVOCATION_VERIFIED, stages["OH50"].state)
        self.assertEqual(
            StageStateV3.FOUNDRY_CYCLE_RECEIPT_VERIFIED,
            stages["FORMATION_INNOVATION"].state,
        )
        self.assertEqual(StageStateV3.NOT_REQUIRED, stages["ALPHA_OMEGA_IF_REQUIRED"].state)
        self.assertTrue(result.formation_binding_receipt.verify())
        self.assertTrue(result.convergence_receipt.verify())
        self.assertTrue(result.convergence_receipt.truth_boundary["formation_foundry_cycle_verified"])
        self.assertFalse(
            result.convergence_receipt.truth_boundary[
                "formation_mission_identity_native_to_foundry_receipt"
            ]
        )
        self.assertFalse(result.convergence_receipt.provider_execution_verified)
        self.assertFalse(result.convergence_receipt.f130_terminal_completion_verified)
        self.assertFalse(result.convergence_receipt.completion_verified)

    def test_same_cycle_id_different_foundry_body_is_rejected(self):
        altered = foundry_result(
            cycle_id=self.foundry.cycle_id,
            innovation_marker="different-body",
        )
        self.assertNotEqual(
            self.foundry.as_dict()["receipt_sha256"],
            altered.as_dict()["receipt_sha256"],
        )
        with self.assertRaisesRegex(ValueError, "FORMATION_DECISION_FOUNDRY_RECEIPT_MISMATCH"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(self.oh50.manifest, self.formation),
                oh50_producer_receipt=self.oh50.receipt,
                foundry_result=altered,
            )

    def test_v3_receipt_is_deterministic(self):
        left = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=request(self.oh50.manifest, self.formation),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
        )
        right = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=request(self.oh50.manifest, self.formation),
            oh50_producer_receipt=self.oh50.receipt,
            foundry_result=self.foundry,
        )
        self.assertEqual(
            left.convergence_receipt.receipt_digest,
            right.convergence_receipt.receipt_digest,
        )


class RuntimeConvergenceBindingV3ProofOSTests(unittest.TestCase):
    def test_v2_change_impacts_v3(self):
        impacted, selected = selected_for("federation/runtime_convergence_binding_v2.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V3", impacted)
        self.assertIn("runtime_convergence_binding_v3", selected)

    def test_foundry_change_impacts_v3(self):
        impacted, selected = selected_for("evidenceops/innovation_engine/foundry_model.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V3", impacted)
        self.assertIn("runtime_convergence_binding_v3", selected)

    def test_formation_adapter_change_impacts_v3(self):
        impacted, selected = selected_for("evidenceops/innovation_engine/of50_adapter.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V3", impacted)
        self.assertIn("runtime_convergence_binding_v3", selected)


if __name__ == "__main__":
    unittest.main()
