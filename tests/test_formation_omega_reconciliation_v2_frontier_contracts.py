from __future__ import annotations

import json
import unittest
from pathlib import Path

from benchmarking.cfbe_omega.reconciliation_fabric_v2_profile import (
    DimensionProof,
    evaluate,
)


ROOT = Path(__file__).resolve().parents[1]


class ReconciliationV2FrontierContractTests(unittest.TestCase):
    def test_governance_contract_is_fail_closed_about_external_tools(self):
        contract = json.loads(
            (ROOT / "governance" / "formation_omega_reconciliation_fabric_v2.json").read_text(encoding="utf-8")
        )
        self.assertFalse(contract["sovereign_authority_created"])
        self.assertFalse(contract["external_effect_default"])
        forbidden = set(contract["forbidden_claims_without_proof"])
        for claim in (
            "TLA_MODEL_CHECKED",
            "OPA_RUNTIME_BOUND",
            "OPENTELEMETRY_BACKEND_CONNECTED",
            "SIGSTORE_SIGNED",
            "PROVIDER_LIVE",
            "FRONTIER_LEADER",
        ):
            self.assertIn(claim, forbidden)

    def test_tla_model_declares_core_safety_invariants(self):
        text = (ROOT / "formal" / "FormationOmegaReconciliationV2.tla").read_text(encoding="utf-8")
        for invariant in (
            "NoMergeOnSemanticConflict",
            "NoStalePermitMerge",
            "NoA1ExternalEffectAtMerge",
            "RollbackRequiredForMerge",
            "ClosureRequiresMerge",
            "ClosureRequiresRollback",
            "ClosureExcludesConflict",
        ):
            self.assertIn(invariant, text)
        self.assertIn("Safety ==", text)
        self.assertIn("/\\ ~semanticConflict", text)
        self.assertIn("/\\ main = permitMain", text)
        self.assertIn("/\\ head = permitHead", text)
        self.assertIn("/\\ checkedHead = head", text)

    def test_rego_policy_mirrors_default_deny_boundaries(self):
        text = (ROOT / "policy" / "formation_omega_reconciliation_v2.rego").read_text(encoding="utf-8")
        self.assertIn("default allow := false", text)
        for reason in (
            "SEMANTIC_CONFLICT",
            "EXACT_PROVIDER_SNAPSHOT_REQUIRED",
            "REQUIRED_CHECKS_INCOMPLETE",
            "ROLLBACK_UNPROVEN",
            "A1_INTERNAL_NO_EXTERNAL_EFFECT",
            "OWNER_AUTHORIZATION_REQUIRED",
        ):
            self.assertIn(reason, text)
        self.assertIn("count(deny) == 0", text)

    def test_cfbe_keeps_unverified_frontier_adapters_evidence_discounted(self):
        report = evaluate(default_state="DETERMINISTIC_CI_BOUNDED_RUNTIME")
        self.assertGreater(report.raw_architecture, report.proof_adjusted)
        self.assertFalse(report.model_checked)
        self.assertFalse(report.policy_runtime_verified)
        self.assertFalse(report.trace_backend_verified)
        self.assertFalse(report.signed_attestation_verified)
        self.assertIn("formal_safety", report.gap_dimensions)
        self.assertIn("policy_as_code", report.gap_dimensions)
        self.assertIn("causal_observability", report.gap_dimensions)
        self.assertIn("attested_provenance", report.gap_dimensions)
        self.assertNotEqual("FRONTIER_LEADER", report.leadership)

    def test_cfbe_accepts_receiver_local_proof_without_inheriting_it(self):
        proofs = (
            DimensionProof("desired_state_reconciliation", "DETERMINISTIC_CI_BOUNDED_RUNTIME"),
            DimensionProof("stale_state_fencing", "DETERMINISTIC_CI_BOUNDED_RUNTIME"),
            DimensionProof("formal_safety", "PROVIDER_LIVE_INDEPENDENT_READBACK", independent_readback=True),
        )
        report = evaluate(
            proofs,
            default_state="CONTROL_PLANE_OR_SOURCE_ONLY",
            model_checked=True,
        )
        self.assertTrue(report.model_checked)
        self.assertFalse(report.policy_runtime_verified)
        self.assertFalse(report.trace_backend_verified)
        self.assertFalse(report.signed_attestation_verified)
        self.assertIn("policy_as_code", report.gap_dimensions)
        self.assertIn("causal_observability", report.gap_dimensions)

    def test_operational_cycles_do_not_fake_specialist_provider_proofs(self):
        report = evaluate(
            default_state="DETERMINISTIC_CI_BOUNDED_RUNTIME",
            repeated_operational_cycles=5,
        )
        self.assertEqual(5, report.repeated_operational_cycles)
        self.assertFalse(report.model_checked)
        self.assertFalse(report.policy_runtime_verified)
        self.assertFalse(report.trace_backend_verified)
        self.assertFalse(report.signed_attestation_verified)
        self.assertIn("formal_safety", report.gap_dimensions)
        self.assertIn("attested_provenance", report.gap_dimensions)


if __name__ == "__main__":
    unittest.main()
