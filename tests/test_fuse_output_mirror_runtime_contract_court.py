from __future__ import annotations

import runpy
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

SOURCE_CONTRACT_MODULES = [
    "test_fuse_24x7_autonomy_v1.py",
    "test_fuse_autonomous_improvement_loop_v1.py",
    "test_fuse_bootstrap_memory_self_improvement_v1.py",
    "test_fuse_chatgpt_failure_repair_v1.py",
    "test_fuse_constraint_routing_v1.py",
    "test_fuse_directive_fidelity_v1.py",
    "test_fuse_forest_first_anticipatory_v1.py",
    "test_fuse_parallel_frontend_continuity_v1.py",
    "test_fuse_unified_capability_fabric_v1.py",
    "test_output_mirror_source_contract_v1.py",
    "test_output_mirror_v2_developer1000_court.py",
    "test_output_mirror_v3_power_diary.py"
]

class FuseOutputMirrorRuntimeContractCourt(unittest.TestCase):
    def test_all_source_contract_functions_execute(self) -> None:
        total = 0
        for filename in SOURCE_CONTRACT_MODULES:
            namespace = runpy.run_path(
                str(TESTS / filename),
                run_name=f"__fuse_proof_{Path(filename).stem}",
            )
            functions = sorted(
                (name, fn)
                for name, fn in namespace.items()
                if name.startswith("test_") and callable(fn)
            )
            self.assertTrue(functions, f"NO_TEST_FUNCTIONS_DISCOVERED:{filename}")
            for name, fn in functions:
                with self.subTest(file=filename, test=name):
                    fn()
                    total += 1
        self.assertGreaterEqual(total, 24)

if __name__ == "__main__":
    unittest.main()
