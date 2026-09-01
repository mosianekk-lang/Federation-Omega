import json
from pathlib import Path
import unittest

from benchmarking.cfbe_omega.empirical_frontier_closure_v1 import (
    MINIMUM_OWNER_VALUE_PAIRS,
    ProofState,
    current_snapshot,
    held_external_lanes,
    next_executable_lanes,
    render_json,
)
from frontier_convergence.empirical_frontier_canary_v1 import hosted_canary_projection


ROOT = Path(__file__).resolve().parents[1]
HYPERLEVERAGE_CLOSURE = ROOT / "benchmarking/cfbe_omega/CFBE_HYPERLEVERAGE_100_CLOSURE_20260901.json"


class EmpiricalFrontierClosureV1Tests(unittest.TestCase):
    def test_exact_nine_lanes_and_provider_verified_gates(self):
        closure = current_snapshot()
        by_id = {lane.lane_id: lane for lane in closure.lanes}
        self.assertEqual(9, len(by_id))
        self.assertEqual(ProofState.PROVIDER_VERIFIED, by_id["WORKLOAD_IDENTITY"].state)
        self.assertEqual(ProofState.PROVIDER_VERIFIED, by_id["SLSA_ATTESTATION"].state)
        self.assertIn("github-actions:33450913670", by_id["WORKLOAD_IDENTITY"].evidence_refs)
        self.assertIn("github-attestation:44277491", by_id["SLSA_ATTESTATION"].evidence_refs)
        self.assertFalse(any(lane.provider_effect_authorized for lane in closure.lanes))
        self.assertFalse(any(lane.stable_promotion_authorized for lane in closure.lanes))

    def test_hyperleverage_projection_closes_both_explicit_provider_gates(self):
        payload = json.loads(HYPERLEVERAGE_CLOSURE.read_text(encoding="utf-8"))
        programme = payload["capability_programme"]
        self.assertEqual(2, programme["explicit_provider_gates"])
        self.assertEqual(2, programme["provider_verified_closed"])
        self.assertEqual(0, programme["provider_gate_open"])
        self.assertEqual("PROVIDER_VERIFIED_CLOSED", payload["FHU-042"]["state"])
        self.assertEqual("PROVIDER_VERIFIED_CLOSED", payload["FHU-047"]["state"])
        self.assertFalse(payload["FHU-047"]["long_lived_service_account_key_used"])
        self.assertFalse(payload["FHU-047"]["provider_mutation_performed"])
        self.assertFalse(payload["FHU-047"]["external_deployment_effect"])
        self.assertTrue(payload["truth_boundary"]["fhu_047_workload_identity_closure_does_not_imply_cloud_run_or_gemini_deployment_readiness"])

    def test_hosted_proof_does_not_inherit_serving_provider_deployment(self):
        closure = current_snapshot()
        runtime = next(lane for lane in closure.lanes if lane.lane_id == "DURABLE_RUNTIME")
        self.assertEqual(ProofState.HOSTED_VERIFIED, runtime.state)
        self.assertEqual(
            "SERVING_PROVIDER_DEPLOYMENT_AND_HEALTH_READBACK_REQUIRED",
            runtime.terminal_gate,
        )
        self.assertFalse(runtime.provider_effect_authorized)

    def test_toolbox_and_openrouter_are_not_overcertified(self):
        closure = current_snapshot()
        by_id = {lane.lane_id: lane for lane in closure.lanes}
        self.assertEqual(ProofState.SOURCE_READY, by_id["TOOLBOX_GOVERNANCE"].state)
        self.assertEqual(ProofState.HOLD_CREDENTIAL_BINDING, by_id["MULTI_PROVIDER_ROUTING"].state)
        self.assertIn("OPENROUTER_ACTIONS_CREDENTIAL_BINDING_REQUIRED", by_id["MULTI_PROVIDER_ROUTING"].terminal_gate)

    def test_owner_value_pair_count_alone_can_never_promote(self):
        held = current_snapshot(owner_value_pairs=MINIMUM_OWNER_VALUE_PAIRS)
        owner = next(lane for lane in held.lanes if lane.lane_id == "OWNER_VALUE")
        self.assertEqual(ProofState.HOLD_REAL_OBSERVATIONS, owner.state)
        self.assertEqual("MINIMUM_10_COURT_VERIFIED_OWNER_VALUE_PAIRS_REQUIRED", owner.terminal_gate)

    def test_owner_value_requires_minimum_pairs_and_court_verification(self):
        with self.assertRaisesRegex(ValueError, "OWNER_VALUE_COURT_CANNOT_VERIFY_SUBMINIMUM_COHORT"):
            current_snapshot(owner_value_pairs=MINIMUM_OWNER_VALUE_PAIRS - 1, owner_value_court_verified=True)

        eligible = current_snapshot(
            owner_value_pairs=MINIMUM_OWNER_VALUE_PAIRS,
            owner_value_court_verified=True,
        )
        owner = next(lane for lane in eligible.lanes if lane.lane_id == "OWNER_VALUE")
        self.assertEqual(ProofState.HOSTED_VERIFIED, owner.state)
        self.assertIsNone(owner.terminal_gate)

    def test_closure_hash_and_json_are_deterministic(self):
        a = current_snapshot()
        b = current_snapshot()
        self.assertEqual(a.closure_sha256, b.closure_sha256)
        self.assertEqual(a.to_dict(), b.to_dict())
        decoded = json.loads(render_json())
        self.assertEqual(a.closure_sha256, decoded["closure_sha256"])
        self.assertEqual(9, decoded["lane_count"])

    def test_safe_next_lanes_exclude_credential_and_value_holds(self):
        closure = current_snapshot()
        executable = set(next_executable_lanes(closure))
        self.assertEqual(
            {"DURABLE_RUNTIME", "LIVE_AGENT_TELEMETRY", "TRACE_EVAL_OPTIMIZER", "AI_ASSET_VALUE_GOVERNANCE"},
            executable,
        )
        held = set(held_external_lanes(closure))
        self.assertIn("MULTI_PROVIDER_ROUTING", held)
        self.assertIn("OWNER_VALUE", held)
        self.assertIn("TOOLBOX_GOVERNANCE", held)

    def test_hosted_canary_is_no_effect_and_bound_to_closure(self):
        closure = current_snapshot()
        canary = hosted_canary_projection()
        self.assertEqual(closure.closure_sha256, canary["closure_sha256"])
        self.assertEqual(9, canary["lane_count"])
        self.assertFalse(canary["provider_effect_authorized"])
        self.assertFalse(canary["stable_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
