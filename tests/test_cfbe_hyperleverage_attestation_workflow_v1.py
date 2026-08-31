from __future__ import annotations

import unittest
from pathlib import Path


class CfbeHyperleverageAttestationWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.workflow = (root / '.github/workflows/cfbe-hyperleverage-attestation-v1.yml').read_text(encoding='utf-8')

    def test_dispatch_is_owner_only_and_exact_title(self) -> None:
        self.assertIn("github.event.issue.title == '[CFBE-DISPATCH] HYPERLEVERAGE_100_ATTEST_V1'", self.workflow)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.workflow)

    def test_permissions_are_attestation_scoped_without_deploy_or_package_write(self) -> None:
        self.assertIn('id-token: write', self.workflow)
        self.assertIn('attestations: write', self.workflow)
        self.assertIn('contents: read', self.workflow)
        self.assertNotIn('contents: write', self.workflow)
        self.assertNotIn('packages: write', self.workflow)
        self.assertNotIn('deployments: write', self.workflow)

    def test_action_is_immutable_pinned_and_registry_push_disabled(self) -> None:
        self.assertIn('actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6', self.workflow)
        self.assertIn('push-to-registry: false', self.workflow)
        self.assertIn('gh attestation verify', self.workflow)

    def test_artifact_is_deterministic_and_bounded_to_cfbe_evidence(self) -> None:
        self.assertIn("date_time=(1980, 1, 1, 0, 0, 0)", self.workflow)
        self.assertIn('FEDERATION_COMPETITIVE_UPGRADES_100_20260901.csv', self.workflow)
        self.assertIn('FEDERATION_COMPETITIVE_BENCHMARK_V2_20260901.md', self.workflow)
        self.assertIn('cfbe-hyperleverage-100.zip', self.workflow)


if __name__ == '__main__':
    unittest.main()
