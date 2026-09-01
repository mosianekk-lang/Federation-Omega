from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import MetaCognitiveState
from benchmarking.cfbe_omega.sovara_sol62_convergence_v1 import (
    RouteState,
    BENCHMARK_DIMENSIONS,
    benchmark_summary,
    bind_transition_to_provider_route,
    compile_convergence_receipt,
    compile_provider_readback_proof,
    compile_telemetry_envelope,
    compile_versioned_toolbox,
    evaluate_gene_controls,
    load_genome,
    metacognitive_provider_policy,
    promotion_gate,
)
from ops.sovara_provider_execution_fabric import (
    CellState,
    ProviderCell,
    ProofReceipt,
    Substrate,
)
from sol_61_runtime.sol_62 import TransitionSpec


def cell(
    provider: str = "openai",
    *,
    state: CellState = CellState.PROVEN,
    operational: bool = True,
    circuit_open: bool = False,
) -> ProviderCell:
    return ProviderCell(
        provider=provider,
        state=state,
        authority_scope="read-only-route-contract",
        public_endpoint=False,
        provider_call_proven=operational,
        semantic_readback_proven=operational,
        substrate=Substrate.PRIVATE_RUNTIME,
        credential_reference_ready=operational,
        runtime_authorised=operational,
        health_ok=True,
        funding_or_quota_ready=operational,
        circuit_open=circuit_open,
    )


def receipt(provider: str = "openai", *, ready: bool = True) -> ProofReceipt:
    return ProofReceipt(
        provider=provider,
        identity_verified=ready,
        metadata_verified=ready,
        semantic_nonce_verified=ready,
        resolved_model_readback=ready,
        usage_readback=ready,
        cost_readback=ready,
        generation_readback=ready,
    )


def transition(*, consequential: bool = False) -> TransitionSpec:
    return TransitionSpec(
        transition_id="tr-1",
        mission_id="mission-1",
        operation="generate",
        target="artifact:report",
        from_state={"status": "pending"},
        to_state={"status": "done"},
        dependencies=(),
        required_proofs=(),
        constraints=(),
        conflict_domains=("artifact:report",),
        priority=90,
        risk_class="HIGH" if consequential else "LOW",
        consequential=consequential,
        simulation_required=consequential,
        source_version="abc123",
    )


