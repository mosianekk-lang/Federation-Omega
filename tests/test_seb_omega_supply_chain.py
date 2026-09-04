import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = '.github/workflows/seb-omega.yml'


class SebOmegaSupplyChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (ROOT / WORKFLOW_PATH).read_text(encoding='utf-8')
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

    def test_workflow_has_exact_airlock_permission(self) -> None:
        self.assertIn('attestations: write', self.workflow)
        self.assertIn(WORKFLOW_PATH, self.policy['attestations_write_workflow_allowlist'])


if __name__ == '__main__':
    unittest.main()
