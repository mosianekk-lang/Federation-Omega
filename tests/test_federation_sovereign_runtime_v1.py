from __future__ import annotations

import unittest

from ao_harmonic_v3.intelligence_router import IntelligenceSignals, IntelligenceTier

from federation_sovereign_runtime import (
    ASTRA_CONTEXT_WINDOW,
    ASTRA_MAX_OUTPUT_TOKENS,
    ASTRA_MODEL_ID,
    ASTRA_PUBLIC_CAPABILITIES,
    AdaptiveReasoningController,
    AlignmentSentinel,
    ContextItem,
    ContextVirtualizer,
    FederationSovereignRuntimeBinding,
    MissionFrame,
    MissionSteeringController,
    NonblockingToolBroker,
    ProcessorProfile,
    ProcessorRequirement,
    ReasoningEffort,
    SovereignProcessorMarket,
    SteeringEvent,
    SteeringKind,
    ToolEffect,
    ToolTicket,
    WorkState,
    astra_air_binding,
    configuration_update_item,
    public_astra_profile,
    with_async_tool,
)


class SovereignRuntimeTests(unittest.TestCase):
    @staticmethod
    def mission() -> MissionFrame:
        return MissionFrame(
            mission_id="MISSION-FSIR-001",
            owner="Kim Kagiso Mosiane",
            root_objective="Build a sovereign Federation intelligence runtime.",
            current_objective="Build a sovereign Federation intelligence runtime.",
            success_conditions=("Provider-neutral runtime passes regressions",),
            completed_work_refs=("proof:forest-first", "proof:human-first"),
        )

    def test_side_question_preserves_root_and_current_objective(self) -> None:
        controller = MissionSteeringController()
        original = self.mission()
        result = controller.apply(
            original,
            SteeringEvent(
                event_id="STEER-1",
                kind=SteeringKind.SIDE_QUESTION,
                content="What is the current proof boundary?",
            ),
        )
        self.assertTrue(result.accepted)
        self.assertEqual(original.root_objective, result.mission.root_objective)
        self.assertEqual(original.current_objective, result.mission.current_objective)
        self.assertEqual(original.completed_work_refs, result.mission.completed_work_refs)

    def test_objective_change_requires_explicit_owner_authority(self) -> None:
        controller = MissionSteeringController()
        original = self.mission()
        held = controller.apply(
            original,
            SteeringEvent(
                event_id="STEER-2",
                kind=SteeringKind.OBJECTIVE_CHANGE,
                content="Replace the entire mission.",
                owner_authorized=False,
            ),
        )
        self.assertFalse(held.accepted)
        self.assertTrue(held.human_required)
        self.assertEqual(original.current_objective, held.mission.current_objective)

        accepted = controller.apply(
            original,
            SteeringEvent(
                event_id="STEER-3",
                kind=SteeringKind.OBJECTIVE_CHANGE,
                content="Build the sovereign runtime and its empirical benchmark court.",
                owner_authorized=True,
            ),
        )
        self.assertTrue(accepted.accepted)
        self.assertEqual(
            "Build the sovereign runtime and its empirical benchmark court.",
            accepted.mission.current_objective,
        )
        self.assertEqual(original.root_objective, accepted.mission.root_objective)

    def test_reasoning_effort_escalates_with_pressure_and_failures(self) -> None:
        controller = AdaptiveReasoningController()
        routine = controller.choose(complexity=0.1, consequence=0.1, uncertainty=0.1, adversarial_complexity=0.1)
        hard = controller.choose(
            current=routine,
            complexity=0.9,
            consequence=0.9,
            uncertainty=0.8,
            adversarial_complexity=0.8,
            high_stakes=True,
            repeated_failures=2,
        )
        self.assertEqual(ReasoningEffort.LOW, routine.effort)
        self.assertIn(hard.effort, {ReasoningEffort.XHIGH, ReasoningEffort.MAX})
        self.assertGreater(hard.configuration_version, routine.configuration_version)

    def test_external_async_tool_requires_authority_and_readback(self) -> None:
        broker = NonblockingToolBroker()
        with self.assertRaises(PermissionError):
            broker.submit(
                ToolTicket(
                    call_id="CALL-1",
                    tool_name="provider-write",
                    effect=ToolEffect.REVERSIBLE_EXTERNAL,
                )
            )
        ticket = broker.submit(
            ToolTicket(
                call_id="CALL-2",
                tool_name="provider-write",
                effect=ToolEffect.REVERSIBLE_EXTERNAL,
                authorization_ref="OWNER:MISSION-SCOPED",
                readback_required=True,
            )
        )
        self.assertEqual(WorkState.RUNNING, ticket.state)
        self.assertTrue(broker.independent_work_may_continue(dependency_call_ids=("OTHER",)))
        self.assertFalse(broker.independent_work_may_continue(dependency_call_ids=("CALL-2",)))
        completed = broker.complete("CALL-2", result_ref="provider:readback:123")
        self.assertEqual(WorkState.COMPLETE, completed.state)

    def test_uncertain_external_failure_moves_to_hold_readback(self) -> None:
        broker = NonblockingToolBroker()
        broker.submit(
            ToolTicket(
                call_id="CALL-X",
                tool_name="provider-write",
                effect=ToolEffect.REVERSIBLE_EXTERNAL,
                authorization_ref="OWNER:MISSION-SCOPED",
                readback_required=True,
            )
        )
        failed = broker.fail("CALL-X", error="timeout after dispatch", effect_uncertain=True)
        self.assertEqual(WorkState.HOLD_READBACK, failed.state)

    def test_context_compaction_never_silently_drops_pinned_proof(self) -> None:
        virtualizer = ContextVirtualizer()
        capsule = virtualizer.compact(
            (
                ContextItem("proof-1", "critical proof", 80, 1.0, 1.0, proof_bearing=True, pinned=True),
                ContextItem("optional-1", "background", 50, 0.2, 0.1),
            ),
            budget_tokens=60,
        )
        self.assertTrue(capsule.overflow)
        self.assertEqual(("proof-1",), tuple(item.item_id for item in capsule.selected))
        self.assertIn("optional-1", capsule.omitted_ids)

    def test_processor_market_fails_closed_on_missing_measurements(self) -> None:
        market = SovereignProcessorMarket()
        profile = ProcessorProfile(
            processor_id="P1",
            provider="TEST",
            model="test-model",
            capabilities=frozenset({"REASONING"}),
            available=True,
            authorized=True,
        )
        decision = market.select(
            ProcessorRequirement(required_capabilities=frozenset({"REASONING"})),
            (profile,),
        )
        self.assertIsNone(decision.selected)
        self.assertEqual("HOLD_NO_PROVEN_ELIGIBLE_PROCESSOR", decision.state)

    def test_processor_market_chooses_best_measured_eligible_processor(self) -> None:
        market = SovereignProcessorMarket()
        a = ProcessorProfile(
            processor_id="A",
            provider="P",
            model="A",
            capabilities=frozenset({"REASONING", "TOOLS"}),
            available=True,
            authorized=True,
            measured_quality=0.9,
            measured_latency_score=0.7,
            measured_cost_score=0.6,
            measured_privacy_score=0.8,
        )
        b = ProcessorProfile(
            processor_id="B",
            provider="P",
            model="B",
            capabilities=frozenset({"REASONING", "TOOLS"}),
            available=True,
            authorized=True,
            measured_quality=0.8,
            measured_latency_score=0.9,
            measured_cost_score=0.9,
            measured_privacy_score=0.9,
        )
        decision = market.select(
            ProcessorRequirement(required_capabilities=frozenset({"REASONING", "TOOLS"})),
            (a, b),
        )
        self.assertIsNotNone(decision.selected)
        self.assertEqual("B", decision.selected.processor_id)

    def test_alignment_sentinel_detects_objective_authority_and_scope_drift(self) -> None:
        findings = AlignmentSentinel().inspect(
            mission=self.mission(),
            proposed_objective="Different objective",
            required_authority="A2_EXTERNAL_REVERSIBLE",
            allowed_authority="A1_INTERNAL",
            claimed_scope="UNIVERSAL_RUNTIME",
            proven_scope="SOURCE_BOUND",
        )
        self.assertEqual(
            {
                "OBJECTIVE_DRIFT",
                "AUTHORITY_SCOPE_CHANGE",
                "CLAIM_SCOPE_EXCEEDS_OR_DIFFERS_FROM_PROOF",
            },
            {item.code for item in findings},
        )


