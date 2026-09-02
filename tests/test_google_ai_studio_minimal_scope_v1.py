from pathlib import Path
import unittest


class GoogleAIStudioMinimalScopeV1Tests(unittest.TestCase):
    def test_only_expected_google_endpoints_are_used(self) -> None:
        workflow = Path('.github/workflows/google-ai-studio-semantic-canary-v1.yml').read_text(encoding='utf-8')
        self.assertIn('generativelanguage.googleapis.com/v1beta/models', workflow)
        self.assertIn('gemini-api-key', workflow)
        self.assertNotIn('gmail.googleapis.com', workflow)
        self.assertNotIn('drive.googleapis.com', workflow)
        self.assertNotIn('script.googleapis.com', workflow)


if __name__ == '__main__':
    unittest.main()
