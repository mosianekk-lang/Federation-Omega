from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_evolution_program import SYSTEM_PROFILES
from evidenceops.caseforge.federation_evolution_runtime import COMMON_RUNTIME_STAGES
from evidenceops.caseforge.federation_specialized_paths import (
    SpecializedPathContract,
    SpecializedPathResolver,
)


class SpecializedPathTests(unittest.TestCase):
    def test_every_registered_system_resolves_a_machine_readable_path(self) -> None:
        resolved = SpecializedPathResolver().resolve_all()
        self.assertEqual(set(SYSTEM_PROFILES), set(resolved))
        for system_id, path in resolved.items():
            with self.subTest(system_id=system_id):
                self.assertTrue(path.algorithm_chain)
                self.assertEqual(COMMON_RUNTIME_STAGES, path.common_runtime_stages)
                self.assertEqual("A1_INTERNAL", path.authority_ceiling)
                self.assertFalse(path.external_effect)
                self.assertTrue(path.stronger_or_equal_to_common)

    def test_high_value_unique_paths_preserve_domain_algorithms(self) -> None:
        resolver = SpecializedPathResolver()
        expected = {
            "TRUTHGRID": "TRUTHSTATE",
            "JFRIE": "JURISDICTION_FIRST",
            "LEX_OMEGA": "AUTHORITY_HIERARCHY",
            "KAIO": "FLUID_COMPILER",
            "MODISA": "FORMATION_FIELD",
            "FEDERATION_OMEGA": "AIRLOCK",
            "CASEFORGE": "BLIND_RUNNER",
        }
        for system_id, algorithm in expected.items():
            with self.subTest(system_id=system_id):
                path = resolver.resolve(system_id)
                self.assertIn(algorithm, path.algorithm_chain)

    def test_specialized_path_cannot_skip_common_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "may not skip"):
            SpecializedPathContract(
                system_id="TRUTHGRID",
                optimization_objective="truth",
                algorithm_chain=("TRUTHSTATE",),
                vetoes=(),
                common_runtime_stages=COMMON_RUNTIME_STAGES[:-1],
            ).validate()

    def test_specialized_path_cannot_expand_authority(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot expand authority"):
            SpecializedPathContract(
                system_id="KAIO",
                optimization_objective="fluid intelligence",
                algorithm_chain=("FLUID_COMPILER",),
                vetoes=(),
                authority_ceiling="A5",
            ).validate()

    def test_execution_context_requires_proof_and_rollback_for_mutation(self) -> None:
        context = SpecializedPathResolver().execution_context("MODISA")
        self.assertTrue(context.proof_required)
        self.assertTrue(context.rollback_required_for_mutation)
        self.assertFalse(context.external_effect)


if __name__ == "__main__":
    unittest.main()
