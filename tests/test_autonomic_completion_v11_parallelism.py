import threading
import time
from pathlib import Path
import tempfile

import pytest

from federation.autonomic_completion_v5 import (
    AutonomicCompletionKernel,
    ExecutionContext,
    PARALLEL_SAFE_EFFECT_CLASSES,
    RuntimeMode,
    WorkPacket,
)
from federation.federation_learning_v1 import FederationLearningLedger
from federation.prompt_scientist_v2 import PromptGenome
from federation.run_store_v1 import RunStore


def genome():
    return PromptGenome("V11", "V5", {
        "OWNER_AUTHORITY":"IMMUTABLE",
        "PROOF_FLOOR":"IMMUTABLE",
        "SECURITY_FLOOR":"IMMUTABLE",
        "PRIVACY_FLOOR":"IMMUTABLE",
        "TRUTH_BOUNDARIES":"IMMUTABLE",
        "PROVIDER_NATIVE_PROOF":"IMMUTABLE",
        "ROLLBACK_REQUIREMENTS":"IMMUTABLE",
        "PARALLELISM_POLICY":"MAX_COLLISION_SAFE",
    })


@pytest.mark.parametrize("effect_class", sorted(PARALLEL_SAFE_EFFECT_CLASSES))
def test_v11_safe_effect_classes_are_parallel_eligible(effect_class):
    assert WorkPacket("P", effect_class=effect_class).parallel_eligible is True


@pytest.mark.parametrize("effect_class", [
    "CANONICAL_WRITE", "PROVIDER_MUTATION", "EXTERNAL_EFFECT",
    "IAM_SECURITY_MUTATION", "PRODUCTION_TRAFFIC", "SPEND",
])
def test_v11_consequential_or_shared_effect_classes_do_not_gain_parallel_authority(effect_class):
    assert WorkPacket("P", effect_class=effect_class).parallel_eligible is False


def test_v11_mixed_safe_classes_fan_out_in_one_wave():
    with tempfile.TemporaryDirectory() as td:
        kernel=AutonomicCompletionKernel(
            RunStore(Path(td)/"run.db"),
            FederationLearningLedger(Path(td)/"learn.jsonl"),
        )
        classes=("READ_ONLY","LOCAL_REVERSIBLE","BUILD_TEST","CI_VALIDATION","PROVIDER_READ")
        packets=tuple(
            WorkPacket(f"P{i}", collision_keys=(f"k{i}",), effect_class=effect_class)
            for i,effect_class in enumerate(classes)
        )
        ctx=ExecutionContext(
            "M-V11-PARALLEL","BUILD","PRODUCTION_VERIFIED",RuntimeMode.CURRENT_RUN,
            genome(),packets,maximum_parallelism=5,
        )
        guard=threading.Lock(); active=0; peak=0
        def execute(packet):
            nonlocal active,peak
            with guard:
                active+=1; peak=max(peak,active)
            time.sleep(0.02)
            with guard:
                active-=1
            return True,f"proof:{packet.packet_id}"
        result=kernel.run_cycle(ctx,cycle=1,packet_executor=execute)
        assert result.telemetry.executed_packets==5
        assert result.telemetry.achieved_parallelism==5
        assert peak >= 3
        assert all(packet.done for packet in result.context.packets)


def test_v11_collision_keys_still_serialize_conflicting_safe_packets():
    with tempfile.TemporaryDirectory() as td:
        kernel=AutonomicCompletionKernel(
            RunStore(Path(td)/"run.db"),
            FederationLearningLedger(Path(td)/"learn.jsonl"),
        )
        packets=(
            WorkPacket("A",collision_keys=("shared",),effect_class="BUILD_TEST"),
            WorkPacket("B",collision_keys=("shared",),effect_class="CI_VALIDATION"),
            WorkPacket("C",collision_keys=("other",),effect_class="PROVIDER_READ"),
        )
        ctx=ExecutionContext("M-COLLISION","BUILD","PRODUCTION_VERIFIED",RuntimeMode.CURRENT_RUN,genome(),packets)
        result=kernel.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,p.packet_id))
        done={p.packet_id for p in result.context.packets if p.done}
        assert "C" in done
        assert len(done & {"A","B"})==1
        assert result.telemetry.executed_packets==2


def test_v11_parallel_safe_work_runs_before_serial_effect_and_does_not_inherit_authority():
    with tempfile.TemporaryDirectory() as td:
        kernel=AutonomicCompletionKernel(
            RunStore(Path(td)/"run.db"),
            FederationLearningLedger(Path(td)/"learn.jsonl"),
        )
        packets=(
            WorkPacket("BUILD",collision_keys=("build",),effect_class="BUILD_TEST"),
            WorkPacket("READ",collision_keys=("provider-read",),effect_class="PROVIDER_READ"),
            WorkPacket("WRITE",collision_keys=("canonical",),effect_class="CANONICAL_WRITE"),
            WorkPacket("EFFECT",collision_keys=("provider",),effect_class="PROVIDER_MUTATION",owner_reserved=True),
        )
        ctx=ExecutionContext(
            "M-SERIAL-GUARD","BUILD","PRODUCTION_VERIFIED",RuntimeMode.CURRENT_RUN,
            genome(),packets,owner_effect_authority=False,
        )
        result=kernel.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,p.packet_id))
        done={p.packet_id for p in result.context.packets if p.done}
        assert done=={"BUILD","READ"}
        assert result.telemetry.executed_packets==2
        assert next(p for p in result.context.packets if p.packet_id=="WRITE").done is False
        assert next(p for p in result.context.packets if p.packet_id=="EFFECT").done is False
