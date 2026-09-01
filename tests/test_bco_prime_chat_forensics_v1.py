from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from benchmarking.cfbe_omega import bco_prime_capability_fabric_v1 as core
from benchmarking.cfbe_omega import bco_prime_chat_forensics_v1 as cff


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "benchmarking" / "cfbe_omega" / "BCO_PRIME_CHAT_FORENSICS_V1.json"
CONVERSATION_ID = "6a94a11c-fcc0-83e9-9c92-e7ae8a9c50b0"


def incident_bundle() -> dict:
    return {
        "conversation": {
            "expected_id": CONVERSATION_ID,
            "observed_id": CONVERSATION_ID,
            "expected_title": "Load Federation Omega",
            "observed_title": "Load Federation Omega",
        },
        "sources": [
            {"source_id": "rendered-transcript", "kind": "rendered_text", "accessible": True, "captured": True, "sha256": "a" * 64},
            {"source_id": "browser-dom", "kind": "browser_dom", "accessible": True, "captured": True, "sha256": "b" * 64},
            {"source_id": "execution-trace", "kind": "execution_trace", "accessible": True, "captured": True, "sha256": "c" * 64},
            {"source_id": "provider-api", "kind": "provider_api", "accessible": True, "captured": True, "sha256": "d" * 64},
            {"source_id": "native-export", "kind": "native_export", "accessible": False, "captured": False},
        ],
        "observations": {
            "work_durations_seconds": [795, 14, 1702],
            "final_tool_action_present": True,
            "final_response_commit_observed": False,
            "trace_steps": [
                {"step_id": "repair", "kind": "edit", "status": "OBSERVED"},
                {"step_id": "rerun", "kind": "test", "status": "RESULT_UNAVAILABLE"},
            ],
            "errors": [
                {"error_id": "pre-auth", "stage": "PRE_AUTH_NAVIGATION", "terminal_window": False, "server_confirmed": False},
            ],
            "claimed_outputs": ["runnable_code", "tests", "provider_readback", "final_response"],
            "proven_outputs": ["architecture", "partial_execution_trace"],
        },
        "provider": {"provider_ref": "8101b853e489d81d9848b1ccfb878fc2cbaf08a1", "durable_artifact_matches": []},
        "cff": {"engine_state": "AUDIT_BLOCKED", "native_export": False, "native_message_ids": False, "native_timestamps": False},
        "present_proof": ["partial_execution_trace"],
    }


