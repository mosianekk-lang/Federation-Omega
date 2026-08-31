import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROCESS_A = r'''
import json
import os
from pathlib import Path
from federation.mission_ir import MissionIR
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import WorkItem, WorkStatus

root = Path(os.environ["BCO_ROOT"])
witness = root / "effect-count.txt"
mission = MissionIR(
    mission_id="BCO-XPROC-001",
    objective="Prove one mission survives an operating-system process restart.",
    domain="TEST",
    outcome_contract="One restart-safe mission with no duplicate prior effect.",
    source_frontier="main@xproc",
    privacy_class="PUBLIC",
    rights_state="NOT_APPLICABLE",
    effect_class="READ_ONLY",
    rollback_required=False,
    proof_requirements=("READBACK",),
).normalized()
runtime = DurableMissionRuntimeV1(
    root,
    source_frontier="main@xproc",
    policy_sha256="policy-xproc-v1",
    environment_sha256="env-xproc-v1",
)
runtime.open(mission, required_proof_axes=("source",), trace_id="trace-xproc-a")
runtime.set_work_item(
    mission.mission_id,
    WorkItem.create(work_id="A", lane="effect", objective="Perform one bounded synthetic effect"),
)
count = int(witness.read_text(encoding="utf-8")) if witness.exists() else 0
count += 1
witness.write_text(str(count), encoding="utf-8")
runtime.update_work_status(mission.mission_id, "A", WorkStatus.VERIFIED, result_refs=("effect-witness:1",))
runtime.set_work_item(
    mission.mission_id,
    WorkItem.create(work_id="B", lane="resume", objective="Continue only after restart", dependencies=("A",)),
)
request = runtime.request(
    mission.mission_id,
    step_id="B",
    request_type="CONTINUATION_INPUT",
    target="cross-process-court",
    reason="Persist one pending continuation request across process exit.",
    input_identity={"token": "continue"},
    continuation_key="resume-B",
    expires_at="2026-09-01T01:00:00+02:00",
    created_at="2026-08-31T22:40:00+02:00",
)
checkpoint = runtime.checkpoint(
    mission.mission_id,
    trace_id="trace-xproc-a",
    created_at="2026-08-31T22:41:00+02:00",
)
print(json.dumps({"request_id": request.request_id, "checkpoint_id": checkpoint.checkpoint_id, "effect_count": count}))
'''


PROCESS_B = r'''
import json
import os
from pathlib import Path
from federation.mission_ir import MissionIR
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import WorkStatus

root = Path(os.environ["BCO_ROOT"])
witness = root / "effect-count.txt"
mission = MissionIR(
    mission_id="BCO-XPROC-001",
    objective="Prove one mission survives an operating-system process restart.",
    domain="TEST",
    outcome_contract="One restart-safe mission with no duplicate prior effect.",
    source_frontier="main@xproc",
    privacy_class="PUBLIC",
    rights_state="NOT_APPLICABLE",
    effect_class="READ_ONLY",
    rollback_required=False,
    proof_requirements=("READBACK",),
).normalized()
runtime = DurableMissionRuntimeV1(
    root,
    source_frontier="main@xproc",
    policy_sha256="policy-xproc-v1",
    environment_sha256="env-xproc-v1",
)
receipt = runtime.resume(mission, now="2026-08-31T22:42:00+02:00", trace_id="trace-xproc-b")
projection = runtime.project(mission.mission_id)
pending = runtime.pending_requests(mission.mission_id)
assert receipt.state == "RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", receipt
assert receipt.ready_work_ids == ("B",), receipt.ready_work_ids
assert len(pending) == 1, pending
assert projection.work_items["A"].status == WorkStatus.VERIFIED
assert witness.read_text(encoding="utf-8") == "1"
runtime.resolve_request(
    mission.mission_id,
    pending[0].request_id,
    response_ref="response:xproc",
    response_sha256="d" * 64,
    proof_refs=("proof:xproc",),
    resolved_at="2026-08-31T22:42:30+02:00",
)
runtime.update_work_status(mission.mission_id, "B", WorkStatus.VERIFIED, result_refs=("resume:verified",))
runtime.checkpoint(
    mission.mission_id,
    trace_id="trace-xproc-b",
    created_at="2026-08-31T22:43:00+02:00",
)
print(json.dumps({
    "state": receipt.state,
    "effect_count": int(witness.read_text(encoding="utf-8")),
    "pending_after": len(runtime.pending_requests(mission.mission_id)),
    "work_a": runtime.project(mission.mission_id).work_items["A"].status.value,
    "work_b": runtime.project(mission.mission_id).work_items["B"].status.value,
    "ledger": runtime.verify(mission.mission_id)["ledger"]["state"],
}))
'''


class DurableMissionRuntimeCrossProcessTests(unittest.TestCase):
    def _run(self, code, root):
        env = dict(os.environ)
        env["BCO_ROOT"] = str(root)
        completed = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_process_b_resumes_without_repeating_process_a_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._run(PROCESS_A, root)
            self.assertEqual(1, first["effect_count"])
            second = self._run(PROCESS_B, root)
            self.assertEqual("RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", second["state"])
            self.assertEqual(1, second["effect_count"])
            self.assertEqual(0, second["pending_after"])
            self.assertEqual("VERIFIED", second["work_a"])
            self.assertEqual("VERIFIED", second["work_b"])
            self.assertEqual("VERIFIED", second["ledger"])


if __name__ == "__main__":
    unittest.main()
