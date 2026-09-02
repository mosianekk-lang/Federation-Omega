from pathlib import Path
import unittest


class GoogleAIStudioReceiptTruthBoundaryV1Tests(unittest.TestCase):
    def test_receipt_distinguishes_semantic_call_from_mutation(self) -> None:
        workflow = Path('.github/workflows/google-ai-studio-semantic-canary-v1.yml').read_text(encoding='utf-8')
        self.assertIn("'provider_semantic_call_attempted': False", workflow)
        self.assertIn("receipt['provider_semantic_call_attempted'] = True", workflow)
        self.assertIn("'provider_mutation_attempted': False", workflow)
        self.assertIn('One bounded Gemini Developer API semantic canary only.', workflow)


if __name__ == '__main__':
    unittest.main()
