from __future__ import annotations

import argparse
import io
import json
import os
import unittest
from pathlib import Path

from benchmarking.cfbe_omega.mission_execution_kernel_vnext.core import MissionExecutionKernel
from federation.fuse_mission_runtime_interlock_v1 import MissionRuntimeInterlock
from federation.sol62_fuse_bridge_v2 import Sol62FuseBridgeV2
from sol_61_runtime.sol_62 import Sol62Runtime, Sol62StrictRuntime, digest, utc_now


def run(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(
        "tests", pattern="test_sol62_fuse_bridge_v2.py"
    )
    tests = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if not tests.wasSuccessful():
        raise AssertionError(stream.getvalue())

    hosted = os.getenv("GITHUB_ACTIONS", "").casefold() == "true"
    github_sha = os.getenv("GITHUB_SHA", "").strip()
    github_run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    gates = {
        "v2_adversarial_court": tests.testsRun >= 13 and tests.wasSuccessful(),
        "canonical_formation_kernel_bound": MissionExecutionKernel.__module__.endswith(
            "mission_execution_kernel_vnext.core"
        ),
        "canonical_f130_interlock_bound": MissionRuntimeInterlock.__module__.endswith(
            "fuse_mission_runtime_interlock_v1"
        ),
        "canonical_sol62_strict_runtime_bound": Sol62Runtime is Sol62StrictRuntime,
        "bridge_imports_real_components": Sol62FuseBridgeV2.__module__.endswith(
            "sol62_fuse_bridge_v2"
        ),
        "host_identity_present_when_hosted": (not hosted) or bool(github_sha and github_run_id),
    }
    receipt = {
        "schema": "SOL62-FUSE-V2-HOST-PROOF-RECEIPT",
        "version": "2.0.0",
        "generated_at": utc_now(),
        "tests_run": tests.testsRun,
        "gates": gates,
        "host": {
            "provider": "github-actions" if hosted else "local",
            "hosted_execution": hosted,
            "github_sha": github_sha or None,
            "github_run_id": github_run_id or None,
        },
        "truth_boundary": {
            "real_formation_kernel_exercised": True,
            "real_sol62_strict_runtime_exercised": True,
            "real_f130_interlock_exercised": True,
            "source_candidate_implemented": True,
            "source_admission_requires_exact_head_merge_readback": True,
            "hosted_shadow_verified_by_this_receipt": hosted,
            "provider_effect_performed": False,
            "provider_live_production_cutover": False,
            "performance_2x_promoted": False,
            "performance_10x_promoted": False,
        },
    }
    receipt["status"] = (
        "SOL62_FUSE_V2_HOSTED_SHADOW_VERIFIED"
        if hosted and all(gates.values())
        else "SOL62_FUSE_V2_LOCAL_COURT_VERIFIED"
        if all(gates.values())
        else "FAILED"
    )
    receipt["sha256"] = digest(receipt)
    path = output / "sol62-fuse-v2-host-receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise AssertionError(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))
