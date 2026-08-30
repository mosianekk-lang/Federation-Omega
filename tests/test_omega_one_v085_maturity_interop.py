import unittest

from omega_one.interop import EffectClass, OmegaInteropSpine, OmegaTaskState, UniversalCapabilityContract
from omega_one.maturity import CapabilityMaturityCompiler, CapabilityRecord, MaturityStage, ProofClaim


def claims_through(stage: MaturityStage):
    return tuple(
        ProofClaim(item, True, (f"proof:{item.name}",))
        for item in MaturityStage
        if item <= stage
    )


class MaturityCompilerTests(unittest.TestCase):
    def test_contiguous_proof_promotes_only_to_last_contiguous_stage(self):
        record = CapabilityRecord(
            "CAP-031",
            "OpenAPI compiler",
            "adapters",
            claims_through(MaturityStage.DETERMINISTIC_TESTED),
        )
        verdict = CapabilityMaturityCompiler.compile(record)
        self.assertEqual(verdict.lowest_proven_stage, MaturityStage.DETERMINISTIC_TESTED)
        self.assertEqual(verdict.next_required_stage, MaturityStage.CI_ADMITTED)
        self.assertFalse(verdict.overclaim)
        self.assertEqual(verdict.detached_proven_stages, ())

    def test_detached_ci_cannot_skip_design_source_test(self):
        record = CapabilityRecord(
            "CAP-X",
            "Detached CI",
            "test",
            (ProofClaim(MaturityStage.CI_ADMITTED, True, ("ci:1",)),),
        )
        verdict = CapabilityMaturityCompiler.compile(record)
        self.assertIsNone(verdict.lowest_proven_stage)
        self.assertEqual(verdict.highest_claimed_stage, MaturityStage.CI_ADMITTED)
        self.assertTrue(verdict.overclaim)
        self.assertEqual(
            verdict.missing_predecessors,
            (
                MaturityStage.DESIGNED,
                MaturityStage.SOURCE_IMPLEMENTED,
                MaturityStage.DETERMINISTIC_TESTED,
            ),
        )
        self.assertEqual(verdict.detached_proven_stages, (MaturityStage.CI_ADMITTED,))

    def test_detached_provider_receipt_is_preserved_without_maturity_inheritance(self):
        record = CapabilityRecord(
            "CAP-Z",
            "Detached provider receipt",
            "provider",
            (
                ProofClaim(MaturityStage.DESIGNED, True, ("design:1",)),
                ProofClaim(MaturityStage.SOURCE_IMPLEMENTED, True, ("source:1",)),
                ProofClaim(MaturityStage.PROVIDER_EXECUTED, True, ("provider:1",)),
            ),
        )
        verdict = CapabilityMaturityCompiler.compile(record)
        self.assertEqual(verdict.lowest_proven_stage, MaturityStage.SOURCE_IMPLEMENTED)
        self.assertEqual(verdict.next_required_stage, MaturityStage.DETERMINISTIC_TESTED)
        self.assertEqual(
            verdict.missing_predecessors,
            (
                MaturityStage.DETERMINISTIC_TESTED,
                MaturityStage.CI_ADMITTED,
                MaturityStage.DEPLOYED,
            ),
        )
        self.assertEqual(verdict.detached_proven_stages, (MaturityStage.PROVIDER_EXECUTED,))
        self.assertIn("provider:1", verdict.evidence_refs)

    def test_full_value_chain(self):
        record = CapabilityRecord(
            "CAP-Y", "Full", "test", claims_through(MaturityStage.VALUE_VERIFIED)
        )
        verdict = CapabilityMaturityCompiler.compile(record)
        self.assertEqual(verdict.lowest_proven_stage, MaturityStage.VALUE_VERIFIED)
        self.assertIsNone(verdict.next_required_stage)
        self.assertFalse(verdict.overclaim)

    def test_portfolio_distribution(self):
        a = CapabilityRecord("A", "A", "d", claims_through(MaturityStage.SOURCE_IMPLEMENTED))
        b = CapabilityRecord("B", "B", "d", ())
        distribution = CapabilityMaturityCompiler.stage_distribution(
            CapabilityMaturityCompiler.compile_portfolio([b, a])
        )
        self.assertEqual(distribution["SOURCE_IMPLEMENTED"], 1)
        self.assertEqual(distribution["UNPROVEN"], 1)


