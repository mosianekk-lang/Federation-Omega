from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / '.github/workflows/fdof-hosted-state-export-v1.yml'
RESTORE_PATH = ROOT / '.github/workflows/fdof-hosted-state-restore-v1.yml'
POLICY_PATH = ROOT / 'governance/github_airlock_policy.json'

CHECKOUT_SHA = '11d5960a326750d5838078e36cf38b85af677262'
SETUP_PYTHON_SHA = 'a26af69be951a213d495a4c3e4e4022e16d87065'
UPLOAD_SHA = 'ea165f8d65b6e75b540449e92b4886f43607fa02'
DOWNLOAD_SHA = 'd3f86a106a0bac45b974a628896c90dbdf5c8093'


class FdofHostedStateCrossRunWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.export = EXPORT_PATH.read_text(encoding='utf-8')
        self.restore = RESTORE_PATH.read_text(encoding='utf-8')
        self.policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))

    def test_export_is_owner_gated_read_only_and_immutable(self) -> None:
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.export)
        self.assertIn("github.event.issue.title == '[FDOF-HOSTED-STATE] EXPORT-V1'", self.export)
        self.assertIn('contents: read', self.export)
        self.assertIn('issues: read', self.export)
        self.assertNotIn('id-token: write', self.export)
        self.assertNotIn('contents: write', self.export)
        self.assertIn(f'actions/checkout@{CHECKOUT_SHA}', self.export)
        self.assertIn(f'actions/setup-python@{SETUP_PYTHON_SHA}', self.export)
        self.assertIn(f'actions/upload-artifact@{UPLOAD_SHA}', self.export)
        self.assertIn('persist-credentials: false', self.export)
        self.assertNotIn('schedule:', self.export)

    def test_restore_is_separate_run_read_only_and_exact_source_bound(self) -> None:
        self.assertIn('workflow_run:', self.restore)
        self.assertIn("workflows: ['FDOF Hosted State Export v1']", self.restore)
        self.assertIn('actions: read', self.restore)
        self.assertIn('contents: read', self.restore)
        self.assertNotIn('id-token: write', self.restore)
        self.assertNotIn('contents: write', self.restore)
        self.assertIn(f'actions/checkout@{CHECKOUT_SHA}', self.restore)
        self.assertIn(f'actions/setup-python@{SETUP_PYTHON_SHA}', self.restore)
        self.assertIn(f'actions/download-artifact@{DOWNLOAD_SHA}', self.restore)
        self.assertIn(f'actions/upload-artifact@{UPLOAD_SHA}', self.restore)
        self.assertIn('ref: ${{ github.event.workflow_run.head_sha }}', self.restore)
        self.assertIn('run-id: ${{ github.event.workflow_run.id }}', self.restore)
        self.assertIn('HOSTED_STATE_TRIGGER_SOURCE_MISMATCH', self.restore)
        self.assertIn('HOSTED_STATE_AUTHORITY_LEASE_TRANSFERRED', self.restore)
        self.assertIn('HOSTED_STATE_ACTIVE_LEASE_NOT_ENFORCED', self.restore)
        self.assertIn('HOSTED_STATE_FENCING_TOKEN_NOT_MONOTONIC', self.restore)
        self.assertIn('HOSTED_STATE_IDEMPOTENCY_COLLISION_NOT_BLOCKED', self.restore)
        self.assertNotIn('schedule:', self.restore)

    def test_airlock_explicitly_admits_only_the_required_events(self) -> None:
        export_path = '.github/workflows/fdof-hosted-state-export-v1.yml'
        restore_path = '.github/workflows/fdof-hosted-state-restore-v1.yml'
        self.assertIn(export_path, self.policy['active_workflow_allowlist'])
        self.assertIn(restore_path, self.policy['active_workflow_allowlist'])
        self.assertEqual(self.policy['allowed_events'][export_path], ['issues'])
        self.assertEqual(self.policy['allowed_events'][restore_path], ['workflow_run'])
        self.assertIn(export_path, self.policy['execution_quarantine']['keep_active'])
        self.assertIn(restore_path, self.policy['execution_quarantine']['keep_active'])
        self.assertNotIn(export_path, self.policy['oidc_workflow_allowlist'])
        self.assertNotIn(restore_path, self.policy['oidc_workflow_allowlist'])
        self.assertNotIn(export_path, self.policy['provider_mutation_workflow_allowlist'])
        self.assertNotIn(restore_path, self.policy['provider_mutation_workflow_allowlist'])


if __name__ == '__main__':
    unittest.main()
