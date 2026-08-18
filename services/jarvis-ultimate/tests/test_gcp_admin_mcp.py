import copy
import unittest

from jarvis.gcp_admin_mcp import (
    AdapterState,
    CONTRACT,
    EvidenceEnvelope,
    ProviderRouteDisabled,
    TOOL_SPECS,
    capability_snapshot,
    health_is_deployment_proof,
    invoke,
    plan,
    readiness,
    semantic_sha256,
    validate_global_wif_receipt,
    validate_lineage_attestation,
    validate_mcp_wif_receipt,
    validate_tool_arguments,
)


NOW = 1_800_000_000.0


def evidence(payload, ref="provider:receipt", observed_at=NOW - 10):
    return EvidenceEnvelope(payload=payload, observed_at=observed_at, proof_ref=ref)


def global_wif_receipt():
    payload = dict(CONTRACT["proofGates"]["globalWifReceipt"]["exact"])
    for key in CONTRACT["proofGates"]["globalWifReceipt"]["requiredTrue"]:
        payload[key] = True
    for key in CONTRACT["proofGates"]["globalWifReceipt"]["requiredEmptyArrays"]:
        payload[key] = []
    return payload


def mcp_wif_receipt():
    payload = dict(CONTRACT["proofGates"]["mcpWifReceipt"]["exact"])
    payload["evidenceHashes"] = {
        key: semantic_sha256({"evidence": key})
        for key in CONTRACT["proofGates"]["mcpWifReceipt"]["evidenceHashKeys"]
    }
    return payload


def join(mode="SERVING", revision="federation-omega-gcp-admin-mcp-b123"):
    source = {"resolvedRepoSource": {"commitSha": "a" * 40}}
    source_verification = {"repository": "mosianekk-lang/Federation-Omega", "commitSha": "a" * 40}
    digest = "sha256:" + "b" * 64
    return {
        "attestationMode": mode,
        "projectId": "sov-hybrid-suite",
        "projectNumber": "257649435135",
        "region": "africa-south1",
        "service": "federation-omega-gcp-admin-mcp",
        "revision": revision,
        "imageDigest": digest,
        "artifactUri": f"africa-south1-docker.pkg.dev/sov-hybrid-suite/federation-omega/federation-omega-gcp-admin-mcp@{digest}",
        "buildId": "build-123",
        "buildStatus": "SUCCESS",
        "source": source,
        "sourceHash": semantic_sha256(source),
        "sourceVerification": source_verification,
        "sourceVerificationHash": semantic_sha256(source_verification),
        "deployer": "federation-omega-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
        "auditTimestamp": "2026-08-18T10:00:00+00:00",
        "auditMethod": "google.cloud.run.v2.Services.UpdateService",
        "auditResource": "projects/sov-hybrid-suite/locations/africa-south1/services/federation-omega-gcp-admin-mcp",
        "runtimeServiceAccount": "federation-omega-admin@sov-hybrid-suite.iam.gserviceaccount.com",
        "buildServiceAccount": "federation-omega-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
        "iamPolicyHash": "c" * 64,
        "iamEtag": "etag-1",
        "iamPrivate": True,
        "publicIamMembers": [],
        "traffic": [{"revision": revision, "percent": 100, "tag": ""}],
        "revisionLineages": [],
    }


def comparison(mode="SERVING", revision="federation-omega-gcp-admin-mcp-b123"):
    first_join = join(mode, revision)
    second_join = copy.deepcopy(first_join)
    return {
        "pass1": {
            "capturedAt": "2026-08-18T10:00:00+00:00",
            "join": first_join,
            "issues": [],
            "contradictions": [],
            "evidenceHashes": {"service": "d" * 64},
        },
        "pass2": {
            "capturedAt": "2026-08-18T10:00:02+00:00",
            "join": second_join,
            "issues": [],
            "contradictions": [],
            "evidenceHashes": {"service": "e" * 64},
        },
        "pass1JoinHash": semantic_sha256(first_join),
        "pass2JoinHash": semantic_sha256(second_join),
        "identifiersMatch": True,
        "issues": [],
        "contradictions": [],
    }


