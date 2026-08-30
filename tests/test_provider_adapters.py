from __future__ import annotations

from dataclasses import replace
import unittest

from omega_one.interop import EffectClass, UniversalCapabilityContract
from omega_one.provider_adapters import (
    AuthorityLevel,
    AvailabilityState,
    CapabilityFlag,
    CircuitState,
    CopilotAdapter,
    FeatureMaturity,
    GeminiADKAdapter,
    OpenAIChatGPTAdapter,
    PrivacyClass,
    ProviderAdapterRegistry,
    ProviderAvailabilityMetadata,
    ProviderId,
    ProviderRequestRejected,
    default_provider_adapters,
    default_provider_registry,
)


class ProviderDescriptorTests(unittest.TestCase):
    def test_default_descriptors_cover_three_providers_and_preserve_ucc(self) -> None:
        adapters = default_provider_adapters()
        self.assertEqual(
            {adapter.descriptor.provider for adapter in adapters},
            {
                ProviderId.OPENAI_CHATGPT,
                ProviderId.GEMINI_ADK,
                ProviderId.GITHUB_COPILOT,
            },
        )
        hashes = {adapter.descriptor.ucc_sha256 for adapter in adapters}
        self.assertEqual(len(hashes), 1)
        for adapter in adapters:
            descriptor = adapter.descriptor
            self.assertTrue(descriptor.zero_dilution)
            self.assertEqual(descriptor.preservation_state, "FULL_UCC_PRESERVED")
            self.assertFalse(descriptor.gate.live_execution_authorized)
            self.assertFalse(descriptor.gate.external_effects_authorized)
            self.assertEqual(descriptor.gate.authority_ceiling, AuthorityLevel.A0_READ_ONLY)
            self.assertTrue(descriptor.source_urls)

    def test_openai_preview_and_stable_surfaces_are_not_conflated(self) -> None:
        descriptor = OpenAIChatGPTAdapter().descriptor
        multi_agent = descriptor.support(CapabilityFlag.MULTI_AGENT)
        handoffs = descriptor.support(CapabilityFlag.HANDOFFS)
        self.assertTrue(multi_agent.supported)
        self.assertTrue(multi_agent.preview)
        self.assertEqual(multi_agent.maturity, FeatureMaturity.BETA)
        self.assertTrue(handoffs.supported)
        self.assertFalse(handoffs.preview)
        self.assertEqual(handoffs.maturity, FeatureMaturity.STABLE)
        self.assertEqual(descriptor.concurrency.recommended_concurrency, 3)
        self.assertIsNone(descriptor.concurrency.documented_hard_limit)

    def test_unknown_provider_capabilities_remain_unverified_not_inherited(self) -> None:
        copilot = CopilotAdapter().descriptor
        self.assertFalse(copilot.support(CapabilityFlag.MULTI_AGENT).supported)
        self.assertEqual(
            copilot.support(CapabilityFlag.MULTI_AGENT).maturity,
            FeatureMaturity.UNVERIFIED,
        )
        gemini = GeminiADKAdapter().descriptor
        self.assertFalse(gemini.support(CapabilityFlag.BATCH_QUEUE).supported)
        self.assertEqual(
            gemini.support(CapabilityFlag.BATCH_QUEUE).maturity,
            FeatureMaturity.UNVERIFIED,
        )


class ProviderEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = OpenAIChatGPTAdapter()

    def request(self, **overrides: object):
        return self.adapter.build_request(
            request_id="req-001",
            mission_id="mission-001",
            capability=CapabilityFlag.HANDOFFS,
            payload={"task": "route one bounded branch", "context": {"case": 7}},
            **overrides,
        )

    def test_valid_envelope_is_admitted(self) -> None:
        decision = self.adapter.admit(self.request())
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.reasons, ())

    def test_preview_requires_explicit_opt_in(self) -> None:
        request = self.adapter.build_request(
            request_id="req-preview",
            mission_id="mission-001",
            capability=CapabilityFlag.MULTI_AGENT,
            payload={"task": "fan out"},
        )
        self.assertIn("PREVIEW_OPT_IN_REQUIRED", self.adapter.admit(request).reasons)
        self.assertTrue(self.adapter.admit(replace(request, allow_preview=True)).admitted)

    def test_ucc_hash_and_zero_dilution_are_enforced(self) -> None:
        request = self.request()
        tampered_hash = replace(request, source_ucc_sha256="0" * 64)
        reasons = self.adapter.admit(tampered_hash).reasons
        self.assertIn("SOURCE_UCC_HASH_MISMATCH", reasons)
        self.assertIn("DESCRIPTOR_UCC_HASH_MISMATCH", reasons)

        weakened_ucc = UniversalCapabilityContract(
            capability_id=request.ucc.capability_id,
            name=request.ucc.name,
            description=request.ucc.description,
            input_schema=request.ucc.input_schema,
            output_schema=request.ucc.output_schema,
            effect_class=request.ucc.effect_class,
            authority_ceiling=request.ucc.authority_ceiling,
            privacy_class=request.ucc.privacy_class,
            rollback_required=request.ucc.rollback_required,
            proof_required=request.ucc.proof_required,
            metadata={"omega.zero_dilution": False},
        )
        weakened = replace(request, ucc=weakened_ucc)
        self.assertIn("ZERO_DILUTION_METADATA_REQUIRED", self.adapter.admit(weakened).reasons)

    def test_authority_privacy_effect_and_cost_fail_closed(self) -> None:
        authority = self.adapter.admit(
            self.request(authority=AuthorityLevel.A2_EFFECT, owner_authorized=True)
        )
        self.assertIn("AUTHORITY_CEILING_EXCEEDED", authority.reasons)

        privacy = self.adapter.admit(self.request(privacy_class=PrivacyClass.P0_PUBLIC))
        self.assertIn("PRIVACY_CLASS_DILUTION", privacy.reasons)

        effect = self.adapter.admit(
            self.request(effect_class=EffectClass.EXTERNAL_EFFECT, consequential=True)
        )
        self.assertIn("EFFECT_CLASS_UCC_MISMATCH", effect.reasons)
        self.assertIn("LOCAL_ADAPTER_NON_EFFECT_ONLY", effect.reasons)

        cost = self.adapter.admit(
            self.request(estimated_cost_units=1, cost_budget_units=0, cost_authorized=False)
        )
        self.assertIn("COST_BUDGET_EXCEEDED", cost.reasons)
        self.assertIn("COST_AUTHORIZATION_REQUIRED", cost.reasons)
        self.assertIn("LOCAL_COST_CEILING_EXCEEDED", cost.reasons)

    def test_live_invocation_is_not_an_escape_hatch(self) -> None:
        request = self.request(deterministic_local_only=False)
        with self.assertRaises(ProviderRequestRejected) as caught:
            self.adapter.invoke(request)
        self.assertIn("LIVE_PROVIDER_EXECUTION_DISABLED", caught.exception.reasons)

        network = self.adapter.validate_request(
            self.request(network_requested=True, credentials_requested=True)
        )
        self.assertIn("NETWORK_USE_NOT_AUTHORIZED", network.reasons)
        self.assertIn("CREDENTIAL_USE_NOT_AUTHORIZED", network.reasons)


