from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from federation.self_hosting_rd_challenger_v1 import (
    ArtifactExpectation,
    ChallengerPlan,
    ChallengerTaskSpec,
    execute_challenger,
)

ROOT = Path(__file__).resolve().parents[1]


def _goal_digest() -> str:
    return sha256(b"owner-goal").hexdigest()


def _workspace(root: Path) -> str:
    (root / "sample.py").write_text("def add(a,b):\n    return a+b\n", encoding="utf-8")
    (root / "test_sample.py").write_text(
        "import unittest\nfrom sample import add\n"
        "class T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(add(2,3),5)\n"
        "if __name__ == '__main__': unittest.main()\n",
        encoding="utf-8",
    )
    return sha256((root / "sample.py").read_bytes()).hexdigest()


def _plan(expected_sha: str, dependencies: tuple[str, ...] = ()) -> ChallengerPlan:
    return ChallengerPlan(
        candidate_id="CHALLENGER-1",
        source_epoch="source:example",
        owner_goal_digest=_goal_digest(),
        build_tasks=(ChallengerTaskSpec("BUILD","compile",("python3","-m","compileall","-q",".")),),
        test_tasks=(ChallengerTaskSpec("TEST","unit",("python3","-m","unittest","-q","test_sample.py")),),
        artifacts=(ArtifactExpectation("sample.py", expected_sha),),
        external_runtime_dependencies=dependencies,
        rollback_ref="rollback:sample-v0",
        disconnected_required=True,
    )


class SelfHostingRDChallengerV1Tests(unittest.TestCase):
    def test_local_challenger_reaches_ready_without_maturity_inheritance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            expected=_workspace(root)
            receipt=execute_challenger(_plan(expected),root)
            self.assertTrue(receipt.challenger_ready)
            self.assertTrue(receipt.all_tasks_succeeded)
            self.assertTrue(receipt.reproducible_artifacts)
            self.assertTrue(receipt.dependency_exit)
            self.assertTrue(receipt.disconnected_rebuild)
            self.assertTrue(receipt.rollback_ready)
            self.assertFalse(receipt.provider_effect_authorized)
            self.assertFalse(receipt.production_activation_authorized)
            self.assertFalse(receipt.physical_device_proof)
            self.assertFalse(receipt.persistent_host_proof)
            self.assertFalse(receipt.matched_eval_proven)
            self.assertFalse(receipt.owner_value_proven)
            self.assertFalse(receipt.independent_judge_ack)

    def test_reproducibility_fingerprint_is_stable_across_fresh_workspaces(self):
        fingerprints=[]
        for _ in range(2):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)
                expected=_workspace(root)
                fingerprints.append(execute_challenger(_plan(expected),root).reproducibility_fingerprint)
        self.assertEqual(fingerprints[0],fingerprints[1])

    def test_inline_python_is_forbidden(self):
        task=ChallengerTaskSpec("TEST","unsafe",("python3","-c","print(1)"))
        with self.assertRaisesRegex(PermissionError,"INLINE_CODE"):
            task.validate()

    def test_network_reference_is_forbidden(self):
        task=ChallengerTaskSpec("TEST","net",("python3","-m","unittest","https://example.invalid/test.py"))
        with self.assertRaisesRegex(PermissionError,"NETWORK_REFERENCE"):
            task.validate()

    def test_external_runtime_dependency_holds_readiness(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            expected=_workspace(root)
            receipt=execute_challenger(_plan(expected,("vendor-runtime",)),root)
            self.assertFalse(receipt.dependency_exit)
            self.assertFalse(receipt.challenger_ready)

    def test_artifact_mismatch_holds_readiness(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            _workspace(root)
            receipt=execute_challenger(_plan("0"*64),root)
            self.assertFalse(receipt.reproducible_artifacts)
            self.assertFalse(receipt.challenger_ready)

    def test_workspace_escape_is_forbidden(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            expected=_workspace(root)
            p=_plan(expected)
            bad=ChallengerPlan(
                candidate_id=p.candidate_id,source_epoch=p.source_epoch,owner_goal_digest=p.owner_goal_digest,
                build_tasks=p.build_tasks,test_tasks=p.test_tasks,
                artifacts=(ArtifactExpectation("../escape.py",expected),),
                external_runtime_dependencies=(),rollback_ref=p.rollback_ref,disconnected_required=True,
            )
            with self.assertRaisesRegex(ValueError,"WORKSPACE_ESCAPE"):
                execute_challenger(bad,root)

    def test_governance_keeps_local_evidence_separate_from_value(self):
        g=json.loads((ROOT/"governance/self_hosting_rd_challenger_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(g["effect_ceiling"],"LOCAL_WORKSPACE")
        self.assertIn("inline-python-c",g["forbidden"])
        self.assertIn("network-url",g["forbidden"])
        self.assertTrue(g["maturity_boundary"]["challenger_ready_is_source_independent_local_evidence_only"])
        self.assertFalse(g["maturity_boundary"]["matched_eval_proven"])
        self.assertFalse(g["maturity_boundary"]["owner_value_proven"])
        self.assertFalse(g["maturity_boundary"]["independent_judge_ack"])

if __name__ == "__main__":
    unittest.main()
