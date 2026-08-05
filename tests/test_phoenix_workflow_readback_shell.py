from __future__ import annotations

import unittest
from pathlib import Path


class PhoenixWorkflowReadbackShellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = Path(
            ".github/workflows/phoenix-emergency-freeze.yml"
        ).read_text(encoding="utf-8")

    def test_malformed_parameter_default_is_not_used(self) -> None:
        self.assertNotIn('${payload:-{}}', self.workflow)

    def test_empty_or_non_object_provider_readback_fails_closed(self) -> None:
        self.assertIn(
            'if [[ -z "${payload}" ]] || ! jq -e \'type == "object"\'',
            self.workflow,
        )
        self.assertIn("payload='{}'", self.workflow)
        self.assertIn(
            'workflow_state="$(jq -r \'.state // "READ_FAILED"\' <<< "${payload}")"',
            self.workflow,
        )

    def test_jq_reads_normalized_payload_directly(self) -> None:
        self.assertIn(
            'workflow_id="$(jq -r \'.id // 0\' <<< "${payload}")"',
            self.workflow,
        )
        self.assertIn(
            'workflow_path="$(jq -r \'.path // empty\' <<< "${payload}")"',
            self.workflow,
        )


if __name__ == "__main__":
    unittest.main()
