from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from proofos_omega import changed_paths_from_git


def _git(root: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if p.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {p.stderr}")
    return p.stdout.strip()


class ProofOSDeletionImpactRegressionTests(unittest.TestCase):
    def test_deletion_only_diff_is_a_changed_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git(root, "init", "-q")
            _git(root, "config", "user.name", "ProofOS Regression")
            _git(root, "config", "user.email", "proofos-regression@example.invalid")

            sentinel = root / "NONEXISTENT"
            sentinel.write_text("accidental direct-main sentinel\n", encoding="utf-8")
            _git(root, "add", "NONEXISTENT")
            _git(root, "commit", "-qm", "fixture: add accidental sentinel")
            base_sha = _git(root, "rev-parse", "HEAD")

            sentinel.unlink()
            _git(root, "add", "-A")
            _git(root, "commit", "-qm", "fixture: delete accidental sentinel")
            head_sha = _git(root, "rev-parse", "HEAD")

            self.assertEqual(
                ["NONEXISTENT"],
                changed_paths_from_git(root, base_sha, head_sha),
            )


if __name__ == "__main__":
    unittest.main()
