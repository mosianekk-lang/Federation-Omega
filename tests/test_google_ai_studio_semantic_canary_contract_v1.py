import json
from pathlib import Path
import unittest


class GoogleAIStudioSemanticCanaryContractV1Tests(unittest.TestCase):
    def test_contract_is_fail_closed_and_non_mutating(self) -> None:
        payload = json.loads(
            Path('governance/google_ai_studio_semantic_canary_v1.json').read_text(encoding='utf-8')
        )
        self.assertEqual(payload['schema'], 'GOOGLE-AI-STUDIO-SEMANTIC-CANARY-CONTRACT-V1')
        self.assertTrue(payload['trigger']['owner_only'])
        self.assertFalse(payload['authority']['provider_mutation'])
        self.assertFalse(payload['authority']['repository_mutation'])
        self.assertEqual(payload['credential_handling']['access'], 'TRANSIENT_RUNNER_MEMORY_ONLY')
        self.assertFalse(payload['credential_handling']['log_recording'])
        self.assertFalse(payload['credential_handling']['receipt_recording'])
        self.assertTrue(payload['proof_requirement']['semantic_exact_match'])
        self.assertEqual(payload['proof_requirement']['classification'], 'GEMINI_SEMANTIC_READBACK_PROVEN')


if __name__ == '__main__':
    unittest.main()
