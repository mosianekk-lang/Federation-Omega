from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from artifact_lineage import (  # noqa: E402
    clean_start_receipt,
    guard_state,
    rollback_drill,
    tree_sha256,
    verify_matter_state_hash,
)
from proofloop import run_bounded_cycle  # noqa: E402


class ArtifactLineageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = (
            HERE / "config" / "mpmb1435_26_control_manifest.json"
        )

    def _state(self, root: Path, suffix: str) -> Path:
        state = root / "state"
        previous = os.environ.get("EVIDENCEOPS_CYCLE_SUFFIX")
        os.environ["EVIDENCEOPS_CYCLE_SUFFIX"] = suffix
        try:
            clean_start_receipt(
                state,
                "unit-test clean start",
                "unit-test",
                "pull_request",
            )
            run_bounded_cycle(self.manifest, state)
        finally:
            if previous is None:
                os.environ.pop("EVIDENCEOPS_CYCLE_SUFFIX", None)
            else:
                os.environ["EVIDENCEOPS_CYCLE_SUFFIX"] = previous
        return state

    def test_state_guard_accepts_verified_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = self._state(Path(temporary), "guard-valid")
            receipt = guard_state(state)
            self.assertEqual(receipt["external_effects"], 0)
            self.assertEqual(
                verify_matter_state_hash(state),
                receipt["matter_twin_state_sha256"],
            )

    def test_state_guard_rejects_tampered_matter_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = self._state(Path(temporary), "guard-tamper")
            path = state / "matter_twin.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["facts"]["F-MPMB1435-CORE-IDENTITY"][
                "proposition"
            ] = "tampered"
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                verify_matter_state_hash(state)

    def test_rollback_drill_restores_exact_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = self._state(Path(temporary), "rollback")
            before = tree_sha256(state, {"rollback_receipt.json"})
            receipt = rollback_drill(state)
            after = tree_sha256(state, {"rollback_receipt.json"})
            self.assertEqual(before, after)
            self.assertEqual(
                receipt["state"],
                "ROLLBACK_RESTORE_SEMANTIC_READBACK_VERIFIED",
            )
            self.assertTrue(receipt["semantic_readback"])
            self.assertEqual(receipt["external_effects"], 0)
            guard_state(state)

    def test_clean_start_receipt_is_hash_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "state"
            receipt = clean_start_receipt(
                state,
                "no provider artifact",
                "test-branch",
                "pull_request",
            )
            self.assertEqual(
                receipt["state"], "NO_PRIOR_ARTIFACT_CLEAN_START"
            )
            self.assertEqual(receipt["external_effects"], 0)


if __name__ == "__main__":
    unittest.main()
