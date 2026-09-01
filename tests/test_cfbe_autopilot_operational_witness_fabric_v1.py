from __future__ import annotations

import json
import unittest
from hashlib import sha256
from pathlib import Path

from benchmarking.cfbe_omega.autopilot_operational_witness_fabric_v1 import (
    ENVIRONMENT,
    JOB_NAME,
    SCHEMA,
    WORKFLOW_NAME,
    RuntimeIdentity,
    compile_bubbles_provider_readback_witnesses,
)
from benchmarking.cfbe_omega.autopilot_metacognition_observed_intake_v1 import EvidenceWitness


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "autopilot-operational-witness.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
HEAD = "4" * 40


def probe(*, mutation: bool = False, secret_values: bool = False, verified: bool = True) -> bytes:
    state = "AUTHENTICATED_READBACK_VERIFIED" if verified else "BLOCKED_TRUSTED_TOKEN_BINDING"
    payload = {
        "schema": "BUBBLES-PROVIDER-SURFACE-PROBE-V1",
        "mutation_attempted": mutation,
        "secret_values_recorded": secret_values,
        "surfaces": {
            "federation_omega_operator": {
                "classification": state,
                "body": {"private-looking-content": "must never be copied into witness output"},
            },
            "archon_admin_plane_v5": {
                "classification": "AUTHENTICATED_CAPABILITY_AUDIT_REACHABLE" if verified else "PUBLIC_SURFACE_REACHABLE_AUTH_PENDING",
                "token_access_error": "example diagnostic that must stay behind the digest boundary",
            },
            "afeme_v4": {
                "classification": "IDENTITY_TOKEN_READ_VERIFIED" if verified else "IAM_PROTECTED_REACHABLE_AUTH_PENDING",
            },
        },
    }
    return (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")


def identity(**overrides: object) -> RuntimeIdentity:
    values = {
        "source_head_sha": HEAD,
        "run_id": "33459112867",
        "run_attempt": 1,
        "event_name": "push",
        "head_branch": "main",
        "workflow": WORKFLOW_NAME,
        "job": JOB_NAME,
        "observed_at_utc": "2026-09-01T01:33:06Z",
    }
    values.update(overrides)
    return RuntimeIdentity(**values)  # type: ignore[arg-type]


class AutoPilotOperationalWitnessFabricTests(unittest.TestCase):
    def test_real_main_push_compiles_minimal_execution_and_readback_witnesses(self) -> None:
        raw = probe()
        bundle = compile_bubbles_provider_readback_witnesses(identity=identity(), provider_probe_raw=raw)
        payload = bundle.to_dict()

        self.assertEqual(SCHEMA, bundle.schema)
        self.assertEqual("WITNESS_EXECUTION_AND_READBACK_VERIFIED", bundle.status)
        self.assertEqual(HEAD, bundle.source_head_sha)
        self.assertEqual("OBSERVED_OPERATIONAL_WITNESS_INPUT", bundle.evidence_mode)
        self.assertEqual(ENVIRONMENT, bundle.environment)
        self.assertEqual(3, bundle.verified_surface_count)
        self.assertEqual("sha256:" + sha256(raw).hexdigest(), bundle.provider_probe_digest)
        self.assertFalse(bundle.blockers)
        self.assertFalse(bundle.observed_pair_emitted)
        self.assertFalse(bundle.observed_resume_emitted)
        self.assertFalse(bundle.provider_effect_authorized)
        self.assertFalse(bundle.stable_promotion_authorized)
        self.assertFalse(bundle.full_autopilot_runtime_proven)

        execution = EvidenceWitness.from_mapping(payload["execution_witness"]).validate(expected_source_head_sha=HEAD)
        readback = EvidenceWitness.from_mapping(payload["readback_witness"]).validate(expected_source_head_sha=HEAD)
        self.assertEqual("EXECUTION", execution.kind)
        self.assertEqual("IMMUTABLE_EXECUTION_RECEIPT", execution.evidence_class)
        self.assertFalse(execution.independent)
        self.assertEqual("READBACK", readback.kind)
        self.assertEqual("PROVIDER_LIVE_INDEPENDENT_READBACK", readback.evidence_class)
        self.assertTrue(readback.independent)

        serialized = json.dumps(payload, sort_keys=True).lower()
        for forbidden in (
            "private-looking-content",
            "example diagnostic",
            "token_access_error",
            "response body",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_auth_pending_real_cycle_emits_execution_witness_and_hold_not_false_readback(self) -> None:
        raw = probe(verified=False)
        bundle = compile_bubbles_provider_readback_witnesses(identity=identity(), provider_probe_raw=raw)
        payload = bundle.to_dict()

        self.assertEqual("HOLD_EXECUTION_VERIFIED_READBACK_UNPROVEN", bundle.status)
        self.assertEqual("OBSERVED_OPERATIONAL_EXECUTION_WITNESS_ONLY", bundle.evidence_mode)
        self.assertEqual(("INDEPENDENT_PROVIDER_READBACK_NOT_VERIFIED",), bundle.blockers)
        self.assertEqual(0, bundle.verified_surface_count)
        self.assertIsNone(bundle.readback_witness)
        execution = EvidenceWitness.from_mapping(payload["execution_witness"]).validate(expected_source_head_sha=HEAD)
        self.assertEqual("EXECUTION", execution.kind)
        self.assertFalse(bundle.observed_pair_emitted)
        self.assertFalse(bundle.provider_effect_authorized)

    def test_provider_probe_mutation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "WITNESS_FABRIC_PROVIDER_MUTATION_REJECTED"):
            compile_bubbles_provider_readback_witnesses(identity=identity(), provider_probe_raw=probe(mutation=True))

    def test_secret_recording_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "WITNESS_FABRIC_SECRET_RECORDING_REJECTED"):
            compile_bubbles_provider_readback_witnesses(identity=identity(), provider_probe_raw=probe(secret_values=True))

    def test_only_real_main_push_bubbles_readback_job_is_admitted(self) -> None:
        cases = (
            (identity(event_name="pull_request"), "WITNESS_FABRIC_REAL_MAIN_PUSH_REQUIRED"),
            (identity(head_branch="feature"), "WITNESS_FABRIC_MAIN_BRANCH_REQUIRED"),
            (identity(workflow="Other Workflow"), "WITNESS_FABRIC_WORKFLOW_MISMATCH"),
            (identity(job="contract"), "WITNESS_FABRIC_JOB_MISMATCH"),
        )
        for runtime_identity, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    compile_bubbles_provider_readback_witnesses(identity=runtime_identity, provider_probe_raw=probe())

    def test_receipt_is_hash_bound_and_does_not_promote_itself(self) -> None:
        first = compile_bubbles_provider_readback_witnesses(identity=identity(), provider_probe_raw=probe())
        second = compile_bubbles_provider_readback_witnesses(identity=identity(), provider_probe_raw=probe())
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertTrue(first.receipt_sha256.startswith("sha256:"))
        self.assertFalse(first.provider_effect_authorized)
        self.assertFalse(first.stable_promotion_authorized)
        self.assertFalse(first.full_autopilot_runtime_proven)

    def test_workflow_is_read_only_and_policy_scoped(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        workflow_path = ".github/workflows/autopilot-operational-witness.yml"

        self.assertIn("workflow_run:", workflow)
        self.assertIn("Bubbles Command Bus", workflow)
        self.assertIn("conclusion == 'success'", workflow)
        self.assertIn("event == 'push'", workflow)
        self.assertIn("head_branch == 'main'", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("statuses: write", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("gh api --method post", workflow.lower())
        self.assertNotIn("gh api -x post", workflow.lower())
        self.assertIn("autopilot-operational-witness", workflow)

        self.assertIn(workflow_path, policy["active_workflow_allowlist"])
        self.assertEqual(["workflow_run"], policy["allowed_events"][workflow_path])
        self.assertIn(workflow_path, policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(workflow_path, policy["oidc_workflow_allowlist"])
        self.assertNotIn(workflow_path, policy["provider_mutation_workflow_allowlist"])
        self.assertNotIn(workflow_path, policy["attestations_write_workflow_allowlist"])


if __name__ == "__main__":
    unittest.main()
