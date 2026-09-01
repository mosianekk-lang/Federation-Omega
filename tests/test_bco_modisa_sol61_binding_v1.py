from __future__ import annotations

from dataclasses import replace
import hashlib
import tempfile
import unittest

from benchmarking.cfbe_omega.bco_modisa_sol61_binding_v1 import (
    ModisaGateState,
    bind_bco_modisa_sol61,
    evaluate_modisa_gate,
    load_modisa_kernel,
    triad_capability_manifest,
)
from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    PrimeObservation,
    StrategyCandidate,
    compile_prime_decision,
)
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import MetaCognitiveState
from formation_omega.reconciliation_fabric_v2 import TaskGraphProfile
from sol_61_runtime.runtime import SolRuntime


OBJECTIVE = "Bind BCO-Prime, Modisa and SOL 6.1"


def digest(text: str = OBJECTIVE) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strategy(
    strategy_id: str,
    *,
    domain: str,
    quality: float,
    external: bool = False,
) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_id=strategy_id,
        failure_domain=domain,
        expected_quality=quality,
        evidence_strength=0.90,
        reliability=0.90,
        reversibility=0.95,
        information_gain=0.80,
        failure_domain_diversity=0.80,
        latency_cost=0.10,
        monetary_cost=0.0,
        owner_burden=0.05,
        risk=0.08,
        external_effect=external,
        proof_refs=(f"proof:{strategy_id}",),
    )


def observation(
    *,
    provider_runtime_available: bool = True,
    owner_approval_required: bool = False,
    effect_class: str = "READ_ONLY",
    exact_authority: bool = True,
) -> PrimeObservation:
    return PrimeObservation(
        mission_id="mission-bco-modisa-sol61",
        objective_sha256=digest(),
        graph=TaskGraphProfile(
            node_count=6,
            edge_count=4,
            ready_parallel_count=4,
            shared_state_key_count=0,
            deterministic_fraction=0.60,
            uncertainty=0.20,
            evidence_conflict=0.10,
            consequential_fraction=0.0,
        ),
        meta_state=MetaCognitiveState(
            confidence=0.85,
            evidence_coverage=0.90,
            contradiction_pressure=0.10,
            novelty=0.25,
            progress=0.60,
            plan_stability=0.85,
            context_freshness=0.95,
            resource_pressure=0.20,
            repeated_failure_count=0,
        ),
        effect_class=effect_class,
        reversible=True,
        exact_authority=exact_authority,
        provider_runtime_available=provider_runtime_available,
        owner_approval_required=owner_approval_required,
        active_streams=2,
        shared_write_pressure=0.05,
        owner_burden=0.05,
        architecture_overlap=0.10,
        frontier_gap=0.15,
        evidence_refs=("evidence:current",),
    )


