from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from realityguard import RealityGuard
from realityguard.model import Verdict
from realityguard.schema import InputError


ROOT = Path(__file__).resolve().parents[1]


def base_payload():
    return {
        "claim": {"text": "The artifact is built.", "claimed_state": "BUILT", "subject": "artifact", "scope": ["artifact"]},
        "evidence": [{"kind": "FILE", "supports_state": "BUILT", "grade": "ARTIFACT", "reference": "sha256:abc", "scope": ["artifact"]}],
        "context": {"required_scope": ["artifact"], "observed_scope": ["artifact"]},
    }


class RealityGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = RealityGuard()

    def scan(self, payload):
        return self.guard.scan(payload)

    def test_bounded_built_claim_allowed(self):
        self.assertEqual(self.scan(base_payload()).verdict, Verdict.ALLOW_BOUNDED)

    def test_deterministic_correlation_id(self):
        payload = base_payload()
        self.assertEqual(self.scan(payload).correlation_id, self.scan(copy.deepcopy(payload)).correlation_id)

    def test_false_ownership_is_critical(self):
        payload = json.loads((ROOT / "examples/false_ownership.json").read_text())
        result = self.scan(payload)
        self.assertEqual(result.verdict, Verdict.BLOCK_FALSE_REALITY)
        self.assertIn("RG-011", {f.code for f in result.findings})
        self.assertNotIn("RG-008", {f.code for f in result.findings})

    def test_interface_semantic_gap(self):
        payload = json.loads((ROOT / "examples/interface_semantic_gap.json").read_text())
        result = self.scan(payload)
        self.assertIn("RG-022", {f.code for f in result.findings})
        self.assertEqual(result.verdict, Verdict.BLOCK_FALSE_REALITY)

    def test_local_test_does_not_prove_deployment(self):
        payload = base_payload()
        payload["claim"]["claimed_state"] = "DEPLOYED"
        payload["evidence"][0].update({"supports_state": "TESTED", "grade": "TEST_RESULT"})
        self.assertEqual(self.scan(payload).proven_state.name, "TESTED")

    def test_failed_test_is_inadmissible(self):
        payload = base_payload()
        payload["evidence"][0].update({"supports_state": "TESTED", "grade": "TEST_RESULT", "passed": False})
        self.assertEqual(self.scan(payload).proven_state.name, "DESCRIBED")

    def test_stale_evidence_is_inadmissible(self):
        payload = base_payload()
        payload["evidence"][0]["current"] = False
        self.assertEqual(self.scan(payload).proven_state.name, "DESCRIBED")

    def test_self_report_cannot_prove_built(self):
        payload = base_payload()
        payload["evidence"][0]["grade"] = "SELF_REPORTED"
        self.assertEqual(self.scan(payload).proven_state.name, "DESCRIBED")

    def test_running_requires_readback_quality(self):
        payload = base_payload()
        payload["claim"]["claimed_state"] = "RUNNING"
        payload["evidence"][0].update({"supports_state": "RUNNING", "grade": "INDEPENDENT_READBACK", "semantic": False, "independent": False})
        self.assertEqual(self.scan(payload).proven_state.name, "DESCRIBED")

    def test_independent_running_readback_admitted(self):
        payload = base_payload()
        payload["claim"]["claimed_state"] = "RUNNING"
        payload["evidence"][0].update({"supports_state": "RUNNING", "grade": "INDEPENDENT_READBACK", "independent": True})
        self.assertEqual(self.scan(payload).proven_state.name, "RUNNING")

    def test_acceptance_requires_owner_grade(self):
        payload = base_payload()
        payload["claim"]["claimed_state"] = "ACCEPTED"
        payload["evidence"][0].update({"supports_state": "ACCEPTED", "grade": "INDEPENDENT_READBACK", "independent": True})
        self.assertEqual(self.scan(payload).proven_state.name, "DESCRIBED")

    def test_owner_acceptance_admitted(self):
        payload = base_payload()
        payload["claim"]["claimed_state"] = "ACCEPTED"
        payload["evidence"][0].update({"supports_state": "ACCEPTED", "grade": "OWNER_ACCEPTED", "semantic": True})
        self.assertEqual(self.scan(payload).proven_state.name, "ACCEPTED")

    def test_partial_scope_blocks_completion(self):
        payload = base_payload()
        payload["claim"]["completion_asserted"] = True
        payload["context"] = {"required_scope": ["a", "b"], "observed_scope": ["a"]}
        self.assertEqual(self.scan(payload).verdict, Verdict.BLOCK_COMPLETION)

    def test_shallow_totality_is_critical(self):
        payload = base_payload()
        payload["claim"]["text"] = "The entire account is complete."
        payload["context"]["shallow_or_paginated"] = True
        self.assertEqual(self.scan(payload).verdict, Verdict.BLOCK_FALSE_REALITY)

    def test_draft_not_sent(self):
        payload = base_payload()
        payload["claim"]["text"] = "The email was sent."
        payload["context"]["draft_only"] = True
        self.assertIn("RG-008", {f.code for f in self.scan(payload).findings})

    def test_transport_not_semantic(self):
        payload = base_payload()
        payload["context"].update({"transport_success": True, "semantic_success": False})
        self.assertIn("RG-014", {f.code for f in self.scan(payload).findings})

    def test_metadata_not_content(self):
        payload = base_payload()
        payload["context"].update({"metadata_only": True, "content_review_claimed": True})
        self.assertIn("RG-018", {f.code for f in self.scan(payload).findings})

    def test_derivative_inflation(self):
        payload = base_payload()
        payload["context"]["derivative_counted_as_source"] = True
        self.assertIn("RG-017", {f.code for f in self.scan(payload).findings})

    def test_stale_receipt(self):
        payload = base_payload()
        payload["context"].update({"historical_receipt": True, "fresh_readback": False})
        self.assertIn("RG-013", {f.code for f in self.scan(payload).findings})

    def test_self_sealing_proof(self):
        payload = base_payload()
        payload["context"]["self_generated_proof"] = True
        self.assertEqual(self.scan(payload).verdict, Verdict.BLOCK_FALSE_REALITY)

    def test_governance_theatre(self):
        payload = base_payload()
        payload["context"].update({"governance_artifact": True, "enforcement_runtime": False})
        self.assertIn("RG-012", {f.code for f in self.scan(payload).findings})

    def test_persistent_agent_illusion(self):
        payload = base_payload()
        payload["context"].update({"persistent_agent_claim": True, "persistent_runtime_proof": False})
        self.assertIn("RG-019", {f.code for f in self.scan(payload).findings})

    def test_permanent_model_claim_is_critical(self):
        payload = base_payload()
        payload["context"]["permanent_model_change_claim"] = True
        self.assertEqual(self.scan(payload).verdict, Verdict.BLOCK_FALSE_REALITY)

    def test_version_maturity_inflation(self):
        payload = base_payload()
        payload["context"].update({"version_label": "v∞", "maturity_evidence": False})
        self.assertIn("RG-023", {f.code for f in self.scan(payload).findings})

    def test_state_fossilization(self):
        payload = base_payload()
        payload["context"]["state_changed_since_proof"] = True
        self.assertIn("RG-024", {f.code for f in self.scan(payload).findings})

    def test_avoidable_manual_burden(self):
        payload = base_payload()
        payload["context"]["manual_user_task_avoidable"] = True
        self.assertIn("RG-006", {f.code for f in self.scan(payload).findings})

    def test_options_instead_of_action(self):
        payload = base_payload()
        payload["context"].update({"action_available": True, "instructions_substituted": True})
        self.assertIn("RG-004", {f.code for f in self.scan(payload).findings})

    def test_late_boundary_disclosure(self):
        payload = base_payload()
        payload["context"]["boundary_disclosed_after_challenge"] = True
        self.assertIn("RG-010", {f.code for f in self.scan(payload).findings})

    def test_checkpoint_is_not_continuity(self):
        payload = base_payload()
        payload["claim"]["text"] = "Full cross-chat continuity moves with you."
        payload["context"]["checkpoint_only"] = True
        self.assertIn("RG-009", {f.code for f in self.scan(payload).findings})

    def test_owner_decision_route(self):
        payload = base_payload()
        payload["context"]["owner_decision_required"] = True
        self.assertEqual(self.scan(payload).verdict, Verdict.REQUIRE_OWNER_DECISION)

    def test_reactive_only_correction_is_logged(self):
        payload = base_payload()
        payload["context"]["reactive_only_correction"] = True
        self.assertIn("RG-028", {f.code for f in self.scan(payload).findings})

    def test_correction_debt_orphaning_is_logged(self):
        payload = base_payload()
        payload["context"]["source_corrected_without_dependents"] = True
        self.assertIn("RG-029", {f.code for f in self.scan(payload).findings})

    def test_ungoverned_self_upgrade_is_critical(self):
        payload = base_payload()
        payload["context"]["automatic_upgrade_without_governance"] = True
        result = self.scan(payload)
        self.assertIn("RG-030", {f.code for f in result.findings})
        self.assertEqual(result.verdict, Verdict.BLOCK_FALSE_REALITY)

    def test_invalid_payload_rejected(self):
        with self.assertRaises(InputError):
            self.scan({"claim": {"text": ""}})

    def test_secret_values_do_not_affect_rule_logic(self):
        payload = base_payload()
        payload["context"]["api_key"] = "opaque-test-secret-value"
        self.assertEqual(self.scan(payload).verdict, Verdict.ALLOW_BOUNDED)


if __name__ == "__main__":
    unittest.main()
