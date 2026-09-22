from __future__ import annotations

import unittest

from ao_harmonic_v3.forest_integrity_adapter import (
    CRITICAL_LEGACY_CONTROLS,
    ROUTE_ADMISSIBILITY_FIELDS,
    ForestIntegrityShadowAdapter,
)
from ao_harmonic_v3.forest_omega import ForestFirstOmega, ForestOmegaContext
from ao_harmonic_v3.models import TruthState


class PhoenixProviderCutoverV3ForestIntegrityAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = ForestIntegrityShadowAdapter()

    def test_legacy_true_controls_are_not_promoted_to_verified_truth(self):
        context = ForestOmegaContext(
            matter_id="M1",
            objective="protect objective",
            desired_outcome="safe verified completion",
        )
        report = self.adapter.evaluate(context)
        self.assertEqual(len(report.control_assessments), len(CRITICAL_LEGACY_CONTROLS))
        self.assertTrue(all(row["declared_value"] for row in report.control_assessments))
        self.assertTrue(all(row["typed_state"] == "DECLARED_TRUE_UNBOUND" for row in report.control_assessments))
        self.assertTrue(all(row["consequentially_proven"] is False for row in report.control_assessments))
        self.assertFalse(report.consequential_release_ready)

    def test_legacy_tree_fact_remains_unverified_without_provenance(self):
        context = ForestOmegaContext(
            matter_id="M2",
            objective="understand fact pattern",
            desired_outcome="evidence-bound decision",
            tree_facts=("A legacy string fact with no source binding",),
        )
        report = self.adapter.evaluate(context)
        self.assertEqual(len(report.evidence_atoms), 1)
        atom = report.evidence_atoms[0]
        self.assertEqual(atom["truth_state"], TruthState.UNVERIFIED)
        self.assertEqual(atom["source_refs"], ())
        self.assertFalse(atom["direct"])

    def test_missing_admissibility_fields_fail_closed_even_when_legacy_route_scores_high(self):
        route = {
            "route_id": "HIGH-SCORE-LEGACY",
            "feasibility": 1.0,
            "proof_strength": 1.0,
            "reversibility": 1.0,
            "speed": 1.0,
            "strategic_value": 10.0,
            "owner_burden": 0.0,
        }
        context = ForestOmegaContext(
            matter_id="M3",
            objective="choose safe route",
            desired_outcome="authorized completion",
            route_alternatives=(route,),
        )
        legacy = ForestFirstOmega().run(context)
        shadow = self.adapter.evaluate(context)
        self.assertEqual(legacy.decision["selected_path"]["route_id"], "HIGH-SCORE-LEGACY")
        self.assertEqual(shadow.admissible_paths, ())
        self.assertEqual(set(shadow.missing_route_fields["HIGH-SCORE-LEGACY"]), set(ROUTE_ADMISSIBILITY_FIELDS))

    def test_explicitly_admissible_route_can_enter_shadow_ranking_without_runtime_rewire(self):
        route = {
            "route_id": "EXPLICITLY-ADMISSIBLE",
            "available": True,
            "authorised": True,
            "safe": True,
            "deadline_viable": True,
            "privacy_acceptable": True,
            "cost_acceptable": True,
            "dependencies_ready": True,
            "evidence_sufficient": True,
            "rollback_available": True,
            "strategic_value": 0.8,
            "proof_strength": 0.9,
            "reversibility": 1.0,
            "information_gain": 0.7,
        }
        context = ForestOmegaContext(
            matter_id="M4",
            objective="preserve objective",
            desired_outcome="safe route",
            route_alternatives=(route,),
        )
        report = self.adapter.evaluate(context)
        self.assertEqual(tuple(row["path_id"] for row in report.admissible_paths), ("EXPLICITLY-ADMISSIBLE",))
        self.assertFalse(report.runtime_rewired)
        self.assertFalse(report.external_effect)
        self.assertFalse(report.provider_effect_proved)

    def test_consequential_legacy_context_is_held_without_typed_owner_approval(self):
        route = {
            "route_id": "REVERSIBLE",
            "available": True,
            "authorised": True,
            "safe": True,
            "deadline_viable": True,
            "privacy_acceptable": True,
            "cost_acceptable": True,
            "dependencies_ready": True,
            "evidence_sufficient": True,
            "rollback_available": True,
        }
        context = ForestOmegaContext(
            matter_id="M5",
            objective="take consequential action",
            desired_outcome="authorized effect",
            consequential_action_planned=True,
            route_alternatives=(route,),
            tree_facts=("unverified legacy fact",),
        )
        report = self.adapter.evaluate(context)
        self.assertFalse(report.owner_approval_represented)
        self.assertFalse(report.consequential_release_ready)
        self.assertEqual(report.authority_ceiling, "A1_INTERNAL")


if __name__ == "__main__":
    unittest.main()