def lineage_record(include_rollback=True):
    result = {
        "state": "ATTESTED",
        "proofBoundary": "provider_identifiers_matched_across_two_independent_reads",
        "current": comparison(),
    }
    if include_rollback:
        result["rollback"] = comparison("ROLLBACK", "federation-omega-gcp-admin-mcp-prior")
    return {
        "auditId": "audit-123",
        "timestamp": "2026-08-18T10:00:03+00:00",
        "action": "gcp_deployment_lineage_attest",
        "inputHash": "f" * 64,
        "status": "DONE",
        "result": result,
    }


class AdapterContractTests(unittest.TestCase):
    def test_contract_binds_exact_v022_surface_and_source(self):
        self.assertEqual(CONTRACT["serverVersion"], "0.2.2")
        self.assertEqual(CONTRACT["sourceBindings"]["mcpHead"], "bec80d87c5bb05e8a6a1a4453c71aef3d1d02ad6")
        self.assertEqual(CONTRACT["sourceBindings"]["mcpServiceTree"], "c72557e541a1be9c1b5205c79f5a18b9f3caf473")
        self.assertEqual(set(TOOL_SPECS), set(CONTRACT["exactToolNames"]))
        self.assertEqual(len(TOOL_SPECS), 17)

    def test_capability_is_truthfully_source_ready_and_provider_disabled(self):
        snapshot = capability_snapshot()
        self.assertEqual(snapshot["state"], AdapterState.SOURCE_READY_PROVIDER_DISABLED.value)
        self.assertFalse(snapshot["providerExecutionAllowed"])
        self.assertEqual(snapshot["readOnlyToolCount"], 14)
        self.assertEqual(snapshot["effectfulToolCount"], 3)

    def test_unknown_and_forbidden_tools_fail_closed(self):
        for tool in ("gcp_cloud_run_deploy", "credential_discovery", "unknown_tool"):
            gate = validate_tool_arguments(tool, {})
            self.assertFalse(gate.valid)
            self.assertIn("TOOL_NOT_ALLOWLISTED", gate.reasons)

    def test_read_only_plan_hashes_arguments_and_executes_nothing(self):
        result = plan("gcp_cloud_run_service", {
            "project": "sov-hybrid-suite",
            "region": "africa-south1",
            "service": "federation-omega-gcp-admin-mcp",
        })
        self.assertTrue(result["schemaValid"])
        self.assertFalse(result["executionAllowed"])
        self.assertEqual(result["effectState"], "NO_EFFECTS_EXECUTED")
        self.assertRegex(result["argumentsHash"], r"^[0-9a-f]{64}$")
        self.assertNotIn("sov-hybrid-suite", str(result))

    def test_effectful_tools_reject_secret_ingress_and_remain_disabled(self):
        gate = validate_tool_arguments("gcp_enable_service", {
            "project": "sov-hybrid-suite",
            "service": "run.googleapis.com",
            "approvalToken": "must-never-be-persisted",
        })
        self.assertFalse(gate.valid)
        self.assertIn("EFFECTFUL_TOOL_DISABLED", gate.reasons)
        self.assertIn("SECRET_INPUT_PROHIBITED:approvalToken", gate.reasons)
        self.assertNotIn("must-never-be-persisted", str(gate.public()))

    def test_exact_nested_schema_rejects_unknown_fields(self):
        gate = validate_tool_arguments("apps_script_dry_run", {
            "scriptId": "script-1",
            "proposedContent": {"files": [], "secret": "x"},
        })
        self.assertFalse(gate.valid)
        self.assertIn("ARGUMENT_UNKNOWN:proposedContent.secret", gate.reasons)
        self.assertIn("SECRET_INPUT_PROHIBITED:proposedContent.secret", gate.reasons)

    def test_invoke_is_hard_disabled_even_for_valid_read_request(self):
        with self.assertRaisesRegex(ProviderRouteDisabled, "PROVIDER_ROUTE_DISABLED"):
            invoke("gcp_project_info", {"project": "sov-hybrid-suite"})

    def test_health_is_never_accepted_as_deployment_proof(self):
        result = health_is_deployment_proof({
            "ok": True,
            "version": "0.2.2",
            "proofBoundary": "transport_liveness_only",
        })
        self.assertFalse(result.valid)
        self.assertIn("HEALTH_IS_LIVENESS_ONLY", result.reasons)

    def test_global_wif_receipt_requires_exact_fresh_provider_state(self):
        valid = validate_global_wif_receipt(evidence(global_wif_receipt()), NOW)
        self.assertTrue(valid.valid, valid.reasons)
        wrong = global_wif_receipt()
        wrong["provider_state"] = "NOT_FOUND"
        invalid = validate_global_wif_receipt(evidence(wrong), NOW)
        self.assertFalse(invalid.valid)
        self.assertIn("GLOBAL_WIF_MISMATCH:provider_state", invalid.reasons)

    def test_mcp_wif_receipt_requires_all_exact_evidence_hashes(self):
        valid = validate_mcp_wif_receipt(evidence(mcp_wif_receipt()), NOW)
        self.assertTrue(valid.valid, valid.reasons)
        wrong = mcp_wif_receipt()
        wrong["evidenceHashes"].pop("provider.json")
        invalid = validate_mcp_wif_receipt(evidence(wrong), NOW)
        self.assertFalse(invalid.valid)
        self.assertIn("MCP_WIF_EVIDENCE_HASH_KEYS_INVALID", invalid.reasons)

    def test_stale_provider_evidence_fails_closed(self):
        result = validate_mcp_wif_receipt(
            evidence(mcp_wif_receipt(), observed_at=NOW - 901), NOW
        )
        self.assertFalse(result.valid)
        self.assertIn("PROOF_STALE", result.reasons)

    def test_two_pass_lineage_preserves_source_image_revision_and_traffic(self):
        result = validate_lineage_attestation(evidence(lineage_record()), NOW)
        self.assertTrue(result.valid, result.reasons)

    def test_lineage_rejects_cross_pass_drift(self):
        record = lineage_record()
        second = record["result"]["current"]["pass2"]["join"]
        second["imageDigest"] = "sha256:" + "9" * 64
        second["artifactUri"] = second["artifactUri"].rsplit("@", 1)[0] + "@" + second["imageDigest"]
        record["result"]["current"]["pass2JoinHash"] = semantic_sha256(second)
        result = validate_lineage_attestation(evidence(record), NOW)
        self.assertFalse(result.valid)
        self.assertIn("LINEAGE_JOIN_DRIFT", result.reasons)

    def test_lineage_rejects_public_iam_and_invalid_traffic(self):
        record = lineage_record()
        for key in ("pass1", "pass2"):
            current = record["result"]["current"][key]["join"]
            current["iamPrivate"] = False
            current["publicIamMembers"] = ["allUsers"]
            current["traffic"] = [{"revision": current["revision"], "percent": 90, "tag": ""}]
        record["result"]["current"]["pass1JoinHash"] = semantic_sha256(record["result"]["current"]["pass1"]["join"])
        record["result"]["current"]["pass2JoinHash"] = semantic_sha256(record["result"]["current"]["pass2"]["join"])
        result = validate_lineage_attestation(evidence(record), NOW)
        self.assertFalse(result.valid)
        self.assertIn("LINEAGE_PRIVATE_IAM_REQUIRED", result.reasons)
        self.assertIn("LINEAGE_PUBLIC_IAM_PROHIBITED", result.reasons)
        self.assertIn("LINEAGE_TRAFFIC_TOTAL_INVALID", result.reasons)

    def test_promotion_evidence_requires_rollback_lineage(self):
        record = lineage_record(include_rollback=False)
        result = validate_lineage_attestation(evidence(record), NOW, require_rollback=True)
        self.assertFalse(result.valid)
        self.assertIn("ROLLBACK_LINEAGE_REQUIRED", result.reasons)

    def test_complete_evidence_only_makes_read_lane_eligible_but_disabled(self):
        result = readiness(
            global_wif=evidence(global_wif_receipt(), "gcp:global"),
            mcp_wif=evidence(mcp_wif_receipt(), "gcp:mcp"),
            lineage=evidence(lineage_record(), "gcp:lineage"),
            now=NOW,
        )
        self.assertTrue(result["evidenceComplete"])
        self.assertEqual(result["inventoryReadLane"], "ELIGIBLE_BUT_FEATURE_DISABLED")
        self.assertFalse(result["executionAllowed"])
        self.assertIn("DISABLED", result["deploymentLane"])
        self.assertIn("ROLLBACK", result["promotionLane"])


if __name__ == "__main__":
    unittest.main()
