from __future__ import annotations

import json
import runpy
import sys
import traceback
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
DIAGNOSTIC_PATH = ROOT / "airlock-output" / "fuse-runtime-contract-diagnostics.json"

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
    "test_output_mirror_v3_power_diary.py",
]

class FuseOutputMirrorRuntimeContractCourt(unittest.TestCase):
    def test_all_source_contract_functions_execute(self) -> None:
        total = 0
        diagnostics = []
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
            if not functions:
                diagnostics.append(
                    {
                        "file": filename,
                        "test": None,
                        "error_type": "NO_TEST_FUNCTIONS_DISCOVERED",
                        "message": "",
                        "traceback_tail": [],
                    }
                )
                continue
            for name, fn in functions:
                total += 1
                try:
                    fn()
                except Exception as exc:
                    diagnostics.append(
                        {
                            "file": filename,
                            "test": name,
                            "error_type": type(exc).__name__,
                            "message": str(exc)[:500],
                            "traceback_tail": traceback.format_exc(limit=4).splitlines()[-12:],
                        }
                    )

        if diagnostics:
            DIAGNOSTIC_PATH.parent.mkdir(parents=True, exist_ok=True)
            DIAGNOSTIC_PATH.write_text(
                json.dumps(
                    {
                        "schema": "FUSE_OUTPUT_MIRROR_RUNTIME_DIAGNOSTIC_V1",
                        "total_functions_executed": total,
                        "failure_count": len(diagnostics),
                        "failures": diagnostics,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            for item in diagnostics:
                print("FUSE_RUNTIME_CONTRACT_DIAGNOSTIC " + json.dumps(item, sort_keys=True), file=sys.stderr)
            self.fail(f"RUNTIME_CONTRACT_FAILURES:{len(diagnostics)}")

        self.assertGreaterEqual(total, 24)

if __name__ == "__main__":
    unittest.main()
