import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / "governance"


def load(name: str):
    return json.loads((GOV / name).read_text(encoding="utf-8"))


class ForestFirstArchitectureConsolidationV1Tests(unittest.TestCase):
    def setUp(self):
        self.arch = load("ao_harmonic_forest_first_architecture_consolidation_v1.json")
        self.compat = load("ao_harmonic_forest_first_compatibility_manifest_v1.json")
        self.deps = load("ao_harmonic_forest_first_dependency_contract_v1.json")
        self.migration = load("ao_harmonic_forest_first_migration_contracts_v1.json")

    def test_exact_eight_layers_and_human_root(self):
        layers = self.arch["layers"]
        self.assertEqual(len(layers), 8)
        self.assertEqual([layer["id"] for layer in layers], [f"L{i}" for i in range(8)])
        self.assertEqual(layers[0]["name"], "HUMAN_SOVEREIGNTY")
        self.assertTrue(layers[0]["must_remain_independent"])

    def test_all_registered_systems_are_accounted_for_without_deletion(self):
        dispositions = self.arch["system_dispositions"]
        self.assertEqual(len(dispositions), 27)
        names = [row["system"] for row in dispositions]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(row["destructive_change_allowed"] is False for row in dispositions))
        self.assertFalse(any(row["disposition"] == "DELETE" for row in dispositions))

    def test_new_top_level_system_requires_all_four_uniqueness_criteria(self):
        rule = self.arch["top_level_system_admission_rule"]
        self.assertTrue(rule["all_required"])
        self.assertEqual(
            {row["id"] for row in rule["criteria"]},
            {"UNIQUE_AUTHORITY", "UNIQUE_STATE", "UNIQUE_RUNTIME", "UNIQUE_FAILURE_DOMAIN"},
        )

    def test_compatibility_never_inherits_authority_or_maturity(self):
        for row in self.compat["entries"]:
            self.assertFalse(row["silent_authority_transfer"])
            self.assertFalse(row["maturity_inheritance"])
            self.assertFalse(row["deletion_allowed"])
            self.assertTrue(row["lineage_policy"].startswith("PRESERVE"))

    def test_independent_assurance_remains_independent(self):
        by_name = {row["system"]: row for row in self.arch["system_dispositions"]}
        for system in ("Sentinel Ω", "JARVIS", "Reality Guard", "CFBE-Ω"):
            self.assertEqual(by_name[system]["disposition"], "KEEP_INDEPENDENT")

    def test_forbidden_authority_transfers_exist(self):
        forbidden = {(edge["from"], edge["transition"]) for edge in self.deps["forbidden_edges"]}
        self.assertIn(("ASSURANCE_REALITY", "EXECUTE_EXTERNAL_EFFECT"), forbidden)
        self.assertIn(("LEARNING_EVOLUTION", "INHERIT_PROVIDER_OR_DOMAIN_AUTHORITY"), forbidden)
        self.assertIn(("ANY", "SILENTLY_OVERRIDE_RESERVED_CONSEQUENTIAL_DECISION"), forbidden)

    def test_runtime_and_provider_effect_remain_false(self):
        self.assertFalse(self.arch["truth_boundary"]["runtime_changed"])
        self.assertFalse(self.arch["truth_boundary"]["provider_effect"])
        self.assertFalse(self.deps["truth_boundary"]["runtime_binding_changed"])
        self.assertFalse(self.migration["truth_boundary"]["migration_executed"])
        self.assertFalse(self.migration["truth_boundary"]["provider_effect"])

    def test_migration_is_ordered_and_non_destructive_before_retirement(self):
        phases = self.migration["phases"]
        self.assertEqual([p["id"] for p in phases], [f"P{i}" for i in range(7)])
        for phase in phases[:-1]:
            self.assertNotIn("delete", " ".join(phase["actions"]).lower())
        self.assertTrue(self.migration["rollback_policy"]["every_phase_reversible_until_P6"])
        self.assertTrue(self.migration["rollback_policy"]["historical_proof_never_rewritten"])


if __name__ == "__main__":
    unittest.main()
