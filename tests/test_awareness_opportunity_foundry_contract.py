from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AWARENESS = ROOT / "governance" / "federation_surface_awareness_v1.json"
BOOTSTRAP = ROOT / "governance" / "federation_awareness_bootstrap_v1.json"
CONTRACT = ROOT / "governance" / "federation_awareness_opportunity_foundry_v1.json"
IMPLEMENTATION = ROOT / "federation_consolidation" / "awareness_opportunity_foundry.py"


class AwarenessOpportunityFoundryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.awareness = json.loads(AWARENESS.read_text(encoding="utf-8"))
        cls.bootstrap = json.loads(BOOTSTRAP.read_text(encoding="utf-8"))
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_and_implementation_are_bound(self) -> None:
        self.assertEqual(
            "FEDOMEGA-AWARENESS-OPPORTUNITY-FOUNDRY-CONTRACT-1",
            self.contract["schema"],
        )
        self.assertTrue(IMPLEMENTATION.is_file())
        self.assertEqual(
            "federation_consolidation/awareness_opportunity_foundry.py",
            self.contract["implementation"],
        )
        foundry = self.awareness["opportunity_foundry"]
        self.assertEqual(
            "governance/federation_awareness_opportunity_foundry_v1.json",
            foundry["contract"],
        )
        self.assertTrue(foundry["safe_internal_builds_automatic"])
        self.assertTrue(foundry["provider_gated_builds_registered_not_mutated"])

    def test_all_seven_internal_capabilities_are_declared(self) -> None:
        expected = {
            "PUBLIC_PRIVATE_AWARENESS_BINDING_VALIDATOR",
            "OBSERVED_MAIN_DRIFT_DETECTOR",
            "MISSION_TO_SURFACE_ROUTER",
            "NON_SECRET_CREDENTIAL_HANDLE_PREFLIGHT",
            "GMAIL_CONTINUITY_VS_CI_SIGNAL_FILTER",
            "FUTURE_NODE_AWARENESS_PACKET_GENERATOR",
            "AO_CRA_OPPORTUNITY_AND_BUILD_TRIGGER_REGISTRAR",
        }
        self.assertEqual(expected, set(self.contract["built_internal_capabilities"]))

    def test_bootstrap_runs_foundry_before_terminal_event(self) -> None:
        actions = [row["action"] for row in self.bootstrap["bootstrap_sequence"]]
        foundry = actions.index(
            "RUN_AWARENESS_OPPORTUNITY_FOUNDRY_AND_REGISTER_AO_CRA_BUILDS"
        )
        internal = actions.index(
            "EXECUTE_SAFE_INTERNAL_BUILDS_AND_HOLD_PROVIDER_GATED_EFFECTS"
        )
        terminal = actions.index(
            "EXECUTE_EXACT_ACTIVE_MISSION_AND_RECORD_TERMINAL_LEARNING_EVENT"
        )
        self.assertLess(foundry, internal)
        self.assertLess(internal, terminal)
        self.assertEqual(
            "FEDERATION_OPPORTUNITY_REGISTRY_PRIVATE_V1",
            self.bootstrap["private_opportunity_registry_alias"],
        )

    def test_provider_effects_and_credentials_remain_held(self) -> None:
        execution = self.contract["execution_contract"]
        self.assertTrue(execution["automatically_build_safe_internal_capabilities"])
        self.assertTrue(execution["automatically_register_provider_gated_builds"])
        self.assertFalse(execution["provider_mutation_performed"])
        self.assertFalse(execution["raw_credentials_accepted"])
        truth = self.contract["truth_boundary"]
        self.assertFalse(
            truth["internal_build_completion_proves_external_provider_readiness"]
        )
        self.assertTrue(
            truth["provider_or_external_effect_requires_fresh_authority_and_native_readback"]
        )

    def test_public_files_contain_no_private_exact_pointer_or_secret(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (AWARENESS, BOOTSTRAP, CONTRACT)
        )
        for private_value in (
            "1KfJVGnlgsdiXC_LOqtB0uSyCf94XdDXrhkxK5vNHM00",
            "1dnbLsLf97_dfX12Bd_rNfIhHp01Sf5Rl_pnqKFgJuds",
            "19fbb0ce6ae8e1ae",
        ):
            self.assertNotIn(private_value, text)
        patterns = (
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
            re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
        )
        self.assertFalse(any(pattern.search(text) for pattern in patterns))


if __name__ == "__main__":
    unittest.main()