class AstraHarvestTests(unittest.TestCase):
    def test_public_astra_profile_has_public_specs_without_fake_empirical_scores(self) -> None:
        profile = public_astra_profile(available=False, authorized=False)
        self.assertEqual(ASTRA_MODEL_ID, profile.model)
        self.assertEqual(1_050_000, ASTRA_CONTEXT_WINDOW)
        self.assertEqual(128_000, ASTRA_MAX_OUTPUT_TOKENS)
        self.assertIn("ASYNC_TOOL_CALLING", ASTRA_PUBLIC_CAPABILITIES)
        self.assertIn("MID_TURN_STEERING", ASTRA_PUBLIC_CAPABILITIES)
        self.assertIsNone(profile.measured_quality)
        self.assertFalse(profile.available)
        self.assertFalse(profile.authorized)

    def test_astra_async_modifier_is_limited_to_function_or_custom_tools(self) -> None:
        tool = with_async_tool({"type": "function", "name": "lookup", "parameters": {"type": "object"}})
        self.assertTrue(tool["async"])
        with self.assertRaises(ValueError):
            with_async_tool({"type": "web_search"})

    def test_configuration_update_uses_supported_effort(self) -> None:
        item = configuration_update_item(ReasoningEffort.XHIGH)
        self.assertEqual("configuration_update", item["type"])
        self.assertEqual("xhigh", item["reasoning"]["effort"])
        with self.assertRaises(ValueError):
            configuration_update_item("none")

    def test_astra_air_binding_reuses_existing_router_without_claiming_execution(self) -> None:
        binding = astra_air_binding(
            IntelligenceTier.HIGH,
            available=True,
            authorised=True,
            estimated_monthly_cost=0.0,
            already_paid_or_included=True,
        )
        self.assertEqual("gpt-6-astra", binding.model)
        self.assertEqual("high", binding.reasoning_effort)
        self.assertTrue(binding.programmatic)

    def test_ao_harmonic_binding_can_prepare_but_not_execute_astra_request(self) -> None:
        runtime = FederationSovereignRuntimeBinding()
        decision = runtime.route_astra(
            IntelligenceSignals(
                task_id="ASTRA-ROUTE-1",
                complexity=0.7,
                consequence=0.5,
                uncertainty=0.4,
                required_accuracy=0.8,
            ),
            available=True,
            authorised=True,
            estimated_monthly_cost=0.0,
            already_paid_or_included=True,
        )
        self.assertTrue(decision.execution_allowed)
        payload = runtime.prepare_astra_response(decision, "Analyze the mission.")
        self.assertEqual("gpt-6-astra", payload["model"])
        self.assertEqual("Analyze the mission.", payload["input"])
        acceptance = runtime.restore_acceptance_test()
        self.assertFalse(acceptance["truth_boundary"]["astra_provider_invoked"])
        self.assertFalse(acceptance["truth_boundary"]["provider_acceptance_proved"])


if __name__ == "__main__":
    unittest.main()
