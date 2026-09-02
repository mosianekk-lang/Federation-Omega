from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "evidenceops-pst-corpus-v2-extract.yml"


class PSTRecoveryFailureDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.text)

    def test_workflow_remains_valid_yaml(self):
        self.assertIn("jobs", self.workflow)

    def test_failed_extraction_always_emits_compact_diagnostic(self):
        self.assertEqual(self.text.count("always() && steps.extraction.outcome == 'failure'"), 2)
        self.assertIn("EVIDENCEOPS-PST-V2-EXTRACTION-FAILURE-DIAGNOSTIC-1", self.text)
        self.assertIn("evidenceops-pst-v2-extraction-failure-diagnostic-${{ github.run_id }}", self.text)

    def test_diagnostic_does_not_publish_corpus_or_raw_logs(self):
        self.assertIn("'corpus_content_included': False", self.text)
        self.assertIn("'raw_parser_logs_included': False", self.text)
        self.assertNotIn("path: /mnt/corpus", self.text)
        self.assertNotIn("path: /mnt/pst", self.text)

    def test_failed_path_removes_downloaded_source(self):
        diagnostic = self.text.index("Build privacy-safe failed-closed extraction diagnostic")
        upload = self.text.index("Upload privacy-safe failed-closed extraction diagnostic")
        self.assertIn('rm -f "$SOURCE_PATH"', self.text[diagnostic:upload])


if __name__ == "__main__":
    unittest.main()
