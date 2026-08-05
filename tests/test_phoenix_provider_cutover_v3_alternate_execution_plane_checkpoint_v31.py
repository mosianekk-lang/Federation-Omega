from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from alpha_omega_commercial.commercial_execution_plane_admission import (
    CommercialExecutionPlaneError,
    build_execution_plane_admission,
)

ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR_CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_authority_binding_checkpoint_v30.json"
PREDECESSOR_PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v30.json"
CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_alternate_execution_plane_checkpoint_v31.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v31.json"

SOURCE_SHA = "bba0c434f8f82812e36dc5045e67c3b5d8273f72"
ARTIFACT_DIGEST = "4942620cb37c534232f234d07dd4b34544d1aa7cac03a17466dfa6f21af22264"
PREVIOUS_MAIN = "7393f25f781a45fa4b29c48b0ab542f6c0683bb4"
PREVIOUS_ARTIFACT = "55be5b70b98cbbd94c9e5fadd0a0d530a5f73125dbd4c005191e2933ad201c30"
CANDIDATE_SHA = "c" * 64


def actual_provider_state() -> dict:
    return {
        "live_main": SOURCE_SHA,
        "phoenix_artifact_sha256": ARTIFACT_DIGEST,
        "previous_main": PREVIOUS_MAIN,
        "previous_phoenix_artifact_sha256": PREVIOUS_ARTIFACT,
        "github_installation_scope": "selected",
        "private_core_visible": False,
        "private_ops_visible": False,
        "private_github_admin_authority": False,
        "gcp_admin_authority": False,
        "gcp_native_runner_available": False,
        "sealed_owner_artifact_available": False,
        "openai_existing_key_management_available": False,
        "current_candidate_sha256": CANDIDATE_SHA,
        "candidate_bound_to_live_main": True,
        "candidate_bound_to_artifact": True,
        "credential_value_recorded": False,
    }


class AlternateExecutionPlaneCheckpointV31Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predecessor_checkpoint = json.loads(PREDECESSOR_CHECKPOINT.read_text())
        cls.predecessor_projection = json.loads(PREDECESSOR_PROJECTION.read_text())
        cls.checkpoint = json.loads(CHECKPOINT.read_text())
        cls.projection = json.loads(PROJECTION.read_text())
        cls.truth = cls.checkpoint["commercial_truth"]
        cls.readback = cls.checkpoint["provider_authority_readback"]

    def build(self, state: dict, *, readback: dict | None = None) -> dict:
        return build_execution_plane_admission(
            provider_state=state,
            predecessor_checkpoint=self.predecessor_checkpoint,
            predecessor_projection=self.predecessor_projection,
            commercial_truth=self.truth,
            provider_readback=readback or self.readback,
            source_sha=SOURCE_SHA,
            phoenix_artifact_digest=f"sha256:{ARTIFACT_DIGEST}",
        )

    def test_actual_provider_state_is_exact_and_blocked_without_overclaim(self):
        receipt = self.build(actual_provider_state())
        self.assertEqual("NONE", receipt["selected_route"])
        self.assertEqual(
            "PROVIDER_BLOCKED_ROUTE_SPECIFIC_AUTHORITY_OR_PACKET_REQUIRED",
            receipt["status"],
        )
        self.assertIn(
            "SEALED_OWNER_PACKET_OR_GCP_NATIVE_RUNNER_AND_AUTHORITY",
            receipt["route_specific_gates"],
        )
        self.assertFalse(receipt["provider_mutation_performed"])
        self.assertFalse(receipt["external_effect_performed"])
        self.assertFalse(receipt["external_commercial_gate_advanced"])
        self.assertEqual(0, receipt["commercial_truth"]["verified_live_revenue_events"])

    def test_gcp_native_route_can_be_admitted_without_private_github(self):
        state = actual_provider_state()
        state.update(
            gcp_admin_authority=True,
            gcp_native_runner_available=True,
            sealed_owner_artifact_available=True,
        )
        receipt = self.build(state)
        self.assertEqual("GCP_NATIVE_SEALED_ARTIFACT", receipt["selected_route"])
        self.assertEqual("READY_FOR_FRESH_EXACT_OWNER_AUTHORIZATION", receipt["status"])
        self.assertEqual([], receipt["route_specific_gates"])
        self.assertIn("PRIVATE_GITHUB_ADMIN_AUTHORITY", receipt["internally_closed_constraints"])
        self.assertFalse(receipt["independent_open_gate"]["blocks_execution_plane_selection"])

    def test_owner_only_packet_route_stays_owner_reserved(self):
        state = actual_provider_state()
        state["sealed_owner_artifact_available"] = True
        receipt = self.build(state)
        self.assertEqual("OWNER_ONLY_SEALED_PACKET", receipt["selected_route"])
        self.assertIn(
            "OWNER_RESERVED_EXTERNAL_EXECUTION_AUTHORITY_AND_PROVIDER_NATIVE_READBACK",
            receipt["route_specific_gates"],
        )
        self.assertFalse(receipt["owner_authorization_consumed"])

    def test_drift_partial_topology_credentials_and_truth_fail_closed(self):
        state = actual_provider_state()
        state["candidate_bound_to_live_main"] = False
        receipt = self.build(state)
        self.assertIn("REGENERATE_JUST_IN_TIME_CANDIDATE", receipt["route_specific_gates"])

        state = actual_provider_state()
        state["private_core_visible"] = True
        with self.assertRaises(Exception):
            self.build(state)

        state = actual_provider_state()
        state["credential_value_recorded"] = True
        with self.assertRaises(Exception):
            self.build(state)

        altered_truth = copy.deepcopy(self.truth)
        altered_truth["customer_demand"] = "VERIFIED"
        with self.assertRaises(CommercialExecutionPlaneError):
            build_execution_plane_admission(
                provider_state=actual_provider_state(),
                predecessor_checkpoint=self.predecessor_checkpoint,
                predecessor_projection=self.predecessor_projection,
                commercial_truth=altered_truth,
                provider_readback=self.readback,
                source_sha=SOURCE_SHA,
                phoenix_artifact_digest=ARTIFACT_DIGEST,
            )

    def test_provider_readback_drift_and_mutation_fail_closed(self):
        altered = copy.deepcopy(self.readback)
        altered["installed_repositories"].append("mosianekk-lang/Federation-Omega-Ops")
        with self.assertRaises(CommercialExecutionPlaneError):
            self.build(actual_provider_state(), readback=altered)
        altered = copy.deepcopy(self.readback)
        altered["provider_mutation_performed"] = True
        with self.assertRaises(CommercialExecutionPlaneError):
            self.build(actual_provider_state(), readback=altered)

    def test_checkpoint_projection_hashes_and_dependency_order(self):
        for payload, field, expected in (
            (self.checkpoint, "checkpoint_sha256", "fe9db3f08fde29e6b4c5b1470fc840dd8fb8b0863c9ae41e1279b265e62a3cfa"),
            (self.projection, "projection_sha256", "329f4a5d97e2d1e94abd90e4ce87b8aa608bd9d3f81976b14b4e7d054db1911b"),
        ):
            body = dict(payload)
            claimed = body.pop(field)
            calculated = hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            self.assertEqual(expected, claimed)
            self.assertEqual(claimed, calculated)
        self.assertEqual([f"C{i:02d}" for i in range(1, 16)], self.projection["dependency_order"])
        self.assertTrue(self.projection["service_enabled_platform_first"])
        self.assertTrue(self.projection["self_service_saas_held"])


if __name__ == "__main__":
    unittest.main()
