from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "github_airlock_image_catalog_contract", ROOT / "tools" / "github_airlock.py"
)
assert SPEC and SPEC.loader
AIRLOCK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AIRLOCK
SPEC.loader.exec_module(AIRLOCK)
POLICY = AIRLOCK.load_policy(ROOT / "governance" / "github_airlock_policy.json")
PATH = ".github/workflows/sovara-creative-image-catalog-readback.yml"


class SovaraImageCatalogAirlockContractTests(unittest.TestCase):
    def rules(self, findings):
        return {finding.rule for finding in findings}

    def test_exact_read_only_contract_is_allowlisted(self):
        text = """name: SOVARA Creative Image Catalog Readback
on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: sovara-image-catalog-${{ github.ref }}
  cancel-in-progress: false
jobs:
  readback:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: receipt
          path: receipt.json
"""
        self.assertEqual([], AIRLOCK.analyse_workflow(PATH, text, POLICY))

    def test_schedule_is_rejected(self):
        text = """name: SOVARA Creative Image Catalog Readback
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 * * * *'
permissions:
  contents: read
concurrency:
  group: sovara-image-catalog
jobs:
  readback:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        findings = AIRLOCK.analyse_workflow(PATH, text, POLICY)
        self.assertIn("UNAUTHORISED_TRIGGER", self.rules(findings))

    def test_oidc_and_source_write_are_rejected(self):
        text = """name: SOVARA Creative Image Catalog Readback
on:
  push:
    branches: [main]
permissions:
  contents: write
  id-token: write
concurrency:
  group: sovara-image-catalog
jobs:
  readback:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        rules = self.rules(AIRLOCK.analyse_workflow(PATH, text, POLICY))
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", rules)
        self.assertIn("UNAUTHORISED_OIDC", rules)

    def test_non_main_push_is_rejected(self):
        text = """name: SOVARA Creative Image Catalog Readback
on:
  push:
    branches: [main, develop]
permissions:
  contents: read
concurrency:
  group: sovara-image-catalog
jobs:
  readback:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        findings = AIRLOCK.analyse_workflow(PATH, text, POLICY)
        self.assertIn("UNAUTHORISED_PUSH_SCOPE", self.rules(findings))


if __name__ == "__main__":
    unittest.main()
