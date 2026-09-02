from pathlib import Path
import unittest


class GoogleAIStudioNoPlaintextKeyContractTests(unittest.TestCase):
    def test_canary_never_persists_secret_stdout(self) -> None:
        workflow = Path('.github/workflows/google-ai-studio-semantic-canary-v1.yml').read_text(encoding='utf-8')
        self.assertIn('capture_output=True', workflow)
        self.assertIn("api_key = secret.stdout.strip()", workflow)
        self.assertNotIn("'api_key': api_key", workflow)
        self.assertNotIn('Path(', workflow.split("api_key = secret.stdout.strip()")[1].split("receipt:")[0])


if __name__ == '__main__':
    unittest.main()
