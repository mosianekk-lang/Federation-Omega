from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from ops.openai_rotation_evidence_intake import (
    RotationEvidenceError,
    build_closure_receipt_candidate,
    canonical_sha256,
    evaluate_evidence,
    required_gate_keys,
    validate_evidence,
)

EVALUATED_AT = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)


def manifest() -> dict:
    return {
        "schema": "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-1",
        "manifest_id": "OPENAI-ROTATION-20260804-A",
        "owner": "Kim Kagiso Mosiane",
        "provider_key": {
            "display_name": "Federation Omega Rotation 2026-08-04",
        },
        "destinations": [
            {
                "destination_id": "mosiane-live-thread",
                "secret_id": "openai-mosiane-live-thread-20260804",
                "runtime_service": "mosiane-live-thread",
                "runtime_identity": (
                    "superior-logic-runtime@"
                    "sov-hybrid-suite.iam.gserviceaccount.com"
                ),
            },
            {
                "destination_id": "modisa-legal-v2",
                "secret_id": "openai-modisa-legal-v2-20260804",
                "runtime_service": None,
                "runtime_identity": None,
            },
        ],
    }


def evidence(
    evidence_type: str,
    *,
    destination_id: str | None = None,
    provider_native: bool = True,
    owner_attested: bool = False,
    observed_at: str = "2026-08-05T08:50:00Z",
    details: dict | None = None,
    suffix: str = "",
) -> dict:
    item = {
        "schema": "FEDOMEGA-OPENAI-ROTATION-PROVIDER-EVIDENCE-2",
        "manifest_id": "OPENAI-ROTATION-20260804-A",
        "evidence_id": f"EVD-{evidence_type}-{destination_id or 'PROVIDER'}{suffix}",
        "evidence_type": evidence_type,
        "destination_id": destination_id,
        "provider": "OPENAI" if destination_id is None else "GOOGLE_CLOUD",
        "observed_at": observed_at,
        "provider_native": provider_native,
        "owner_attested": owner_attested,
        "provider_reference": (
            f"provider://{destination_id or 'openai'}/"
            f"{evidence_type.lower()}{suffix}"
        ),
        "plaintext_observed": False,
        "credential_value_recorded": False,
        "intake_provider_mutation_performed": False,
        "external_effect_performed": False,
        "details": details or {},
    }
    item["evidence_sha256"] = canonical_sha256(item)
    return item


def details_for(evidence_type: str, destination_id: str | None) -> dict:
    secret = (
        "openai-mosiane-live-thread-20260804"
        if destination_id == "mosiane-live-thread"
        else "openai-modisa-legal-v2-20260804"
    )
    if evidence_type == "KEY_CREATION_ASSERTION":
        return {
            "display_name": "Federation Omega Rotation 2026-08-04",
            "created": True,
        }
    if evidence_type == "SECRET_METADATA_READBACK":
        return {
            "secret_id": secret,
            "payload_read": False,
            "metadata_readback": True,
        }
    if evidence_type == "RUNTIME_IDENTITY_READBACK":
        if destination_id == "mosiane-live-thread":
            return {
                "runtime_identity": (
                    "superior-logic-runtime@"
                    "sov-hybrid-suite.iam.gserviceaccount.com"
                ),
                "runtime_service": "mosiane-live-thread",
            }
        return {
            "runtime_identity": (
                "modisa-private-runtime@"
                "sov-hybrid-suite.iam.gserviceaccount.com"
            ),
            "private_execution_plane": True,
        }
    if evidence_type == "SECRET_REFERENCE_BINDING_READBACK":
        return {
            "secret_id": secret,
            "runtime_environment_name": "OPENAI_API_KEY",
            "literal_value_present": False,
            "reference_readback": True,
        }
    if evidence_type == "ROLLBACK_TARGET_CAPTURE":
        return {
            "rollback_target": f"revision://{destination_id}/previous",
            "rollback_target_readback": True,
        }
    if evidence_type == "CANARY_HEALTH":
        if destination_id == "mosiane-live-thread":
            return {"health_verified": True, "traffic_percent": 0}
        return {
            "health_verified": True,
            "isolated_non_production": True,
            "external_actions_disabled": True,
        }
    if evidence_type == "SEMANTIC_PROBE":
        if destination_id == "mosiane-live-thread":
            return {
                "trace_id": "trace-live-thread",
                "semantic_fingerprint": "sha256:live-thread-action-response",
                "hash_chain_valid": True,
                "action_specific_response": True,
            }
        return {
            "trace_id": "trace-modisa",
            "semantic_fingerprint": "sha256:modisa-seven-chamber-response",
            "seven_independent_opinions": True,
            "council_complete": True,
            "proof_bound_release": True,
            "external_actions_disabled": True,
        }
    if evidence_type == "EXPOSED_KEY_REVOCATION":
        return {"revoked": True, "revocation_readback": True}
    if evidence_type == "EXPOSED_KEY_REJECTION":
        return {
            "rejected": True,
            "response_class": "AUTHENTICATION_REJECTED",
            "tested_value_recorded": False,
        }
    raise AssertionError(evidence_type)


