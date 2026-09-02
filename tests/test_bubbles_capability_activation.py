from __future__ import annotations

import unittest

from bubbles.capability_activation import ActivationState, build_activation_snapshot


SOURCE = "5668d842ff52a0b84a9daf400e13506509927775"


def provider_surface(*, operator_token: bool = False, archon_token: bool = False) -> dict:
    return {
        "schema": "BUBBLES-PROVIDER-SURFACE-PROBE-V1",
        "mutation_attempted": False,
        "surfaces": {
            "federation_omega_operator": {
                "classification": "AUTHENTICATED_READBACK_VERIFIED" if operator_token else "BLOCKED_TRUSTED_TOKEN_BINDING",
                "trusted_token_available": operator_token,
                "public_health": {"http_status": 200, "body": {"ok": True}},
                "public_contract": {"http_status": 200, "body": {"ok": True}},
            },
            "archon_admin_plane_v5": {
                "classification": "AUTHENTICATED_READBACK_VERIFIED" if archon_token else "PUBLIC_SURFACE_REACHABLE_AUTH_PENDING",
                "trusted_token_available": archon_token,
                "public_openapi": {"http_status": 200},
            },
            "archon_apps_script_exact_deployment": {
                "overall_classification": "DEPLOYMENT_PROVIDER_REACHABLE_ACTION_SEMANTICS_UNVERIFIED"
            },
        },
    }


def current_blocked_authority() -> dict:
    return {
        "classification": "TRUSTED_PROVIDER_AUTHORITY_STILL_BLOCKED",
        "provider_authenticated": False,
        "access_token_test": {"ok": False, "stderr": "invalid_target"},
    }


def current_verified_authority() -> dict:
    return {
        "classification": "GOOGLE_AUTH_AND_OPERATOR_READBACK_VERIFIED",
        "provider_authenticated": True,
        "access_token_test": {"ok": True},
        "fo_token_available": True,
        "operator_public_health": {
            "http_status": 200,
            "body_present": True,
            "body_ok": True,
            "raw_body_recorded": False,
        },
        "operator_public_contract": {
            "http_status": 200,
            "body_present": True,
            "body_ok": False,
            "raw_body_recorded": False,
        },
        "operator_authenticated_status": {
            "http_status": 200,
            "body_present": True,
            "body_ok": True,
            "raw_body_recorded": False,
        },
        "operator_architron_read": {
            "http_status": 200,
            "body_present": True,
            "body_ok": True,
            "raw_body_recorded": False,
        },
        "archon_token_available": True,
        "archon_authenticated_readback": True,
        "raw_authenticated_response_bodies_recorded": False,
        "secret_values_recorded": False,
        "mutation_attempted": False,
    }


class BubblesCapabilityActivationTests(unittest.TestCase):
    def lane(self, snapshot: dict, lane_id: str) -> dict:
        return next(lane for lane in snapshot["lanes"] if lane["lane_id"] == lane_id)

    def test_current_authority_failure_overrides_historical_success(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            provider_surface_receipt=provider_surface(),
            provider_authority_receipt=current_blocked_authority(),
            schedule_configured=True,
        )
        cloud = self.lane(snapshot, "GOOGLE_CLOUD_EFFECTS")
        self.assertEqual(ActivationState.AUTHORITY_GATED.value, cloud["state"])
        self.assertTrue(snapshot["provider_authority_conflict"]["current_authority_failed"])
        self.assertFalse(snapshot["all_green"])

    def test_schedule_event_proves_bounded_scheduled_runtime(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="schedule",
            provider_surface_receipt=provider_surface(),
            provider_authority_receipt=current_blocked_authority(),
            schedule_configured=True,
        )
        scheduled = self.lane(snapshot, "SCHEDULED_MISSIONS")
        monitor = self.lane(snapshot, "CONDITION_MONITORING")
        self.assertEqual(ActivationState.OPERATIONAL.value, scheduled["state"])
        self.assertEqual(ActivationState.HOSTED_VERIFIED.value, monitor["state"])
        self.assertTrue(snapshot["schedule_proof"]["current_event_is_schedule"])

    def test_prior_provider_verified_schedule_promotes_same_bound_workflow(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            provider_surface_receipt=provider_surface(),
            provider_authority_receipt=current_blocked_authority(),
            schedule_configured=True,
            schedule_provider_verified=True,
        )
        scheduled = self.lane(snapshot, "SCHEDULED_MISSIONS")
        self.assertEqual(ActivationState.OPERATIONAL.value, scheduled["state"])
        self.assertIsNone(scheduled["next_gate"])
        self.assertTrue(snapshot["schedule_proof"]["provider_verified_prior_schedule"])

    def test_push_with_configured_schedule_without_provider_proof_does_not_fake_execution(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            provider_surface_receipt=provider_surface(),
            provider_authority_receipt=current_blocked_authority(),
            schedule_configured=True,
            schedule_provider_verified=False,
        )
        scheduled = self.lane(snapshot, "SCHEDULED_MISSIONS")
        self.assertEqual(ActivationState.SOURCE_READY.value, scheduled["state"])
        self.assertEqual("NATURAL_SCHEDULE_EVENT_READBACK", scheduled["next_gate"])

    def test_authenticated_provider_does_not_self_certify_mutation(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="schedule",
            provider_surface_receipt=provider_surface(operator_token=True, archon_token=True),
            provider_authority_receipt={
                "classification": "TRUSTED_PROVIDER_AUTHORITY_VERIFIED",
                "provider_authenticated": True,
                "access_token_test": {"ok": True},
            },
            schedule_configured=True,
        )
        cloud = self.lane(snapshot, "GOOGLE_CLOUD_EFFECTS")
        self.assertEqual(ActivationState.HOSTED_VERIFIED.value, cloud["state"])
        self.assertEqual("ACTION_SPECIFIC_MUTATION_PLUS_TARGET_READBACK", cloud["next_gate"])

    def test_summary_only_authority_receipt_promotes_readiness_not_mutation(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            provider_surface_receipt={},
            provider_authority_receipt=current_verified_authority(),
            schedule_configured=True,
            schedule_provider_verified=True,
        )
        cloud_read = self.lane(snapshot, "GOOGLE_CLOUD_READ")
        cloud_effects = self.lane(snapshot, "GOOGLE_CLOUD_EFFECTS")
        archon = self.lane(snapshot, "ARCHON_ADMIN")
        self.assertEqual(ActivationState.HOSTED_VERIFIED.value, cloud_read["state"])
        self.assertEqual(ActivationState.HOSTED_VERIFIED.value, cloud_effects["state"])
        self.assertEqual("ACTION_SPECIFIC_MUTATION_PLUS_TARGET_READBACK", cloud_effects["next_gate"])
        self.assertEqual(ActivationState.HOSTED_VERIFIED.value, archon["state"])
        self.assertFalse(snapshot["provider_authority_conflict"]["current_authority_failed"])
        self.assertTrue(snapshot["provider_authority_conflict"]["current_provider_authenticated"])

    def test_owner_value_and_full_twin_remain_data_gated(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="schedule",
            provider_surface_receipt=provider_surface(),
            provider_authority_receipt=current_blocked_authority(),
            schedule_configured=True,
        )
        self.assertEqual(ActivationState.DATA_GATED.value, self.lane(snapshot, "EMPIRICAL_OWNER_VALUE")["state"])
        self.assertEqual(ActivationState.DATA_GATED.value, self.lane(snapshot, "FULL_GOVERNED_DIGITAL_TWIN")["state"])


if __name__ == "__main__":
    unittest.main()
