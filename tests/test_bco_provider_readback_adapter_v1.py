import tempfile
import unittest

from benchmarking.cfbe_omega.bco_provider_readback_adapter_v1 import (
    ProviderReadbackLevel,
    bind_provider_readback_request,
    compile_provider_readback_evidence,
    evaluate_provider_readback_floor,
)
from federation.mission_ir import MissionIR
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1


class BCOProviderReadbackAdapterTests(unittest.TestCase):
    def _public_receipt(self):
        return {
            "schema": "BUBBLES-PROVIDER-SURFACE-PROBE-V1",
            "mutation_attempted": False,
            "secret_values_recorded": False,
            "surfaces": {
                "federation_omega_operator": {
                    "classification": "BLOCKED_TRUSTED_TOKEN_BINDING",
                    "public_health": {"http_status": 200, "body": {"ok": True}},
                    "public_contract": {"http_status": 200, "body": {"ok": True}},
                    "authenticated_status": None,
                    "authenticated_cloud_read": None,
                },
                "archon_admin_plane_v5": {
                    "classification": "PUBLIC_SURFACE_REACHABLE_AUTH_PENDING",
                    "public_openapi": {"http_status": 200, "body": {"text": "openapi"}},
                    "authenticated_capability_audit": None,
                },
                "afeme_v4": {
                    "classification": "IAM_PROTECTED_REACHABLE_AUTH_PENDING",
                    "public_probe": {"http_status": 403, "body": {"text": "forbidden"}},
                    "authenticated_probe": None,
                },
            },
        }

    def _authenticated_action_receipt(self):
        receipt = self._public_receipt()
        receipt["surfaces"]["federation_omega_operator"] = {
            "classification": "AUTHENTICATED_READBACK_VERIFIED",
            "public_health": {"http_status": 200, "body": {"ok": True}},
            "public_contract": {"http_status": 200, "body": {"ok": True}},
            "authenticated_status": {"http_status": 200, "body": {"ok": True, "status": "READY"}},
            "authenticated_cloud_read": {
                "http_status": 200,
                "body": {"ok": True, "service": "architron9", "mutation": "NONE"},
            },
        }
        return receipt

    def _mission(self):
        return MissionIR(
            mission_id="BCO-PROVIDER-READ-001",
            objective="Resume only when the required provider readback proof floor is met.",
            domain="BCO_PROVIDER_READBACK",
            outcome_contract="One proof-floor-governed read-only provider receipt.",
            source_frontier="main@provider-readback-test",
            privacy_class="PUBLIC",
            rights_state="NOT_APPLICABLE",
            effect_class="READ_ONLY",
            rollback_required=False,
            proof_requirements=("READBACK",),
        ).normalized()

    def _runtime_with_request(self, root):
        runtime = DurableMissionRuntimeV1(
            root,
            source_frontier="main@provider-readback-test",
            policy_sha256="policy-provider-read-v1",
            environment_sha256="env-provider-read-v1",
        )
        mission = self._mission()
        runtime.open(mission, required_proof_axes=("source",))
        request = runtime.request(
            mission.mission_id,
            step_id="READ-PROVIDER",
            request_type="PROVIDER_READBACK",
            target="federation-omega-operator",
            reason="Require action-specific authenticated read evidence before continuation.",
            input_identity={"action": "READ_CLOUD_RUN_SERVICE", "mutation": "NONE"},
            continuation_key="continue-provider-read",
            effect_class="READ_ONLY",
            created_at="2026-08-31T23:00:00+02:00",
        )
        return runtime, mission, request

    def test_public_reachability_does_not_upgrade_to_authenticated_readback(self):
        evidence = compile_provider_readback_evidence(self._public_receipt(), proof_ref="artifact:public")
        self.assertEqual("PUBLIC_REACHABILITY", evidence.level)
        self.assertEqual(1, evidence.level_rank)
        self.assertEqual((), evidence.authenticated_surfaces)
        floor = evaluate_provider_readback_floor(
            evidence,
            ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ,
        )
        self.assertEqual("HOLD_PROVIDER_READBACK_FLOOR_UNMET", floor.state)
        self.assertEqual("PUBLIC_REACHABILITY", floor.observed_level)

    def test_action_specific_authenticated_receipt_meets_highest_read_floor(self):
        evidence = compile_provider_readback_evidence(
            self._authenticated_action_receipt(),
            proof_ref="artifact:authenticated",
        )
        self.assertEqual("ACTION_SPECIFIC_AUTHENTICATED_READ", evidence.level)
        self.assertEqual(("federation_omega_operator",), evidence.action_specific_surfaces)
        floor = evaluate_provider_readback_floor(
            evidence,
            ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ,
        )
        self.assertEqual("PROOF_FLOOR_MET", floor.state)

    def test_unmet_floor_keeps_bco_request_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, mission, request = self._runtime_with_request(tmp)
            binding = bind_provider_readback_request(
                runtime,
                mission.mission_id,
                request.request_id,
                self._public_receipt(),
                receipt_ref="artifact:public-provider-probe",
                required_level=ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ,
            )
            self.assertEqual("HOLD_PROVIDER_READBACK_FLOOR_UNMET", binding.state)
            self.assertFalse(binding.request_resolved)
            self.assertEqual((request.request_id,), tuple(item.request_id for item in runtime.pending_requests(mission.mission_id)))

    def test_met_floor_resolves_request_without_granting_effect_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, mission, request = self._runtime_with_request(tmp)
            binding = bind_provider_readback_request(
                runtime,
                mission.mission_id,
                request.request_id,
                self._authenticated_action_receipt(),
                receipt_ref="artifact:authenticated-provider-probe",
                required_level=ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ,
                resolved_at="2026-08-31T23:01:00+02:00",
            )
            self.assertEqual("PROVIDER_READBACK_BOUND", binding.state)
            self.assertTrue(binding.request_resolved)
            self.assertFalse(binding.provider_effect_authorized)
            self.assertEqual((), runtime.pending_requests(mission.mission_id))
            request_state = runtime.requests(mission.mission_id)[0]
            self.assertEqual("RESOLVED", request_state.state)
            self.assertIn("provider-readback-level:ACTION_SPECIFIC_AUTHENTICATED_READ", request_state.proof_refs)

    def test_receipt_with_mutation_or_secret_recording_is_rejected(self):
        mutated = self._public_receipt()
        mutated["mutation_attempted"] = True
        with self.assertRaisesRegex(ValueError, "MUTATION_BOUNDARY_VIOLATED"):
            compile_provider_readback_evidence(mutated)

        secret_breach = self._public_receipt()
        secret_breach["secret_values_recorded"] = True
        with self.assertRaisesRegex(ValueError, "SECRET_BOUNDARY_VIOLATED"):
            compile_provider_readback_evidence(secret_breach)


if __name__ == "__main__":
    unittest.main()
