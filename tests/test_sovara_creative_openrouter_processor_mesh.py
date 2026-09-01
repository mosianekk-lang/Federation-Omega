import unittest

from sovara.creative.openrouter_adapter import OpenRouterReceiptState, OpenRouterSemanticReceipt
from sovara.creative.openrouter_processor_mesh import (
    CognitiveCapabilityContract,
    EndpointFamily,
    MeshPlanState,
    MeshProofState,
    ModelCapability,
    ProcessorStrategy,
    ProviderEnvelope,
    compile_mesh_plan,
    discovery_endpoints,
    endpoint_for_outputs,
    evaluate_mesh_receipt,
    rank_candidates,
    supports_contract,
)
from sovara.creative.policy import PrivacyClass


FREE_OMNI = ModelCapability.from_api_record(
    {
        "id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "canonical_slug": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "context_length": 256000,
        "architecture": {
            "input_modalities": ["text", "image", "audio", "video"],
            "output_modalities": ["text"],
        },
        "supported_parameters": ["tools", "tool_choice", "reasoning", "response_format"],
        "pricing": {"prompt": "0", "completion": "0"},
        "providers": [{"name": "nvidia"}],
    }
)

FREE_EMBED = ModelCapability.from_api_record(
    {
        "id": "liquid/lfm-2.5-embedding-350m:free",
        "context_length": 512,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["embeddings"]},
        "supported_parameters": [],
        "pricing": {"prompt": "0", "completion": "0"},
    }
)

PAID_TEXT = ModelCapability.from_api_record(
    {
        "id": "vendor/frontier-paid",
        "context_length": 200000,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_parameters": ["tools", "tool_choice", "response_format", "reasoning"],
        "pricing": {"prompt": "0.000001", "completion": "0.000005"},
        "providers": [{"name": "p1"}, {"name": "p2"}],
    }
)


