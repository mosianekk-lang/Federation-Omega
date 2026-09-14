#!/usr/bin/env python3
"""Exhaustive inherited and additive release verifier for BCO-Prime v3.1."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarking.cfbe_omega import bco_prime_baseline_registry_v3_1 as baseline
from benchmarking.cfbe_omega import bco_prime_drift_harvest_v3_1 as drift
from benchmarking.cfbe_omega import bco_prime_successor_v3_1 as successor
from scripts import verify_bco_prime_successor_v3 as verify_v3


SEALED_V2_SHA256 = "e7bc80b11cf6f82ebc84f757a1c62015f4e3fc15979aa18767921b5c4866cf1a"
SEALED_V3_SHA256 = "4dc2a02c8501a2042fd09a58c51a61045f9c7aa07864f75d10b59a6d8953903e"
SOURCE = "# SPDX-License-Identifier: MIT\nimport hashlib\ndef verify_payload(value):\n    return hashlib.sha256(repr(value).encode()).hexdigest()\n"


def _assert_receipt(receipt: Mapping[str, Any], operation: str) -> None:
    if receipt.get("operation") != operation or receipt.get("namespace") != "successor_v3_1":
        raise AssertionError(f"receipt namespace or operation mismatch: {operation}")
    if receipt.get("providerEffectAuthorized") is not False or receipt.get("stablePromotionAuthorized") is not False:
        raise AssertionError("effect or stable promotion boundary escaped")


def verify(workspace_root: Path) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    inherited = verify_v3.verify(workspace_root / "inherited-v3")
    if inherited["state"] != "PASS":
        raise AssertionError("inherited v3 verification failed")
    with tempfile.TemporaryDirectory(prefix="bco-v31-proof-", dir=workspace_root) as directory:
        run_root = Path(directory)
        monitored = run_root / "monitored"
        monitored.mkdir()
        (monitored / "capability.py").write_text(SOURCE, encoding="utf-8")
        predecessor = run_root / "predecessor.zip"
        with zipfile.ZipFile(predecessor, "w") as handle:
            handle.writestr("upstream/capability.py", SOURCE)
        policies = {"mode": "strict", "stablePromotionAuthorized": False}
        capabilities = [{"id": "capability-a", "state": "SHADOW_ONLY"}]
        expected_tests = {"repository": "PASS"}
        expected_results = {"canonical_core": 100, "v3_operations": 14, "v3_1_operations": 9}
        envelope = baseline.create_signed_baseline(
            root=monitored,
            relative_paths=["capability.py"],
            predecessor_archive=predecessor,
            policies=policies,
            capabilities=capabilities,
            expected_tests=expected_tests,
            expected_results=expected_results,
            generation=1,
            parent_baseline_sha256=SEALED_V3_SHA256,
            signing_seed=b"v" * 32,
            key_id="release-verifier-fixture",
        )
        baseline.write_baseline_atomic(run_root / "baseline.json", envelope)
        registry = successor.SuccessorRegistryV31(run_root)
        receipts: list[dict[str, Any]] = []

        def execute(operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
            receipt = registry.execute(operation, payload or {})
            _assert_receipt(receipt, operation)
            receipts.append(receipt)
            return receipt

        execute("BCO-PRIME-V3-1-MANIFEST")
        fingerprint = envelope["signature"]["public_key_fingerprint"]
        verified = execute(
            "BCO-PRIME-V3-1-BASELINE-VERIFY",
            {"baseline_path": "baseline.json", "expected_public_key_fingerprint": fingerprint, "minimum_generation": 1, "expected_parent_baseline_sha256": SEALED_V3_SHA256},
        )["output"]
        if verified["valid"] is not True:
            raise AssertionError("signed baseline verification failed")
        drift_payload = {
            "baseline_path": "baseline.json",
            "monitored_root": "monitored",
            "expected_public_key_fingerprint": fingerprint,
            "minimum_generation": 1,
            "policies": policies,
            "capabilities": capabilities,
            "test_results": expected_tests,
            "result_assertions": expected_results,
            "coverage_complete": True,
        }
        report = execute("BCO-PRIME-V3-1-DRIFT-CHECK", drift_payload)["output"]
        if report["state"] != "NO_DRIFT":
            raise AssertionError("clean baseline drifted")
        scan = execute(
            "BCO-PRIME-V3-1-INCREMENTAL-SCAN",
            {
                "scan_root": "monitored",
                "source_id": "source-1",
                "tenant_id": "tenant-1",
                "matter_id": "matter-1",
                "baseline_sha256": envelope["body_sha256"],
                "cancelled": False,
            },
        )["output"]
        if scan["state"] != "COMPLETE" or not scan["records"]:
            raise AssertionError("incremental scan failed")
        difference = execute("BCO-PRIME-V3-1-HARVEST-DIFF", {"previous": scan, "current": scan})["output"]
        if difference["added_dna_ids"] or difference["removed_dna_ids"]:
            raise AssertionError("unchanged scan produced a DNA delta")
        repair = execute("BCO-PRIME-V3-1-SHADOW-REPAIR-PLAN", {"drift_report": report, "baseline_sha256": envelope["body_sha256"]})["output"]
        if repair["state"] != "NO_REPAIR_REQUIRED" or repair["sourceMutationAuthorized"] is not False:
            raise AssertionError("repair boundary failed")
        scoreboard = execute("BCO-PRIME-V3-1-REGRESSION-SCOREBOARD", {"drift_report": report})["output"]
        if scoreboard["state"] != "PASS":
            raise AssertionError("clean scoreboard failed")
        cycle_result = execute(
            "BCO-PRIME-V3-1-CYCLE-RUN",
            {
                **drift_payload,
                "cycle_root": "cycles",
                "cycle_id": "release-cycle-1",
                "mission_id": "release-proof",
                "mission_version": 1,
                "cancel_token": {"mission_version": 1, "cancelled": False, "cancel_at": []},
                "current_scan": scan,
                "previous_scan": scan,
            },
        )["output"]
        if cycle_result["state"] != "PASS" or cycle_result["commitPerformed"] is not True:
            raise AssertionError("governed cycle failed")
        cycles = run_root / "cycles"
        baseline.write_baseline_atomic(cycles / "baseline.json", envelope)
        target_hash = baseline.digest(envelope)
        rolled_back = execute(
            "BCO-PRIME-V3-1-CONTROL-POINTER-ROLLBACK",
            {
                "control_root": "cycles",
                "expected_current_baseline_sha256": "unused-before-first-pointer",
                "target_baseline_path": "baseline.json",
                "target_baseline_sha256": target_hash,
            },
        )["output"]
        if rolled_back["state"] != "ROLLED_BACK_CONTROL_POINTER_ONLY" or rolled_back["sourceMutationAuthorized"] is not False:
            raise AssertionError("control-only rollback failed")
        if len(receipts) != len(successor.SUCCESSOR_OPERATIONS_V3_1):
            raise AssertionError("v3.1 operation coverage incomplete")
        try:
            registry.execute("BCO-PRIME-V3-1-MANIFEST", {"providerEffectAuthorized": True})
        except successor.SuccessorV31ContractError:
            pass
        else:
            raise AssertionError("effect-key escape was accepted")
        tampered = json.loads(json.dumps(envelope))
        tampered["body"]["policies"]["mode"] = "weak"
        if baseline.verify_signed_baseline(tampered, expected_public_key_fingerprint=fingerprint)["valid"] is not False:
            raise AssertionError("tampered signature was accepted")

    result: dict[str, Any] = {
        "schema": "BCO_PRIME_SUCCESSOR_RELEASE_VERIFICATION_V3_1",
        "state": "PASS",
        "sealedV2Sha256": SEALED_V2_SHA256,
        "sealedV3Sha256": SEALED_V3_SHA256,
        "canonical_core_routes": inherited["canonical_core_routes"],
        "legacy_routes": inherited["legacy_routes"],
        "v2_meta_routes": inherited["v2_meta_routes"],
        "expected_blocked_engine_routes": inherited["expected_blocked_engine_routes"],
        "v3_routes": inherited["successor_routes"],
        "v3_1_routes": len(successor.SUCCESSOR_OPERATIONS_V3_1),
        "canonical_core_invariant_preserved": inherited["canonical_core_invariant_preserved"],
        "runtimeState": "ON_DEMAND_GOVERNED",
        "baselineTrustRootRequired": True,
        "baselineAutoAdvanceAuthorized": False,
        "sourceMutationAuthorized": False,
        "providerEffectAuthorized": False,
        "stablePromotionAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = drift.digest(result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BCO-Prime v3.1 exhaustive release verifier")
    parser.add_argument("--workspace-root", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify(Path(args.workspace_root)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
