from __future__ import annotations

import base64
import codecs
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from federation_consolidation.estate_delta_transaction import (
    BOUNDED_SCOPE_CLAIM_TEXT,
    EstateDeltaError,
    canonical_json,
    canonical_sha256,
    select_observation_route,
    validate_public_pointer,
    validate_route_catalog,
    validate_schema_alignment,
    validate_transaction,
    validate_genesis_transaction_against_manifest,
    verify_chain,
)


class SourcePayloadBundle(dict):
    def __init__(self, values: dict, supporting_payloads: dict):
        super().__init__(values)
        self.supporting_payloads = supporting_payloads


def route_catalog() -> dict:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (root / "federation_consolidation/data/estate_observation_route_catalog_v1.json").read_text(
            encoding="utf-8"
        )
    )


def rehash(value: dict) -> dict:
    body_hash = canonical_sha256(value["body"])
    value["integrity"]["body_sha256"] = body_hash
    value["integrity"]["event_hash"] = canonical_sha256({
        "body": value["body"],
        "body_hash": body_hash,
        "previous_event_hash": value["integrity"]["previous_event_hash"],
    })
    return value


def candidate() -> dict:
    body = {
        "schema": "FEDERATION-ESTATE-DELTA-TRANSACTION-1",
        "transaction_id": "FEDERATION-ESTATE-CENSUS-20260827-001",
        "register_id": "FEDERATION-ESTATE-DELTA-REGISTER",
        "sequence": 1,
        "event_type": "CENSUS_SNAPSHOT",
        "mission_id": "FEDERATION-ESTATE-DELTA-REGISTER-20260827",
        "authority": "A0_READ_ONLY",
        "occurred_at": "2026-08-27T03:18:40Z",
        "observed_at": "2026-08-27T03:18:40Z",
        "artifact_classification": "PUBLIC_SAFE_PRIVATE_POINTERS_REDACTED",
        "scope": {
            "scope_label": "CONNECTED_CALLABLE_BOUNDED_CENSUS",
            "claim_text": BOUNDED_SCOPE_CLAIM_TEXT,
            "canonical_status": "PARTIAL_PROVEN",
            "totality_claimed": False,
            "expected_sources": ["public Federation operator health and contract"],
            "inspected_to_end": ["public Federation operator health and contract"],
            "all_expected_bounded_sources_enumerated": True,
        },
        "lineage": {
            "previous_transaction_id": None,
            "historical_baselines": [{
                "baseline_id": "EFSL-20260802-001",
                "claimed_sha256": "1ceb1c3e711fbb6968e9bbf318370af8cbce1ecbbcea84880e353d3e22e7d458",
                "verification_state": "HISTORICAL_REFERENCE_UNRESOLVED",
                "chain_parent": False,
            }],
        },
        "inputs": [{
            "source_id": "SRC:CENSUS-MANIFEST-20260827",
            "source_class": "DERIVED_CENSUS_MANIFEST",
            "observed_at": "2026-08-27T03:18:40Z",
            "content_sha256": "1" * 64,
            "locator_state": "BUNDLED_IMMUTABLE",
            "proof_state": "DERIVED_VERIFIED",
        }],
        "surface_snapshots": [
            {
                "snapshot_id": "SNAP:GEMINI-GAP-001",
                "subject_id": "PROVIDER:GEMINI",
                "surface": "GEMINI",
                "evidence_class": "DERIVED_ABSENCE_OF_REQUIRED_PROOF",
                "observed_at": "2026-08-27T03:18:40Z",
                "proof_state": "UNVERIFIED",
                "state": "CONFIG_BOUND_ONLY",
                "input_source_ids": ["SRC:CENSUS-MANIFEST-20260827"],
                "metrics": [{"name": "DIRECT_CANARY_INSTALLED", "value": False}],
                "boundary_ids": ["BOUNDARY:DIRECT-GEMINI"],
            },
            {
                "snapshot_id": "SNAP:WIF-CURRENT-001",
                "subject_id": "PROVIDER:GOOGLE-WIF",
                "surface": "CLOUD_CONTROL",
                "evidence_class": "PROVIDER_NATIVE_READBACK",
                "observed_at": "2026-08-27T03:07:38Z",
                "proof_state": "READBACK_VERIFIED",
                "state": "PROVIDER_ABSENT",
                "input_source_ids": ["SRC:CENSUS-MANIFEST-20260827"],
                "metrics": [
                    {"name": "POOL_PRESENT", "value": False},
                    {"name": "PROVIDER_PRESENT", "value": False}
                ],
                "boundary_ids": ["BOUNDARY:WIF-TOKEN-EXCHANGE"],
            },
            {
                "snapshot_id": "SNAP:Z-CLOUD-OPERATOR-001",
                "subject_id": "SURFACE:CLOUD-OPERATOR",
                "surface": "CLOUD_CONTROL",
                "evidence_class": "PROVIDER_NATIVE_READBACK",
                "observed_at": "2026-08-27T03:18:40Z",
                "proof_state": "READBACK_VERIFIED",
                "state": "OPERATOR_READY",
                "input_source_ids": ["SRC:CENSUS-MANIFEST-20260827"],
                "metrics": [{"name": "OPERATOR_HEALTH", "value": "OPERATOR_READY"}],
                "boundary_ids": ["BOUNDARY:DIRECT-GEMINI"],
            },
        ],
        "projections": [
            {
                "subject_id": "PROVIDER:GEMINI",
                "state": "CONFIG_BOUND_ONLY",
                "proof_state": "UNVERIFIED",
                "selection_rule": "NO_PROVIDER_READBACK_HOLD",
                "winning_snapshot_id": "SNAP:GEMINI-GAP-001",
                "hold": True,
            },
            {
                "subject_id": "PROVIDER:GOOGLE-WIF",
                "state": "PROVIDER_ABSENT",
                "proof_state": "READBACK_VERIFIED",
                "selection_rule": "LATEST_PROVIDER_NATIVE_READBACK",
                "winning_snapshot_id": "SNAP:WIF-CURRENT-001",
                "hold": True,
            },
            {
                "subject_id": "SURFACE:CLOUD-OPERATOR",
                "state": "OPERATOR_READY",
                "proof_state": "READBACK_VERIFIED",
                "selection_rule": "LATEST_PROVIDER_NATIVE_READBACK",
                "winning_snapshot_id": "SNAP:Z-CLOUD-OPERATOR-001",
                "hold": True,
            },
        ],
        "contradictions": [{
            "contradiction_id": "CONTRADICTION:WIF-001",
            "subject_id": "PROVIDER:GOOGLE-WIF",
            "earlier_claim": "WIF was previously described as verified.",
            "current_snapshot_id": "SNAP:WIF-CURRENT-001",
            "disposition": "SUPERSEDED_RETAINED",
            "affects_totality": True,
        }],
        "unresolved_boundaries": [
            {
                "boundary_id": "BOUNDARY:DIRECT-GEMINI",
                "description": "Direct Gemini provider receipt is absent.",
                "state": "OPEN",
                "material_to_totality": True,
                "closure_evidence": "Provider-native model and usage readback.",
                "avoidable_user_task": False,
            },
            {
                "boundary_id": "BOUNDARY:WIF-TOKEN-EXCHANGE",
                "description": "WIF token exchange is not proven.",
                "state": "OPEN",
                "material_to_totality": True,
                "closure_evidence": "Fresh pool, provider and token-exchange readback.",
                "avoidable_user_task": False,
            },
        ],
        "effects": {
            "mutation_count": 0,
            "external_effect_count": 0,
            "provider_mutation_performed": False,
            "email_sent": False,
            "cost_incurred": 0,
        },
        "privacy": {
            "credential_value_recorded": False,
            "private_provider_identifier_recorded": False,
            "private_locator_count": 0,
            "redaction_policy": "ALIASES_COUNTS_STATES_AND_HASHES_ONLY",
        },
        "completion": {
            "status": "PARTIAL_PROVEN",
            "totality_allowed": False,
            "unresolved_boundary_count": 2,
            "unresolved_contradiction_count": 0,
            "independent_check_state": "PASSED_BOUNDED_SCOPE",
            "truth_boundary": (
                "This transaction proves only the named connected and callable bounded scope at "
                "2026-08-27T03:18:40Z; it is not whole-estate, runtime-activation or "
                "provider-execution proof."
            ),
        },
    }
    body_hash = canonical_sha256(body)
    return {
        "body": body,
        "integrity": {
            "canonicalization": "UTF8_JSON_SORT_KEYS_COMPACT_SEPARATORS_ENSURE_ASCII_FALSE",
            "body_sha256": body_hash,
            "previous_event_hash": None,
            "event_hash": canonical_sha256({"body": body, "body_hash": body_hash, "previous_event_hash": None}),
        },
    }


