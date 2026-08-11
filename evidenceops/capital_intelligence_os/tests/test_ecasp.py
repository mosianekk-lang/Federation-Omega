import unittest

from superior_logic.ecasp import (
    CorpusActivationState,
    CorpusObject,
    CorpusPreservationState,
    CorpusStatus,
    ECASPRequest,
    ecasp_triggered,
    evaluate_ecasp,
)


def complete_object(object_id: str) -> CorpusObject:
    return CorpusObject(
        object_id=object_id,
        discovered=True,
        indexed=True,
        body_retrieved=True,
        parsed=True,
        material_attachments_expected=1,
        material_attachments_processed=1,
        module_decomposed=True,
        deduped=True,
        version_reconciled=True,
        conflict_tested=True,
        requirement_coverage_tested=True,
        selected_or_rejected=True,
        verified=True,
        preservation_state=CorpusPreservationState.FULL_PRESERVED,
        activation_state=CorpusActivationState.ACTIVE_VALIDATED,
    )


class ECASPRegressionTests(unittest.TestCase):
    def test_trigger_detection(self):
        self.assertTrue(ecasp_triggered("Do a full sweep and choose the best combination"))
        self.assertFalse(ecasp_triggered("Read this one document"))

    def test_original_416_message_incident_is_blocked(self):
        objects = tuple(
            CorpusObject(object_id=f"gmail-{i}", discovered=True, indexed=True)
            for i in range(416)
        )
        result = evaluate_ecasp(
            ECASPRequest(
                instruction="Do a full sweep of all ChatGPT emails",
                intended_claim="final best code combination",
                expected_object_count=416,
                objects=objects,
            )
        )
        self.assertTrue(result.triggered)
        self.assertFalse(result.allow_exhaustive_final)
        self.assertEqual(CorpusStatus.INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE, result.status)
        self.assertNotIn("G1_INVENTORY", result.missing_gates)
        self.assertIn("G2_BODY_COVERAGE", result.missing_gates)
        self.assertIn("G10_CLAIM_LANGUAGE", result.missing_gates)
        self.assertNotIn("G11_NON_DILUTION_PRESERVATION", result.missing_gates)

    def test_complete_code_archive_can_release_only_when_non_dilution_gate_passes(self):
        objects = tuple(complete_object(f"module-{i}") for i in range(7))
        result = evaluate_ecasp(
            ECASPRequest(
                instruction="Audit every module and select the strongest stack",
                intended_claim="exhaustive final strongest stack",
                expected_object_count=7,
                objects=objects,
                capability_universe_mapped=True,
                lineage_map_complete=True,
                conflict_dependency_matrix_complete=True,
                requirement_coverage_complete=True,
                counterexample_search_complete=True,
                independent_readback_complete=True,
            )
        )
        self.assertTrue(result.allow_exhaustive_final)
        self.assertEqual(CorpusStatus.EXHAUSTIVE_FINAL, result.status)
        self.assertEqual((), result.missing_gates)
        self.assertEqual(7, result.object_counts["non_dilution_compliant"])

    def test_permanent_exclusion_without_owner_and_backup_fails_g11(self):
        item = complete_object("module-delete")
        item = CorpusObject(**{
            **item.__dict__,
            "permanent_exclusion_requested": True,
            "owner_decision_reference": None,
            "preservation_copy_reference": None,
        })
        result = evaluate_ecasp(
            ECASPRequest(
                instruction="Audit everything",
                intended_claim="complete",
                expected_object_count=1,
                objects=(item,),
                capability_universe_mapped=True,
                lineage_map_complete=True,
                conflict_dependency_matrix_complete=True,
                requirement_coverage_complete=True,
                counterexample_search_complete=True,
                independent_readback_complete=True,
            )
        )
        self.assertIn("G11_NON_DILUTION_PRESERVATION", result.missing_gates)
        self.assertFalse(result.allow_exhaustive_final)

    def test_duplicate_carrier_can_be_archived_without_deletion(self):
        item = complete_object("duplicate-carrier")
        item = CorpusObject(**{
            **item.__dict__,
            "preservation_state": CorpusPreservationState.ARCHIVED_QUERYABLE,
            "activation_state": CorpusActivationState.PRESERVED_DORMANT,
        })
        self.assertTrue(item.non_dilution_compliant())
        self.assertTrue(item.analytical_chain_complete())

    def test_legal_corpus_can_release_only_bounded_selection(self):
        analysed = complete_object("policy-a")
        unresolved = CorpusObject(object_id="scan-b", discovered=True, indexed=True)
        result = evaluate_ecasp(
            ECASPRequest(
                instruction="Review all documents and recommend the best authority",
                intended_claim="best authority from the reviewed subset",
                expected_object_count=2,
                objects=(analysed, unresolved),
                bounded_selection=True,
                bounded_scope_description="the one fully extracted policy",
                unresolved_material_objects_disclosed=True,
            )
        )
        self.assertFalse(result.allow_exhaustive_final)
        self.assertEqual(CorpusStatus.BOUNDED_SELECTION, result.status)
        self.assertIn("G2_BODY_COVERAGE", result.missing_gates)

    def test_excluded_immaterial_object_requires_reason(self):
        item = CorpusObject(
            object_id="newsletter",
            discovered=True,
            indexed=True,
            excluded_as_immaterial=True,
            exclusion_reason=None,
        )
        result = evaluate_ecasp(
            ECASPRequest(
                instruction="Audit everything",
                intended_claim="complete",
                expected_object_count=1,
                objects=(item,),
            )
        )
        self.assertIn("G2_BODY_COVERAGE", result.missing_gates)


if __name__ == "__main__":
    unittest.main()
