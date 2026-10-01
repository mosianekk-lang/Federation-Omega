import unittest

from federation.formation_cyber_investigative_engine_v1 import (
    AnalysisDisposition,
    FormationCyberInvestigativeEngine,
    InvestigationKind,
    InvestigationTarget,
    RightsScope,
)


class FormationCyberInvestigativeEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = FormationCyberInvestigativeEngine()

    def test_owned_source_gets_direct_source_analysis(self):
        plan = self.engine.compile(InvestigationTarget(
            target_id="owned-repo",
            objective="understand implementation and operational capability",
            kinds=frozenset({InvestigationKind.SOURCE_CODE, InvestigationKind.API_SURFACE}),
            rights_scope=RightsScope.OWNER_CONTROLLED,
            source_available=True,
        ))
        self.assertEqual(plan.disposition, AnalysisDisposition.DIRECT_SOURCE_ANALYSIS.value)
        self.assertIn("FCIE-SOURCE-GRAPH", [c.capability_id for c in plan.capabilities])
        self.assertFalse(plan.external_effect_authorized)

    def test_closed_binary_without_source_uses_clean_room(self):
        plan = self.engine.compile(InvestigationTarget(
            target_id="licensed-binary",
            objective="derive operational behaviour",
            kinds=frozenset({InvestigationKind.BINARY_METADATA, InvestigationKind.BEHAVIOUR_TRACE}),
            rights_scope=RightsScope.LICENSED_ANALYSIS,
            binaries_available=True,
        ))
        self.assertEqual(plan.disposition, AnalysisDisposition.CLEAN_ROOM_BEHAVIOURAL_SPEC.value)
        self.assertIn("NO_PROPRIETARY_SOURCE_EQUIVALENCE_FROM_BLACK_BOX", plan.proof_requirements)

    def test_unknown_rights_holds(self):
        plan = self.engine.compile(InvestigationTarget(
            target_id="unknown",
            objective="inspect",
            kinds=frozenset({InvestigationKind.SOURCE_CODE}),
            rights_scope=RightsScope.UNKNOWN,
        ))
        self.assertEqual(plan.disposition, AnalysisDisposition.HOLD_RIGHTS_OR_AUTHORITY.value)
        self.assertIn("HOLD_WITH_EXACT_RIGHTS_OR_AUTHORITY_GAP", plan.stages)

    def test_protected_content_without_source_is_metadata_only(self):
        plan = self.engine.compile(InvestigationTarget(
            target_id="protected",
            objective="understand capability",
            kinds=frozenset({InvestigationKind.BINARY_METADATA}),
            rights_scope=RightsScope.LICENSED_ANALYSIS,
            binaries_available=True,
            protected_content=True,
        ))
        self.assertEqual(plan.disposition, AnalysisDisposition.METADATA_ONLY.value)
        self.assertIn("DRM_OR_ACCESS_CONTROL_CIRCUMVENTION", plan.prohibited_actions)

    def test_network_and_software_capabilities_compose(self):
        plan = self.engine.compile(InvestigationTarget(
            target_id="device-software",
            objective="map device software and network capability",
            kinds=frozenset({
                InvestigationKind.NETWORK_DEVICE,
                InvestigationKind.CONFIGURATION,
                InvestigationKind.LOG_TELEMETRY,
                InvestigationKind.DIGITAL_TWIN,
            }),
            rights_scope=RightsScope.OWNER_CONTROLLED,
            logs_available=True,
        ))
        ids={c.capability_id for c in plan.capabilities}
        self.assertTrue({"FCIE-NETWORK-IDENTITY","FCIE-CONFIG-SCHEMA","FCIE-LOG-MINER","FCIE-DIGITAL-TWIN"}.issubset(ids))
        self.assertIn("FAILURE_FINGERPRINT_AND_WORKAROUND_COMPILATION", plan.stages)


if __name__ == "__main__":
    unittest.main()
