from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sol_61_runtime.fdof_bubbles_host_bridge_v1 import (
    ECHO,
    IDEMPOTENCY_KEY,
    run_hosted_bridge,
)
from sol_61_runtime.fdof_hosted_state_v1 import export_capsule, write_capsule
from sol_61_runtime.sol_62_frontier_primitives import AuthorityLease
from sol_61_runtime.sol_62_runtime import Sol62Runtime


SOURCE_SHA = "8" * 40


class FdofBubblesHostBridgeV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def prepare_inputs(self) -> tuple[Path, Path]:
        seed = Sol62Runtime(self.root / "seed-runtime")
        try:
            seed.control.cas_put(
                "fdof.test", "seed", {"cross_run": True}, expected_version=0
            )
            seed.control.append_event(
                "mission-seed", "FDOF_HOST_BRIDGE_TEST_SEEDED", {"cross_run": True}
            )
            seed.create_authority_lease(
                AuthorityLease(
                    lease_id="authority-must-not-transfer",
                    action="publish",
                    target="repo/main",
                    actor="seed-worker",
                    source_version=SOURCE_SHA,
                    issued_at_epoch=100,
                    expires_at_epoch=200,
                    nonce="test-nonce",
                )
            )
            capsule = export_capsule(seed, source_version=SOURCE_SHA)
        finally:
            seed.close()

        capsule_path = self.root / "capsule.json"
        write_capsule(str(capsule_path), capsule)
        receipt_path = self.root / "restore-receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "state": "HOSTED_SEPARATE_RUN_STATE_CONTINUITY_VERIFIED",
                    "trigger_head_sha": SOURCE_SHA,
                    "capsule_sha256": capsule["capsule_sha256"],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return capsule_path, receipt_path

    def test_restored_state_gates_bubbles_canary_and_exports_next_capsule(self) -> None:
        capsule_path, receipt_path = self.prepare_inputs()
        output = self.root / "output"
        result = run_hosted_bridge(
            capsule_path=capsule_path,
            restore_receipt_path=receipt_path,
            runtime_root=self.root / "bridge-runtime",
            output_dir=output,
            source_sha=SOURCE_SHA,
            now_epoch=10_000,
        )
        self.assertEqual(result["state"], "HOSTED_FDOF_BUBBLES_BRIDGE_VERIFIED")
        self.assertEqual(result["provider_execution_state"], "VERIFIED")
        self.assertEqual(result["health_state"], "HEALTHY")
        self.assertTrue(result["authority_leases_absent"])
        self.assertFalse(result["provider_effect"])
        self.assertFalse(result["external_effect"])
        self.assertFalse(result["provider_authority"])
        self.assertFalse(result["persistent_24x7_host"])
        self.assertEqual(result["bubbles_semantic_state"], "BUBBLES_LOCAL_COMMAND_BUS_CANARY_VERIFIED")
        self.assertTrue(all(result["bubbles_semantic_checks"].values()))
        self.assertTrue((output / "bridge-receipt.json").exists())
        self.assertTrue((output / "next-capsule.json").exists())

        next_capsule = json.loads((output / "next-capsule.json").read_text(encoding="utf-8"))
        self.assertNotIn("authority_leases", next_capsule["tables"])
        idem_rows = next_capsule["tables"]["idempotency"]["rows"]
        self.assertTrue(any(row["idem_key"] == IDEMPOTENCY_KEY for row in idem_rows))
        exec_rows = [
            row for row in next_capsule["tables"]["state"]["rows"]
            if row["namespace"] == "fdof.provider_execution"
        ]
        self.assertTrue(exec_rows)
        self.assertIn('"state":"VERIFIED"', exec_rows[0]["value_json"])

    def test_wrong_restore_receipt_state_fails_closed(self) -> None:
        capsule_path, receipt_path = self.prepare_inputs()
        receipt_path.write_text(
            json.dumps(
                {
                    "state": "UNVERIFIED",
                    "trigger_head_sha": SOURCE_SHA,
                    "capsule_sha256": json.loads(capsule_path.read_text())["capsule_sha256"],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(Exception):
            run_hosted_bridge(
                capsule_path=capsule_path,
                restore_receipt_path=receipt_path,
                runtime_root=self.root / "blocked-runtime",
                output_dir=self.root / "blocked-output",
                source_sha=SOURCE_SHA,
                now_epoch=10_000,
            )


if __name__ == "__main__":
    unittest.main()
