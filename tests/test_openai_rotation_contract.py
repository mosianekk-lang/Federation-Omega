from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

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


class OpenAIRotationContractTests(unittest.TestCase):
    def test_canonical_manifest_passes(self) -> None:
        validated = validate_manifest(load_manifest())
        self.assertEqual(validated["schema"], "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-1")
        self.assertEqual(len(validated["destinations"]), 2)

    def test_duplicate_secret_reference_is_rejected(self) -> None:
        manifest = load_manifest()
        manifest["destinations"][1]["secret_id"] = manifest["destinations"][0]["secret_id"]
        with self.assertRaisesRegex(RotationContractError, "distinct secret reference"):
            validate_manifest(manifest)

    def test_compromised_shared_alias_is_rejected_as_secret_id(self) -> None:
        manifest = load_manifest()
        manifest["destinations"][0]["secret_id"] = "OPENAI_API_KEY"
        with self.assertRaises(RotationContractError):
            validate_manifest(manifest)

    def test_key_like_material_is_rejected_without_literal_fixture(self) -> None:
        manifest = load_manifest()
        manifest["provider_key"]["display_name"] = "sk-" + "proj-" + ("A" * 32)
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
        manifest = load_manifest()
        receipt = receipt_template(manifest)
        for destination in receipt["destinations"]:
            destination.update(
                {
                    "secret_reference_readback": True,
                    "least_privilege_identity_readback": True,
                    "canary_health_verified": True,
                    "semantic_probe_verified": True,
                    "rollback_target_captured": True,
                    "production_promotion": "VERIFIED_REVISION_ONLY",
                }
            )
        receipt["provider_closure"] = {
            "exposed_key_revoked": True,
            "exposed_key_rejection_verified": True,
        }
        receipt["completion_state"] = "COMPLETE_REDACTED_AND_VERIFIED"
        validated = validate_receipt(manifest, receipt)
        self.assertEqual(validated["completion_state"], "COMPLETE_REDACTED_AND_VERIFIED")

    def test_completion_claim_cannot_be_set_in_manifest(self) -> None:
        manifest = copy.deepcopy(load_manifest())
        manifest["completion_state"] = "COMPLETE"
        with self.assertRaisesRegex(RotationContractError, "must not claim completion"):
            validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
