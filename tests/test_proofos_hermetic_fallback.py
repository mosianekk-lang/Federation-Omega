from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from proofos_omega.core import ImpactCompiler, ProofPolicy, ProofSelector, RunnerError
from proofos_omega.hermetic import run_hermetic_r5_fallback


class ProofOSHermeticFallbackTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        process = subprocess.run(
            ["git", *args],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            self.fail(f"git {' '.join(args)} failed: {process.stderr}")
        return process.stdout.strip()

    def _policy(self) -> ProofPolicy:
        return ProofPolicy(
            {
                "schema": "FEDERATION-PROOFOS-OMEGA-V1",
                "version": "1.0.0",
                "authority_ceiling": "A1_INTERNAL",
                "external_effect_default": False,
                "selector": {
                    "fallback_full_suite_test_id": "full_federation_fallback",
                    "sentinel_percent": 0,
                    "production_extensions": [".py"],
                    "nonproduction_prefixes": ["tests", "docs"],
                },
                "risk_rules": [
                    {
                        "risk": "R5_RELEASE",
                        "patterns": ["app/**"],
                        "reason": "TEST_RELEASE_BOUNDARY",
                    }
                ],
                "subsystem_rules": [
                    {"subsystem": "APP", "patterns": ["app/**"], "depends_on": []}
                ],
                "historical_associations": [],
                "tests": [
                    {
                        "id": "bootstrap",
                        "kind": "unittest_glob",
                        "target": "test_bootstrap.py",
                        "patterns": ["app/**"],
                        "subsystems": ["APP"],
                        "always": True,
                        "hard_always_run": True,
                        "sentinel_eligible": False,
                        "failure_class": "SOURCE_INTEGRITY_FAILURE",
                        "block_scope": "GLOBAL",
                        "timeout_seconds": 30,
                    },
                    {
                        "id": "full_federation_fallback",
                        "kind": "unittest_glob",
                        "target": "test_*.py",
                        "patterns": [],
                        "subsystems": [],
                        "min_risk": "R5_RELEASE",
                        "hard_always_run": False,
                        "sentinel_eligible": False,
                        "failure_class": "GENERAL_REGRESSION",
                        "block_scope": "GLOBAL",
                        "timeout_seconds": 30,
                    },
                ],
            }
        )

    def _repo(self, root: Path) -> tuple[ProofPolicy, object]:
        (root / "app").mkdir()
        (root / "tests").mkdir()
        (root / "app/runtime.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "tests/test_bootstrap.py").write_text(
            "import unittest\n"
            "class Bootstrap(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        (root / "tests/test_clean_head.py").write_text(
            "from pathlib import Path\n"
            "import unittest\n"
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "class CleanHead(unittest.TestCase):\n"
            "    def test_no_pollution(self):\n"
            "        self.assertFalse((ROOT / 'polluted.marker').exists())\n",
            encoding="utf-8",
        )
        self._git(root, "init")
        self._git(root, "config", "user.email", "proofos@example.invalid")
        self._git(root, "config", "user.name", "ProofOS Test")
        self._git(root, "add", ".")
        self._git(root, "commit", "-m", "fixture")
        head = self._git(root, "rev-parse", "HEAD")
        policy = self._policy()
        impact = ImpactCompiler(policy).assess(["app/runtime.py"])
        manifest = ProofSelector(policy).compile_manifest(
            base_sha="1" * 40,
            head_sha=head,
            impact=impact,
        )
        return policy, manifest

    def test_dirty_untracked_state_cannot_false_block_r5_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = self._repo(root)
            (root / "polluted.marker").write_text("dirty\n", encoding="utf-8")

            dirty = subprocess.run(
                ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(0, dirty.returncode)

            execution = run_hermetic_r5_fallback(
                policy=policy,
                manifest=manifest,
                repo_root=root,
            )
            self.assertIsNotNone(execution)
            assert execution is not None
            self.assertEqual("PASS", execution.result.status)
            self.assertTrue(execution.clean_checkout_verified)
            self.assertEqual(manifest.head_sha, execution.head_sha)

    def test_tracked_source_drift_fails_closed_before_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = self._repo(root)
            (root / "tests/test_clean_head.py").write_text(
                "import unittest\nclass Drift(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RunnerError, "PROOF_KEY_DRIFT"):
                run_hermetic_r5_fallback(
                    policy=policy,
                    manifest=manifest,
                    repo_root=root,
                )

    def test_non_git_harness_retains_legacy_runner_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app").mkdir()
            (root / "tests").mkdir()
            (root / "app/runtime.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "tests/test_bootstrap.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
            policy = self._policy()
            manifest = ProofSelector(policy).compile_manifest(
                base_sha="1" * 40,
                head_sha="2" * 40,
                impact=ImpactCompiler(policy).assess(["app/runtime.py"]),
            )
            self.assertIsNone(
                run_hermetic_r5_fallback(
                    policy=policy,
                    manifest=manifest,
                    repo_root=root,
                )
            )


if __name__ == "__main__":
    unittest.main()
