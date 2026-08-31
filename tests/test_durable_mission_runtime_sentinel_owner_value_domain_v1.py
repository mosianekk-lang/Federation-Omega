import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


DOMAIN_HEAD = "e" * 40
MISSION_SOURCE = f"sentinel-owner-value-shadow@{DOMAIN_HEAD}"


PROCESS_A = rf'''
import json
import os
from pathlib import Path
from federation.mission_ir import MissionIR
from federation.sentinel_omega.owner_value_ingress import OwnerValueMissionObservationAdapter
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import WorkItem, WorkStatus

root = Path(os.environ["BCO_ROOT"])
witness = root / "baseline-execution-count.txt"
artifact = root / "baseline-owner-value.json"
mission = MissionIR(
    mission_id="BCO-SENTINEL-OV-001",
    objective="Prove the Sentinel owner-value ingress pipeline survives a whole-mission restart.",
    domain="SENTINEL_OWNER_VALUE",
    outcome_contract="One proof-bound synthetic owner-value pair compiled after restart.",
    source_frontier="{MISSION_SOURCE}",
    privacy_class="PUBLIC",
    rights_state="NOT_APPLICABLE",
    effect_class="NO_EFFECT",
    rollback_required=False,
    proof_requirements=("READBACK",),
).normalized()
runtime = DurableMissionRuntimeV1(
    root,
    source_frontier="{MISSION_SOURCE}",
    policy_sha256="sentinel-owner-value-policy-v1",
    environment_sha256="python-domain-court-v1",
)
runtime.open(mission, required_proof_axes=("source",), trace_id="trace-sentinel-ov-a")
runtime.set_work_item(
    mission.mission_id,
    WorkItem.create(work_id="BASELINE", lane="sentinel", objective="Normalize one synthetic baseline owner-value fixture"),
)
baseline_mapping = {{
    "observation_id": "synthetic-baseline-1",
    "pair_id": "synthetic-pair-1",
    "variant": "BASELINE",
    "mission_class": "BCO_SENTINEL_DOMAIN_CANARY",
    "mission_id": "synthetic-owner-value-mission-1",
    "task_signature": "synthetic-owner-value-task-v1",
    "oracle_id": "synthetic-owner-value-oracle-v1",
    "source_head_sha": "{DOMAIN_HEAD}",
    "observed_at": "2026-08-31T22:50:00+02:00",
    "accepted": True,
    "verified_output_ratio": 1.0,
    "owner_intervention_seconds": 180.0,
    "owner_intervention_count": 3,
    "clarification_count": 2,
    "correction_count": 1,
    "elapsed_seconds": 420.0,
    "independent_readback": True,
    "proof_refs": ("proof:synthetic:baseline",),
    "evidence_class": "OBSERVED_OWNER_VALUE",
    "measurement_state": "MEASURED",
}}
record, observation = OwnerValueMissionObservationAdapter.adapt(baseline_mapping)
assert record.court_eligible_single_observation
assert observation.fingerprint == "OWNER_VALUE_MEASURED:BASELINE"
artifact.write_text(json.dumps(record.to_kdv_mapping(), sort_keys=True), encoding="utf-8")
count = int(witness.read_text(encoding="utf-8")) if witness.exists() else 0
count += 1
witness.write_text(str(count), encoding="utf-8")
runtime.update_work_status(
    mission.mission_id,
    "BASELINE",
    WorkStatus.VERIFIED,
    result_refs=("artifact:baseline-owner-value",),
)
runtime.set_work_item(
    mission.mission_id,
    WorkItem.create(
        work_id="PAIR",
        lane="sentinel",
        objective="Compile the synthetic BASELINE/BUBBLES pair after restart",
        dependencies=("BASELINE",),
    ),
)
request = runtime.request(
    mission.mission_id,
    step_id="PAIR",
    request_type="SYNTHETIC_CANDIDATE_FIXTURE",
    target="sentinel-owner-value-domain-court",
    reason="Persist continuation until the candidate fixture is introduced after restart.",
    input_identity={{"pair_id": "synthetic-pair-1", "variant": "BUBBLES"}},
    continuation_key="compile-synthetic-pair",
    expires_at="2026-09-01T02:00:00+02:00",
    created_at="2026-08-31T22:51:00+02:00",
)
checkpoint = runtime.checkpoint(
    mission.mission_id,
    trace_id="trace-sentinel-ov-a",
    created_at="2026-08-31T22:52:00+02:00",
)
print(json.dumps({{
    "effect_count": count,
    "request_id": request.request_id,
    "checkpoint_id": checkpoint.checkpoint_id,
    "observation_fingerprint": observation.fingerprint,
}}))
'''