def github_fidelity_candidate() -> tuple[dict, dict, dict, dict]:
    value = candidate()
    value["body"]["scope"]["expected_sources"] = ["GitHub accessible account and repository"]
    value["body"]["scope"]["inspected_to_end"] = ["GitHub accessible account and repository"]
    value["body"]["surface_snapshots"] = [{
        "snapshot_id": "SNAP:GITHUB-001",
        "subject_id": "SURFACE:GITHUB",
        "surface": "GITHUB",
        "evidence_class": "REPOSITORY_EXACT_HEAD",
        "observed_at": "2026-08-27T03:18:40Z",
        "proof_state": "READBACK_VERIFIED",
        "state": "CURRENT_HEAD_PASS_PROVIDER_ADMISSION_FAIL",
        "input_source_ids": ["SRC:CENSUS-MANIFEST-20260827"],
        "metrics": [
            {"name": "PROVIDER_ADMISSION_STATUS", "value": "FAIL"},
            {"name": "TREE_ITEMS", "value": 2680},
        ],
        "boundary_ids": [
            "BOUNDARY:PROVIDER-NATIVE-BRANCH-PROTECTION",
            "BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS",
            "BOUNDARY:WIF-REPOSITORY-TRUST",
        ],
    }]
    value["body"]["projections"] = [{
        "subject_id": "SURFACE:GITHUB",
        "state": "CURRENT_HEAD_PASS_PROVIDER_ADMISSION_FAIL",
        "proof_state": "READBACK_VERIFIED",
        "selection_rule": "HIGHEST_CURRENT_EVIDENCE",
        "winning_snapshot_id": "SNAP:GITHUB-001",
        "hold": True,
    }]
    value["body"]["contradictions"] = []
    value["body"]["unresolved_boundaries"] = [
        {
            "boundary_id": "BOUNDARY:PROVIDER-NATIVE-BRANCH-PROTECTION",
            "description": "Provider-native branch protection",
            "state": "OPEN",
            "material_to_totality": True,
            "closure_evidence": "Current repository ruleset and branch-protection readback.",
            "avoidable_user_task": False,
        },
        {
            "boundary_id": "BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS",
            "description": "Surfaces outside connected or accessible accounts",
            "state": "OPEN",
            "material_to_totality": True,
            "closure_evidence": "Authorized account inventory and closed pagination per provider.",
            "avoidable_user_task": False,
        },
        {
            "boundary_id": "BOUNDARY:WIF-REPOSITORY-TRUST",
            "description": "WIF token exchange and repository trust",
            "state": "OPEN",
            "material_to_totality": True,
            "closure_evidence": "Provider-native pool, provider, binding, repository trust and successful exchange readback.",
            "avoidable_user_task": False,
        },
    ]
    value["body"]["completion"]["unresolved_boundary_count"] = 3
    value["body"]["completion"]["unresolved_contradiction_count"] = 0
    manifest = {
        "missionId": value["body"]["mission_id"],
        "observedAtUtc": value["body"]["observed_at"],
        "authority": "A0_READ_ONLY",
        "canonicalStatus": "PARTIAL_PROVEN",
        "state": {"repositoryCi": "CURRENT_HEAD_PASS"},
        "surfaces": {"github": {"treeItems": 2680, "providerAdmission": {"status": "FAIL"}}},
        "unresolvedBoundaries": [
            "Provider-native branch protection",
            "Surfaces outside connected or accessible accounts",
            "WIF token exchange and repository trust",
        ],
        "mutations": [],
    }
    bounded = {
        "claim": "A current bounded census covers the connected and callable Federation surfaces listed in scope, with unresolved boundaries named.",
        "declaredStatus": "PARTIAL",
        "claimScope": "The accessible GitHub account and repository are bounded to this synthetic test fixture.",
        "sourceCoverage": {
            "allExpectedSourcesEnumerated": True,
            "manifestCurrent": True,
            "expected": ["GitHub accessible account and repository"],
            "inspectedToEnd": ["GitHub accessible account and repository"],
        },
        "candidateTests": {
            "executedAgainstCandidate": True,
            "allPassed": True,
            "failures": [],
        },
        "authority": {
            "canonicalSourceResolved": False,
            "conflictsResolved": False,
            "supersessionResolved": False,
        },
        "evidence": {
            "current": True,
            "independentReadback": True,
            "contradictions": [],
            "unknowns": ["Provider execution remains outside the fixture."],
        },
        "requirements": {"criticalTotal": 10, "criticalProven": 7},
        "counterexampleSearch": {"performed": True, "findings": []},
        "fruit": {
            "expected": ["bounded inventory"],
            "observed": ["bounded inventory"],
        },
        "independentCheckPassed": True,
    }
    totality = {
        "claim": "The full Federation estate has been exhaustively swept and everything is known.",
        "declaredStatus": "COMPREHENSIVE",
        "claimScope": "Universal current Federation estate across every connected and private surface.",
        "sourceCoverage": {
            "allExpectedSourcesEnumerated": False,
            "manifestCurrent": False,
            "expected": ["connected surface", "inaccessible surface"],
            "inspectedToEnd": ["connected surface"],
        },
        "candidateTests": {
            "executedAgainstCandidate": True,
            "allPassed": False,
            "failures": ["Inaccessible surface remains open."],
        },
        "authority": {
            "canonicalSourceResolved": False,
            "conflictsResolved": False,
            "supersessionResolved": False,
        },
        "evidence": {
            "current": True,
            "independentReadback": True,
            "contradictions": ["A current boundary disproves totality."],
            "unknowns": ["Inaccessible surface."],
        },
        "requirements": {"criticalTotal": 10, "criticalProven": 6},
        "counterexampleSearch": {
            "performed": True,
            "findings": ["At least one boundary remains."],
        },
        "fruit": {
            "expected": ["bounded inventory"],
            "observed": ["bounded inventory"],
        },
        "independentCheckPassed": False,
    }
    drift = {
        "intent": {"mutationRequested": False},
        "queue": {
            "configuredId": "SYNTHETIC-QUEUE-ALIAS",
            "liveProcessorId": "SYNTHETIC-QUEUE-ALIAS",
            "triggerFresh": True,
        },
        "schema": {"declaredFingerprint": None, "liveFingerprint": None},
        "transport": {"success": True},
        "capability": {
            "action": "SOVARA_WIF_INVENTORY_V1",
            "enabled": True,
            "expectedFields": [
                "projectId", "projectNumber", "poolStatus", "providerStatus", "receiptSha256"
            ],
            "actualResponse": {
                "projectId": "SYNTHETIC-PROJECT",
                "projectNumber": "100000000000",
                "poolStatus": "HTTP_404_ABSENT",
                "providerStatus": "HTTP_404_ABSENT",
                "receiptSha256": "a" * 64,
            },
            "recentResponses": [],
            "lastProvenAt": "2026-08-27T03:17:40Z",
            "expiryHours": 24,
        },
        "authority": {
            "required": ["OWNER_OAUTH_READ_ONLY"],
            "current": ["OWNER_OAUTH_READ_ONLY"],
            "checkedAt": "2026-08-27T03:17:40Z",
        },
        "artifact": {
            "retrievable": True,
            "declaredHash": "a" * 64,
            "calculatedHash": "a" * 64,
        },
        "lineage": {"sourceHash": "a" * 64},
        "rollback": {"symbolic": False, "revision": None, "imageDigest": None, "viable": None},
        "counterfactual": {"expectedChanges": [], "observedChanges": []},
    }
    source_objects = {
        "SRC:BOUNDED-CLAIM-20260827": bounded,
        "SRC:CENSUS-MANIFEST-20260827": manifest,
        "SRC:DRIFT-READBACK-20260827": drift,
        "SRC:TOTALITY-GATE-20260827": totality,
    }
    preliminary_payloads = {
        source_id: canonical_json(payload) for source_id, payload in source_objects.items()
    }
    formation_packet = {
        "mission": {
            "id": value["body"]["mission_id"],
            "version": 2,
            "stopRequested": False,
            "constraints": {
                "authorizedClasses": ["A0"],
                "maximumCost": 0,
                "zeroNewRecurringCost": True,
                "maximumUserBurden": 0,
                "manualUserTasksAllowed": False,
                "externalWritesAllowed": False,
                "externalCommunicationsAllowed": False,
            },
        },
        "proposedAction": {
            "missionId": value["body"]["mission_id"],
            "missionVersion": 2,
            "authorityClass": "A0",
            "estimatedCost": 0,
            "recurringCost": 0,
            "estimatedUserBurden": 0,
            "manualUserTasks": [],
            "avoidableUserOrchestration": False,
            "reversible": True,
        },
        "pendingActions": [],
    }
    foresight_plan = {
        "activationMode": "FULL",
        "authorityExpansion": False,
        "fanInCount": 1,
        "horizons": [{"horizon": index} for index in range(1, 51)],
        "lanes": ["PRIMARY_EXECUTOR", "TWIN_FORESIGHT_VERIFIER"],
        "mission": {"id": value["body"]["mission_id"], "version": 2},
        "runtimeState": "ON_DEMAND_GOVERNED",
        "stopState": "ACTIVE",
        "visibleLedgerRequired": True,
    }
    supporting_payloads = {
        "formation_packet": canonical_json(formation_packet),
        "foresight_plan": canonical_json(foresight_plan),
    }
    oifa = {
        "mission_id": value["body"]["mission_id"],
        "input_hashes": {
            "formation_packet": hashlib.sha256(
                supporting_payloads["formation_packet"].encode("utf-8")
            ).hexdigest(),
            "foresight_plan": hashlib.sha256(
                supporting_payloads["foresight_plan"].encode("utf-8")
            ).hexdigest(),
            "drift_packet": hashlib.sha256(
                preliminary_payloads["SRC:DRIFT-READBACK-20260827"].encode("utf-8")
            ).hexdigest(),
            "totality_packet": hashlib.sha256(
                preliminary_payloads["SRC:TOTALITY-GATE-20260827"].encode("utf-8")
            ).hexdigest(),
            "bounded_packet": hashlib.sha256(
                preliminary_payloads["SRC:BOUNDED-CLAIM-20260827"].encode("utf-8")
            ).hexdigest(),
            "evidence_manifest": hashlib.sha256(
                preliminary_payloads["SRC:CENSUS-MANIFEST-20260827"].encode("utf-8")
            ).hexdigest(),
        },
        "overall_fidelity_status": "PARTIAL",
        "owner_instruction_coverage": [{
            "instruction": "Know what is all there",
            "source": "Synthetic test objective",
            "state": "CONFLICT_ESCALATED",
        }],
        "cadence_due": False,
        "material_gaps": ["At least one bounded surface remains open."],
        "contradictions": ["Totality conflicts with the named open boundary."],
        "hard_gates": [
            "No universal claim",
            "No Gemini claim",
            "No WIF claim",
            "No mutation",
        ],
        "recommended_handoff": "Maintain an immutable delta register for bounded evidence.",
        "release_authority": "NONE",
    }
    for field in (
        "owner_objective_test", "two_product_test", "assessor_centrality_test",
        "narrative_test", "applicant_theory_test", "proof_discipline_test",
        "relevance_test", "continuity_test", "cadence_test", "lawful_route_test",
        "sovereignty_test",
    ):
        oifa[field] = {"status": "VERIFIED", "basis": "Synthetic bounded proof."}
    oifa["continuity_test"] = {
        "status": "VERIFIED", "basis": "Synthetic baseline retained."
    }
    oifa["replacement_completeness_test"] = {
        "status": "PARTIAL", "basis": "An inaccessible surface remains open."
    }
    source_objects["SRC:OIFA-FIDELITY-20260827"] = oifa
    source_payloads = SourcePayloadBundle(
        {
            source_id: canonical_json(payload)
            for source_id, payload in source_objects.items()
        },
        supporting_payloads,
    )
    source_classes = {
        "SRC:BOUNDED-CLAIM-20260827": "BOUNDED_CLAIM_GATE",
        "SRC:CENSUS-MANIFEST-20260827": "DERIVED_CENSUS_MANIFEST",
        "SRC:DRIFT-READBACK-20260827": "DRIFT_READBACK",
        "SRC:OIFA-FIDELITY-20260827": "FIDELITY_REPORT",
        "SRC:TOTALITY-GATE-20260827": "TOTALITY_REJECTION_GATE",
    }
    value["body"]["inputs"] = [
        {
            "source_id": source_id,
            "source_class": source_classes[source_id],
            "observed_at": value["body"]["observed_at"],
            "content_sha256": hashlib.sha256(source_payloads[source_id].encode("utf-8")).hexdigest(),
            "locator_state": "SESSION_ARTIFACT_NOT_PUBLISHED",
            "proof_state": "DERIVED_VERIFIED",
        }
        for source_id in sorted(source_payloads)
    ]
    rehash(value)
    return value, manifest, bounded, source_payloads


