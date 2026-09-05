from pathlib import Path
import importlib.util
import json
import re
import sys
import unittest

HERE = Path(__file__).resolve()
if HERE.parent == Path('/mnt/data'):
    ROOT = HERE.parent
    WORKFLOW = ROOT / 'current_fkcm_workflow.yml'
    MODULE = ROOT / 'temp_pubsub_iam_canary_compact.py'
    POLICY = ROOT / 'github_airlock_policy.json'
else:
    ROOT = HERE.parents[1]
    WORKFLOW = ROOT / '.github/workflows/fkcm-pubsub-shadow-canary.yml'
    MODULE = ROOT / 'federation/fkcm_v1/temp_pubsub_iam_canary.py'
    POLICY = ROOT / 'governance/github_airlock_policy.json'

WORKFLOW_PATH = '.github/workflows/fkcm-pubsub-shadow-canary.yml'
OLD_TITLE = 'MODISA_FKCM_PUBSUB_SHADOW_CANARY_V1'
TITLE = 'MODISA_FKCM_PUBSUB_TEMP_IAM_CANARY_V1'
CLASSIFIER = 'run services add-iam-policy-binding'
EXACT = {
    'pubsub.subscriptions.create',
    'pubsub.topics.attachSubscription',
    'pubsub.subscriptions.get',
    'pubsub.subscriptions.consume',
    'pubsub.subscriptions.delete',
    'pubsub.topics.publish',
}


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_text = WORKFLOW.read_text(encoding='utf-8')
        cls.module_text = MODULE.read_text(encoding='utf-8')
        cls.policy = json.loads(POLICY.read_text(encoding='utf-8'))
        spec = importlib.util.spec_from_file_location('fkcm_temp_pubsub_iam_canary_contract', MODULE)
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = loaded
        assert spec and spec.loader
        spec.loader.exec_module(loaded)
        cls.module = loaded

    def test_legacy_court_is_preserved_and_new_court_is_exact_owner_gated(self):
        self.assertEqual(1, self.workflow_text.count(OLD_TITLE))
        self.assertGreaterEqual(self.workflow_text.count(TITLE), 1)
        self.assertIn('provider-canary-temp-iam:', self.workflow_text)
        self.assertIn(f"github.event.issue.title == '{TITLE}'", self.workflow_text)
        self.assertGreaterEqual(self.workflow_text.count("github.event.issue.author_association == 'OWNER'"), 2)
        self.assertNotRegex(self.workflow_text, r'(?m)^\s{0,4}workflow_dispatch\s*:')

    def test_airlock_explicitly_classifies_and_exactly_gates_provider_mutation(self):
        self.assertIn(CLASSIFIER, self.workflow_text.lower())
        self.assertIn(WORKFLOW_PATH, self.policy['provider_mutation_workflow_allowlist'])
        self.assertEqual(TITLE, self.policy['provider_mutation_exact_issue_titles'][WORKFLOW_PATH])
        self.assertIn(WORKFLOW_PATH, self.policy['oidc_workflow_allowlist'])
        self.assertEqual(['issues'], self.policy['allowed_events'][WORKFLOW_PATH])

    def test_keyless_wif_and_pinned_actions_only(self):
        self.assertIn('id-token: write', self.workflow_text)
        self.assertIn('workloadIdentityPools/github-federation-omega/providers/github', self.workflow_text)
        self.assertNotIn('credentials_json:', self.workflow_text)
        for ref in re.findall(r'\buses\s*:\s*([^\s#]+)', self.workflow_text):
            if ref.startswith('./'):
                continue
            self.assertRegex(ref.rsplit('@', 1)[-1], r'^[0-9a-fA-F]{40}$')
        self.assertIn('persist-credentials: false', self.workflow_text)

    def test_workflow_invokes_exact_one_use_helper(self):
        call = 'python -m federation.fkcm_v1.temp_pubsub_iam_canary'
        self.assertEqual(1, self.workflow_text.count(call))
        self.assertIn('--execute', self.workflow_text)
        self.assertIn('--ttl-minutes 30', self.workflow_text)
        self.assertIn('fkcm-temp-iam-proof/*.json', self.workflow_text)
        self.assertIn('if: always()', self.workflow_text)

    def test_exact_six_permission_role_and_no_broad_pubsub_role(self):
        self.assertEqual(EXACT, set(self.module.ROLE_PERMISSIONS))
        self.assertEqual(6, len(self.module.ROLE_PERMISSIONS))
        self.assertNotIn('roles/pubsub.editor', self.module_text)
        self.assertNotIn('roles/pubsub.admin', self.module_text)

    def test_existing_topic_only_and_isolated_temp_subscription(self):
        self.assertIn('evidenceops-heartbeat-events', self.module_text)
        self.assertIn("'pubsub','topics','describe'", self.module_text)
        self.assertNotIn("'pubsub','topics','create'", self.module_text)
        self.assertIn('fkcm-shadow-', self.module_text)
        self.assertIn('attributes.eventId=', self.module_text)
        self.assertIn('existing_subscriptions_touched', self.module_text)

    def test_provider_message_id_equivalence_and_subscription_cleanup(self):
        self.assertIn('provider_consumer_message_id_mismatch', self.module_text)
        self.assertIn('temporary_subscription_deleted', self.module_text)
        self.assertIn('delsub(sid)', self.module_text)
        self.assertIn('temporary_subscription_delete_readback_failed', self.module_text)

    def test_iam_lease_is_conditioned_exact_and_self_revoking(self):
        for permission in EXACT:
            self.assertIn(permission, self.module_text)
        self.assertIn('request.time < timestamp(', self.module_text)
        self.assertIn('add-iam-policy-binding', self.module_text)
        self.assertIn('remove-iam-policy-binding', self.module_text)
        self.assertIn('set-iam-policy', self.module_text)
        self.assertIn("'iam','roles','delete'", self.module_text)
        self.assertIn('--show-deleted', self.module_text)
        self.assertIn('iam_binding_residual_authority_detected', self.module_text)
        self.assertIn('TEMP_IAM_LEASE_REVOKED_ZERO_RESIDUAL_VERIFIED', self.module_text)

    def test_admin_authority_is_proven_before_mutation(self):
        self.assertIn('admin_authority_census.py', self.module_text)
        for permission in self.module.ADMIN_REQUIRED_PERMISSIONS:
            self.assertIn(permission, self.module_text)
        self.assertIn('no_direct_admin_impersonation_path_with_exact_iam_authority', self.module_text)

    def test_cleanup_is_fail_closed_and_promotion_requires_revocation(self):
        self.assertIn('finally:', self.module_text)
        self.assertIn('rr=revoke(sp,rd)', self.module_text)
        self.assertIn('provider_runtime_promotion_eligible', self.module_text)
        self.assertIn('pok and iok', self.module_text)
        self.assertIn('CANARY_NOT_PROMOTION_ELIGIBLE', self.module_text)

    def test_no_secret_key_deployment_billing_or_kdv_effect(self):
        self.assertNotIn('credentials_json', self.module_text.lower())
        self.assertNotIn('secrets versions access', self.module_text.lower())
        self.assertNotIn('gcloud run deploy', self.module_text.lower())
        self.assertNotIn('gcloud services enable', self.module_text.lower())
        self.assertIn('service_account_key_used', self.module_text)
        self.assertIn('billing_configuration_changed', self.module_text)
        self.assertIn('kdv_cutover', self.module_text)


if __name__ == '__main__':
    unittest.main()