PROCESS_B = rf'''
import json
import os
from pathlib import Path
from federation.mission_ir import MissionIR
from federation.sentinel_omega.owner_value_ingress import (
    OBSERVED_OWNER_VALUE,
    OwnerValueMissionObservationAdapter,
    OwnerValueMissionRecord,
    OwnerValuePairCompiler,
)
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import ProofEntry, ProofStatus, WorkStatus

root = Path(os.environ["BCO_ROOT"])
witness = root / "baseline-execution-count.txt"
mission = MissionIR(
    mission_id="BCO-SENTINEL-OV-001",
    objective="Prove the Sentinel owner-value ingress pipeline survives a whole-mission restart.",
    domain="SENTINEL_OWNER_VALUE",
    outcome_contract="One proof-bound synthetic owner-value pair compiled after restart.",
    source_frontier="{MISSION_SOURCE}",
    privacy_class="PUBLIC",
    rights_state="NOT_APPLICABLE",
    effect_class="NO_EFFECT",
    rollback_required=False,
    proof_requirements=("READBACK",),
).normalized()
runtime = DurableMissionRuntimeV1(
    root,
    source_frontier="{MISSION_SOURCE}",
    policy_sha256="sentinel-owner-value-policy-v1",
    environment_sha256="python-domain-court-v1",
)
receipt = runtime.resume(mission, now="2026-08-31T22:53:00+02:00", trace_id="trace-sentinel-ov-b")
assert receipt.state == "RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", receipt
assert receipt.ready_work_ids == ("PAIR",), receipt.ready_work_ids
assert len(receipt.pending_request_ids) == 1, receipt.pending_request_ids
assert witness.read_text(encoding="utf-8") == "1"
baseline_payload = json.loads((root / "baseline-owner-value.json").read_text(encoding="utf-8"))
baseline = OwnerValueMissionRecord.from_mapping(baseline_payload)
candidate_mapping = {{
    "observation_id": "synthetic-bubbles-1",
    "pair_id": "synthetic-pair-1",
    "variant": "BUBBLES",
    "mission_class": "BCO_SENTINEL_DOMAIN_CANARY",
    "mission_id": "synthetic-owner-value-mission-1",
    "task_signature": "synthetic-owner-value-task-v1",
    "oracle_id": "synthetic-owner-value-oracle-v1",
    "source_head_sha": "{DOMAIN_HEAD}",
    "observed_at": "2026-08-31T22:54:00+02:00",
    "accepted": True,
    "verified_output_ratio": 1.0,
    "owner_intervention_seconds": 60.0,
    "owner_intervention_count": 1,
    "clarification_count": 1,
    "correction_count": 0,
    "elapsed_seconds": 240.0,
    "independent_readback": True,
    "proof_refs": ("proof:synthetic:candidate",),
    "evidence_class": "OBSERVED_OWNER_VALUE",
    "measurement_state": "MEASURED",
}}
candidate, observation = OwnerValueMissionObservationAdapter.adapt(candidate_mapping)
compiled = OwnerValuePairCompiler.compile(baseline, candidate)
pair = compiled.to_court_mapping()
assert pair["evidence_mode"] == OBSERVED_OWNER_VALUE
assert pair["baseline_owner_minutes"] == 3.0
assert pair["candidate_owner_minutes"] == 1.0
assert len(pair["proof_refs"]) == 2
(root / "compiled-owner-value-pair.json").write_text(json.dumps(pair, sort_keys=True), encoding="utf-8")
pending = runtime.pending_requests(mission.mission_id)
assert len(pending) == 1
runtime.resolve_request(
    mission.mission_id,
    pending[0].request_id,
    response_ref="fixture:synthetic-bubbles-1",
    response_sha256="f" * 64,
    proof_refs=("proof:synthetic:candidate",),
    resolved_at="2026-08-31T22:55:00+02:00",
)
runtime.update_work_status(
    mission.mission_id,
    "PAIR",
    WorkStatus.VERIFIED,
    result_refs=("artifact:compiled-owner-value-pair",),
)
runtime.bind_proof(
    mission.mission_id,
    ProofEntry.create(
        axis="source",
        status=ProofStatus.PROVEN,
        evidence_refs=("proof:synthetic:sentinel-domain-source",),
        observed_at="2026-08-31T22:55:30+02:00",
    ),
)
runtime.verify_success(
    mission.mission_id,
    mission.outcome_contract,
    evidence_refs=("artifact:compiled-owner-value-pair",),
)
closure = runtime.close(
    mission.mission_id,
    receipt_refs=("court:synthetic-sentinel-owner-value-domain",),
)
assert closure["state"] == "CLOSED_VERIFIED"
assert witness.read_text(encoding="utf-8") == "1"
print(json.dumps({{
    "resume_state": receipt.state,
    "effect_count": 1,
    "pending_after": len(runtime.pending_requests(mission.mission_id)),
    "closure_state": closure["state"],
    "pair_evidence_mode": pair["evidence_mode"],
    "candidate_fingerprint": observation.fingerprint,
}}))
'''


