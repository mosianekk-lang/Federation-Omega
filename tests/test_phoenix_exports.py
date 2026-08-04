from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports", ROOT / "phoenix" / "build_exports.py"
)
assert SPEC and SPEC.loader
EXPORTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EXPORTS
SPEC.loader.exec_module(EXPORTS)


class PhoenixExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "systems" / "example").mkdir(parents=True)
        (self.root / "systems" / "example" / "app.py").write_text(
            "print('verified')\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("# Core\n", encoding="utf-8")
        (self.root / "runtime").mkdir()
        (self.root / "runtime" / "state.json").write_text("{}\n", encoding="utf-8")
        (self.root / ".github" / "workflows").mkdir(parents=True)
        (self.root / ".github" / "workflows" / "unsafe.yml").write_text(
            "name: unsafe\n", encoding="utf-8"
        )
        (self.root / "ipep" / ".github" / "workflows").mkdir(parents=True)
        (self.root / "ipep" / ".github" / "workflows" / "ci.yml").write_text(
            "name: nested unsafe\n", encoding="utf-8"
        )
        (self.root / "docs").mkdir()
        (self.root / "docs" / "credential.md").write_text(
            "example ghp_not_a_real_token\n", encoding="utf-8"
        )
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_phoenix_provider_cutover_v2.py").write_text(
            "raise RuntimeError('migration controller is intentionally absent from Core')\n",
            encoding="utf-8",
        )
        (self.root / "tests" / "test_phoenix_provider_cutover_v3.py").write_text(
            "raise RuntimeError('migration controller is intentionally absent from Core')\n",
            encoding="utf-8",
        )

        template = self.root / "phoenix" / "ops-template"
        (template / ".github").mkdir(parents=True)
        (template / "governance").mkdir()
        (template / "README.md").write_text("# Ops\n", encoding="utf-8")
        (template / ".gitignore").write_text(".env\n", encoding="utf-8")
        (template / ".github" / "CODEOWNERS").write_text(
            "* @owner\n", encoding="utf-8"
        )
        (template / "governance" / "OPS_CONTRACT.json").write_text(
            "{}\n", encoding="utf-8"
        )
        (self.root / "phoenix" / "provider_cutover.py").write_text(
            "print('dry-run')\n", encoding="utf-8"
        )
        (self.root / "phoenix" / "provider_cutover_v3.py").write_text(
            "print('v3 dry-run')\n", encoding="utf-8"
        )

        policy = {
            "version": "test",
            "core": {
                "include_extensions": [".py", ".md", ".json", ".yml"],
                "include_root_files": ["README.md"],
                "excluded_prefixes": [
                    ".git/", ".github/", "runtime/", "deployment_receipts/",
                    "tests/test_phoenix_"
                ],
                "excluded_segments": [
                    "credentials", "receipts", "proofs", "queue", "state"
                ],
                "excluded_suffixes": [".key", ".pem", ".pyc"],
                "secret_markers": ["ghp_", "github_pat_", "sk-proj-"],
            },
            "ops": {
                "template_prefix": "phoenix/ops-template/",
                "required_files": [
                    "README.md", ".gitignore", ".github/CODEOWNERS",
                    "governance/OPS_CONTRACT.json", "provider_cutover.py"
                ],
            },
        }
        self.policy = self.root / "phoenix" / "export_policy.json"
        self.policy.write_text(
            json.dumps(policy, indent=2) + "\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_export_excludes_all_workflows_runtime_secrets_and_migration_tests(self):
        output = self.root / "output"
        receipt = EXPORTS.build(self.root, output, self.policy)
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertTrue((output / "Federation-Omega-Core.tar.gz").is_file())
        self.assertTrue((output / "Federation-Omega-Ops.tar.gz").is_file())

        with tarfile.open(output / "Federation-Omega-Core.tar.gz", "r:gz") as archive:
            names = set(archive.getnames())
        self.assertIn("systems/example/app.py", names)
        self.assertIn("README.md", names)
        self.assertNotIn("runtime/state.json", names)
        self.assertNotIn(".github/workflows/unsafe.yml", names)
        self.assertNotIn("ipep/.github/workflows/ci.yml", names)
        self.assertFalse(any(EXPORTS.is_github_workflow_path(name) for name in names))
        self.assertNotIn("docs/credential.md", names)
        self.assertNotIn("tests/test_phoenix_provider_cutover_v2.py", names)
        self.assertNotIn("tests/test_phoenix_provider_cutover_v3.py", names)

    def test_ops_export_has_no_active_workflow(self):
        output = self.root / "output"
        EXPORTS.build(self.root, output, self.policy)
        with tarfile.open(output / "Federation-Omega-Ops.tar.gz", "r:gz") as archive:
            names = set(archive.getnames())
        self.assertIn("provider_cutover.py", names)
        self.assertIn("governance/OPS_CONTRACT.json", names)
        self.assertFalse(any(EXPORTS.is_github_workflow_path(name) for name in names))

    def test_v2_and_v3_export_builders_contain_no_provider_dispatch_path(self):
        for name in ("build_exports_v2.py", "build_exports_v3.py"):
            source = (ROOT / "phoenix" / name).read_text(encoding="utf-8")
            self.assertNotIn("GH_TOKEN", source)
            self.assertNotIn("workflow_dispatch", source)
            self.assertNotIn("/dispatches", source)
            self.assertNotIn("maybe_dispatch", source)

    def test_v3_final_receipt_is_hash_bound_and_no_apply_is_claimed(self):
        output = self.root / "v3-output"
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "phoenix" / "build_exports_v3.py"),
                "--repo-root",
                str(self.root),
                "--policy",
                str(self.policy),
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        receipt = json.loads(
            (output / "phoenix-export-receipt.json").read_text(encoding="utf-8")
        )
        claimed = receipt.pop("receipt_sha256")
        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), claimed)
        self.assertFalse(receipt["source_mutation_attempted"])
        self.assertFalse(receipt["provider_cutover_engine"]["provider_apply_performed"])
        self.assertNotIn("pst_remote_verifier_dispatch", receipt)


if __name__ == "__main__":
    unittest.main()