class BCOModisaSol61BindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategies = (
            strategy("primary", domain="internal", quality=0.94),
            strategy("challenger", domain="alternate", quality=0.86),
        )

    def test_safe_shadow_decision_binds_and_verifies_in_sol61(self):
        with tempfile.TemporaryDirectory() as tempdir:
            runtime = SolRuntime(tempdir)
            receipt = bind_bco_modisa_sol61(
                runtime=runtime,
                mission_objective=OBJECTIVE,
                success_definition=("triad binding verified",),
                observation=observation(),
                strategies=self.strategies,
            )
            self.assertEqual(ModisaGateState.ADMITTED_INTERNAL, receipt.modisa_gate_state)
            self.assertEqual("VERIFIED", receipt.sol61_completion_state)
            self.assertEqual(
                ("BCO_PRIME_DECISION", "MODISA_GATE", "SOL61_INTERNAL_COMMIT"),
                receipt.present_receipt_types,
            )
            self.assertEqual((), receipt.missing_receipt_types)
            self.assertFalse(receipt.dispatch_authorized)
            self.assertFalse(receipt.external_effect_authorized)
            self.assertTrue(receipt.event_chain_verified)
            self.assertEqual("VERIFIED", runtime.state.workstreams[receipt.workstream_id]["status"])

    def test_objective_hash_mismatch_fails_before_any_sol_write(self):
        with tempfile.TemporaryDirectory() as tempdir:
            runtime = SolRuntime(tempdir)
            broken = replace(observation(), objective_sha256=digest("different"))
            with self.assertRaisesRegex(ValueError, "TRIAD_OBSERVATION_OBJECTIVE_HASH_MISMATCH"):
                bind_bco_modisa_sol61(
                    runtime=runtime,
                    mission_objective=OBJECTIVE,
                    success_definition=("triad binding verified",),
                    observation=broken,
                    strategies=self.strategies,
                )
            self.assertEqual({}, runtime.state.missions)
            self.assertEqual({}, runtime.state.workstreams)

    def test_modisa_rejects_tampered_prime_effect_authority(self):
        decision = compile_prime_decision(observation(), self.strategies)
        tampered = replace(
            decision,
            dispatch_authorized=True,
            external_effect_authorized=True,
        )
        gate = evaluate_modisa_gate(
            decision=tampered,
            mission_objective=OBJECTIVE,
        )
        self.assertEqual(ModisaGateState.REJECTED, gate.state)
        self.assertIn("BCO_PRIME_DISPATCH_AUTHORITY_FORBIDDEN", gate.blockers)
        self.assertIn("BCO_PRIME_EXTERNAL_EFFECT_AUTHORITY_FORBIDDEN", gate.blockers)

    def test_provider_runtime_hold_stays_partial_and_does_not_fake_sol_commit(self):
        with tempfile.TemporaryDirectory() as tempdir:
            runtime = SolRuntime(tempdir)
            receipt = bind_bco_modisa_sol61(
                runtime=runtime,
                mission_objective=OBJECTIVE,
                success_definition=("triad binding verified",),
                observation=observation(
                    provider_runtime_available=False,
                    effect_class="PRIVATE_REVERSIBLE",
                ),
                strategies=self.strategies,
            )
            self.assertEqual(ModisaGateState.HOLD_PROVIDER, receipt.modisa_gate_state)
            self.assertEqual("PARTIALLY_VERIFIED", receipt.sol61_completion_state)
            self.assertIn("SOL61_INTERNAL_COMMIT", receipt.missing_receipt_types)
            self.assertNotIn("SOL61_INTERNAL_COMMIT", receipt.present_receipt_types)
            self.assertTrue(receipt.event_chain_verified)

    def test_owner_hold_stays_partial_and_no_external_effect_is_inherited(self):
        with tempfile.TemporaryDirectory() as tempdir:
            runtime = SolRuntime(tempdir)
            external = (
                strategy("external-a", domain="provider-a", quality=0.94, external=True),
                strategy("external-b", domain="provider-b", quality=0.86, external=True),
            )
            receipt = bind_bco_modisa_sol61(
                runtime=runtime,
                mission_objective=OBJECTIVE,
                success_definition=("triad binding verified",),
                observation=observation(
                    effect_class="CONSEQUENTIAL",
                    exact_authority=False,
                    owner_approval_required=True,
                ),
                strategies=external,
            )
            self.assertEqual(ModisaGateState.HOLD_OWNER, receipt.modisa_gate_state)
            self.assertEqual("PARTIALLY_VERIFIED", receipt.sol61_completion_state)
            self.assertFalse(receipt.dispatch_authorized)
            self.assertFalse(receipt.external_effect_authorized)

    def test_verified_binding_replay_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tempdir:
            runtime = SolRuntime(tempdir)
            first = bind_bco_modisa_sol61(
                runtime=runtime,
                mission_objective=OBJECTIVE,
                success_definition=("triad binding verified",),
                observation=observation(),
                strategies=self.strategies,
            )
            before = runtime.events.read_text(encoding="utf-8")
            second = bind_bco_modisa_sol61(
                runtime=runtime,
                mission_objective=OBJECTIVE,
                success_definition=("triad binding verified",),
                observation=observation(),
                strategies=self.strategies,
            )
            after = runtime.events.read_text(encoding="utf-8")
            self.assertEqual(before, after)
            self.assertEqual(first.workstream_id, second.workstream_id)
            self.assertTrue(second.reused_existing)
            self.assertEqual("VERIFIED", second.sol61_completion_state)

    def test_modisa_kernel_drift_fails_closed(self):
        kernel = load_modisa_kernel()
        kernel["invariants"] = [
            item for item in kernel["invariants"]
            if item != "proof before claim"
        ]
        decision = compile_prime_decision(observation(), self.strategies)
        with self.assertRaisesRegex(ValueError, "MODISA_KERNEL_INVARIANT_DRIFT"):
            evaluate_modisa_gate(
                decision=decision,
                mission_objective=OBJECTIVE,
                kernel=kernel,
            )

    def test_manifest_preserves_asymmetric_authority(self):
        manifest = triad_capability_manifest()
        self.assertEqual("PROPOSE_CHALLENGE_RANK_AND_PLAN", manifest["roles"]["BCO_PRIME"])
        self.assertEqual(
            "MISSION_AUTHORITY_PROOF_CONTINUITY_GATE",
            manifest["roles"]["MODISA"],
        )
        self.assertEqual(
            "DURABLE_COMMIT_COMPLETION_AND_PROVIDER_ADMISSION",
            manifest["roles"]["SOL_6_1"],
        )
        self.assertFalse(manifest["authority"]["dispatch_authorized"])
        self.assertFalse(manifest["authority"]["external_effect_authorized"])
        self.assertFalse(manifest["authority"]["stable_self_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
