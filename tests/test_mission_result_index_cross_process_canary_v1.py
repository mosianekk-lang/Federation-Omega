from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class MissionResultIndexCrossProcessCanaryTests(unittest.TestCase):
    def _run(self, phase: str, state_dir: Path, *, source: str) -> dict[str, object]:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "benchmarking.cfbe_omega.mission_result_index_cross_process_canary_v1",
                phase,
                "--state-dir",
                str(state_dir),
                "--source",
                source,
                "--fresh-until",
                "2026-09-01T00:00:00+02:00",
                "--now",
                "2026-08-31T21:50:00+02:00" if phase == "record" else "2026-08-31T21:51:00+02:00",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        return json.loads(process.stdout.strip())

    def test_process_b_reuses_process_a_result_without_recomputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            source = "main@hosted-synthetic-cross-process-v1"

            recorded = self._run("record", state_dir, source=source)
            reused = self._run("lookup", state_dir, source=source)

            self.assertEqual("PROCESS_A_RECORD", recorded["phase"])
            self.assertEqual("RECORDED", recorded["lookup_state"])
            self.assertEqual(1, recorded["process_compute_count"])
            self.assertEqual(1, recorded["total_compute_count"])

            self.assertEqual("PROCESS_B_LOOKUP", reused["phase"])
            self.assertEqual("HIT", reused["lookup_state"])
            self.assertTrue(reused["reuse"])
            self.assertTrue(reused["no_recomputation"])
            self.assertEqual(0, reused["process_compute_count"])
            self.assertEqual(1, reused["total_compute_count"])

            self.assertEqual(recorded["cache_key"], reused["cache_key"])
            self.assertEqual(recorded["result_sha256"], reused["result_sha256"])
            self.assertEqual(recorded["proof_refs"], reused["proof_refs"])
            self.assertEqual(1, reused["index_record_count"])
            self.assertFalse(reused["payload_blob_persisted"])
            self.assertFalse(reused["provider_effect_authorized"])
            self.assertFalse(reused["authority_inherited"])
            self.assertEqual(0, reused["external_effects"])

            compute_witness = json.loads((state_dir / "compute-witness.json").read_text(encoding="utf-8"))
            self.assertEqual(1, compute_witness["compute_count"])

    def test_process_b_source_drift_cannot_reuse_process_a_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            self._run("record", state_dir, source="main@hosted-synthetic-cross-process-v1")
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "benchmarking.cfbe_omega.mission_result_index_cross_process_canary_v1",
                    "lookup",
                    "--state-dir",
                    str(state_dir),
                    "--source",
                    "main@changed",
                    "--fresh-until",
                    "2026-09-01T00:00:00+02:00",
                    "--now",
                    "2026-08-31T21:51:00+02:00",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, process.returncode)
            self.assertIn("CROSS_PROCESS_CANARY_REUSE_FAILED:MISS", process.stderr)
            compute_witness = json.loads((state_dir / "compute-witness.json").read_text(encoding="utf-8"))
            self.assertEqual(1, compute_witness["compute_count"])


if __name__ == "__main__":
    unittest.main()