class SovaraSol62ConvergenceTests(unittest.TestCase):
    def test_exact_100_profile_is_routed_without_second_authority_plane(self) -> None:
        genes = load_genome()
        receipt_out = compile_convergence_receipt()
        self.assertEqual(100, len(genes))
        self.assertEqual([f"SSX-{i:03d}" for i in range(1, 101)], [g.gene_id for g in genes])
        self.assertEqual(100, receipt_out.routed_count)
        self.assertEqual(50, receipt_out.reuse_count)
        self.assertEqual(42, receipt_out.composed_count)
        self.assertEqual(8, receipt_out.provider_gated_count)
        self.assertFalse(receipt_out.unrouted_gene_ids)
        self.assertFalse(receipt_out.provider_live_universal)
        self.assertFalse(receipt_out.stable_promotion_allowed)
        self.assertFalse(receipt_out.market_superiority_claim)

    def test_provider_gated_controls_are_source_bound_but_not_runtime_promoted(self) -> None:
        decisions = evaluate_gene_controls()
        provider = [d for d in decisions if d.state == "HOLD_PROVIDER_NATIVE_PROOF"]
        self.assertEqual(8, len(provider))
        self.assertTrue(all(d.source_control_implemented for d in provider))
        self.assertTrue(all(not d.provider_runtime_proven for d in provider))
        self.assertTrue(all(not d.external_effect_authorized for d in provider))
        self.assertTrue(all(not d.stable_promotion_allowed for d in provider))

    def test_route_binding_compiles_exact_sol_intent_and_never_inherits_authority(self) -> None:
        binding = bind_transition_to_provider_route(
            transition=transition(consequential=True),
            cells=[cell("openai"), cell("gemini")],
            provider_receipts={"openai": receipt("openai"), "gemini": receipt("gemini")},
            payload={"prompt_hash": "sha256:abc"},
            semantics="IDEMPOTENT",
            actor="worker:sol62",
            source_version="abc123",
            expected_readback={"status": "done"},
            idempotency_key="idem-1",
            preferred_order=("gemini", "openai"),
        )
        self.assertEqual(RouteState.READY, binding.state)
        self.assertEqual("gemini", binding.selected_provider)
        self.assertEqual("private_runtime", binding.selected_substrate)
        self.assertIsNotNone(binding.intent)
        self.assertEqual(binding.effect_id, binding.intent.effect_id)
        self.assertEqual("gemini", binding.intent.provider)
        self.assertTrue(binding.intent.rollback_required)
        self.assertFalse(binding.provider_authority_inherited)
        self.assertFalse(binding.blockers)

    def test_no_eligible_provider_is_local_hold_not_global_claim(self) -> None:
        binding = bind_transition_to_provider_route(
            transition=transition(),
            cells=[cell("openai", operational=False), cell("gemini", operational=False)],
            provider_receipts={},
            payload={"x": 1},
            semantics="IDEMPOTENT",
            actor="worker",
            source_version="abc123",
            expected_readback={"status": "done"},
            idempotency_key="idem-2",
        )
        self.assertEqual(RouteState.HOLD_NO_PROVIDER, binding.state)
        self.assertIsNone(binding.intent)
        self.assertIn("NO_PROVIDER_CELL_CURRENTLY_ELIGIBLE", binding.blockers)

    def test_expected_readback_is_mandatory(self) -> None:
        with self.assertRaisesRegex(ValueError, "SSX_EXPECTED_READBACK_REQUIRED"):
            bind_transition_to_provider_route(
                transition=transition(),
                cells=[cell()],
                provider_receipts={"openai": receipt()},
                payload={"x": 1},
                semantics="IDEMPOTENT",
                actor="worker",
                source_version="abc123",
                expected_readback={},
                idempotency_key="idem-3",
            )

    def test_metacognition_holds_consequential_route_when_evidence_is_low(self) -> None:
        result = metacognitive_provider_policy(
            state=MetaCognitiveState(
                confidence=0.8,
                evidence_coverage=0.4,
                contradiction_pressure=0.1,
                novelty=0.1,
                progress=0.7,
                plan_stability=0.8,
                context_freshness=0.9,
                resource_pressure=0.2,
            ),
            transition=transition(consequential=True),
            cells=[cell()],
            provider_receipts={"openai": receipt()},
        )
        self.assertEqual(RouteState.HOLD_METACOGNITIVE.value, result["state"])
        self.assertIsNone(result["route"])

    def test_nonconsequential_route_can_continue_under_good_meta_state(self) -> None:
        result = metacognitive_provider_policy(
            state=MetaCognitiveState(
                confidence=0.9,
                evidence_coverage=0.9,
                contradiction_pressure=0.05,
                novelty=0.1,
                progress=0.8,
                plan_stability=0.9,
                context_freshness=0.95,
                resource_pressure=0.1,
            ),
            transition=transition(consequential=False),
            cells=[cell()],
            provider_receipts={"openai": receipt()},
        )
        self.assertEqual(RouteState.READY.value, result["state"])
        self.assertEqual("openai", result["route"]["selected_provider"])

    def test_provider_proof_conversion_requires_full_sovara_receipt_and_signature(self) -> None:
        with self.assertRaisesRegex(ValueError, "SSX_PROVIDER_RECEIPT_NOT_PROMOTION_READY"):
            compile_provider_readback_proof(
                receipt=receipt(ready=False),
                effect_id="effect-1",
                transition=transition(),
                provider_ref="provider-run-1",
                readback_evidence={"status": "done"},
                source_version="abc123",
                observed_at="2026-09-01T02:00:00Z",
                signature_ref="attestation:1",
            )
        proof = compile_provider_readback_proof(
            receipt=receipt(),
            effect_id="effect-1",
            transition=transition(),
            provider_ref="provider-run-1",
            readback_evidence={"status": "done"},
            source_version="abc123",
            observed_at="2026-09-01T02:00:00Z",
            signature_ref="attestation:1",
        )
        self.assertEqual("PROVIDER_READBACK", proof.evidence_class)
        self.assertEqual("provider-run-1", proof.provider_correlation_id)
        self.assertEqual("effect-1", proof.attributes["effect_id"])
        self.assertTrue(proof.attributes["sovara_receipt_promotion_ready"])

    def test_versioned_toolbox_requires_unique_identity_and_schema(self) -> None:
        manifest = compile_versioned_toolbox(
            name="federation-tools",
            version="2026.09.01",
            tools=[
                {
                    "tool_id": "drive.read",
                    "version": "1",
                    "owner": "evidenceops",
                    "risk": "READ_ONLY",
                    "permission": "ALLOW_READ",
                    "schema": {"type": "object", "properties": {"id": {"type": "string"}}},
                    "enabled": True,
                },
                {
                    "tool_id": "github.read",
                    "version": "2",
                    "owner": "federation",
                    "risk": "READ_ONLY",
                    "permission": "ALLOW_READ",
                    "schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                    "enabled": True,
                },
            ],
        )
        self.assertEqual(2, len(manifest.tools))
        self.assertTrue(manifest.manifest_sha256.startswith("sha256:"))
        with self.assertRaisesRegex(ValueError, "SSX_TOOLBOX_TOOL_ID_INVALID_OR_DUPLICATE"):
            compile_versioned_toolbox(
                name="dup",
                version="1",
                tools=[
                    {"tool_id": "x", "schema": {"type": "object"}},
                    {"tool_id": "x", "schema": {"type": "object"}},
                ],
            )

    def test_telemetry_cross_links_route_identity_and_rejects_negative_metrics(self) -> None:
        binding = bind_transition_to_provider_route(
            transition=transition(),
            cells=[cell()],
            provider_receipts={"openai": receipt()},
            payload={"x": 1},
            semantics="IDEMPOTENT",
            actor="worker",
            source_version="abc123",
            expected_readback={"status": "done"},
            idempotency_key="idem-4",
        )
        telemetry = compile_telemetry_envelope(
            mission_id="mission-1",
            transition_id="tr-1",
            binding=binding,
            latency_ms=12.3,
            token_count=100,
            cost_usd=0.01,
        )
        self.assertEqual(binding.route_fingerprint, telemetry["route_fingerprint"])
        self.assertEqual(binding.effect_id, telemetry["effect_id"])
        self.assertTrue(telemetry["trace_identity"].startswith("sha256:"))
        with self.assertRaisesRegex(ValueError, "SSX_TELEMETRY_METRICS_INVALID"):
            compile_telemetry_envelope(
                mission_id="mission-1",
                transition_id="tr-1",
                binding=binding,
                latency_ms=-1,
                token_count=0,
                cost_usd=0,
            )

    def test_promotion_gate_never_self_promotes_stable(self) -> None:
        held = promotion_gate(
            deterministic_ci=True,
            hosted_shadow=True,
            provider_native_readback=False,
            operational_cohort=False,
            sustained_owner_value=False,
            rollback_verified=True,
            supply_chain_attested=True,
        )
        self.assertEqual("CANDIDATE_HELD", held.state)
        self.assertFalse(held.stable_promotion_allowed)
        ready = promotion_gate(
            deterministic_ci=True,
            hosted_shadow=True,
            provider_native_readback=True,
            operational_cohort=True,
            sustained_owner_value=True,
            rollback_verified=True,
            supply_chain_attested=True,
        )
        self.assertEqual("CANDIDATE_READY_FOR_INDEPENDENT_STABLE_REVIEW", ready.state)
        self.assertFalse(ready.stable_promotion_allowed)
        self.assertFalse(ready.provider_effect_authorized)

    def test_benchmark_is_twenty_dimensions_and_proof_adjusted_below_architecture(self) -> None:
        summary = benchmark_summary()
        self.assertEqual(20, len(BENCHMARK_DIMENSIONS))
        self.assertEqual(20, summary["dimension_count"])
        self.assertEqual(90.6, summary["architecture_score"])
        self.assertEqual(70.05, summary["proof_adjusted_score"])
        self.assertGreater(summary["architecture_score"], summary["proof_adjusted_score"])


if __name__ == "__main__":
    unittest.main()
