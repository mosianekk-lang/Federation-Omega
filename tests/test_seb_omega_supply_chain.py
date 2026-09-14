import json
import unittest
from pathlib import Path

from tools.github_airlock import analyse_workflow


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = '.github/workflows/seb-omega.yml'
QUALIFICATION_PATH = '.github/workflows/seb-omega-qualification.yml'


class SebOmegaSupplyChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        workflow = ROOT / WORKFLOW_PATH
        if not workflow.is_file():
            raise unittest.SkipTest('workflow-free export excludes repository workflow controls')
        cls.workflow = workflow.read_text(encoding='utf-8')
        cls.qualification = (ROOT / QUALIFICATION_PATH).read_text(encoding='utf-8')
        cls.policy = json.loads(
            (ROOT / 'governance/github_airlock_policy.json').read_text(encoding='utf-8')
        )

    def test_registry_digest_drives_sbom_attestation_and_deployment(self) -> None:
        exact_image = '${{ env.IMAGE_URI }}@${{ env.IMAGE_DIGEST }}'
        self.assertIn(f'image: {exact_image}', self.workflow)
        self.assertIn('subject-name: ${{ env.IMAGE_URI }}', self.workflow)
        self.assertIn('subject-digest: ${{ env.IMAGE_DIGEST }}', self.workflow)
        self.assertIn('push-to-registry: true', self.workflow)
        self.assertIn('--image "${IMAGE_URI}@${IMAGE_DIGEST}"', self.workflow)

    def test_attestation_is_verified_before_deployment(self) -> None:
        verify = self.workflow.index('name: Verify registry SBOM attestation through GitHub CLI')
        deploy = self.workflow.index('name: Deploy immutable zero-traffic revision')
        self.assertLess(verify, deploy)
        self.assertIn('gh attestation verify "oci://${IMAGE_URI}@${IMAGE_DIGEST}"', self.workflow)
        self.assertIn("subject.get('name') == os.environ['IMAGE_URI']", self.workflow)
        self.assertIn("subject.get('digest', {}).get('sha256') == expected", self.workflow)

    def test_provider_gateway_is_explicit_machine_dispatch_only(self) -> None:
        self.assertEqual(['workflow_dispatch'], self.policy['allowed_events'][WORKFLOW_PATH])
        self.assertIn(WORKFLOW_PATH, self.policy['provider_mutation_workflow_allowlist'])
        self.assertIn(WORKFLOW_PATH, self.policy['provider_mutation_machine_dispatch_workflow_allowlist'])
        self.assertEqual([], [row.rule for row in analyse_workflow(WORKFLOW_PATH, self.workflow, self.policy)])
        self.assertNotIn('pull_request:', self.workflow.split('jobs:', 1)[0])
        self.assertNotIn('push:', self.workflow.split('jobs:', 1)[0])

    def test_source_qualification_is_separate_and_effect_free(self) -> None:
        self.assertIn(QUALIFICATION_PATH, self.policy['active_workflow_allowlist'])
        self.assertIn(QUALIFICATION_PATH, self.policy['execution_quarantine']['keep_active'])
        self.assertEqual(
            ['pull_request', 'push', 'workflow_dispatch'],
            self.policy['allowed_events'][QUALIFICATION_PATH],
        )
        self.assertEqual(['main'], self.policy['required_push_branches'][QUALIFICATION_PATH])
        self.assertNotIn('id-token: write', self.qualification)
        self.assertNotIn('google-github-actions/auth@', self.qualification)
        self.assertNotIn('gcloud run deploy', self.qualification)
        self.assertNotIn('gcloud run services update-traffic', self.qualification)
        self.assertEqual([], [row.rule for row in analyse_workflow(QUALIFICATION_PATH, self.qualification, self.policy)])

    def test_workflow_has_exact_airlock_permission(self) -> None:
        self.assertIn('attestations: write', self.workflow)
        self.assertIn(WORKFLOW_PATH, self.policy['attestations_write_workflow_allowlist'])


if __name__ == '__main__':
    unittest.main()