def complete_evidence() -> list[dict]:
    items = [
        evidence(
            "KEY_CREATION_ASSERTION",
            provider_native=False,
            owner_attested=True,
            details=details_for("KEY_CREATION_ASSERTION", None),
        )
    ]
    destination_types = (
        "SECRET_METADATA_READBACK",
        "RUNTIME_IDENTITY_READBACK",
        "SECRET_REFERENCE_BINDING_READBACK",
        "ROLLBACK_TARGET_CAPTURE",
        "CANARY_HEALTH",
        "SEMANTIC_PROBE",
    )
    for destination_id in ("mosiane-live-thread", "modisa-legal-v2"):
        for evidence_type in destination_types:
            items.append(
                evidence(
                    evidence_type,
                    destination_id=destination_id,
                    details=details_for(evidence_type, destination_id),
                )
            )
    items.extend(
        [
            evidence(
                "EXPOSED_KEY_REVOCATION",
                details=details_for("EXPOSED_KEY_REVOCATION", None),
            ),
            evidence(
                "EXPOSED_KEY_REJECTION",
                details=details_for("EXPOSED_KEY_REJECTION", None),
            ),
        ]
    )
    return items


class OpenAIRotationEvidenceIntakeTests(unittest.TestCase):
    def test_required_gate_count_is_exact(self) -> None:
        self.assertEqual(15, len(required_gate_keys()))

    def test_owner_attested_key_creation_is_bounded(self) -> None:
        validated = validate_evidence(
            complete_evidence()[0],
            manifest=manifest(),
            evaluated_at=EVALUATED_AT,
        )
        self.assertTrue(validated["owner_attested"])
        self.assertFalse(validated["provider_native"])

    def test_non_creation_owner_assertion_is_rejected(self) -> None:
        item = evidence(
            "SECRET_METADATA_READBACK",
            destination_id="mosiane-live-thread",
            provider_native=False,
            owner_attested=True,
            details=details_for(
                "SECRET_METADATA_READBACK", "mosiane-live-thread"
            ),
        )
        with self.assertRaisesRegex(RotationEvidenceError, "provider-native"):
            validate_evidence(
                item,
                manifest=manifest(),
                evaluated_at=EVALUATED_AT,
            )

    def test_secret_payload_read_is_rejected(self) -> None:
        item = evidence(
            "SECRET_METADATA_READBACK",
            destination_id="mosiane-live-thread",
            details={
                "secret_id": "openai-mosiane-live-thread-20260804",
                "payload_read": True,
                "metadata_readback": True,
            },
        )
        with self.assertRaisesRegex(RotationEvidenceError, "payload"):
            validate_evidence(
                item,
                manifest=manifest(),
                evaluated_at=EVALUATED_AT,
            )

    def test_tampered_evidence_is_rejected(self) -> None:
        item = complete_evidence()[1]
        item["details"]["metadata_readback"] = False
        with self.assertRaisesRegex(RotationEvidenceError, "hash verification"):
            validate_evidence(
                item,
                manifest=manifest(),
                evaluated_at=EVALUATED_AT,
            )

    def test_stale_canary_is_rejected(self) -> None:
        item = evidence(
            "CANARY_HEALTH",
            destination_id="mosiane-live-thread",
            observed_at="2026-08-05T08:00:00Z",
            details=details_for("CANARY_HEALTH", "mosiane-live-thread"),
        )
        with self.assertRaisesRegex(RotationEvidenceError, "stale"):
            validate_evidence(
                item,
                manifest=manifest(),
                evaluated_at=EVALUATED_AT,
            )

    def test_wrong_secret_reference_is_rejected(self) -> None:
        item = evidence(
            "SECRET_REFERENCE_BINDING_READBACK",
            destination_id="modisa-legal-v2",
            details={
                "secret_id": "openai-mosiane-live-thread-20260804",
                "runtime_environment_name": "OPENAI_API_KEY",
                "literal_value_present": False,
                "reference_readback": True,
            },
        )
        with self.assertRaisesRegex(RotationEvidenceError, "mismatch"):
            validate_evidence(
                item,
                manifest=manifest(),
                evaluated_at=EVALUATED_AT,
            )

    def test_duplicate_provider_reference_is_rejected(self) -> None:
        items = complete_evidence()
        items[1]["provider_reference"] = items[0]["provider_reference"]
        items[1]["evidence_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in items[1].items()
                if key != "evidence_sha256"
            }
        )
        with self.assertRaisesRegex(RotationEvidenceError, "cannot be reused"):
            evaluate_evidence(
                manifest=manifest(),
                evidence_items=items,
                evaluated_at=EVALUATED_AT,
            )

    def test_semantic_fingerprint_reuse_is_rejected(self) -> None:
        items = complete_evidence()
        semantic = [
            item for item in items if item["evidence_type"] == "SEMANTIC_PROBE"
        ]
        semantic[1]["details"]["semantic_fingerprint"] = semantic[0]["details"][
            "semantic_fingerprint"
        ]
        semantic[1]["evidence_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in semantic[1].items()
                if key != "evidence_sha256"
            }
        )
        with self.assertRaisesRegex(RotationEvidenceError, "fingerprint"):
            evaluate_evidence(
                manifest=manifest(),
                evidence_items=items,
                evaluated_at=EVALUATED_AT,
            )

    def test_incomplete_packet_lists_open_gates(self) -> None:
        receipt = evaluate_evidence(
            manifest=manifest(),
            evidence_items=complete_evidence()[:1],
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(
            "INCOMPLETE_PROVIDER_EVIDENCE_OPEN_GATES",
            receipt["status"],
        )
        self.assertEqual(14, len(receipt["open_gates"]))
        self.assertFalse(receipt["provider_mutation_performed"])

    def test_complete_packet_is_hash_bound_and_closure_eligible(self) -> None:
        items = complete_evidence()
        receipt = evaluate_evidence(
            manifest=manifest(),
            evidence_items=items,
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(
            "COMPLETE_PROVIDER_EVIDENCE_CLOSURE_ELIGIBLE",
            receipt["status"],
        )
        self.assertEqual(15, receipt["accepted_evidence_count"])
        body = deepcopy(receipt)
        claimed = body.pop("receipt_sha256")
        self.assertEqual(canonical_sha256(body), claimed)
        closure = build_closure_receipt_candidate(
            manifest=manifest(),
            evidence_items=items,
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(
            "COMPLETE_REDACTED_AND_VERIFIED",
            closure["completion_state"],
        )
        self.assertEqual(2, len(closure["destinations"]))
        self.assertFalse(closure["plaintext_observed"])

    def test_old_key_rejection_must_not_record_tested_value(self) -> None:
        item = evidence(
            "EXPOSED_KEY_REJECTION",
            details={
                "rejected": True,
                "response_class": "AUTHENTICATION_REJECTED",
                "tested_value_recorded": True,
            },
        )
        with self.assertRaisesRegex(RotationEvidenceError, "must not be recorded"):
            validate_evidence(
                item,
                manifest=manifest(),
                evaluated_at=EVALUATED_AT,
            )

    def test_key_shaped_material_is_rejected_without_literal_fixture(self) -> None:
        item = complete_evidence()[0]
        item["details"]["display_name"] = "sk-" + "proj-" + ("A" * 32)
        item["evidence_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in item.items()
                if key != "evidence_sha256"
            }
        )
        with self.assertRaisesRegex(RotationEvidenceError, "credential pattern"):
            validate_evidence(
                item,
                manifest=manifest(),
                evaluated_at=EVALUATED_AT,
            )


if __name__ == "__main__":
    unittest.main()