class InteropSpineTests(unittest.TestCase):
    def base(self, **overrides):
        values = dict(
            capability_id="CAP-READ",
            name="Read Document",
            description="Read a document",
            input_schema={"type": "object", "properties": {"document_id": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"content": {"type": "string"}}},
            metadata={"omega-only-rich-semantic": {"preserve": True}},
        )
        values.update(overrides)
        return UniversalCapabilityContract(**values)

    def test_mcp_projection_uses_2026_stateless_routing_headers(self):
        bundle = OmegaInteropSpine.compile(self.base(), mission_id="M1")
        self.assertEqual(bundle.mcp.headers["MCP-Protocol-Version"], "2026-07-28")
        self.assertEqual(bundle.mcp.headers["Mcp-Method"], "tools/call")
        self.assertEqual(bundle.mcp.headers["Mcp-Name"], "Read-Document")
        self.assertEqual(
            bundle.mcp.request_meta["io.modelcontextprotocol/clientInfo"]["name"],
            "omega-one",
        )
        self.assertTrue(bundle.mcp.execution_ready)

    def test_a2a_governance_is_agent_capability_extension_not_skill_custom_field(self):
        bundle = OmegaInteropSpine.compile(self.base(), mission_id="M1")
        card = bundle.a2a.agent_card
        self.assertEqual(card["skills"][0]["id"], "CAP-READ")
        self.assertNotIn("extensions", card["skills"][0])
        ext = card["capabilities"]["extensions"][0]
        self.assertEqual(ext["uri"], "urn:omega-one:governance:v1")
        self.assertTrue(ext["required"])
        self.assertTrue(ext["params"]["zeroDilution"])
        self.assertEqual(card["supportedInterfaces"], [])
        self.assertFalse(bundle.a2a.execution_ready)
        self.assertEqual(bundle.a2a.hold_reason, "A2A_RUNTIME_INTERFACE_REQUIRED")

    def test_external_effect_is_projected_but_held_for_sovara(self):
        ucc = self.base(
            capability_id="CAP-SEND",
            name="Send Message",
            effect_class=EffectClass.EXTERNAL_EFFECT,
            rollback_required=True,
        )
        bundle = OmegaInteropSpine.compile(ucc, mission_id="M2")
        self.assertFalse(bundle.mcp.execution_ready)
        self.assertEqual(bundle.mcp.hold_reason, "SOVARA_EFFECT_AUTHORITY_REQUIRED")
        self.assertFalse(bundle.a2a.execution_ready)
        self.assertEqual(bundle.a2a.hold_reason, "SOVARA_EFFECT_AUTHORITY_REQUIRED")
        self.assertFalse(bundle.otel.attributes["omega.execution.ready"])

    def test_write_requires_rollback(self):
        ucc = self.base(effect_class=EffectClass.WRITE, rollback_required=False)
        with self.assertRaises(ValueError):
            OmegaInteropSpine.compile(ucc, mission_id="M3")

    def test_bundle_is_deterministic(self):
        ucc = self.base()
        first = OmegaInteropSpine.compile(ucc, mission_id="M4", trace_id="T")
        second = OmegaInteropSpine.compile(ucc, mission_id="M4", trace_id="T")
        self.assertEqual(first.bundle_sha256, second.bundle_sha256)
        self.assertEqual(first.source_ucc_sha256, second.source_ucc_sha256)

    def test_zero_dilution_preserves_exact_internal_contract(self):
        ucc = self.base(
            proof_required=("semantic_readback", "rollback"),
            metadata={
                "omega-only-rich-semantic": {"preserve": True, "creative_freedom": "FULL"},
                "future_standard_field": ["A", "B", "C"],
            },
        )
        bundle = OmegaInteropSpine.compile(ucc, mission_id="M-ZD")
        self.assertEqual(bundle.source_contract, ucc)
        self.assertTrue(bundle.zero_dilution_verified)
        self.assertTrue(OmegaInteropSpine.verify_zero_dilution(bundle))
        self.assertEqual(bundle.source_contract.metadata["future_standard_field"], ["A", "B", "C"])
        self.assertTrue(bundle.mcp.tool["_meta"]["omega.zero_dilution"])

    def test_a2a_task_state_mapping(self):
        self.assertEqual(
            OmegaInteropSpine.task_state_to_a2a(OmegaTaskState.AUTH_REQUIRED),
            "auth-required",
        )
        self.assertEqual(
            OmegaInteropSpine.task_state_to_a2a(OmegaTaskState.CANCELLED),
            "canceled",
        )

    def test_otel_uses_standard_execute_tool_operation_and_preserves_causal_fields(self):
        bundle = OmegaInteropSpine.compile(
            self.base(), mission_id="mission-7", trace_id="trace-7"
        )
        self.assertEqual(bundle.otel.attributes["service.name"], "omega-one")
        self.assertEqual(bundle.otel.attributes["omega.mission.id"], "mission-7")
        self.assertEqual(bundle.otel.attributes["omega.trace.id"], "trace-7")
        self.assertEqual(bundle.otel.attributes["gen_ai.operation.name"], "execute_tool")
        self.assertTrue(bundle.otel.attributes["omega.zero_dilution"])


if __name__ == "__main__":
    unittest.main()
