from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_n_directive_v2.yaml"
BOOTSTRAP = ROOT / "governance" / "federation_node_bootstrap_v2.json"
MINIMUM_BOOTSTRAP_VERSION = (2, 3, 0)


def parse_version(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise AssertionError(f"invalid semantic version: {value!r}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


class FederationNDirectiveV2Tests(unittest.TestCase):
    def test_policy_contains_monotonic_innovation_contract(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        required = (
            "policy_id: FEDOMEGA-N-DIRECTIVE-V2",
            "version: 2.1.0",
            "input: n",
            "close the current critical dependency",
            "invoke the Formation Engine at full authorised capability",
            "invoke the Alpha-to-Omega Autonomous Solution Foundry at full authorised capability",
            "formation_engine_contract:",
            "alpha_omega_foundry_contract:",
            "innovation_frontier_contract:",
            "reuse-or-optimise, compose-or-extend, materially-new-or-innovative",
            "highest-information reversible experiment",
            "full_power_definition:",
            "authorised, safe, mission-aligned and evidence-matched",
            "prepare and start the next eligible experiment or packet",
            "explicit reusable continuation line: n = proceed",
            "future_nodes:",
            "mandatory at node creation or registration before substantive work",
            "authority_ceiling: A1_INTERNAL",
            "external_effect_default: false",
            "no invisible access to closed or unrelated chats is claimed",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_future_node_bootstrap_is_fail_closed_and_engine_bound(self) -> None:
        bootstrap = json.loads(BOOTSTRAP.read_text(encoding="utf-8"))
        self.assertGreaterEqual(parse_version(bootstrap["version"]), MINIMUM_BOOTSTRAP_VERSION)
        self.assertTrue(bootstrap["required_before_substantive_work"])
        self.assertTrue(bootstrap["surface_awareness"]["required"])
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V2", bootstrap["inherited_policies"])
        self.assertIn("AO-CRA-FEDERATION-INHERITANCE-V1", bootstrap["inherited_policies"])
        engines = bootstrap["n_directive"]["required_engines"]
        self.assertEqual("REQUIRED", engines["formation_engine"])
        self.assertEqual("REQUIRED", engines["alpha_omega_foundry"])
        self.assertEqual("REQUIRED", engines["ao_cra"])
        self.assertEqual("REQUIRED", engines["innovation_frontier"])
        self.assertTrue(bootstrap["full_power"]["reuse_before_rebuild"])
        self.assertFalse(bootstrap["full_power"]["invented_capabilities"])
        self.assertFalse(bootstrap["full_power"]["authority_expansion"])
        self.assertEqual("n = proceed", bootstrap["output_contract"]["explicit_continuation_line"])
        for field in (
            "formation_engine_result",
            "alpha_omega_foundry_result",
            "ao_cra_result_when_boundary_exists",
            "solution_alternatives_considered",
            "innovation_delta",
            "learning_delta",
            "complete_next_best_automated_pathway",
        ):
            with self.subTest(field=field):
                self.assertTrue(bootstrap["output_contract"][field])
        self.assertFalse(bootstrap["output_contract"]["status_only_closure_with_safe_work"])
        self.assertFalse(bootstrap["output_contract"]["terminal_limitation_without_build_trigger"])
        self.assertEqual("A1_INTERNAL", bootstrap["authority"]["ceiling"])
        self.assertFalse(bootstrap["authority"]["external_effect_default"])
        self.assertFalse(bootstrap["authority"]["trust_inheritance"])
        ao_cra = bootstrap["ao_cra"]
        self.assertTrue(ao_cra["mandatory_for_all_engines"])
        self.assertTrue(ao_cra["mandatory_for_all_operations"])
        self.assertEqual("UNRESOLVED_ENGINEERING_BUILD", ao_cra["gap_classification"])
        self.assertTrue(ao_cra["workaround_is_not_deployment"])
        self.assertFalse(ao_cra["terminal_boundary_without_build_record"])
        self.assertEqual("BOOTSTRAP_BLOCKED_FAIL_CLOSED", bootstrap["failure_state"])

    def test_governance_contracts_bind_the_policy_and_engines(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        required = (
            "FEDOMEGA-N-DIRECTIVE-V2",
            "Formation Engine",
            "Alpha-to-Omega",
            "AO-CRA-FEDERATION-INHERITANCE-V1",
            "innovation frontier",
            "n = proceed",
            "complete next-best automated pathway",
        )
        for phrase in required:
            with self.subTest(contract="AGENTS.md", phrase=phrase):
                self.assertIn(phrase, agents)

        copilot_path = ROOT / ".github" / "copilot-instructions.md"
        if copilot_path.exists():
            copilot = copilot_path.read_text(encoding="utf-8")
            for phrase in required[:-1]:
                with self.subTest(contract="copilot-instructions.md", phrase=phrase):
                    if phrase == "AO-CRA-FEDERATION-INHERITANCE-V1":
                        continue
                    self.assertIn(phrase, copilot)

    def test_policy_does_not_expand_consequential_authority(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        held = (
            "external communications",
            "legal filing",
            "payments and financial commitments",
            "evidence deletion or mutation",
            "material production deployment",
            "authority expansion",
            "trust transfer",
        )
        for phrase in held:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, policy)

    def test_first_viable_solution_cannot_skip_innovation_scan(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn("first_viable_route_without_innovation_scan", policy)
        self.assertIn("SOLUTION_PREMATURITY", policy)
        self.assertIn("anti_prematurity_rule", policy)


if __name__ == "__main__":
    unittest.main()