class ProviderInvocationTests(unittest.TestCase):
    def test_fake_invocation_is_deterministic_non_effect_and_hash_verified(self) -> None:
        adapter = GeminiADKAdapter()
        request = adapter.build_request(
            request_id="req-deterministic",
            mission_id="mission-001",
            capability=CapabilityFlag.PARALLEL_AGENTS,
            payload={"task": "compare two documents", "context": {"documents": 2}},
        )
        first = adapter.invoke(request)
        second = adapter.invoke(request)
        self.assertEqual(first, second)
        self.assertEqual(first.status, "LOCAL_FAKE_COMPLETED")
        self.assertFalse(first.network_used)
        self.assertFalse(first.credentials_used)
        self.assertFalse(first.external_effect)
        self.assertEqual(first.cost_units, 0)
        self.assertTrue(first.verified())
        self.assertNotIn("compare two documents", str(first.output))

    def test_circuit_metadata_opens_and_recovers_deterministically(self) -> None:
        adapter = OpenAIChatGPTAdapter()
        for _ in range(3):
            state = adapter.record_failure()
        self.assertEqual(state.circuit, CircuitState.OPEN)
        self.assertEqual(state.availability, AvailabilityState.UNAVAILABLE)
        request = adapter.build_request(
            request_id="req-circuit",
            mission_id="mission-001",
            capability=CapabilityFlag.HANDOFFS,
            payload={"task": "route"},
        )
        self.assertIn("PROVIDER_CIRCUIT_OPEN", adapter.admit(request).reasons)
        recovered = adapter.record_success()
        self.assertEqual(recovered.circuit, CircuitState.CLOSED)
        self.assertTrue(adapter.admit(request).admitted)

    def test_registry_uses_only_explicit_semantically_safe_fallback(self) -> None:
        registry = default_provider_registry()
        primary = registry.get(ProviderId.OPENAI_CHATGPT)
        primary.set_availability(
            ProviderAvailabilityMetadata(
                provider=ProviderId.OPENAI_CHATGPT,
                availability=AvailabilityState.UNAVAILABLE,
                circuit=CircuitState.OPEN,
                consecutive_failures=3,
                reason="TEST_OUTAGE",
            )
        )
        base = primary.build_request(
            request_id="req-fallback",
            mission_id="mission-001",
            capability=CapabilityFlag.PARALLEL_AGENTS,
            payload={"task": "read-only comparison"},
            allow_fallback=True,
            fallback_providers=(ProviderId.GEMINI_ADK,),
        )
        vetoes = registry.safe_fallback_vetoes(base, ProviderId.GEMINI_ADK)
        self.assertIn("CROSS_PROVIDER_DATA_TRANSFER_NOT_AUTHORIZED", vetoes)

        authorized = replace(base, allow_cross_provider_data_transfer=True)
        self.assertEqual(
            registry.safe_fallback_vetoes(authorized, ProviderId.GEMINI_ADK),
            (),
        )
        receipt = registry.invoke(authorized)
        self.assertEqual(receipt.provider, ProviderId.GEMINI_ADK)
        self.assertEqual(receipt.fallback_from, ProviderId.OPENAI_CHATGPT)
        self.assertTrue(receipt.verified())

    def test_registry_does_not_fallback_from_non_availability_rejection(self) -> None:
        primary = OpenAIChatGPTAdapter()
        registry = ProviderAdapterRegistry((primary, GeminiADKAdapter()))
        request = primary.build_request(
            request_id="req-no-escape",
            mission_id="mission-001",
            capability=CapabilityFlag.HANDOFFS,
            payload={"task": "write something"},
            authority=AuthorityLevel.A2_EFFECT,
            effect_class=EffectClass.EXTERNAL_EFFECT,
            consequential=True,
            owner_authorized=True,
            allow_fallback=True,
            allow_cross_provider_data_transfer=True,
            fallback_providers=(ProviderId.GEMINI_ADK,),
        )
        with self.assertRaises(ProviderRequestRejected) as caught:
            registry.invoke(request)
        self.assertIn("AUTHORITY_CEILING_EXCEEDED", caught.exception.reasons)
        self.assertNotIn("NO_SAFE_FALLBACK", caught.exception.reasons)


if __name__ == "__main__":
    unittest.main()
