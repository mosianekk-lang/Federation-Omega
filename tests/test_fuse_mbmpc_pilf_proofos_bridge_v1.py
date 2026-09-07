from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


class TestFUSEMBMPCPILFProofOSBridge(unittest.TestCase):
    """Run the exact pytest-style MBMPC × PILF courts through a unittest-admitted bridge.

    ProofOS currently admits deterministic unittest/compileall targets. The source
    courts are pytest-style free functions (including pytest.raises), so stdlib
    unittest discovery sees the files but collects zero cases. This bridge keeps
    the ProofOS execution contract intact while executing the exact source courts
    with the repository-declared pytest runtime.
    """

    def test_exact_mbmpc_pilf_pytest_courts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        targets = (
            "tests/test_fuse_mbmpc_pilf_closure_bridge_v1.py",
            "tests/test_bubbles_mbmpc_pilf_host_binding_v1.py",
        )
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *targets],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=180,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(
            proc.returncode,
            0,
            "MBMPC × PILF exact pytest courts failed:\n" + proc.stdout[-12000:],
        )


if __name__ == "__main__":
    unittest.main()
