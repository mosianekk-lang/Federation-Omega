from __future__ import annotations

import json
import unittest
from pathlib import Path

from federation_consolidation.ao_cra import (
    BoundaryClass,
    BoundaryEvent,
    ENGINE_IDS,
    LifecycleState,
    create_build_trigger,
    is_boundary_statement,
    validate_promotion,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "ao_cra_federation_inheritance_v1.json"
BOOTSTRAP = ROOT / "governance" / "federation_node_bootstrap_v2.json"
AGENTS = ROOT / "AGENTS.md"


class AOCraFederationInheritanceTests(unittest.TestCase):
    def test_policy_covers_all_registered_federation_engine_families(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual("AO-CRA-FEDERATION-INHERITANCE-V1", policy["policy_id"])
        self.assertTrue(policy["inheritance"]["all_registered_engines"])
        self.assertTrue(policy["inheritance"]["all_federation_operations"])
        self.assertEqual(set(ENGINE_IDS), set(policy["engine_adapters"]))
        self.assertGreaterEqual(len(policy["operation_classes"]), 15)

    def test_boundary_language_creates_active_build_not_terminal_excuse(self) -> None:
        statement = "The provider API is unavailable and the connector permission is blocked."
        self.assertTrue(is_boundary_statement(statement))
        trigger = create_build_trigger(
            BoundaryEvent(
                statement=statement,
                desired_capability="Read provider state through an authorised adapter.",
                owning_engine="CLOUDOPS",
                dependency="provider authentication",
                source_trigger="test",
            ),
            existing_capabilities=("read-only connector",),
        )
        self.assertEqual(BoundaryClass.BLOCKED_DEPENDENCY_ACTIVE.value, trigger.classification)
        self.assertEqual(LifecycleState.BLOCKED_DEPENDENCY.value, trigger.lifecycle_state)
        self.assertTrue(trigger.build_id.startswith("BUILD-AO-FED-"))
        self.assertFalse(trigger.external_effect)
        self.assertIn("materially different route", trigger.next_executable_action)

    def test_workaround_remains_open_build(self) -> None:
        trigger = create_build_trigger(
            BoundaryEvent(
                statement="Native successor creation is unavailable.",
                desired_capability="Create and seed one successor conversation.",
                owning_engine="FORMATION_ENGINE",
                workaround="Generate a signed continuation packet.",
            )
        )
        self.assertEqual(BoundaryClass.WORKAROUND_ACTIVE_BUILD_OPEN.value, trigger.classification)
        self.assertEqual(LifecycleState.WORKAROUND_ACTIVE.value, trigger.lifecycle_state)
        self.assertNotEqual(LifecycleState.DEPLOYED.value, trigger.lifecycle_state)

    def test_promotion_requires_exact_evidence(self) -> None:
        trigger = create_build_trigger(
            BoundaryEvent(
                statement="Runtime capability is missing.",
                desired_capability="Provide a governed runtime.",
                owning_engine="FEDERATION_OMEGA_CORE",
            )
        )
        with self.assertRaises(ValueError):
            validate_promotion(
                trigger,
                LifecycleState.DEPLOYED,
                ("implementation", "tests", "acceptance", "readback"),
            )
        validate_promotion(
            trigger,
            LifecycleState.DEPLOYED,
            ("implementation", "tests", "acceptance", "readback", "runtime", "health", "persistence", "rollback"),
        )

    def test_bootstrap_and_agent_contract_require_ao_cra(self) -> None:
        bootstrap = json.loads(BOOTSTRAP.read_text(encoding="utf-8"))
        self.assertIn("AO-CRA-FEDERATION-INHERITANCE-V1", bootstrap["inherited_policies"])
        self.assertEqual("REQUIRED", bootstrap["n_directive"]["required_engines"]["ao_cra"])
        self.assertIn("AO_CRA_BOUNDARY_TO_BUILD_PREFLIGHT", bootstrap["n_directive"]["required_sequence"])
        self.assertIn("AO-CRA-FEDERATION-INHERITANCE-V1", AGENTS.read_text(encoding="utf-8"))

    def test_policy_forbids_authority_expansion_and_false_runtime_promotion(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual("A1_INTERNAL", policy["authority_ceiling"])
        self.assertFalse(policy["external_effect_default"])
        self.assertTrue(policy["proof_and_promotion"]["workaround_is_not_deployment"])
        self.assertTrue(policy["proof_and_promotion"]["source_is_not_runtime"])
        prohibited = " ".join(policy["prohibited"]).lower()
        self.assertIn("authority expansion", prohibited)
        self.assertIn("design or code existence promoted as deployed runtime", prohibited)


if __name__ == "__main__":
    unittest.main()
