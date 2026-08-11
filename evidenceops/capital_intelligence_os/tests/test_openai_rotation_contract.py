from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ops.openai_callable_route_gate import validate_complete_rotation
from ops.openai_rotation_contract import (
    RotationContractError,
    build_redacted_plan,
    receipt_template,
    validate_manifest,
    validate_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "governance" / "openai_credential_rotation_manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def complete_receipt() -> tuple[dict, dict]:
    manifest = load_manifest()
    receipt = receipt_template(manifest)
    route_types = {
        "mosiane-live-thread": "DIRECT_GOOGLE_CLOUD_API",
        "modisa-legal-v2": "AUTHENTICATED_APPS_SCRIPT_WEB_APP",
    }
    actions = {
        "mosiane-live-thread": "GET_CLOUD_RUN_SERVICE",
        "modisa-legal-v2": "RUN_MODISA_CANARY",
    }
    fingerprints = {
        "mosiane-live-thread": "sha256:live-thread-service-metadata",
        "modisa-legal-v2": "sha256:modisa-canary-result",
    }
    for destination in receipt["destinations"]:
        destination_id = destination["destination_id"]
        destination.update(
            {
                "secret_reference_readback": True,
                "least_privilege_identity_readback": True,
                "canary_health_verified": True,
                "semantic_probe_verified": True,
                "rollback_target_captured": True,
                "production_promotion": "VERIFIED_REVISION_ONLY",
                "execution_route": {
                    "route_type": route_types[destination_id],
                    "depends_on_api_write_trigger": False,
                    "callable_provider_readback": True,
                    "provider_proof_ref": f"provider://{destination_id}/proof",
                    "executed_at": "2026-08-04T18:45:00Z",
                    "generic_health_response": False,
                    "requested_action": actions[destination_id],
                    "response_action": actions[destination_id],
                    "semantic_fields_verified": True,
                    "semantic_response_fingerprint": fingerprints[destination_id],
                },
            }
        )
    receipt["provider_closure"] = {
        "exposed_key_revoked": True,
        "exposed_key_rejection_verified": True,
    }
    receipt["completion_state"] = "COMPLETE_REDACTED_AND_VERIFIED"
    return manifest, receipt


class OpenAIRotationContractTests(unittest.TestCase):
    def test_canonical_manifest_passes(self) -> None:
        validated = validate_manifest(load_manifest())
        self.assertEqual(
            validated["schema"],
            "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-1",
        )
        self.assertEqual(len(validated["destinations"]), 2)

    def test_duplicate_secret_reference_is_rejected(self) -> None:
        manifest = load_manifest()
        manifest["destinations"][1]["secret_id"] = (
            manifest["destinations"][0]["secret_id"]
        )
        with self.assertRaisesRegex(
            RotationContractError,
            "distinct secret reference",
        ):
            validate_manifest(manifest)

    def test_compromised_shared_alias_is_rejected_as_secret_id(self) -> None:
        manifest = load_manifest()
        manifest["destinations"][0]["secret_id"] = "OPENAI_API_KEY"
        with self.assertRaises(RotationContractError):
            validate_manifest(manifest)

    def test_key_like_material_is_rejected_without_literal_fixture(self) -> None:
        manifest = load_manifest()
        manifest["provider_key"]["display_name"] = (
            "sk-" + "proj-" + ("A" * 32)
        )
        with self.assertRaisesRegex(RotationContractError, "credential pattern"):
            validate_manifest(manifest)

    def test_redacted_plan_contains_references_not_values(self) -> None:
        plan = build_redacted_plan(load_manifest())
        rendered = json.dumps(plan)
        self.assertFalse(plan["contains_raw_credential"])
        self.assertNotIn("sk-" + "proj-", rendered)
        self.assertIn("openai-mosiane-live-thread-20260804", rendered)
        self.assertIn("openai-modisa-legal-v2-20260804", rendered)

    def test_incomplete_receipt_fails_closed(self) -> None:
        manifest = load_manifest()
        receipt = receipt_template(manifest)
        with self.assertRaisesRegex(RotationContractError, "readback missing"):
            validate_receipt(manifest, receipt)

    def test_complete_redacted_receipt_passes(self) -> None:
        manifest, receipt = complete_receipt()
        validated = validate_receipt(manifest, receipt)
        self.assertEqual(
            validated["completion_state"],
            "COMPLETE_REDACTED_AND_VERIFIED",
        )

    def test_complete_rotation_requires_callable_routes(self) -> None:
        manifest, receipt = complete_receipt()
        validated = validate_complete_rotation(manifest, receipt)
        self.assertEqual(
            validated["completion_state"],
            "COMPLETE_REDACTED_AND_VERIFIED",
        )

    def test_api_write_trigger_route_is_rejected(self) -> None:
        manifest, receipt = complete_receipt()
        route = receipt["destinations"][0]["execution_route"]
        route["route_type"] = "SHEET_API_EDIT_TRIGGER"
        route["depends_on_api_write_trigger"] = True
        with self.assertRaisesRegex(
            RotationContractError,
            "Non-execution route rejected",
        ):
            validate_complete_rotation(manifest, receipt)

    def test_generic_health_response_is_rejected_as_execution(self) -> None:
        manifest, receipt = complete_receipt()
        receipt["destinations"][1]["execution_route"][
            "generic_health_response"
        ] = True
        with self.assertRaisesRegex(
            RotationContractError,
            "Generic runtime health",
        ):
            validate_complete_rotation(manifest, receipt)

    def test_response_action_must_match_requested_action(self) -> None:
        manifest, receipt = complete_receipt()
        route = receipt["destinations"][0]["execution_route"]
        route["response_action"] = "STATUS"
        with self.assertRaisesRegex(
            RotationContractError,
            "Response action does not match",
        ):
            validate_complete_rotation(manifest, receipt)

    def test_semantic_fields_are_required(self) -> None:
        manifest, receipt = complete_receipt()
        route = receipt["destinations"][0]["execution_route"]
        route["semantic_fields_verified"] = False
        with self.assertRaisesRegex(
            RotationContractError,
            "Action-specific semantic fields missing",
        ):
            validate_complete_rotation(manifest, receipt)

    def test_action_agnostic_fingerprint_reuse_is_rejected(self) -> None:
        manifest, receipt = complete_receipt()
        first = receipt["destinations"][0]["execution_route"]
        second = receipt["destinations"][1]["execution_route"]
        second["semantic_response_fingerprint"] = (
            first["semantic_response_fingerprint"]
        )
        with self.assertRaisesRegex(
            RotationContractError,
            "Action-agnostic response fingerprint",
        ):
            validate_complete_rotation(manifest, receipt)

    def test_legacy_positional_queue_schema_is_rejected(self) -> None:
        manifest, receipt = complete_receipt()
        route = receipt["destinations"][0]["execution_route"]
        route["queue_contract"] = {
            "header_driven": False,
            "uses_positional_columns": True,
            "schema_readback_ref": "provider://queue/header",
            "column_map": {
                "status": "status",
                "result": "resultJson",
                "started_at": "startedAt",
                "completed_at": "completedAt",
            },
        }
        with self.assertRaisesRegex(
            RotationContractError,
            "header-driven",
        ):
            validate_complete_rotation(manifest, receipt)

    def test_header_driven_canonical_queue_schema_passes(self) -> None:
        manifest, receipt = complete_receipt()
        route = receipt["destinations"][0]["execution_route"]
        route["queue_contract"] = {
            "header_driven": True,
            "uses_positional_columns": False,
            "schema_readback_ref": "provider://queue/header",
            "column_map": {
                "status": "status",
                "result": "resultJson",
                "started_at": "startedAt",
                "completed_at": "completedAt",
            },
        }
        validated = validate_complete_rotation(manifest, receipt)
        self.assertEqual(
            validated["completion_state"],
            "COMPLETE_REDACTED_AND_VERIFIED",
        )

    def test_missing_callable_route_is_rejected(self) -> None:
        manifest, receipt = complete_receipt()
        del receipt["destinations"][0]["execution_route"]
        with self.assertRaisesRegex(
            RotationContractError,
            "Callable execution route missing",
        ):
            validate_complete_rotation(manifest, receipt)

    def test_completion_claim_cannot_be_set_in_manifest(self) -> None:
        manifest = copy.deepcopy(load_manifest())
        manifest["completion_state"] = "COMPLETE"
        with self.assertRaisesRegex(
            RotationContractError,
            "must not claim completion",
        ):
            validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
