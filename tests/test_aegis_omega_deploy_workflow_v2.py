from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/aegis-omega-zero-traffic-v1.yml"
POLICY = ROOT / "governance/github_airlock_policy.json"
PROOFOS = ROOT / "governance/proofos_omega_policy_extension_aegis_omega_v1.json"


class AegisOmegaProviderWorkflowV2Tests(unittest.TestCase):
    def text(self) -> str:
        if not WORKFLOW.is_file():
            self.skipTest("workflow-free export intentionally excludes provider workflows")
        return WORKFLOW.read_text(encoding="utf-8")

    def test_owner_only_private_dispatch_and_immutable_actions(self):
        value = self.text()
        self.assertIn("github.event.issue.title == '[FO-DISPATCH] AEGIS_OMEGA_ZERO_TRAFFIC_V1'", value)
        self.assertIn("github.event.issue.author_association == 'OWNER'", value)
        self.assertRegex(value, r"(?m)^\s*contents:\s*read\s*$")
        self.assertRegex(value, r"(?m)^\s*id-token:\s*write\s*$")
        self.assertNotRegex(value, r"(?m)^\s*contents:\s*write\s*$")
        self.assertIn("persist-credentials: false", value)
        refs = re.findall(r"uses:\s*([^\s#]+)", value)
        self.assertTrue(refs)
        for ref in refs:
            if ref.startswith("./"):
                continue
            self.assertRegex(ref, r"@[0-9a-f]{40}$")

    def test_canary_is_isolated_from_production_service(self):
        value = self.text()
        self.assertIn("PRODUCTION_SERVICE: aegis-omega", value)
        self.assertIn("CANARY_SERVICE: aegis-omega-canary-v2", value)
        self.assertIn('gcloud run deploy "$CANARY_SERVICE"', value)
        self.assertNotIn('gcloud run deploy "$PRODUCTION_SERVICE"', value)
        self.assertIn("production_service_state_restored", value)
        self.assertIn("production_service_iam_unchanged", value)

    def test_prestate_is_captured_before_mutating_secret_or_runtime(self):
        value = self.text()
        pre = value.index("Capture production and provider prestate before any canary effect")
        production = value.index('gcloud run services describe "$PRODUCTION_SERVICE"', pre)
        secret = value.index('gcloud secrets create "$CANARY_SECRET"')
        image = value.index("docker build --pull")
        deploy = value.index('gcloud run deploy "$CANARY_SERVICE"')
        self.assertLess(pre, production)
        self.assertLess(production, secret)
        self.assertLess(production, image)
        self.assertLess(production, deploy)
        self.assertIn("stale canary service exists; refusing to overwrite unknown provider state", value)

    def test_both_revisions_are_unconditional_zero_traffic(self):
        value = self.text()
        deploy_blocks = re.findall(
            r'gcloud run deploy "\$CANARY_SERVICE" \\\n(?P<body>.*?)(?=\n\s*gcloud run services describe)',
            value,
            flags=re.S,
        )
        self.assertEqual(len(deploy_blocks), 2)
        for block in deploy_blocks:
            self.assertIn("--no-allow-unauthenticated", block)
            self.assertIn("--no-traffic", block)
            self.assertNotIn("--allow-unauthenticated", block)
        self.assertIn("candidate_revision_percent", value)
        self.assertIn("candidate_a_normal_traffic_percent", value)
        self.assertIn("candidate_b_normal_traffic_percent", value)
        self.assertIn("production_traffic_changed", value)
        self.assertNotIn("update-traffic --to-latest", value)

    def test_ephemeral_secret_payload_is_never_read_and_is_deleted(self):
        value = self.text()
        self.assertIn('CANARY_SECRET="aegis-omega-canary-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"', value)
        self.assertIn("gcloud secrets create", value)
        self.assertIn("gcloud secrets versions add", value)
        self.assertIn("gcloud secrets add-iam-policy-binding", value)
        self.assertIn('gcloud secrets delete "$CANARY_SECRET"', value)
        self.assertNotIn("gcloud secrets versions access", value)
        self.assertIn("'secret_payload_logged':False", value)
        self.assertIn("'secret_payload_read_back':False", value)

    def test_rollback_restores_provider_state_and_deletes_canary_assets(self):
        value = self.text()
        for marker in (
            'gcloud run services delete "$CANARY_SERVICE"',
            'gcloud secrets delete "$CANARY_SECRET"',
            'gcloud artifacts docker images delete "$IMAGE"',
            "canary_service_deleted",
            "production_service_state_restored",
            "production_service_iam_unchanged",
            "project_iam_unchanged",
            "final_equivalence_verified",
            "ephemeral_secret_deleted",
            "ephemeral_image_deleted",
            "firestore_provider_state_cleaned",
            "FIRESTORE_CLEANUP_VERIFIED",
        ):
            self.assertIn(marker, value)
        self.assertIn("assert final_ok, receipt", value)

    def test_synthetic_case_is_private_defensive_and_human_gated(self):
        value = self.text()
        self.assertIn("provider-canary-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}", value)
        self.assertIn("requires_human_approval", value)
        self.assertIn("approval_required", value)
        self.assertIn("evidence_chain_valid", value)
        self.assertIn("provider_canary_evidence_artifact_retained", value)
        self.assertIn("firestore_provider_state_cleaned", value)
        self.assertNotIn("provider_canary_evidence_case_retained", value)
        self.assertIn("No production traffic promotion, model inference or external user effect.", value)

    def test_synthetic_firestore_state_is_deleted_and_read_back_absent(self):
        value = self.text()
        self.assertIn('"aegis_cases/$CASE_ID"', value)
        self.assertIn('"aegis_outbox/$CASE_ID"', value)
        self.assertIn('"aegis_requests/$REQUEST_DOC_ID"', value)
        self.assertIn('hashlib.sha256(os.environ["REQUEST_ID"].encode("utf-8")).hexdigest()', value)
        self.assertIn('READBACK_CODE', value)
        self.assertIn('if [[ "$READBACK_CODE" != "404" ]]', value)
        self.assertIn("and os.environ.get('FIRESTORE_CLEANUP_VERIFIED')=='true'", value)

    def test_airlock_policy_admits_exact_provider_gateway(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        path = ".github/workflows/aegis-omega-zero-traffic-v1.yml"
        self.assertIn(path, policy["active_workflow_allowlist"])
        self.assertEqual(policy["allowed_events"][path], ["issues"])
        self.assertIn(path, policy["oidc_workflow_allowlist"])
        self.assertIn(path, policy["provider_mutation_workflow_allowlist"])
        self.assertEqual(
            policy["provider_mutation_exact_issue_titles"][path],
            "[FO-DISPATCH] AEGIS_OMEGA_ZERO_TRAFFIC_V1",
        )
        required = set(policy["provider_mutation_required_markers"][path])
        self.assertTrue({
            "--no-allow-unauthenticated",
            "public_invocation",
            "production_traffic_changed",
            "provider_mutation_performed",
            "gcloud secrets create",
            "gcloud secrets add-iam-policy-binding",
        } <= required)
        forbidden = set(policy["provider_mutation_forbidden_markers"][path])
        self.assertIn("--allow-unauthenticated", forbidden)
        self.assertIn("update-traffic --to-latest", forbidden)

    def test_proofos_selects_provider_v2_regression(self):
        proof = json.loads(PROOFOS.read_text(encoding="utf-8"))
        rows = {row["id"]: row for row in proof["tests"]}
        row = rows["aegis_omega_provider_workflow_v2"]
        self.assertEqual(row["kind"], "unittest_glob")
        self.assertEqual(row["target"], "test_aegis_omega_deploy_workflow_v2.py")
        self.assertIn(".github/workflows/aegis-omega-zero-traffic-v1.yml", row["patterns"])


if __name__ == "__main__":
    unittest.main()
