from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "governance" / "federation_n_directive_domain_conformance.py"
)
SPEC = importlib.util.spec_from_file_location(
    "federation_n_directive_domain_conformance",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
DOMAIN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DOMAIN
SPEC.loader.exec_module(DOMAIN)

PROFILES = (
    ROOT
    / "tests"
    / "fixtures"
    / "federation_n_domain_conformance_profiles.json"
)
BASE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "federation_n_future_node_valid.json"
)
BOOTSTRAP = ROOT / "governance" / "federation_node_bootstrap_v2.json"
POLICY = ROOT / "governance" / "federation_n_directive_v2.yaml"


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


class FederationNDirectiveDomainConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_document = load_json(PROFILES)
        cls.base_fixture = load_json(BASE_FIXTURE)
        cls.bootstrap = load_json(BOOTSTRAP)
        cls.policy_text = POLICY.read_text(encoding="utf-8")

    def build_suite(self) -> dict:
        return DOMAIN.build_cross_domain_suite(
            profile_document=self.profile_document,
            base_fixture=self.base_fixture,
            bootstrap=self.bootstrap,
            policy_text=self.policy_text,
        )

    def test_profile_document_contains_exact_four_domains(self) -> None:
        validation = DOMAIN.validate_profile_document(self.profile_document)
        self.assertTrue(validation["passed"])
        profiles = self.profile_document["profiles"]
        self.assertEqual(4, len(profiles))
        self.assertEqual(
            set(DOMAIN.EXPECTED_DOMAINS),
            {profile["domain_id"] for profile in profiles},
        )

    def test_each_domain_profile_is_fail_closed_and_complete(self) -> None:
        for profile in self.profile_document["profiles"]:
            with self.subTest(domain=profile["domain_id"]):
                validation = DOMAIN.validate_domain_profile(profile)
                self.assertTrue(validation["passed"], validation["violations"])
                self.assertTrue(
                    set(profile["required_controls"]).issubset(
                        set(profile["success_criteria"])
                    )
                )
                self.assertTrue(
                    set(profile["prohibited_outcomes"]).issubset(
                        set(profile["constraints"])
                    )
                )

    def test_all_four_domain_canaries_pass_complete_contract(self) -> None:
        suite = self.build_suite()
        self.assertTrue(suite["passed"])
        self.assertEqual(
            "CROSS_DOMAIN_CONFORMANCE_VERIFIED_SYNTHETIC",
            suite["status"],
        )
        self.assertEqual(4, len(suite["domain_results"]))
        for result in suite["domain_results"]:
            with self.subTest(domain=result["domain_id"]):
                self.assertTrue(result["passed"])
                self.assertTrue(result["domain_validation"]["passed"])
                self.assertEqual(3, result["formation_route_family_count"])
                self.assertEqual(4, result["innovation_candidate_count"])
                self.assertEqual(
                    result["required_output_total"],
                    result["required_output_count"],
                )
                self.assertEqual(0, result["authority_violations"])
                self.assertEqual(0, result["synthetic_owner_prompts_required"])
                self.assertTrue(result["deterministic_replay"])
                self.assertEqual(
                    "n = proceed",
                    result["canary"]["continuation"],
                )

    def test_cross_domain_coverage_delta_is_bounded_and_complete(self) -> None:
        suite = self.build_suite()
        self.assertEqual(0, suite["baseline"]["behavioural_domain_receipts"])
        self.assertEqual("0/4", suite["baseline"]["domain_transfer_coverage"])
        self.assertFalse(
            suite["baseline"]["intelligence_improvement_claim"]
        )
        self.assertEqual(4, suite["current"]["domains_passed"])
        self.assertEqual("4/4", suite["current"]["domain_transfer_coverage"])
        self.assertEqual(
            100.0,
            suite["current"]["required_output_coverage_percent"],
        )
        self.assertEqual(
            12,
            suite["current"]["formation_route_families_observed"],
        )
        self.assertEqual(16, suite["current"]["innovation_candidates_observed"])
        self.assertEqual(0, suite["current"]["authority_violations"])
        self.assertEqual(
            4,
            suite["synthetic_coverage_delta"][
                "behavioural_domain_receipts"
            ],
        )

    def test_domain_objectives_capabilities_and_controls_survive_compilation(self) -> None:
        suite = self.build_suite()
        profiles = {
            profile["domain_id"]: profile
            for profile in self.profile_document["profiles"]
        }
        for result in suite["domain_results"]:
            profile = profiles[result["domain_id"]]
            canary = result["canary"]
            with self.subTest(domain=result["domain_id"]):
                self.assertEqual(
                    profile["objective"],
                    canary["formation_engine_result"]["objective_locked"],
                )
                self.assertEqual(
                    profile["available_capabilities"],
                    canary["formation_engine_result"][
                        "capabilities_inspected"
                    ],
                )
                self.assertEqual(
                    profile["success_criteria"],
                    canary["alpha_omega_foundry_result"][
                        "solution_genome"
                    ]["requirements"],
                )
                self.assertTrue(
                    set(profile["required_controls"]).issubset(
                        set(
                            canary["alpha_omega_foundry_result"][
                                "solution_genome"
                            ]["requirements"]
                        )
                    )
                )
                proof = canary["proof_and_maturity"]
                self.assertEqual("A1_INTERNAL", proof["authority_ceiling"])
                self.assertFalse(proof["external_effect"])
                self.assertFalse(proof["provider_mutation"])
                self.assertFalse(proof["trust_transfer"])

    def test_missing_domain_control_fails_closed(self) -> None:
        profile = copy.deepcopy(self.profile_document["profiles"][0])
        profile["required_controls"].append("missing synthetic control")
        validation = DOMAIN.validate_domain_profile(profile)
        self.assertFalse(validation["passed"])
        self.assertIn(
            "REQUIRED_CONTROL_NOT_IN_SUCCESS_CRITERIA",
            {item["code"] for item in validation["violations"]},
        )

    def test_authority_tamper_fails_domain_validation(self) -> None:
        profile = self.profile_document["profiles"][0]
        fixture = DOMAIN.build_domain_fixture(profile, self.base_fixture)
        canary = DOMAIN.base.run_synthetic_n_canary(
            fixture,
            self.bootstrap,
            self.policy_text,
        )
        canary["proof_and_maturity"]["external_effect"] = True
        validation = DOMAIN.validate_domain_canary(
            profile,
            fixture,
            canary,
        )
        self.assertFalse(validation["passed"])
        codes = {item["code"] for item in validation["violations"]}
        self.assertIn("DOMAIN_AUTHORITY_BOUNDARY_VIOLATION", codes)

    def test_suite_receipt_is_deterministic_and_hash_bound(self) -> None:
        first = self.build_suite()
        second = self.build_suite()
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        unhashed = dict(first)
        claimed = unhashed.pop("receipt_sha256")
        self.assertEqual(DOMAIN.base.canonical_sha256(unhashed), claimed)

    def test_real_world_intelligence_and_value_remain_unverified(self) -> None:
        suite = self.build_suite()
        self.assertIn(
            "PENDING_REAL_COMPARABLE_TASKS",
            suite["terminal_learning_event"]["intelligence_claim"],
        )
        self.assertIn(
            "real-world task accuracy improvement",
            suite["proof_boundary"]["unverified"],
        )
        self.assertIn(
            "longitudinal owner-burden reduction",
            suite["proof_boundary"]["unverified"],
        )
        self.assertFalse(suite["proof_boundary"]["external_effect"])
        self.assertFalse(suite["proof_boundary"]["provider_mutation"])
        self.assertFalse(suite["proof_boundary"]["trust_transfer"])

    def test_cli_executes_cross_domain_suite(self) -> None:
        process = subprocess.run(
            [sys.executable, str(MODULE_PATH)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(
            "CROSS_DOMAIN_CONFORMANCE_VERIFIED_SYNTHETIC",
            payload["status"],
        )
        self.assertEqual("4/4", payload["current"]["domain_transfer_coverage"])
        self.assertEqual("n = proceed", payload["continuation"])


if __name__ == "__main__":
    unittest.main()