class EstateDeltaTransactionTests(unittest.TestCase):
    def test_valid_bounded_genesis_transaction(self):
        result = validate_transaction(candidate())
        self.assertEqual("VALID_STRUCTURAL_BOUNDED_TRANSACTION", result["state"])
        self.assertEqual(3, result["surface_count"])

    def test_candidate_is_deterministic(self):
        self.assertEqual(candidate()["integrity"], candidate()["integrity"])

    def test_tamper_is_rejected(self):
        value = candidate()
        value["body"]["surface_snapshots"][1]["state"] = "VERIFIED"
        with self.assertRaisesRegex(EstateDeltaError, "body SHA-256 mismatch"):
            validate_transaction(value)

    def test_secret_shaped_value_is_rejected(self):
        value = candidate()
        value["body"]["scope"]["claim_text"] = "sk-proj-" + "A" * 30
        with self.assertRaisesRegex(EstateDeltaError, "secret-shaped"):
            validate_transaction(value)

    def test_private_locator_field_is_rejected(self):
        value = candidate()
        value["body"]["inputs"][0]["private_locator"] = "opaque"
        with self.assertRaisesRegex(EstateDeltaError, "private or secret field"):
            validate_transaction(value)

    def test_totality_promotion_is_rejected(self):
        value = candidate()
        value["body"]["scope"]["totality_claimed"] = True
        body_hash = canonical_sha256(value["body"])
        value["integrity"]["body_sha256"] = body_hash
        value["integrity"]["event_hash"] = canonical_sha256({"body": value["body"], "body_hash": body_hash, "previous_event_hash": None})
        with self.assertRaisesRegex(EstateDeltaError, "cannot claim totality"):
            validate_transaction(value)

    def test_latest_provider_native_readback_wins(self):
        value = candidate()
        value["body"]["surface_snapshots"].append({
            "snapshot_id": "SNAP:WIF-HISTORICAL-001",
            "subject_id": "PROVIDER:GOOGLE-WIF",
            "surface": "CLOUD_CONTROL",
            "evidence_class": "HISTORICAL_CLAIM",
            "observed_at": "2026-08-27T03:17:38Z",
            "proof_state": "HISTORICAL_UNRESOLVED",
            "state": "VERIFIED",
            "input_source_ids": ["SRC:CENSUS-MANIFEST-20260827"],
            "metrics": [],
            "boundary_ids": [],
        })
        value["body"]["surface_snapshots"].sort(key=lambda row: row["snapshot_id"])
        body_hash = canonical_sha256(value["body"])
        value["integrity"]["body_sha256"] = body_hash
        value["integrity"]["event_hash"] = canonical_sha256({"body": value["body"], "body_hash": body_hash, "previous_event_hash": None})
        self.assertEqual("VALID_STRUCTURAL_BOUNDED_TRANSACTION", validate_transaction(value)["state"])

    def test_missing_provider_hold_is_rejected(self):
        value = candidate()
        value["body"]["projections"][0]["hold"] = False
        body_hash = canonical_sha256(value["body"])
        value["integrity"]["body_sha256"] = body_hash
        value["integrity"]["event_hash"] = canonical_sha256({"body": value["body"], "body_hash": body_hash, "previous_event_hash": None})
        with self.assertRaisesRegex(EstateDeltaError, "must hold"):
            validate_transaction(value)

    def test_unresolved_boundary_count_must_match(self):
        value = candidate()
        value["body"]["completion"]["unresolved_boundary_count"] = 1
        body_hash = canonical_sha256(value["body"])
        value["integrity"]["body_sha256"] = body_hash
        value["integrity"]["event_hash"] = canonical_sha256({"body": value["body"], "body_hash": body_hash, "previous_event_hash": None})
        with self.assertRaisesRegex(EstateDeltaError, "boundary count mismatch"):
            validate_transaction(value)

    def test_genesis_chain_verifies(self):
        result = verify_chain([candidate()])
        self.assertEqual("VALID_STRUCTURAL_CHAIN", result["state"])
        self.assertEqual(1, result["transaction_count"])

    def test_public_pointer_remains_prepared_without_runtime_receipt(self):
        root = Path(__file__).resolve().parents[1]
        pointer = json.loads(
            (root / "governance/federation_estate_delta_register_public_v1.json").read_text(encoding="utf-8")
        )
        result = validate_public_pointer(pointer)
        self.assertEqual("PREPARED_EXTERNAL_PUBLICATION_PENDING", result["publication_state"])

    def test_canonical_public_pointer_rejects_any_runtime_receipt(self):
        root = Path(__file__).resolve().parents[1]
        pointer = json.loads(
            (root / "governance/federation_estate_delta_register_public_v1.json").read_text(
                encoding="utf-8"
            )
        )
        pointer["current_transaction"] = {
            "transaction_id": "FEDERATION-ESTATE-CENSUS-20260827-001",
            "sequence": 1,
            "observed_at": "2026-08-27T03:18:40Z",
            "canonical_status": "PARTIAL_PROVEN",
            "event_hash": "a" * 64,
            "availability": "APPROVED_EXTERNAL_IMMUTABLE_EVIDENCE_PLANE",
        }
        pointer["publication_state"] = "PUBLISHED"
        with self.assertRaisesRegex(EstateDeltaError, "alias-only"):
            validate_public_pointer(pointer)

    def test_json_schema_declares_closed_world_root(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "federation_consolidation/data/estate_delta_transaction_v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(["body", "integrity"], schema["required"])

    def test_source_route_catalog_is_valid_but_runtime_unverified(self):
        result = validate_route_catalog(route_catalog())
        self.assertEqual("VALID_SOURCE_ROUTE_CATALOG_RUNTIME_UNVERIFIED", result["state"])
        self.assertEqual(2, result["route_count"])

    def test_registry_collision_and_discovery_adapter_are_exactly_bound(self):
        value = route_catalog()
        value["registry_collision_note"] = "x"
        with self.assertRaisesRegex(EstateDeltaError, "note is not contract-bound"):
            validate_route_catalog(value)

        value = route_catalog()
        value["registry_collision_build"]["build_id"] = "AO-CRA-UNRELATED-001"
        with self.assertRaisesRegex(EstateDeltaError, "AO-CRA build contract differs"):
            validate_route_catalog(value)

        value = route_catalog()
        value["route_discovery_adapter"]["discovery_order"] = [
            "source", "capabilities", "commands", "receipts"
        ]
        with self.assertRaisesRegex(EstateDeltaError, "adapter boundary mismatch"):
            validate_route_catalog(value)

    def test_exact_federation_census_intent_selects_a0_route(self):
        result = select_observation_route("  Federation   Census ", route_catalog())
        self.assertEqual("FEDERATION_CENSUS_A0", result["route_id"])
        self.assertEqual("SOURCE_ROUTE_SELECTED_RUNTIME_UNVERIFIED", result["state"])
        self.assertFalse(result["provider_execution_inherited"])

    def test_exact_provider_observation_intent_selects_a0_route(self):
        result = select_observation_route("provider observation", route_catalog())
        self.assertEqual("PROVIDER_OBSERVATION_A0", result["route_id"])
        self.assertEqual("provider-observation", result["capability"])

    def test_unknown_intent_fails_closed(self):
        with self.assertRaisesRegex(EstateDeltaError, "NO_SOURCE_ROUTE"):
            select_observation_route("deploy gemini", route_catalog())

    def test_duplicate_intent_is_rejected_as_ambiguous(self):
        value = route_catalog()
        value["routes"][1]["intents"].append("federation census")
        value["routes"][1]["intents"].sort()
        with self.assertRaisesRegex(EstateDeltaError, "AMBIGUOUS_SOURCE_ROUTE"):
            validate_route_catalog(value)

    def test_effectful_route_escalation_is_rejected(self):
        value = route_catalog()
        value["routes"][0]["effectful"] = True
        with self.assertRaisesRegex(EstateDeltaError, "non-effectful"):
            validate_route_catalog(value)

    def test_runtime_activation_claim_is_rejected(self):
        value = route_catalog()
        value["routes"][0]["activation_state"] = "ACTIVE"
        with self.assertRaisesRegex(EstateDeltaError, "cannot claim runtime"):
            validate_route_catalog(value)

    def test_provider_native_readback_cannot_be_unverified_runtime_claim(self):
        value = candidate()
        value["body"]["surface_snapshots"][1]["proof_state"] = "UNVERIFIED"
        value["body"]["surface_snapshots"][1]["state"] = "RUNTIME_ACTIVE"
        value["body"]["projections"][1]["proof_state"] = "UNVERIFIED"
        value["body"]["projections"][1]["state"] = "RUNTIME_ACTIVE"
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "incompatible with evidence class"):
            validate_transaction(value)

    def test_future_surface_observation_is_rejected(self):
        value = candidate()
        value["body"]["surface_snapshots"][1]["observed_at"] = "2099-01-01T00:00:00Z"
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "cannot postdate"):
            validate_transaction(value)

    def test_input_enum_drift_is_rejected(self):
        value = candidate()
        value["body"]["inputs"][0]["source_class"] = "RUNTIME_RECEIPT"
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "source class"):
            validate_transaction(value)

    def test_timestamp_requires_seconds(self):
        value = candidate()
        value["body"]["observed_at"] = "2026-08-27T03:18Z"
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "with seconds"):
            validate_transaction(value)

    def test_non_finite_canonical_json_is_rejected(self):
        with self.assertRaises(ValueError):
            canonical_sha256({"metric": float("nan")})

    def test_boolean_sequence_is_rejected(self):
        value = candidate()
        value["body"]["sequence"] = True
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "positive integer"):
            validate_transaction(value)

    def test_boolean_zero_effect_count_is_rejected(self):
        value = candidate()
        value["body"]["effects"]["mutation_count"] = False
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "exactly zero"):
            validate_transaction(value)

    def test_empty_chain_is_not_valid(self):
        with self.assertRaisesRegex(EstateDeltaError, "empty transaction chain"):
            verify_chain([])

    def test_fake_lineage_parent_is_rejected(self):
        first = candidate()
        second = deepcopy(first)
        second["body"]["sequence"] = 2
        second["body"]["transaction_id"] = "FEDERATION-ESTATE-DELTA-20260827-002"
        second["body"]["event_type"] = "CENSUS_DELTA"
        second["body"]["lineage"]["previous_transaction_id"] = "FEDERATION-ESTATE-CENSUS-19990101-999"
        second["integrity"]["previous_event_hash"] = first["integrity"]["event_hash"]
        rehash(second)
        with self.assertRaisesRegex(EstateDeltaError, "transaction ID lineage"):
            verify_chain([first, second])

    def test_public_pointer_paths_and_rules_are_contract_bound(self):
        root = Path(__file__).resolve().parents[1]
        pointer = json.loads(
            (root / "governance/federation_estate_delta_register_public_v1.json").read_text(encoding="utf-8")
        )
        pointer["transaction_contract_path"] = "wrong/schema.json"
        with self.assertRaisesRegex(EstateDeltaError, "contract path"):
            validate_public_pointer(pointer)
        pointer = json.loads(
            (root / "governance/federation_estate_delta_register_public_v1.json").read_text(encoding="utf-8")
        )
        pointer["rules"]["append_only"] = False
        with self.assertRaisesRegex(EstateDeltaError, "rules mismatch"):
            validate_public_pointer(pointer)

    def test_public_pointer_private_drive_url_is_rejected(self):
        root = Path(__file__).resolve().parents[1]
        pointer = json.loads(
            (root / "governance/federation_estate_delta_register_public_v1.json").read_text(encoding="utf-8")
        )
        pointer["private_artifact_alias"] = "https://drive.google.com/file/d/" + "A" * 30
        with self.assertRaisesRegex(EstateDeltaError, "secret-shaped|alias mismatch"):
            validate_public_pointer(pointer)

    def test_query_style_private_drive_urls_are_rejected(self):
        for url in (
            "https://drive.google.com/open?id=" + "A" * 30,
            "https://drive.google.com/uc?id=" + "B" * 30,
            "https://docs.google.com/open?id=" + "C" * 30,
            "https://drive.google.com/open?fileId=" + "D" * 30,
            "https://drive.usercontent.google.com/download?id=" + "E" * 30,
            "https://drive.google.com/open%3Fid%3D" + "F" * 30,
        ):
            with self.subTest(url=url):
                value = candidate()
                value["body"]["scope"]["claim_text"] = url
                rehash(value)
                with self.assertRaisesRegex(EstateDeltaError, "secret-shaped"):
                    validate_transaction(value)

    def test_route_capability_action_and_readbacks_are_contract_bound(self):
        value = route_catalog()
        value["routes"][0]["capability"] = "provider-deployment"
        with self.assertRaisesRegex(EstateDeltaError, "capability is not contract-bound"):
            validate_route_catalog(value)
        value = route_catalog()
        value["routes"][0]["proof_action_id"] = "UNRELATED-ACTION"
        with self.assertRaisesRegex(EstateDeltaError, "proof action is not contract-bound"):
            validate_route_catalog(value)
        value = route_catalog()
        value["routes"][0]["required_readbacks"] = []
        with self.assertRaisesRegex(EstateDeltaError, "readbacks are not contract-bound"):
            validate_route_catalog(value)

    def test_structural_validator_does_not_infer_external_source_coverage(self):
        value = candidate()
        value["body"]["scope"]["expected_sources"] = ["Invented complete estate"]
        value["body"]["scope"]["inspected_to_end"] = ["Invented complete estate"]
        rehash(value)
        self.assertEqual(
            "VALID_STRUCTURAL_BOUNDED_TRANSACTION",
            validate_transaction(value)["state"],
        )

    def test_structural_validator_does_not_infer_manifest_subject_coverage(self):
        value = candidate()
        value["body"]["surface_snapshots"] = [
            row for row in value["body"]["surface_snapshots"]
            if row["subject_id"] != "SURFACE:CLOUD-OPERATOR"
        ]
        value["body"]["projections"] = [
            row for row in value["body"]["projections"]
            if row["subject_id"] != "SURFACE:CLOUD-OPERATOR"
        ]
        value["body"]["scope"]["expected_sources"] = [
            "ARCHITRON and CloudOps inspected ranges",
            "public Federation operator health and contract",
        ]
        value["body"]["scope"]["inspected_to_end"] = list(
            value["body"]["scope"]["expected_sources"]
        )
        rehash(value)
        self.assertEqual(
            "VALID_STRUCTURAL_BOUNDED_TRANSACTION",
            validate_transaction(value)["state"],
        )

    def test_schema_and_validator_contracts_are_aligned(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "federation_consolidation/data/estate_delta_transaction_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("SCHEMA_VALIDATOR_ALIGNED", validate_schema_alignment(schema)["state"])

    def test_any_schema_semantic_drift_breaks_alignment(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "federation_consolidation/data/estate_delta_transaction_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        schema["$defs"]["contradiction"]["properties"]["disposition"]["enum"].append("DISCARDED")
        with self.assertRaisesRegex(EstateDeltaError, "canonical digest drifted"):
            validate_schema_alignment(schema)

    def test_manifest_fidelity_rejects_rehashed_wrong_count(self):
        value, manifest, bounded, source_payloads = github_fidelity_candidate()
        self.assertEqual(
            "VALID_GENESIS_PROJECTION_FIDELITY_AND_SOURCE_BUNDLE",
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )["state"],
        )
        value["body"]["surface_snapshots"][0]["metrics"][1]["value"] = 999999
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "differs from manifest"):
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )

    def test_manifest_fidelity_uses_projection_winner_not_last_snapshot(self):
        value, manifest, bounded, source_payloads = github_fidelity_candidate()
        value["body"]["surface_snapshots"][0]["metrics"][1]["value"] = 999999
        historical = deepcopy(value["body"]["surface_snapshots"][0])
        historical["snapshot_id"] = "SNAP:GITHUB-HISTORICAL-002"
        historical["evidence_class"] = "HISTORICAL_CLAIM"
        historical["proof_state"] = "HISTORICAL_UNRESOLVED"
        historical["state"] = "HISTORICAL_BASELINE"
        historical["metrics"][1]["value"] = 2680
        value["body"]["surface_snapshots"].append(historical)
        value["body"]["surface_snapshots"].sort(key=lambda row: row["snapshot_id"])
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "exactly one snapshot per subject"):
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )

    def test_manifest_fidelity_binds_state_proof_hold_and_truth(self):
        mutations = (
            ("state", lambda value: (
                value["body"]["surface_snapshots"][0].__setitem__("state", "RUNTIME_ACTIVE"),
                value["body"]["projections"][0].__setitem__("state", "RUNTIME_ACTIVE"),
            ), "state/proof/hold"),
            ("hold", lambda value: value["body"]["projections"][0].__setitem__("hold", False),
             "state/proof/hold"),
            ("claim", lambda value: value["body"]["scope"].__setitem__(
                "claim_text", "Complete proof of every estate and provider."
            ), "canonical bounded claim"),
            ("truth", lambda value: value["body"]["completion"].__setitem__(
                "truth_boundary", "All provider execution is proven."
            ), "canonically bounded"),
        )
        for label, mutate, error in mutations:
            with self.subTest(label=label):
                value, manifest, bounded, source_payloads = github_fidelity_candidate()
                mutate(value)
                rehash(value)
                with self.assertRaisesRegex(EstateDeltaError, error):
                    validate_genesis_transaction_against_manifest(
                        value, manifest, bounded, source_payloads
                    )

    def test_manifest_fidelity_binds_winner_topology_and_freshness(self):
        mutations = (
            ("surface", lambda value: value["body"]["surface_snapshots"][0].__setitem__(
                "surface", "CANVA"
            ), "surface differs"),
            ("stale", lambda value: value["body"]["surface_snapshots"][0].__setitem__(
                "observed_at", "2026-08-27T03:17:40Z"
            ), "observation is stale"),
            ("input", lambda value: value["body"]["inputs"][0].__setitem__(
                "source_class", "DRIFT_READBACK"
            ), "input metadata differs"),
            ("boundary", lambda value: value["body"]["surface_snapshots"][0].__setitem__(
                "boundary_ids", []
            ), "boundary assignment differs"),
        )
        for label, mutate, error in mutations:
            with self.subTest(label=label):
                value, manifest, bounded, source_payloads = github_fidelity_candidate()
                mutate(value)
                rehash(value)
                with self.assertRaisesRegex(EstateDeltaError, error):
                    validate_genesis_transaction_against_manifest(
                        value, manifest, bounded, source_payloads
                    )

    def test_manifest_fidelity_binds_complete_census_genesis_envelope(self):
        def add_unexpected_contradiction(value: dict) -> None:
            value["body"]["contradictions"] = [{
                "contradiction_id": "CONTRADICTION:GITHUB-STATUS",
                "subject_id": "SURFACE:GITHUB",
                "earlier_claim": "Historical source claimed complete provider admission.",
                "current_snapshot_id": "SNAP:GITHUB-001",
                "disposition": "SUPERSEDED_RETAINED",
                "affects_totality": True,
            }]

        def swap_boundary_descriptions(value: dict) -> None:
            boundaries = value["body"]["unresolved_boundaries"]
            boundaries[0]["description"], boundaries[1]["description"] = (
                boundaries[1]["description"], boundaries[0]["description"]
            )

        mutations = (
            ("transaction", lambda value: value["body"].__setitem__(
                "transaction_id", "FEDERATION-ESTATE-CENSUS-20260827-002"
            ), "identity differs"),
            ("event", lambda value: value["body"].__setitem__(
                "event_type", "CORRECTION"
            ), "identity differs"),
            ("lineage_removed", lambda value: value["body"]["lineage"].__setitem__(
                "historical_baselines", []
            ), "requires retained historical lineage"),
            ("contradiction", add_unexpected_contradiction,
             "canonical public-safe template"),
            ("boundary_closure", lambda value: value["body"]
                ["unresolved_boundaries"][0].__setitem__(
                    "closure_evidence", "Someone should check later."
                ), "boundary records differ"),
            ("boundary_identity", swap_boundary_descriptions,
             "boundary records differ"),
        )
        for label, mutate, error in mutations:
            with self.subTest(label=label):
                value, manifest, bounded, source_payloads = github_fidelity_candidate()
                mutate(value)
                rehash(value)
                with self.assertRaisesRegex(EstateDeltaError, error):
                    validate_genesis_transaction_against_manifest(
                        value, manifest, bounded, source_payloads
                    )

    def test_manifest_fidelity_binds_complete_input_contract(self):
        mutations = (
            ("removed", lambda value: value["body"]["inputs"].pop(0),
             "inputs differ"),
            ("locator", lambda value: value["body"]["inputs"][0].__setitem__(
                "locator_state", "BUNDLED_IMMUTABLE"
            ), "input metadata differs"),
            ("proof", lambda value: value["body"]["inputs"][0].__setitem__(
                "proof_state", "HISTORICAL_UNRESOLVED"
            ), "input metadata differs"),
            ("stale", lambda value: value["body"]["inputs"][0].__setitem__(
                "observed_at", "2026-08-27T03:17:40Z"
            ), "input metadata differs"),
        )
        for label, mutate, error in mutations:
            with self.subTest(label=label):
                value, manifest, bounded, source_payloads = github_fidelity_candidate()
                mutate(value)
                rehash(value)
                with self.assertRaisesRegex(EstateDeltaError, error):
                    validate_genesis_transaction_against_manifest(
                        value, manifest, bounded, source_payloads
                    )

    def test_manifest_fidelity_binds_supplied_objects_to_source_bytes(self):
        value, manifest, bounded, source_payloads = github_fidelity_candidate()
        manifest["surfaces"]["github"]["treeItems"] = 999999
        value["body"]["surface_snapshots"][0]["metrics"][1]["value"] = 999999
        rehash(value)
        with self.assertRaisesRegex(
            EstateDeltaError, "manifest object differs from hashed source payload"
        ):
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )

    def test_manifest_fidelity_rejects_changed_source_bytes(self):
        value, manifest, bounded, source_payloads = github_fidelity_candidate()
        source_payloads["SRC:CENSUS-MANIFEST-20260827"] += "\n"
        with self.assertRaisesRegex(EstateDeltaError, "source payload hash mismatch"):
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )

    def test_manifest_fidelity_binds_formation_and_foresight_support_bytes(self):
        for role in ("formation_packet", "foresight_plan"):
            with self.subTest(role=role):
                value, manifest, bounded, source_payloads = github_fidelity_candidate()
                source_payloads.supporting_payloads[role] += "\n"
                with self.assertRaisesRegex(EstateDeltaError, "supporting payload hash differs"):
                    validate_genesis_transaction_against_manifest(
                        value, manifest, bounded, source_payloads
                    )

    def test_manifest_fidelity_rejects_semantically_substituted_sources(self):
        for source_id in (
            "SRC:DRIFT-READBACK-20260827",
            "SRC:OIFA-FIDELITY-20260827",
            "SRC:TOTALITY-GATE-20260827",
        ):
            with self.subTest(source_id=source_id):
                value, manifest, bounded, source_payloads = github_fidelity_candidate()
                source_payloads[source_id] = "{}\n"
                input_row = next(
                    row for row in value["body"]["inputs"] if row["source_id"] == source_id
                )
                input_row["content_sha256"] = hashlib.sha256(b"{}\n").hexdigest()
                rehash(value)
                with self.assertRaisesRegex(
                    EstateDeltaError,
                    "drift readback|OIFA fidelity report|totality rejection gate",
                ):
                    validate_genesis_transaction_against_manifest(
                        value, manifest, bounded, source_payloads
                    )

    def test_manifest_fidelity_rejects_swapped_source_roles(self):
        value, manifest, bounded, source_payloads = github_fidelity_candidate()
        oifa_id = "SRC:OIFA-FIDELITY-20260827"
        totality_id = "SRC:TOTALITY-GATE-20260827"
        source_payloads[oifa_id], source_payloads[totality_id] = (
            source_payloads[totality_id], source_payloads[oifa_id]
        )
        for source_id in (oifa_id, totality_id):
            input_row = next(
                row for row in value["body"]["inputs"] if row["source_id"] == source_id
            )
            input_row["content_sha256"] = hashlib.sha256(
                source_payloads[source_id].encode("utf-8")
            ).hexdigest()
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "totality rejection gate"):
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )

    def test_manifest_fidelity_rejects_known_short_private_source_identifier(self):
        for transform in (
            lambda private: private,
            lambda private: "PUBLIC-" + private,
            lambda private: "%53" + private[1:],
            lambda private: base64.urlsafe_b64encode(private.encode("utf-8")).decode("ascii"),
            lambda private: base64.b32encode(private.encode("utf-8")).decode("ascii"),
            lambda private: base64.b85encode(private.encode("utf-8")).decode("ascii"),
            lambda private: base64.a85encode(private.encode("utf-8")).decode("ascii"),
            lambda private: private.encode("utf-8").hex(),
            lambda private: codecs.encode(private, "rot_13"),
            lambda private: private[::-1],
        ):
            with self.subTest(transform=transform):
                value, manifest, bounded, source_payloads = github_fidelity_candidate()
                drift_id = "SRC:DRIFT-READBACK-20260827"
                manifest_id = "SRC:CENSUS-MANIFEST-20260827"
                oifa_id = "SRC:OIFA-FIDELITY-20260827"
                drift = json.loads(source_payloads[drift_id])
                projected_alias = transform(drift["queue"]["configuredId"])
                manifest["surfaces"]["github"]["providerAdmission"]["reason"] = projected_alias
                value["body"]["surface_snapshots"][0]["metrics"].append({
                    "name": "PROVIDER_ADMISSION_REASON", "value": projected_alias,
                })
                value["body"]["surface_snapshots"][0]["metrics"].sort(
                    key=lambda row: row["name"]
                )
                source_payloads[manifest_id] = canonical_json(manifest)
                oifa = json.loads(source_payloads[oifa_id])
                oifa["input_hashes"]["evidence_manifest"] = hashlib.sha256(
                    source_payloads[manifest_id].encode("utf-8")
                ).hexdigest()
                source_payloads[oifa_id] = canonical_json(oifa)
                for source_id in (manifest_id, oifa_id):
                    input_row = next(
                        row for row in value["body"]["inputs"] if row["source_id"] == source_id
                    )
                    input_row["content_sha256"] = hashlib.sha256(
                        source_payloads[source_id].encode("utf-8")
                    ).hexdigest()
                rehash(value)
                with self.assertRaisesRegex(
                    EstateDeltaError,
                    "known private source identifier|opaque private identifier|string metric",
                ):
                    validate_genesis_transaction_against_manifest(
                        value, manifest, bounded, source_payloads
                    )

    def test_manifest_fidelity_rejects_base85_private_value_in_contradiction_prose(self):
        value, manifest, bounded, source_payloads = github_fidelity_candidate()
        drift_id = "SRC:DRIFT-READBACK-20260827"
        oifa_id = "SRC:OIFA-FIDELITY-20260827"
        private_alias = json.loads(source_payloads[drift_id])["queue"]["configuredId"]
        encoded_alias = base64.b85encode(private_alias.encode("utf-8")).decode("ascii")
        value["body"]["contradictions"] = [{
            "contradiction_id": "CONTRADICTION:GITHUB-STATUS",
            "subject_id": "SURFACE:GITHUB",
            "earlier_claim": f"Historical GitHub claim retained {encoded_alias}",
            "current_snapshot_id": "SNAP:GITHUB-001",
            "disposition": "SUPERSEDED_RETAINED",
            "affects_totality": True,
        }]
        oifa = json.loads(source_payloads[oifa_id])
        oifa["contradictions"].append("GitHub historical status conflicts with current evidence.")
        source_payloads[oifa_id] = canonical_json(oifa)
        oifa_input = next(
            row for row in value["body"]["inputs"] if row["source_id"] == oifa_id
        )
        oifa_input["content_sha256"] = hashlib.sha256(
            source_payloads[oifa_id].encode("utf-8")
        ).hexdigest()
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "canonical public-safe template"):
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )

    def test_manifest_fidelity_rejects_extra_nonwinning_snapshot(self):
        value, manifest, bounded, source_payloads = github_fidelity_candidate()
        extra = deepcopy(value["body"]["surface_snapshots"][0])
        extra["snapshot_id"] = "SNAP:GITHUB-000"
        extra["state"] = "RUNTIME_ACTIVE"
        value["body"]["surface_snapshots"].append(extra)
        value["body"]["surface_snapshots"].sort(key=lambda row: row["snapshot_id"])
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "exactly one snapshot per subject"):
            validate_genesis_transaction_against_manifest(
                value, manifest, bounded, source_payloads
            )

    def test_encoded_private_locators_and_opaque_ids_are_rejected(self):
        unsafe_values = (
            "https%253A%252F%252Fdrive.google.com%252Fopen%253Fid%253D" + "A" * 30,
            "https://www.googleapis.com/drive/v3/files/" + "B" * 30,
            "opaque-provider-reference-" + "C" * 40,
        )
        for unsafe in unsafe_values:
            with self.subTest(unsafe=unsafe):
                value, _, _, _ = github_fidelity_candidate()
                value["body"]["unresolved_boundaries"][0]["closure_evidence"] = unsafe
                rehash(value)
                with self.assertRaisesRegex(
                    EstateDeltaError,
                    "secret-shaped|private provider locator|opaque private identifier",
                ):
                    validate_transaction(value)

        value, _, _, _ = github_fidelity_candidate()
        value["body"]["surface_snapshots"][0]["metrics"][1]["value"] = "D" * 38
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "opaque private identifier"):
            validate_transaction(value)

    def test_identifier_fields_reject_numeric_schema_drift(self):
        cases = []
        mission = candidate()
        mission["body"]["mission_id"] = 123
        cases.append(("mission", mission, "mission ID"))

        snapshot = candidate()
        snapshot["body"]["surface_snapshots"][0]["snapshot_id"] = 123
        snapshot["body"]["projections"][0]["winning_snapshot_id"] = 123
        cases.append(("snapshot", snapshot, "surface_snapshots.snapshot_id"))

        baseline = candidate()
        baseline["body"]["lineage"]["historical_baselines"] = [{
            "baseline_id": 123,
            "claimed_sha256": "2" * 64,
            "verification_state": "HISTORICAL_REFERENCE_UNRESOLVED",
            "chain_parent": False,
        }]
        cases.append(("baseline", baseline, "baseline identity"))

        for label, value, error in cases:
            with self.subTest(label=label):
                rehash(value)
                with self.assertRaisesRegex(EstateDeltaError, error):
                    validate_transaction(value)

    def test_opaque_sha_shaped_source_identifier_is_outside_public_alias_namespace(self):
        value = candidate()
        opaque_source_id = "A" * 40
        value["body"]["inputs"][0]["source_id"] = opaque_source_id
        for snapshot in value["body"]["surface_snapshots"]:
            snapshot["input_source_ids"] = [opaque_source_id]
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "input source ID.*public alias namespace"):
            validate_transaction(value)

    def test_non_genesis_lineage_parent_must_be_transaction_id_text(self):
        value = candidate()
        value["body"]["sequence"] = 2
        value["body"]["transaction_id"] = "FEDERATION-ESTATE-DELTA-20260827-002"
        value["body"]["event_type"] = "CENSUS_DELTA"
        value["body"]["lineage"]["previous_transaction_id"] = 42
        value["integrity"]["previous_event_hash"] = "3" * 64
        rehash(value)
        with self.assertRaisesRegex(EstateDeltaError, "valid previous transaction ID"):
            validate_transaction(value)


if __name__ == "__main__":
    unittest.main()
