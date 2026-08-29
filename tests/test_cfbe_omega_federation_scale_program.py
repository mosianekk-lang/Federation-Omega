from __future__ import annotations

import json
from pathlib import Path
import unittest

from proofos_omega.cfbe import BenchmarkObservation, CFBEAdmissionComparator


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "governance" / "cfbe_omega_federation_scale_program_v1.json"
CHALLENGE = ROOT / "governance" / "sovara_creative_gemini_architecture_challenge_v1.json"
REQUEST = ROOT / "governance" / "sovara_gemini_collaboration_request_v1.json"
COURT = ROOT / "benchmarking" / "cfbe_omega" / "federation_scale_admission_spec_v1.json"


class FederationScaleProgramTests(unittest.TestCase):
    def load(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_program_registers_all_twelve_initiatives_and_six_phases(self):
        program = self.load(PROGRAM)
        self.assertEqual(program["schema"], "CFBE-OMEGA-FEDERATION-SCALE-PROGRAM-V1")
        self.assertEqual(len(program["initiatives"]), 12)
        self.assertEqual([p["phase"] for p in program["phases"]], list(range(6)))
        self.assertEqual({x["id"] for x in program["initiatives"]}, {f"I{i:02d}" for i in range(1, 13)})

    def test_live_financial_execution_remains_separate(self):
        program = self.load(PROGRAM)
        self.assertTrue(program["truth_boundary"]["live_financial_execution_requires_separate_explicit_authority"])
        quant = next(x for x in program["initiatives"] if x["id"] == "I08")
        self.assertIn("PAPER_AND_SHADOW_ONLY", quant["authority_ceiling"])
        self.assertEqual(quant["target"], "SHADOW_OR_PAPER_VERIFIED")

    def test_gemini_audit_is_sanitized_proposal_only(self):
        challenge = self.load(CHALLENGE)
        request = self.load(REQUEST)
        self.assertEqual(challenge["challenge_id"], "SC-GEMINI-FED-SCALE-20260829-001")
        self.assertEqual(challenge["proposal_count"], 12)
        self.assertTrue(challenge["sanitized"])
        self.assertFalse(challenge["case_data_allowed"])
        self.assertFalse(challenge["external_effect_allowed"])
        self.assertTrue(request["execute"])
        self.assertFalse(request["promote"])
        self.assertFalse(request["provider_mutation_allowed"])
        self.assertFalse(request["external_communication_allowed"])

    def test_source_only_challenger_cannot_frontier_promote(self):
        comparator = CFBEAdmissionComparator.from_path(COURT)
        incumbent = BenchmarkObservation(
            evidence_state="REPEATED_OPERATIONAL_SCOPED",
            metrics={
                "duplicate_capability_ratio": 0.40,
                "stale_capability_state_ratio": 0.40,
                "owner_intervention_rate": 0.40,
                "mean_time_to_root_cause_seconds": 100.0,
                "p95_route_selection_latency_seconds": 2.0,
                "cost_per_verified_decision": 10.0,
                "security_escape_rate": 0.0,
                "regression_escape_rate": 0.02,
                "provider_readback_coverage": 0.80,
                "critical_proof_chain_coverage": 1.0,
                "value_telemetry_coverage": 0.50,
                "retirement_or_reuse_decision_coverage": 0.50,
            },
        )
        challenger = BenchmarkObservation(
            evidence_state="DETERMINISTIC_CI_BOUNDED_RUNTIME",
            metrics={
                "duplicate_capability_ratio": 0.20,
                "stale_capability_state_ratio": 0.10,
                "owner_intervention_rate": 0.20,
                "mean_time_to_root_cause_seconds": 25.0,
                "p95_route_selection_latency_seconds": 0.8,
                "cost_per_verified_decision": 6.0,
                "security_escape_rate": 0.0,
                "regression_escape_rate": 0.01,
                "provider_readback_coverage": 0.95,
                "critical_proof_chain_coverage": 1.0,
                "value_telemetry_coverage": 0.90,
                "retirement_or_reuse_decision_coverage": 1.0,
            },
        )
        result = comparator.compare(incumbent=incumbent, challenger=challenger)
        self.assertEqual(result.status, "HELD_NO_OPERATIONAL_EVIDENCE")
        self.assertTrue(result.hard_gates_pass)

    def test_security_regression_is_rejected(self):
        comparator = CFBEAdmissionComparator.from_path(COURT)
        baseline = {
            "duplicate_capability_ratio": 0.20,
            "stale_capability_state_ratio": 0.10,
            "owner_intervention_rate": 0.20,
            "mean_time_to_root_cause_seconds": 30.0,
            "p95_route_selection_latency_seconds": 1.0,
            "cost_per_verified_decision": 5.0,
            "security_escape_rate": 0.0,
            "regression_escape_rate": 0.01,
            "provider_readback_coverage": 0.95,
            "critical_proof_chain_coverage": 1.0,
            "value_telemetry_coverage": 0.90,
            "retirement_or_reuse_decision_coverage": 1.0,
        }
        degraded = dict(baseline)
        degraded["security_escape_rate"] = 0.01
        result = comparator.compare(
            incumbent=BenchmarkObservation("REPEATED_OPERATIONAL_SCOPED", baseline),
            challenger=BenchmarkObservation("PROVIDER_LIVE_INDEPENDENT_READBACK", degraded, ("provider-receipt",)),
        )
        self.assertEqual(result.status, "REJECTED_SAFETY_OR_REGRESSION_GATE")
        self.assertFalse(result.hard_gates_pass)


if __name__ == "__main__":
    unittest.main()
