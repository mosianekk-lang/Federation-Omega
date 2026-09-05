from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from bubbles.chat_governor_omega3.state import DurableState, EvidencePointer
from federation.fuse_serving_kernel_v1 import ContextContract, FUSEServingKernelV1, ServingLaneSpec
from federation.mission_ir import MissionIR


class FUSEServingKernelConcurrencyTests(unittest.TestCase):
    def test_parallel_completion_order_cannot_change_proof_projection(self):
        with tempfile.TemporaryDirectory() as temp:
            state = DurableState(str(Path(temp) / "fuse.sqlite3"))
            state.put_evidence(
                EvidencePointer(
                    source_id="canonical",
                    source_type="canonical",
                    title="Canonical source",
                    version="1",
                    verified=True,
                    verified_at="2026-09-05T05:10:00+02:00",
                    sha256="abc",
                )
            )
            kernel = FUSEServingKernelV1(state, max_workers=4)
            context = ContextContract(
                required_source_ids=("canonical",),
                source_versions={"canonical": "1"},
                minimum_verified_sources=1,
            )
            lane_ids = ("alpha", "beta", "gamma", "delta")
            proof_axes = tuple(item.upper() for item in lane_ids)
            lanes = tuple(
                ServingLaneSpec(
                    lane_id=item,
                    action=f"action-{item}",
                    required_proof_axes=(item.upper(),),
                    expected_tool_sequence=(f"tool-{item}",),
                )
                for item in lane_ids
            )
            delays = {"alpha": 0.04, "beta": 0.01, "gamma": 0.03, "delta": 0.02}

            def handler(item: str):
                def run():
                    time.sleep(delays[item])
                    return {
                        "proof_axes": (item.upper(),),
                        "proof_refs": (f"proof://{item}",),
                        "tool_sequence": (f"tool-{item}",),
                    }

                return run

            handlers = {item: handler(item) for item in lane_ids}
            projections = []
            for index in range(3):
                mission = MissionIR(
                    mission_id=f"parallel-{index}",
                    objective="Prove deterministic parallel evidence projection",
                    domain="FUSE",
                    outcome_contract="All parallel lanes complete with stable evidence",
                    source_frontier="test-main",
                    privacy_class="PRIVATE",
                    rights_state="OWNER_CONTROLLED",
                    proof_requirements=proof_axes,
                )
                receipt = kernel.run(
                    mission,
                    context=context,
                    lanes=lanes,
                    handlers=handlers,
                )
                self.assertEqual(receipt.state, "COMPLETE")
                self.assertEqual(receipt.proof_axes, tuple(sorted(proof_axes)))
                self.assertEqual(
                    receipt.proof_refs,
                    tuple(sorted(f"proof://{item}" for item in lane_ids)),
                )
                projections.append((receipt.proof_axes, receipt.proof_refs))

            self.assertTrue(all(item == projections[0] for item in projections[1:]))


if __name__ == "__main__":
    unittest.main()
