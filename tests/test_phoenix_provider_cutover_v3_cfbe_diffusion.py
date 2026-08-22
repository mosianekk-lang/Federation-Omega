from __future__ import annotations

import unittest

from sovara_operator_adapter.benchmark_execution_bridge import (
    CapabilityGene,
    DiffusionCycleState,
    ReceiverState,
    ValueMeasurementEnvelope,
    compile_adoption_work_packet,
    detect_stranded_learning,
    rank_receiver_packets,
    validate_value_measurement,
)


def gene(**overrides):
    values = dict(
        gene_id="GENE-CFBE-P016",
        practice_id="P-016",
        origin="Palantir",
        capability="operational ontology binding object to capability to action to authority to proof",
        priority="P0",
        target_selector="ALL_SYSTEMS_WITH_ACTION_SEMANTICS",
        applicability_tags=("ONTOLOGY", "ACTION_SEMANTICS"),
        cost_class="INCLUDED",
        reversible=True,
        source_current=True,
    )
    values.update(overrides)
    return CapabilityGene(**values)


def receiver(**overrides):
    values = dict(
        receiver_id="KIM_DATAVERSE",
        receiver_class="SYSTEM",
        capability_tags=("ONTOLOGY", "SYSTEM_OF_RECORD"),
        source_current=True,
        authority_ceiling="A1_INTERNAL",
        existing_authority=True,
        independent_readback_available=True,
        rollback_available=True,
    )
    values.update(overrides)
    return ReceiverState(**values)


class CFBEBenchmarkExecutionDiffusionAirlockAdmission(unittest.TestCase):
    def test_safe_receiver_compiles_to_sovara_ready_adaptation(self) -> None:
        packet = compile_adoption_work_packet(gene(), receiver())
        self.assertEqual(packet.disposition, "ADAPT")
        self.assertEqual(packet.status, "READY_FOR_SOVARA_EXECUTION")
        self.assertEqual(packet.aaa_state, "AAA_ADAPT_READY")
        self.assertFalse(packet.authorizes_authority_inheritance)
        self.assertFalse(packet.self_certifies_value)

    def test_already_present_capability_does_not_create_duplicate_execution(self) -> None:
        packet = compile_adoption_work_packet(
            gene(), receiver(already_present_gene_ids=("GENE-CFBE-P016",))
        )
        self.assertEqual(packet.disposition, "ALREADY_PRESENT")
        self.assertEqual(packet.status, "NO_EXECUTION_REQUIRED")
        self.assertFalse(packet.autonomous_execution_admissible)

    def test_irrelevant_receiver_is_explicitly_not_applicable(self) -> None:
        packet = compile_adoption_work_packet(
            gene(applicability_tags=("GPU_RUNTIME",)),
            receiver(capability_tags=("LEGAL_WORKFLOW",)),
        )
        self.assertEqual(packet.disposition, "NOT_APPLICABLE")
        self.assertEqual(packet.status, "NO_EXECUTION_REQUIRED")

    def test_stale_receiver_holds_without_freezing_other_receivers(self) -> None:
        packet = compile_adoption_work_packet(gene(), receiver(source_current=False))
        self.assertEqual(packet.disposition, "HELD_WITH_EXACT_GATE")
        self.assertEqual(packet.status, "HELD_WITH_EXACT_GATE")
        self.assertTrue(packet.continue_unaffected_receivers)

    def test_paid_cost_or_missing_authority_requires_owner_trigger(self) -> None:
        paid = compile_adoption_work_packet(gene(), receiver(paid_or_unknown_incremental_cost=True))
        missing_auth = compile_adoption_work_packet(gene(), receiver(existing_authority=False))
        for packet in (paid, missing_auth):
            self.assertEqual(packet.status, "OWNER_TRIGGER_REQUIRED")
            self.assertTrue(packet.owner_trigger_required)
            self.assertFalse(packet.autonomous_execution_admissible)

    def test_iam_secret_or_external_effect_cannot_inherit_benchmark_authority(self) -> None:
        for field in ("iam_or_secret_change_required", "external_effect_required", "consequential_effect_required"):
            packet = compile_adoption_work_packet(gene(), receiver(**{field: True}))
            self.assertEqual(packet.status, "OWNER_TRIGGER_REQUIRED")
            self.assertFalse(packet.authorizes_authority_inheritance)

    def test_missing_independent_readback_holds_activation(self) -> None:
        packet = compile_adoption_work_packet(
            gene(), receiver(independent_readback_available=False)
        )
        self.assertEqual(packet.status, "HELD_WITH_EXACT_GATE")
        self.assertIn("readback", packet.reason)

    def test_p0_becomes_stranded_after_two_successful_eligible_cycles(self) -> None:
        state = DiffusionCycleState("GENE-CFBE-P016", "KIM_DATAVERSE", "P0", 2)
        self.assertEqual(detect_stranded_learning(state), "STRANDED_LEARNING_REVIEW_REQUIRED")

    def test_exact_provider_or_owner_hold_is_not_stranded(self) -> None:
        state = DiffusionCycleState(
            "GENE-CFBE-P020",
            "TARGET",
            "P0",
            9,
            exact_gate_recorded=True,
            fallback_and_resume_trigger_recorded=True,
        )
        self.assertEqual(detect_stranded_learning(state), "EXACT_GATE_NOT_STRANDED")

    def test_receiver_ranking_excludes_held_and_irrelevant_targets(self) -> None:
        packets = rank_receiver_packets(
            gene(),
            [
                receiver(receiver_id="B", capability_tags=("ONTOLOGY",)),
                receiver(receiver_id="A", capability_tags=("ONTOLOGY",)),
                receiver(receiver_id="STALE", source_current=False),
                receiver(receiver_id="IRRELEVANT", capability_tags=("OTHER",)),
            ],
        )
        self.assertEqual([packet.receiver_id for packet in packets], ["A", "B"])

    def test_value_requires_independent_readback_and_measurement(self) -> None:
        envelope = ValueMeasurementEnvelope(
            work_id="B2E-001",
            receiver_id="KIM_DATAVERSE",
            before_state="missing explicit value-return edge",
            change_executed="added benchmark-to-execution ontology edges",
            execution_ref="KDV-WRITE-001",
            independent_verifier="KDV-READBACK-001",
            readback_state="VERIFIED",
            capability_delta="POSITIVE",
            regression_state="PASS",
        )
        self.assertEqual(
            validate_value_measurement(envelope),
            "VALUE_MEASUREMENT_ADMISSIBLE_RECEIVER_SPECIFIC",
        )

    def test_executor_self_certification_is_rejected(self) -> None:
        envelope = ValueMeasurementEnvelope(
            work_id="B2E-001",
            receiver_id="KIM_DATAVERSE",
            before_state="before",
            change_executed="change",
            execution_ref="SAME-REF",
            independent_verifier="SAME-REF",
            readback_state="VERIFIED",
            capability_delta="POSITIVE",
        )
        self.assertEqual(
            validate_value_measurement(envelope),
            "VALUE_UNVERIFIED_EXECUTOR_SELF_CERTIFICATION",
        )


if __name__ == "__main__":
    unittest.main()