class OpenRouterProcessorMeshTests(unittest.TestCase):
    def test_dynamic_record_parses_modalities_and_free_state(self):
        self.assertTrue(FREE_OMNI.free_variant)
        self.assertIn("video", FREE_OMNI.input_modalities)
        self.assertIn("reasoning", FREE_OMNI.supported_parameters)
        self.assertEqual(FREE_OMNI.context_length, 256000)

    def test_multimodal_contract_selects_free_omni(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-OMNI",
            required_input_modalities=frozenset({"text", "image", "audio", "video"}),
            required_output_modalities=frozenset({"text"}),
            required_parameters=frozenset({"reasoning"}),
            strategy=ProcessorStrategy.PINNED,
            exact_model_id=FREE_OMNI.model_id,
        )
        supported, reasons = supports_contract(FREE_OMNI, contract)
        self.assertTrue(supported, reasons)
        ranked = rank_candidates([PAID_TEXT, FREE_OMNI], contract)
        self.assertEqual([item.model.model_id for item in ranked], [FREE_OMNI.model_id])

    def test_missing_required_modality_is_rejected(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-VIDEO",
            required_input_modalities=frozenset({"text", "video"}),
            required_output_modalities=frozenset({"text"}),
            strategy=ProcessorStrategy.PINNED,
            exact_model_id=PAID_TEXT.model_id,
        )
        supported, reasons = supports_contract(PAID_TEXT, contract)
        self.assertFalse(supported)
        self.assertIn("INPUT_MODALITY_MISMATCH", reasons)

    def test_endpoint_family_maps_output_modalities(self):
        self.assertEqual(endpoint_for_outputs({"text"}), EndpointFamily.CHAT)
        self.assertEqual(endpoint_for_outputs({"image"}), EndpointFamily.IMAGES)
        self.assertEqual(endpoint_for_outputs({"video"}), EndpointFamily.VIDEOS)
        self.assertEqual(endpoint_for_outputs({"speech"}), EndpointFamily.SPEECH)
        self.assertEqual(endpoint_for_outputs({"transcription"}), EndpointFamily.TRANSCRIPTIONS)
        self.assertEqual(endpoint_for_outputs({"embeddings"}), EndpointFamily.EMBEDDINGS)

    def test_discovery_surface_includes_specialized_catalogs(self):
        endpoints = discovery_endpoints()
        self.assertIn(EndpointFamily.MODELS, endpoints)
        self.assertIn(EndpointFamily.IMAGE_MODELS, endpoints)
        self.assertIn(EndpointFamily.VIDEO_MODELS, endpoints)
        self.assertIn(EndpointFamily.EMBEDDING_MODELS, endpoints)

    def test_secret_privacy_fails_closed(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-SECRET",
            strategy=ProcessorStrategy.PINNED,
            exact_model_id=FREE_OMNI.model_id,
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[FREE_OMNI],
            privacy_class=PrivacyClass.SECRET,
        )
        self.assertEqual(plan.state, MeshPlanState.HOLD_PRIVACY)
        self.assertFalse(plan.live_execution_authorized)

    def test_paid_candidate_requires_finite_spend_authority(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-PAID",
            strategy=ProcessorStrategy.PINNED,
            exact_model_id=PAID_TEXT.model_id,
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[PAID_TEXT],
            privacy_class=PrivacyClass.INTERNAL,
            credential_bound=True,
            runtime_identity="runner",
            provider_effect_authorized=True,
            finite_spend_authorized=False,
        )
        self.assertEqual(plan.state, MeshPlanState.HOLD_SPEND)
        self.assertFalse(plan.live_execution_authorized)

    def test_free_candidate_can_be_live_only_when_all_effect_gates_bind(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-FREE",
            strategy=ProcessorStrategy.PINNED,
            exact_model_id=FREE_OMNI.model_id,
            require_tools=True,
            require_structured_output=True,
            require_reasoning=True,
            require_zdr=True,
            deny_data_collection=True,
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[FREE_OMNI],
            privacy_class=PrivacyClass.INTERNAL,
            credential_bound=True,
            runtime_identity="github-actions/openrouter-canary",
            provider_effect_authorized=True,
        )
        self.assertEqual(plan.state, MeshPlanState.READY_SOURCE_ONLY)
        self.assertTrue(plan.live_execution_authorized)
        self.assertTrue(plan.provider["zdr"])
        self.assertEqual(plan.provider["data_collection"], "deny")
        self.assertFalse(plan.provider["allow_fallbacks"])

    def test_auto_router_source_plan_can_compile_without_freezing_vendor_model(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-AUTO",
            strategy=ProcessorStrategy.AUTO,
            required_input_modalities=frozenset({"text"}),
            required_output_modalities=frozenset({"text"}),
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[],
            privacy_class=PrivacyClass.PUBLIC,
        )
        self.assertEqual(plan.state, MeshPlanState.READY_SOURCE_ONLY)
        self.assertEqual(plan.model_id, "openrouter/auto")
        self.assertFalse(plan.live_execution_authorized)

    def test_auto_router_live_request_holds_when_pricing_is_unresolved(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-AUTO-LIVE",
            strategy=ProcessorStrategy.AUTO,
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[],
            privacy_class=PrivacyClass.PUBLIC,
            credential_bound=True,
            runtime_identity="runner",
            provider_effect_authorized=True,
            finite_spend_authorized=True,
        )
        self.assertEqual(MeshPlanState.HOLD_COST_UNRESOLVED, plan.state)
        self.assertIn("ROUTER_PRICING_UNRESOLVED_PRICE_CEILING_REQUIRED", plan.reason_codes)
        self.assertFalse(plan.live_execution_authorized)

    def test_auto_router_live_request_requires_finite_spend_before_unknown_pricing(self):
        contract = CognitiveCapabilityContract(contract_id="CCC-AUTO-NO-SPEND", strategy=ProcessorStrategy.AUTO)
        plan = compile_mesh_plan(
            contract=contract,
            models=[],
            privacy_class=PrivacyClass.PUBLIC,
            credential_bound=True,
            runtime_identity="runner",
            provider_effect_authorized=True,
            finite_spend_authorized=False,
        )
        self.assertEqual(MeshPlanState.HOLD_COST_UNRESOLVED, plan.state)
        self.assertIn("ROUTER_PRICING_UNRESOLVED_FINITE_SPEND_AUTHORITY_REQUIRED", plan.reason_codes)

    def test_auto_router_live_request_can_be_bounded_by_explicit_price_ceiling(self):
        contract = CognitiveCapabilityContract(contract_id="CCC-AUTO-BOUNDED", strategy=ProcessorStrategy.AUTO)
        envelope = ProviderEnvelope(max_price_prompt=0.000001, max_price_completion=0.000005)
        plan = compile_mesh_plan(
            contract=contract,
            models=[],
            privacy_class=PrivacyClass.PUBLIC,
            provider_envelope=envelope,
            credential_bound=True,
            runtime_identity="runner",
            provider_effect_authorized=True,
            finite_spend_authorized=True,
        )
        self.assertEqual(MeshPlanState.READY_SOURCE_ONLY, plan.state)
        self.assertTrue(plan.live_execution_authorized)
        self.assertEqual(plan.provider["max_price"], {"prompt": 0.000001, "completion": 0.000005})

    def test_fusion_is_plugin_not_new_sovereign_model(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-FUSION",
            strategy=ProcessorStrategy.FUSION,
            router_model_id="openrouter/auto",
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[FREE_OMNI],
            privacy_class=PrivacyClass.PUBLIC,
        )
        self.assertEqual(plan.state, MeshPlanState.READY_SOURCE_ONLY)
        self.assertEqual(tuple(plan.plugins), ({"id": "fusion"},))

    def test_floor_and_nitro_compile_provider_sort(self):
        floor = CognitiveCapabilityContract(
            contract_id="CCC-FLOOR",
            strategy=ProcessorStrategy.FLOOR,
            router_model_id="openrouter/free",
        )
        floor_plan = compile_mesh_plan(contract=floor, models=[FREE_OMNI], privacy_class=PrivacyClass.PUBLIC)
        self.assertEqual(floor_plan.provider["sort"], "price")

        nitro = CognitiveCapabilityContract(
            contract_id="CCC-NITRO",
            strategy=ProcessorStrategy.NITRO,
            router_model_id="openrouter/free",
        )
        nitro_plan = compile_mesh_plan(contract=nitro, models=[FREE_OMNI], privacy_class=PrivacyClass.PUBLIC)
        self.assertEqual(nitro_plan.provider["sort"], "throughput")

    def test_explicit_provider_envelope_is_preserved(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-PROVIDER",
            strategy=ProcessorStrategy.PINNED,
            exact_model_id=FREE_OMNI.model_id,
        )
        envelope = ProviderEnvelope(
            only=("nvidia",),
            order=("nvidia",),
            allow_fallbacks=False,
            zdr=True,
            data_collection="deny",
            max_price_prompt=0.0,
            max_price_completion=0.0,
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[FREE_OMNI],
            privacy_class=PrivacyClass.INTERNAL,
            provider_envelope=envelope,
        )
        self.assertEqual(plan.provider["only"], ["nvidia"])
        self.assertEqual(plan.provider["max_price"], {"prompt": 0.0, "completion": 0.0})

    def test_embedding_contract_uses_embedding_endpoint(self):
        contract = CognitiveCapabilityContract(
            contract_id="CCC-EMBED",
            required_input_modalities=frozenset({"text"}),
            required_output_modalities=frozenset({"embeddings"}),
            strategy=ProcessorStrategy.PINNED,
            exact_model_id=FREE_EMBED.model_id,
        )
        plan = compile_mesh_plan(
            contract=contract,
            models=[FREE_EMBED],
            privacy_class=PrivacyClass.PUBLIC,
        )
        self.assertEqual(plan.endpoint, EndpointFamily.EMBEDDINGS)
        self.assertEqual(plan.model_id, FREE_EMBED.model_id)

    def _semantic_receipt(self, request_sha256: str) -> OpenRouterSemanticReceipt:
        return OpenRouterSemanticReceipt(
            state=OpenRouterReceiptState.SEMANTIC_VERIFIED,
            request_fingerprint=request_sha256,
            transport_status=200,
            generation_id="gen-1",
            provider="ResolvedProvider",
            resolved_model="resolved/model",
            prompt_tokens=2,
            completion_tokens=1,
            cost_usd=0.0,
            semantic_verified=True,
            output_sha256="b" * 64,
            failure_code=None,
        )

    def test_receipt_uses_stronger_semantic_receipt_and_never_inherits_behavior(self):
        contract = CognitiveCapabilityContract(contract_id="CCC-RECEIPT", strategy=ProcessorStrategy.AUTO)
        request_sha = "a" * 64
        receipt = evaluate_mesh_receipt(
            contract=contract,
            request_sha256=request_sha,
            modality="text",
            response={
                "model": "resolved/model",
                "provider": "ResolvedProvider",
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "cost": 0.0},
            },
            evidence_refs=("provider-run-1",),
            semantic_receipt=self._semantic_receipt(request_sha),
        )
        self.assertEqual(receipt.proof_state, MeshProofState.SEMANTIC_VERIFIED)
        self.assertEqual(receipt.resolved_model, "resolved/model")
        self.assertEqual(receipt.provider, "ResolvedProvider")
        self.assertTrue(receipt.semantic_verified)
        self.assertFalse(receipt.behavioral_proof_inherited)

    def test_semantic_success_cannot_be_self_asserted(self):
        contract = CognitiveCapabilityContract(contract_id="CCC-SELF-ASSERT", strategy=ProcessorStrategy.AUTO)
        with self.assertRaisesRegex(ValueError, "cannot be self-asserted"):
            evaluate_mesh_receipt(
                contract=contract,
                request_sha256="a" * 64,
                modality="text",
                response={"model": "resolved/model", "provider": "ResolvedProvider", "usage": {"cost": 0.0}},
                semantic_verified=True,
            )

    def test_semantic_receipt_identity_mismatch_is_rejected(self):
        contract = CognitiveCapabilityContract(contract_id="CCC-MISMATCH", strategy=ProcessorStrategy.AUTO)
        with self.assertRaisesRegex(ValueError, "request fingerprint mismatch"):
            evaluate_mesh_receipt(
                contract=contract,
                request_sha256="a" * 64,
                modality="text",
                response={"model": "resolved/model", "provider": "ResolvedProvider", "usage": {"cost": 0.0}},
                semantic_receipt=self._semantic_receipt("c" * 64),
            )


if __name__ == "__main__":
    unittest.main()
