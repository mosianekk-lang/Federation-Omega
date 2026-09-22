import unittest

from ao_harmonic_v3.architecture_consolidation import ArchitectureConsolidationRegistry


class ForestFirstArchitectureInterfaceV1Tests(unittest.TestCase):
    def setUp(self):
        self.registry = ArchitectureConsolidationRegistry()

    def test_superior_logic_resolves_to_cognitive_policy_without_inheritance(self):
        resolved = self.registry.resolve("Superior Logic Doctrine")
        self.assertEqual(resolved.target_authority_layer, "COGNITIVE_KERNEL")
        self.assertEqual(resolved.disposition, "ABSORB")
        self.assertFalse(resolved.proof_inherited)
        self.assertFalse(resolved.authority_inherited)
        self.assertFalse(resolved.maturity_inherited)
        self.assertFalse(resolved.external_effect)

    def test_legacy_identity_remains_resolvable(self):
        resolved = self.registry.resolve("AEON-Ω")
        self.assertTrue(resolved.legacy_calls_allowed)
        self.assertEqual(resolved.disposition, "RETIRE_SOVEREIGN_KEEP_LINEAGE")

    def test_split_identity_exposes_bible_and_scientia_targets(self):
        resolved = self.registry.resolve("Next Frontier AI Bible / Ω-SCIENTIA")
        self.assertEqual(resolved.target_authority_layer, "SPLIT")
        by_name = {item["identity"]: item for item in resolved.target_components}
        self.assertEqual(by_name["Next Frontier AI Bible"]["target_authority_layer"], "LEARNING_EVOLUTION")
        self.assertEqual(by_name["Ω-SCIENTIA"]["target_authority_layer"], "COGNITIVE_KERNEL")
        self.assertFalse(resolved.authority_inherited)
        self.assertFalse(resolved.maturity_inherited)

    def test_top_level_admission_requires_all_four_criteria(self):
        denied = self.registry.admit_top_level_system(unique_authority=True,unique_state=True,unique_runtime=True,unique_failure_domain=False)
        self.assertFalse(denied.admitted_as_top_level_system)
        self.assertEqual(denied.missing_criteria, ("UNIQUE_FAILURE_DOMAIN",))
        admitted = self.registry.admit_top_level_system(unique_authority=True,unique_state=True,unique_runtime=True,unique_failure_domain=True)
        self.assertTrue(admitted.admitted_as_top_level_system)
        self.assertFalse(admitted.authority_expanded)
        self.assertFalse(admitted.external_effect)

    def test_forbidden_transitions_are_machine_checkable(self):
        self.assertTrue(self.registry.transition_forbidden("ASSURANCE_REALITY", "MISSION_EXECUTION", "EXECUTE_EXTERNAL_EFFECT"))
        self.assertTrue(self.registry.transition_forbidden("LEARNING_EVOLUTION", "DOMAIN_INTELLIGENCE", "INHERIT_PROVIDER_OR_DOMAIN_AUTHORITY"))
        self.assertTrue(self.registry.transition_forbidden("MISSION_EXECUTION", "HUMAN_SOVEREIGNTY", "SILENTLY_OVERRIDE_RESERVED_CONSEQUENTIAL_DECISION"))

    def test_independent_assurance_is_preserved(self):
        self.assertEqual(set(self.registry.independent_systems()), {"Sentinel Ω", "CFBE-Ω", "JARVIS", "Reality Guard"})

    def test_p1_remains_source_only(self):
        phase = self.registry.migration_phase("P1")
        self.assertEqual(phase["effect"], "SOURCE_ONLY")
        boundary = self.registry.source_truth_boundary()
        self.assertEqual(boundary,{"runtime_changed":False,"provider_effect":False,"authority_expanded":False,"migration_executed":False})


if __name__ == "__main__":
    unittest.main()
