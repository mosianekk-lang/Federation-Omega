from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
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

SOURCE_REPOSITORY_CONTROL_TESTS = (
    "test_phoenix_provider_cutover_v2.py",
    "test_phoenix_provider_cutover_v3.py",
    "test_phoenix_provider_cutover_v3_1.py",
    "test_phoenix_provider_cutover_v3_authorized_executor.py",
    "test_phoenix_provider_cutover_v3_outcome_reconciler.py",
    "test_provider_airlock_activate.py",
    "test_agent_governance_contract.py",
    "test_pst_composite_runtime_contract.py",
    "test_wif_hardening.py",
)


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
        for name in SOURCE_REPOSITORY_CONTROL_TESTS:
            (self.root / "tests" / name).write_text(
                "raise RuntimeError('source-repository control is intentionally absent from Core')\n",
                encoding="utf-8",
            )
        (self.root / "tests" / "test_core_example.py").write_text(
            "import unittest\n\n"
            "class CoreExampleTests(unittest.TestCase):\n"
            "    def test_core_is_runnable(self):\n"
            "        self.assertEqual(2, 1 + 1)\n",
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
        (template / "provider_cutover_owner_authority_bound.py").write_text(
            "print('owner authority bound')\n", encoding="utf-8"
        )
        (template / "provider_cutover_authority_bound.py").write_text(
            "print('authority bound')\n", encoding="utf-8"
        )
        (self.root / "phoenix" / "provider_cutover.py").write_text(
            "print('dry-run')\n", encoding="utf-8"
        )
        (
            self.root / "phoenix" / "provider_cutover_authorized_executor.py"
        ).write_text("print('authorized v22')\n", encoding="utf-8")
        (
            self.root / "phoenix" / "provider_cutover_authorization_use.py"
        ).write_text("print('authorization use')\n", encoding="utf-8")
        (self.root / "phoenix" / "provider_cutover_v3.py").write_text(
            "print('v3 base')\n", encoding="utf-8"
        )
        (self.root / "phoenix" / "provider_cutover_v3_1.py").write_text(
            "print('v3.1 entrypoint')\n", encoding="utf-8"
        )
        (
            self.root / "phoenix" / "provider_cutover_outcome_reconciler.py"
        ).write_text("print('read-only reconciler')\n", encoding="utf-8")

        policy = {
            "version": "test",
            "core": {
                "include_extensions": [".py", ".md", ".json", ".yml"],
                "include_root_files": ["README.md"],
                "excluded_prefixes": [
                    ".git/",
                    ".github/",
                    "runtime/",
                    "deployment_receipts/",
                    "tests/test_phoenix_",
                ],
                "excluded_test_globs": [
                    "tests/test_phoenix_*",
                    "tests/test_provider_airlock_activate.py",
                    "tests/test_agent_governance_contract.py",
                    "tests/test_pst_composite_runtime_contract.py",
                    "tests/test_wif_hardening.py",
                ],
                "excluded_segments": [
                    "credentials",
                    "receipts",
                    "proofs",
                    "queue",
                    "state",
                ],
                "excluded_suffixes": [".key", ".pem", ".pyc"],
                "secret_markers": ["ghp_", "github_pat_", "sk-proj-"],
            },
            "ops": {
                "template_prefix": "phoenix/ops-template/",
                "required_files": [
                    "README.md",
                    ".gitignore",
                    ".github/CODEOWNERS",
                    "governance/OPS_CONTRACT.json",
                    "provider_cutover_owner_authority_bound.py",
                    "provider_cutover_authority_bound.py",
                    "provider_cutover.py",
                ],
            },
        }
        self.policy_payload = policy
        self.policy = self.root / "phoenix" / "export_policy.json"
        self.policy.write_text(
            json.dumps(policy, indent=2) + "\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def run_exported_tests(
        core_archive: Path,
        extracted: Path,
        *,
        install_requirements: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        extracted.mkdir()
        with tarfile.open(core_archive, "r:gz") as archive:
            archive.extractall(extracted, filter="data")
        env = os.environ.copy()
        env.setdefault("TERM", "dumb")
        env["PYTHONPATH"] = str(extracted)
        env["LOCALAPPDATA"] = str(extracted.parent / "isolated-local-appdata")
        if install_requirements:
            requirements = extracted / "requirements.txt"
            if not requirements.is_file():
                return subprocess.CompletedProcess(
                    args=["requirements.txt"],
                    returncode=1,
                    stdout="",
                    stderr="exported Core is missing requirements.txt",
                )
            installation = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-r",
                    str(requirements),
                ],
                cwd=extracted,
                env=env,
                text=True,
                capture_output=True,
            )
            if installation.returncode != 0:
                return installation
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test*.py",
                "-v",
            ],
            cwd=extracted,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_export_excludes_workflows_runtime_secrets_and_source_control_tests(self):
        output = self.root / "output"
        receipt = EXPORTS.build(self.root, output, self.policy)
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertTrue((output / "Federation-Omega-Core.tar.gz").is_file())
        self.assertTrue((output / "Federation-Omega-Ops.tar.gz").is_file())

        with tarfile.open(output / "Federation-Omega-Core.tar.gz", "r:gz") as archive:
            names = set(archive.getnames())
            manifest_file = archive.extractfile("PHOENIX_CORE_MANIFEST.json")
            assert manifest_file is not None
            manifest = json.load(manifest_file)
        self.assertIn("systems/example/app.py", names)
        self.assertIn("README.md", names)
        self.assertIn("tests/test_core_example.py", names)
        self.assertNotIn("runtime/state.json", names)
        self.assertNotIn(".github/workflows/unsafe.yml", names)
        self.assertNotIn("ipep/.github/workflows/ci.yml", names)
        self.assertFalse(any(EXPORTS.is_github_workflow_path(name) for name in names))
        self.assertNotIn("docs/credential.md", names)
        self.assertFalse(
            any(
                EXPORTS.is_migration_control_test(name, self.policy_payload)
                for name in names
            )
        )
        for name in SOURCE_REPOSITORY_CONTROL_TESTS:
            self.assertNotIn(f"tests/{name}", names)
        self.assertEqual(0, manifest["invariants"]["migration_control_test_count"])

    def test_exported_synthetic_core_test_suite_is_independently_runnable(self):
        output = self.root / "output"
        EXPORTS.build(self.root, output, self.policy)
        process = self.run_exported_tests(
            output / "Federation-Omega-Core.tar.gz",
            self.root / "extracted-core",
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("test_core_is_runnable", process.stderr)

    def test_exported_proofos_cli_imports_and_redacts_with_real_core_policy(self):
        # Exercise production source through the actual archive pipeline, not
        # only classify_core: the secret-marker stage previously removed cli.py.
        self.policy_payload["core"] = json.loads(
            (ROOT / "phoenix/export_policy.json").read_text(encoding="utf-8")
        )["core"]
        self.policy.write_text(json.dumps(self.policy_payload), encoding="utf-8")
        shutil.copytree(ROOT / "proofos_omega", self.root / "proofos_omega",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("test_proofos_execution_budget.py",
                     "test_fuse_one_os_browser_admission.py",
                     "test_fuse_one_os_integration_admission.py"):
            shutil.copyfile(ROOT / "tests" / name, self.root / "tests" / name)
        (self.root / "docs/fine-grained-token.txt").write_text(
            "github" + "_pat_" + "synthetic_not_a_real_credential", encoding="utf-8"
        )
        output = self.root / "output"
        EXPORTS.build(self.root, output, self.policy)
        extracted = self.root / "isolated-core"
        extracted.mkdir()
        with tarfile.open(output / "Federation-Omega-Core.tar.gz", "r:gz") as archive:
            names = set(archive.getnames())
            self.assertIn("proofos_omega/cli.py", names)
            self.assertIn("tests/test_proofos_execution_budget.py", names)
            self.assertIn("tests/test_fuse_one_os_integration_admission.py", names)
            self.assertNotIn("tests/test_fuse_one_os_browser_admission.py", names)
            self.assertNotIn("docs/credential.md", names)
            self.assertNotIn("docs/fine-grained-token.txt", names)
            archive.extractall(extracted, filter="data")
        process = subprocess.run(
            [sys.executable, "-I", "-c", "\n".join((
                "import pathlib, sys",
                "root = pathlib.Path.cwd()",
                "sys.path.insert(0, str(root))",
                "sys.path.insert(0, str(root / 'tests'))",
                "from proofos_omega import cli",
                "import test_proofos_execution_budget",
                "assert pathlib.Path(cli.__file__).resolve() == root / 'proofos_omega/cli.py'",
                "secret = 'github' + '_pat_' + 'abcdefghijklmnopqrstuvwxyz'",
                "assert cli._redact_diagnostic(secret) == '[REDACTED_SECRET]'",
                "print('EXPORTED_PROOFOS_IMPORT_AND_REDACTION_PASS')",
            ))],
            cwd=extracted, text=True, capture_output=True, timeout=20,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("EXPORTED_PROOFOS_IMPORT_AND_REDACTION_PASS", process.stdout)

    def test_browser_core_exclusion_preserves_required_source_admission(self):
        from proofos_omega.core import ProofSelector
        from proofos_omega.impact import ImpactCompiler
        from proofos_omega.policy import ProofPolicy

        policy = json.loads((ROOT / "phoenix/export_policy.json").read_text(encoding="utf-8"))
        browser_path = "tests/test_fuse_one_os_browser_admission.py"
        self.assertIn(browser_path, policy["core"]["excluded_test_globs"])
        self.assertIn("source admission", policy["core"]["excluded_test_rationales"][browser_path])
        self.assertFalse(EXPORTS.is_migration_control_test(
            "tests/test_fuse_one_os_integration_admission.py", policy))
        self.assertNotIn(".mjs", policy["core"]["include_extensions"])
        proof_policy = ProofPolicy.from_path(ROOT / "governance/proofos_omega_policy_v1.json")
        manifest = ProofSelector(proof_policy).compile_manifest(
            base_sha="a" * 40, head_sha="b" * 40,
            impact=ImpactCompiler(proof_policy).assess(["scripts/fuse_one_os_browser_test.mjs"]),
        )
        self.assertIn("fuse_one_os_browser_runtime", {item.test_id for item in manifest.selected_tests})
        browser = proof_policy.tests["fuse_one_os_browser_runtime"]
        self.assertEqual("test_fuse_one_os_browser_admission.py", browser.target)
        self.assertFalse(browser.optional_if_missing)
        self.assertEqual("GLOBAL", browser.block_scope)

    def test_exact_source_paths_are_normalized_and_fail_closed(self):
        for invalid in ("asset.mjs", ["/asset.mjs"], ["../asset.mjs"],
                        ["a/../asset.mjs"], ["a//asset.mjs"], ["./asset.mjs"],
                        ["a\\asset.mjs"], ["a/*.mjs"], ["C:/asset.mjs"],
                        ["asset.mjs", "asset.mjs"], [None]):
            with self.subTest(invalid=invalid):
                policy = json.loads(json.dumps(self.policy_payload))
                policy["core"]["include_source_paths"] = invalid
                with self.assertRaises(ValueError):
                    EXPORTS.exact_core_source_paths(policy)

    def test_exact_source_paths_cannot_bypass_export_security(self):
        files = {
            "assets/approved.mjs": "export const safe = true;\n",
            "assets/unrelated.mjs": "export const safe = true;\n",
            "assets/unrelated.cpp": "int main() { return 0; }\n",
            "assets/unrelated.cmd": "@exit /b 0\n",
            "assets/Dockerfile": "FROM scratch\n",
            "assets/credential.mjs": "github" + "_pat_" + "synthetic_not_a_real_credential",
            "assets/private.pem": "synthetic private key\n",
            "runtime/unsafe.mjs": "runtime state\n",
            "assets/receipts/unsafe.mjs": "receipt state\n",
            ".github/workflows/unsafe.mjs": "workflow source\n",
        }
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (self.root / "assets/link.mjs").symlink_to(self.root / "assets/approved.mjs")
        with (self.root / "assets/oversize.mjs").open("wb") as stream:
            stream.truncate(10 * 1024 * 1024 + 1)
        unrelated = {"assets/unrelated.mjs", "assets/unrelated.cpp", "assets/unrelated.cmd", "assets/Dockerfile"}
        self.policy_payload["core"]["include_source_paths"] = sorted(
            (set(files) - unrelated) | {"assets/link.mjs", "assets/oversize.mjs"}
        )
        included, excluded = EXPORTS.stage_core(self.root, self.root / "stage", self.policy_payload)
        included_paths = {row.path for row in included}
        reasons = {row.path: row.reason for row in excluded}
        self.assertIn("assets/approved.mjs", included_paths)
        self.assertFalse((set(files) - {"assets/approved.mjs"}) & included_paths)
        self.assertEqual("SYMLINK_PROHIBITED", reasons["assets/link.mjs"])
        self.assertEqual("FILE_EXCEEDS_CORE_EXPORT_LIMIT", reasons["assets/oversize.mjs"])
        self.assertTrue(reasons["assets/credential.mjs"].startswith("SECRET_MARKER:"))
        for name in unrelated:
            self.assertEqual("UNAPPROVED_EXTENSION", reasons[name])

    def test_production_exact_assets_and_source_workflow_court_are_bound(self):
        from proofos_omega.core import ProofSelector
        from proofos_omega.impact import ImpactCompiler
        from proofos_omega.policy import ProofPolicy

        policy = json.loads((ROOT / "phoenix/export_policy.json").read_text(encoding="utf-8"))
        assets = EXPORTS.exact_core_source_paths(policy)
        self.assertEqual(19, len(assets))
        for name in assets:
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file())
                self.assertEqual((True, "APPROVED_EXACT_SOURCE_FILE"),
                                 EXPORTS.classify_core(ROOT / name, ROOT, policy))
        proof_policy = ProofPolicy.from_path(ROOT / "governance/proofos_omega_policy_v1.json")
        court = proof_policy.tests["phoenix_core_workflow_source_contracts"]
        self.assertFalse(court.optional_if_missing)
        self.assertEqual("GLOBAL", court.block_scope)
        for path in ("tests/test_fuse_localllm_desktop_source_v1.py",
                     "tests/test_fuse_localllm_gemini_provider_v1.py",
                     "tests/test_sovara_google_interactions_v2_canary.py",
                     "tests/phoenix_core_test_profile.py", "phoenix/build_exports.py"):
            with self.subTest(path=path):
                manifest = ProofSelector(proof_policy).compile_manifest(
                    base_sha="a" * 40, head_sha="b" * 40,
                    impact=ImpactCompiler(proof_policy).assess([path]),
                )
                self.assertIn(court.test_id, {item.test_id for item in manifest.selected_tests})

    def test_repository_core_archive_test_suite_is_independently_runnable(self):
        with tempfile.TemporaryDirectory(prefix="phoenix-real-core-") as temporary:
            temporary_root = Path(temporary)
            output = temporary_root / "output"
            receipt = EXPORTS.build(
                ROOT,
                output,
                ROOT / "phoenix" / "export_policy.json",
            )
            self.assertEqual("VERIFIED", receipt["status"])
            policy = json.loads((ROOT / "phoenix/export_policy.json").read_text(encoding="utf-8"))
            with tarfile.open(output / "Federation-Omega-Core.tar.gz", "r:gz") as archive:
                for name in EXPORTS.exact_core_source_paths(policy):
                    with self.subTest(exported_asset=name):
                        member = archive.extractfile(name)
                        self.assertIsNotNone(member)
                        with member:
                            self.assertEqual((ROOT / name).read_bytes(), member.read())
            process = self.run_exported_tests(
                output / "Federation-Omega-Core.tar.gz",
                temporary_root / "extracted-core",
                install_requirements=True,
            )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertIn("Ran ", process.stderr)
        self.assertIn("OK", process.stderr)

    def test_ops_export_has_authorized_cutover_package_and_no_active_workflow(self):
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

    def test_v30_final_receipt_is_hash_bound_and_no_apply_is_claimed(self):
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
        engine = receipt["provider_cutover_engine"]
        self.assertEqual("3.5", engine["version"])
        self.assertEqual(
            "V30_OWNER_PROVIDER_AUTHORITY_BINDING",
            engine["authorization_execution_gate"],
        )
        self.assertEqual("3.1", engine["provider_controller_version"])
        self.assertTrue(engine["authorization_decision_required"])
        self.assertEqual(
            "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2",
            engine["authorization_decision_schema"],
        )
        self.assertTrue(
            engine["owner_authorization_provider_receipt_hash_binding_required"]
        )
        self.assertTrue(
            engine["owner_authorization_repository_creation_endpoint_binding_required"]
        )
        self.assertFalse(
            engine["owner_authorization_external_commercial_gate_advancement_allowed"]
        )
        self.assertEqual(
            "provider_cutover_owner_authority_bound.py", engine["entrypoint"]
        )
        self.assertEqual(
            "provider_cutover_authority_bound.py",
            engine["authority_bound_internal_entrypoint"],
        )
        self.assertTrue(engine["one_time_authorization_consumption_required"])
        self.assertEqual(300, engine["provider_authority_receipt_max_age_seconds"])
        self.assertEqual(30, engine["provider_authority_receipt_max_future_skew_seconds"])
        self.assertTrue(engine["provider_authority_receipt_semantic_checks_required"])
        self.assertTrue(engine["provider_authority_just_in_time_reprobe_required"])
        self.assertEqual(
            [
                "authority_mode",
                "repository_creation_endpoint",
                "legacy_main_sha",
                "core_target_exists",
                "ops_target_exists",
            ],
            engine["provider_authority_continuity_fields"],
        )
        self.assertFalse(engine["unknown_outcome_automatic_retry"])
        self.assertTrue(engine["read_only_outcome_reconciliation"])
        self.assertFalse(engine["outcome_reconciliation_mutation_allowed"])
        self.assertFalse(engine["provider_apply_performed"])
        self.assertEqual(
            "provider_cutover_outcome_reconciler.py",
            engine["outcome_reconciliation_entrypoint"],
        )
        self.assertEqual(
            "REQUIRED_DURING_APPLY",
            engine["temporary_template_state_restoration"],
        )
        with tarfile.open(output / "Federation-Omega-Ops.tar.gz", "r:gz") as archive:
            names = set(archive.getnames())
        self.assertIn("provider_cutover_owner_authority_bound.py", names)
        self.assertIn("provider_cutover_authority_bound.py", names)
        self.assertIn("provider_cutover.py", names)
        self.assertIn("provider_cutover_authorization_use.py", names)
        self.assertIn("provider_cutover_v3_1.py", names)
        self.assertIn("provider_cutover_v3_base.py", names)
        self.assertIn("provider_cutover_outcome_reconciler.py", names)
        self.assertNotIn("pst_remote_verifier_dispatch", receipt)


if __name__ == "__main__":
    unittest.main()