PROCESS_C = rf'''
import json
import os
from pathlib import Path
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1

root = Path(os.environ["BCO_ROOT"])
runtime = DurableMissionRuntimeV1(
    root,
    source_frontier="{MISSION_SOURCE}",
    policy_sha256="sentinel-owner-value-policy-v1",
    environment_sha256="python-domain-court-v1",
)
verification = runtime.verify("BCO-SENTINEL-OV-001")
projection = runtime.project("BCO-SENTINEL-OV-001")
assert verification["ledger"]["state"] == "VERIFIED"
assert projection.status == "CLOSED_VERIFIED"
assert len(runtime.pending_requests("BCO-SENTINEL-OV-001")) == 0
assert (root / "baseline-execution-count.txt").read_text(encoding="utf-8") == "1"
print(json.dumps({{
    "ledger": verification["ledger"]["state"],
    "projection": projection.status,
    "effect_count": 1,
    "pending": 0,
}}))
'''


class DurableMissionRuntimeSentinelOwnerValueDomainTests(unittest.TestCase):
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

    def test_sentinel_owner_value_domain_survives_restart_without_replaying_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._run(PROCESS_A, root)
            self.assertEqual(1, first["effect_count"])
            self.assertEqual("OWNER_VALUE_MEASURED:BASELINE", first["observation_fingerprint"])

            second = self._run(PROCESS_B, root)
            self.assertEqual("RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", second["resume_state"])
            self.assertEqual(1, second["effect_count"])
            self.assertEqual(0, second["pending_after"])
            self.assertEqual("CLOSED_VERIFIED", second["closure_state"])
            self.assertEqual("OBSERVED_OWNER_VALUE", second["pair_evidence_mode"])
            self.assertEqual("OWNER_VALUE_MEASURED:BUBBLES", second["candidate_fingerprint"])

            third = self._run(PROCESS_C, root)
            self.assertEqual("VERIFIED", third["ledger"])
            self.assertEqual("CLOSED_VERIFIED", third["projection"])
            self.assertEqual(1, third["effect_count"])
            self.assertEqual(0, third["pending"])


if __name__ == "__main__":
    unittest.main()
