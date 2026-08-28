from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proofos_omega.calibration import CalibrationConfig, CalibrationError, ShadowCalibrator
from proofos_omega.core import ImpactCompiler, ProofPolicy, ProofSelector

BASE = "1" * 40
HEAD = "2" * 40


def tiny_policy() -> ProofPolicy:
    return ProofPolicy({
        "schema": "FEDERATION-PROOFOS-OMEGA-V1",
        "version": "1.0.0",
        "authority_ceiling": "A1_INTERNAL",
        "external_effect_default": False,
        "selector": {
            "fallback_full_suite_test_id": "full",
            "sentinel_percent": 0,
            "production_extensions": [".py"],
            "nonproduction_prefixes": ["tests", "docs"],
        },
        "risk_rules": [],
        "subsystem_rules": [
            {"subsystem": "APP", "patterns": ["app/**"], "depends_on": []},
            {"subsystem": "OTHER", "patterns": ["other/**"], "depends_on": []},
        ],
        "historical_associations": [],
        "tests": [
            {"id": "focused", "kind": "unittest_glob", "target": "test_focus.py", "patterns": ["app/**"], "subsystems": ["APP"], "always": True, "hard_always_run": True, "sentinel_eligible": False, "failure_class": "SOURCE_INTEGRITY_FAILURE", "block_scope": "GLOBAL", "timeout_seconds": 30},
            {"id": "shadow_ok", "kind": "unittest_glob", "target": "test_shadow_ok.py", "patterns": ["other/**"], "subsystems": ["OTHER"], "failure_class": "SUBSYSTEM_REGRESSION", "block_scope": "SUBSYSTEM", "timeout_seconds": 30},
            {"id": "shadow_bad", "kind": "unittest_glob", "target": "test_shadow_bad.py", "patterns": ["other/**"], "subsystems": ["OTHER"], "failure_class": "SUBSYSTEM_REGRESSION", "block_scope": "SUBSYSTEM", "timeout_seconds": 30},
            {"id": "full", "kind": "unittest_glob", "target": "test_*.py", "patterns": [], "subsystems": [], "min_risk": "R5_RELEASE", "sentinel_eligible": False, "failure_class": "GENERAL_REGRESSION", "block_scope": "GLOBAL", "timeout_seconds": 30},
        ],
    })


def cfg(percent=100, max_sentinels=2, exclude=()):
    return CalibrationConfig({
        "schema": "FEDERATION-PROOFOS-SHADOW-CALIBRATION-V1",
        "version": "1.0.0",
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
        "omitted_proof_sample_percent": percent,
        "max_sentinels": max_sentinels,
        "exclude_test_ids": list(exclude),
    })


def manifest(policy: ProofPolicy):
    impact = ImpactCompiler(policy).assess(["app/x.py"])
    return ProofSelector(policy).compile_manifest(base_sha=BASE, head_sha=HEAD, impact=impact)


class CalibrationContractTests(unittest.TestCase):
    def test_selection_is_deterministic_and_omitted_only(self):
        p = tiny_policy(); m = manifest(p); c = cfg()
        a = ShadowCalibrator(policy=p, config=c, repo_root=".").choose(m)
        b = ShadowCalibrator(policy=p, config=c, repo_root=".").choose(m)
        self.assertEqual(a, b)
        omitted = {x.test_id for x in m.omitted_tests}
        self.assertTrue(set(a) <= omitted)
        self.assertNotIn("focused", a)
        self.assertNotIn("full", a)

    def test_exclusion_is_respected(self):
        p = tiny_policy(); m = manifest(p)
        chosen = ShadowCalibrator(policy=p, config=cfg(exclude=("shadow_bad",)), repo_root=".").choose(m)
        self.assertNotIn("shadow_bad", chosen)

    def test_failure_becomes_nonblocking_escape_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "app").mkdir(); (root / "tests").mkdir()
            (root / "app/x.py").write_text("VALUE=1\n")
            (root / "tests/test_focus.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n")
            (root / "tests/test_shadow_ok.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n")
            (root / "tests/test_shadow_bad.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail('shadow')\n")
            p = tiny_policy(); m = manifest(p)
            receipt = ShadowCalibrator(policy=p, config=cfg(), repo_root=root).run(m)
            self.assertEqual("PASS_WITH_ESCAPE_CANDIDATE", receipt.status)
            self.assertEqual(1, len(receipt.escape_candidates))
            self.assertEqual("SELECTOR_ESCAPE_CANDIDATE", receipt.escape_candidates[0]["classification"])
            self.assertFalse(receipt.escape_candidates[0]["may_auto_block_current_admission"])

    def test_clean_shadow_is_not_overcertified(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "app").mkdir(); (root / "tests").mkdir()
            (root / "app/x.py").write_text("VALUE=1\n")
            for name in ("focus", "shadow_ok", "shadow_bad"):
                (root / f"tests/test_{name}.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n")
            p = tiny_policy(); m = manifest(p)
            receipt = ShadowCalibrator(policy=p, config=cfg(), repo_root=root).run(m)
            self.assertEqual("PASS_NO_ESCAPE", receipt.status)
            self.assertEqual((), receipt.escape_candidates)

    def test_external_effect_or_authority_expansion_rejected(self):
        base = {
            "schema": "FEDERATION-PROOFOS-SHADOW-CALIBRATION-V1",
            "version": "1.0.0",
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "omitted_proof_sample_percent": 5,
            "max_sentinels": 2,
        }
        bad = dict(base); bad["external_effect"] = True
        self.assertRaises(CalibrationError, CalibrationConfig, bad)
        bad = dict(base); bad["authority_ceiling"] = "A3_EXTERNAL_WRITE"
        self.assertRaises(CalibrationError, CalibrationConfig, bad)

    def test_sample_bounds_rejected(self):
        base = {
            "schema": "FEDERATION-PROOFOS-SHADOW-CALIBRATION-V1",
            "version": "1.0.0",
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "omitted_proof_sample_percent": 101,
            "max_sentinels": 2,
        }
        self.assertRaises(CalibrationError, CalibrationConfig, base)


class RepositoryIntegrationTests(unittest.TestCase):
    def test_current_config_is_nonblocking_and_bounded(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "proofos_omega/shadow_calibration_v1.json"
        if not path.exists(): self.skipTest("config not present")
        c = CalibrationConfig.from_path(path)
        self.assertEqual(5, c.percent)
        self.assertLessEqual(c.max_sentinels, 2)
        self.assertIn("phoenix_exports", c.exclude_test_ids)

    def test_airlock_runs_shadow_after_blocking_proof_court(self):
        root = Path(__file__).resolve().parents[1]
        wf = root / ".github/workflows/github-airlock.yml"
        if not wf.exists(): self.skipTest("workflow-free export")
        text = wf.read_text(encoding="utf-8")
        self.assertIn("Run non-blocking ProofOS shadow selector calibration", text)
        self.assertIn("proofos-shadow-calibration.json", text)
        self.assertLess(text.index("Execute manifest-selected proof court"), text.index("Run non-blocking ProofOS shadow selector calibration"))
        self.assertNotIn("continue-on-error: true", text)


if __name__ == "__main__":
    unittest.main()