class BCOPrimeChatForensicsV1Tests(unittest.TestCase):
    def test_contract_is_additive_twenty_four_and_core_stays_one_hundred(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual("BCO_PRIME_CHAT_FORENSICS_V1", contract["schema"])
        self.assertEqual(24, contract["capability_count"])
        self.assertEqual(24, len(cff.CAPABILITY_SPECS))
        self.assertEqual(24, len(cff.FUNCTION_REGISTRY))
        self.assertEqual(100, core.CAPABILITY_COUNT)
        self.assertEqual(100, cff.capability_manifest()["canonical_core_capability_count_unchanged"])

    def test_all_capabilities_are_deterministic_zero_manual_and_no_effect(self):
        for spec in cff.CAPABILITY_SPECS:
            payload = {}
            if spec.operation == "bind_conversation_identity":
                payload = {"expected_id": "x", "observed_id": "x"}
            first = cff.execute_capability(spec.capability_id, payload)
            second = cff.execute_capability(spec.capability_id, payload)
            self.assertEqual(first, second)
            self.assertEqual([], first["manual_user_tasks"])
            self.assertFalse(first["owner_action_required"])
            self.assertFalse(first["external_effect"])
            self.assertFalse(first["provider_effect_authorized"])
            self.assertFalse(first["authority_expansion"])

    def test_original_incident_detects_final_output_commit_failure(self):
        result = cff.audit_incident(incident_bundle())
        self.assertEqual("FINAL_OUTPUT_COMMIT_FAILURE", result["primary_finding"])
        self.assertEqual("HIGH", result["primary_finding_confidence"])
        self.assertEqual("UNVERIFIED", result["exact_backend_cause"])
        self.assertEqual("UNPROVEN", result["provider_durability"])
        self.assertEqual("PARTIAL_CHECKPOINTED", result["audit_state"])
        self.assertFalse(result["owner_action_required"])

    def test_conversation_collision_fails_closed(self):
        bundle = incident_bundle()
        bundle["conversation"]["observed_id"] = "different"
        with self.assertRaisesRegex(ValueError, "CONVERSATION_ID_MISMATCH"):
            cff.audit_incident(bundle)

    def test_unsupported_export_selects_dom_trace_fallback(self):
        receipt = cff.cff_cap_006_fallback_route({"available_kinds": ["browser_dom", "execution_trace", "rendered_text"]})
        self.assertEqual("BROWSER_DOM_TRACE", receipt["output"]["route"])
        self.assertTrue(receipt["output"]["fallback_used"])

    def test_scope_filter_rejects_unrelated_evidence(self):
        receipt = cff.cff_cap_005_scope_filter({
            "conversation_id": CONVERSATION_ID,
            "evidence": [
                {"evidence_id": "right", "conversation_id": CONVERSATION_ID},
                {"evidence_id": "wrong", "conversation_id": "other"},
            ],
        })
        self.assertEqual(["right"], receipt["output"]["accepted_ids"])
        self.assertEqual(["wrong"], receipt["output"]["rejected_ids"])
        self.assertFalse(receipt["output"]["scope_clean"])

    def test_provider_durability_requires_pinned_matching_artifact(self):
        absent = cff.cff_cap_018_provider_durability({"provider_ref": "abc", "durable_artifact_matches": []})
        present = cff.cff_cap_018_provider_durability({"provider_ref": "abc", "durable_artifact_matches": ["path/file.py"]})
        self.assertEqual("UNPROVEN", absent["output"]["state"])
        self.assertEqual("PROVEN", present["output"]["state"])

    def test_event_chain_and_full_audit_are_deterministic(self):
        payload = {"events": [{"event_id": "e1", "content": "one"}, {"event_id": "e2", "content": "two"}]}
        first = cff.cff_cap_008_event_chain(payload)
        second = cff.cff_cap_008_event_chain(payload)
        self.assertEqual(first, second)
        self.assertEqual(first["output"]["events"][0]["event_hash"], first["output"]["events"][1]["previous_event_hash"])
        self.assertEqual(cff.audit_incident(incident_bundle()), cff.audit_incident(incident_bundle()))

    def test_pre_auth_error_is_not_promoted_to_terminal_cause(self):
        receipt = cff.cff_cap_017_error_provenance({"errors": [
            {"error_id": "unauthorized", "stage": "PRE_AUTH_NAVIGATION", "terminal_window": False, "server_confirmed": False}
        ]})
        self.assertFalse(receipt["output"]["terminal_cause_supported"])

    def test_raw_secret_content_is_hashed_not_echoed(self):
        secret = "sk-" + "x" * 32
        rendered = json.dumps(cff.cff_cap_008_event_chain({"events": [{"content": secret}]}), sort_keys=True)
        self.assertNotIn(secret, rendered)

    def test_boundary_and_unknown_capabilities_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "CHAT_FORENSICS_BOUNDARY"):
            cff.execute_capability("BCO-PRIME-CFF-CAP-024", {"external_effect": True})
        with self.assertRaisesRegex(KeyError, "UNKNOWN_BCO_PRIME_CHAT_FORENSICS_CAPABILITY"):
            cff.execute_capability("BCO-PRIME-CFF-CAP-999", {})

    def test_cli_lists_and_runs(self):
        listing = subprocess.run(
            [sys.executable, "-m", "benchmarking.cfbe_omega.bco_prime_chat_forensics_v1", "list"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        self.assertEqual(24, len(json.loads(listing.stdout)["capabilities"]))
        execution = subprocess.run(
            [sys.executable, "-m", "benchmarking.cfbe_omega.bco_prime_chat_forensics_v1", "run", "BCO-PRIME-CFF-CAP-006", "--payload-json", '{"available_kinds":["rendered_text"]}'],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        self.assertEqual("RENDERED_TEXT_PARTIAL", json.loads(execution.stdout)["output"]["route"])


if __name__ == "__main__":
    unittest.main()
