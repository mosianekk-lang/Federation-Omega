from pathlib import Path
import tempfile


from federation.autonomic_completion_v5 import (
    AutonomicCompletionKernel, ExecutionContext, OutputClass, RuntimeMode, WorkPacket
)
from federation.federation_learning_v1 import FederationLearningLedger
from federation.prompt_scientist_v2 import PromptGenome
from federation.run_store_v1 import RunStore




def genome():
    return PromptGenome("V5.0.0", "V4.0.0", {
        "OWNER_AUTHORITY":"IMMUTABLE", "PROOF_FLOOR":"IMMUTABLE", "SECURITY_FLOOR":"IMMUTABLE",
        "PRIVACY_FLOOR":"IMMUTABLE", "TRUTH_BOUNDARIES":"IMMUTABLE", "PROVIDER_NATIVE_PROOF":"IMMUTABLE",
        "ROLLBACK_REQUIREMENTS":"IMMUTABLE", "OUTPUT_POLICY":"NON_TERMINAL_PROGRESS_CONTINUES",
        "RUNTIME_REENTRY":"PERSIST_OR_RESUME_CAPSULE", "LEARNING_CALLBACK":"EACH_MATERIAL_CYCLE",
    })




def test_progress_does_not_stop_current_run():
    with tempfile.TemporaryDirectory() as td:
        store=RunStore(Path(td)/"run.db"); learn=FederationLearningLedger(Path(td)/"learn.jsonl")
        k=AutonomicCompletionKernel(store,learn)
        packets=tuple(WorkPacket(f"P{i}", (() if i==0 else (f"P{i-1}",))) for i in range(5))
        ctx=ExecutionContext("M1","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.CURRENT_RUN,genome(),packets,commercial_evidence={"FUNCTIONALITY":True},commercial_applicable_gates=("FUNCTIONALITY",))
        out=k.execute_until_boundary(ctx,lambda p:(True,f"proof:{p.packet_id}"))
        assert len(out)==5
        assert all(r.telemetry.output_class==OutputClass.PROGRESS_UPDATE.value for r in out[:-1])
        assert out[-1].telemetry.output_class==OutputClass.TERMINAL_REPORT.value
        assert out[-1].terminal_state=="COMMERCIAL_READY_VERIFIED"
        assert all(p.done for p in out[-1].context.packets)
        assert learn.verify()==(True,5)




def test_persistent_runner_queues_reentry():
    with tempfile.TemporaryDirectory() as td:
        store=RunStore(Path(td)/"run.db"); learn=FederationLearningLedger(Path(td)/"learn.jsonl")
        k=AutonomicCompletionKernel(store,learn)
        packets=(WorkPacket("A"),WorkPacket("B",("A",)))
        ctx=ExecutionContext("M2","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.PERSISTENT_RUNNER,genome(),packets)
        r=k.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,"proof"))
        assert r.telemetry.output_class==OutputClass.PROGRESS_UPDATE.value
        assert r.reentry_id
        assert store.ready_reentries("M2")




def test_no_runner_emits_resume_capsule_only_at_platform_boundary():
    with tempfile.TemporaryDirectory() as td:
        store=RunStore(Path(td)/"run.db"); learn=FederationLearningLedger(Path(td)/"learn.jsonl")
        k=AutonomicCompletionKernel(store,learn)
        packets=(WorkPacket("A"),WorkPacket("B",("A",)))
        ctx=ExecutionContext("M3","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.NO_PERSISTENT_RUNNER,genome(),packets)
        r=k.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,"proof"),force_platform_boundary=True)
        assert r.telemetry.output_class==OutputClass.RESUME_CAPSULE.value
        assert r.resume_capsule["continuation_instruction"]=="CONSUME_CHECKPOINT_AND_EXECUTE_NEXT_READY_WAVE"
        assert r.reentry_id==""




def test_parallel_wave_respects_collision_keys():
    with tempfile.TemporaryDirectory() as td:
        k=AutonomicCompletionKernel(RunStore(Path(td)/"r.db"),FederationLearningLedger(Path(td)/"l.jsonl"))
        packets=(WorkPacket("A",collision_keys=("x",)),WorkPacket("B",collision_keys=("x",)),WorkPacket("C",collision_keys=("y",)))
        ctx=ExecutionContext("M4","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.CURRENT_RUN,genome(),packets,maximum_parallelism=8)
        r=k.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,p.packet_id))
        assert r.telemetry.executed_packets==2
        done={p.packet_id for p in r.context.packets if p.done}
        assert "C" in done and len(done & {"A","B"})==1




def test_owner_reserved_effect_is_not_inherited_from_parallelism():
    with tempfile.TemporaryDirectory() as td:
        k=AutonomicCompletionKernel(RunStore(Path(td)/"r.db"),FederationLearningLedger(Path(td)/"l.jsonl"))
        packets=(WorkPacket("SAFE"),WorkPacket("EFFECT",effect_class="EXTERNAL_EFFECT",owner_reserved=True))
        ctx=ExecutionContext("M5","DEPLOY","COMMERCIAL_READY_VERIFIED",RuntimeMode.CURRENT_RUN,genome(),packets,owner_effect_authority=False)
        r=k.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,p.packet_id))
        assert any(p.packet_id=="SAFE" and p.done for p in r.context.packets)
        assert any(p.packet_id=="EFFECT" and not p.done for p in r.context.packets)




def test_ready_wave_executes_real_parallel_fanout():
    import threading, time
    with tempfile.TemporaryDirectory() as td:
        k=AutonomicCompletionKernel(RunStore(Path(td)/"r.db"),FederationLearningLedger(Path(td)/"l.jsonl"))
        packets=tuple(WorkPacket(f"P{i}",collision_keys=(f"k{i}",)) for i in range(12))
        ctx=ExecutionContext("MP","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.CURRENT_RUN,genome(),packets,maximum_parallelism=12)
        lock=threading.Lock(); active=0; peak=0
        def work(p):
            nonlocal active,peak
            with lock:
                active+=1; peak=max(peak,active)
            time.sleep(0.02)
            with lock: active-=1
            return True,p.packet_id
        start=time.perf_counter(); r=k.run_cycle(ctx,cycle=1,packet_executor=work); elapsed=time.perf_counter()-start
        assert r.telemetry.executed_packets==12
        assert peak >= 6
        assert elapsed < 0.15




def test_prompt_science_runs_each_cycle_and_can_promote_measured_winner():
    from federation.prompt_scientist_v2 import PromptRunMetrics
    with tempfile.TemporaryDirectory() as td:
        def eval_runner(g, fixture):
            good=g.genes.get("OUTPUT_POLICY")=="NON_TERMINAL_PROGRESS_CONTINUES"
            return PromptRunMetrics(g.version,"BUILD",completion_ratio=1.0 if good else 0.5,correctness=1.0,proof_completeness=1.0,execution_efficiency=1.0,parallelizable_packets=1,achieved_parallelism=1,owner_interventions=0 if good else 3,recovery_success=1.0,context_efficiency=1.0,creative_freedom=1.0,output_boundary_stop=not good)
        k=AutonomicCompletionKernel(RunStore(Path(td)/"r.db"),FederationLearningLedger(Path(td)/"l.jsonl"),prompt_evaluator=eval_runner,prompt_fixtures=("fixture",))
        bad=PromptGenome("V4","V3",{**dict(genome().genes),"OUTPUT_POLICY":"HANDOFF_AFTER_PROGRESS","RUNTIME_REENTRY":"NONE"})
        packets=(WorkPacket("A"),WorkPacket("B",("A",)))
        ctx=ExecutionContext("MEVOLVE","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.NO_PERSISTENT_RUNNER,bad,packets)
        r=k.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,p.packet_id),force_platform_boundary=True)
        assert r.context.prompt_genome.version.endswith("-P1") or r.context.prompt_genome.version.endswith("-P3")
        ok,count=k.learning.verify(); assert ok and count==1
        line=(Path(td)/"l.jsonl").read_text()
        assert "PROMPT_PROMOTED" in line




def test_all_packets_done_does_not_fake_commercial_ready_when_evidence_missing():
    with tempfile.TemporaryDirectory() as td:
        store=RunStore(Path(td)/"r.db"); learn=FederationLearningLedger(Path(td)/"l.jsonl")
        k=AutonomicCompletionKernel(store,learn)
        ctx=ExecutionContext(
            "M-COMMERCIAL-HOLD","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.CURRENT_RUN,
            genome(),(WorkPacket("BUILD"),),current_maturity="LOCAL_TESTED",
            commercial_evidence={"FUNCTIONALITY":True},
            commercial_applicable_gates=("FUNCTIONALITY","SECURITY","RELIABILITY"),
        )
        r=k.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,"proof:build"))
        assert r.terminal_state==""
        assert r.telemetry.output_class==OutputClass.PROGRESS_UPDATE.value
        assert r.recompile_required is True
        assert r.maturity_gaps==("SECURITY","RELIABILITY")
        assert r.context.current_maturity=="LOCAL_TESTED"
        cp=store.read("M-COMMERCIAL-HOLD")
        assert cp.state["recompile_required"] is True
        assert cp.state["maturity_gaps"]==["SECURITY","RELIABILITY"] or tuple(cp.state["maturity_gaps"])==("SECURITY","RELIABILITY")




def test_mission_recompiler_can_auto_continue_until_commercial_evidence_is_proven():
    with tempfile.TemporaryDirectory() as td:
        evidence={"FUNCTIONALITY":True}
        store=RunStore(Path(td)/"r.db"); learn=FederationLearningLedger(Path(td)/"l.jsonl")
        def evidence_provider(ctx):
            return dict(evidence)
        def recompiler(ctx,gaps):
            assert gaps==("SECURITY",)
            packets=ctx.packets + (WorkPacket("MATURITY-SECURITY", dependencies=tuple(p.packet_id for p in ctx.packets)),)
            return ExecutionContext(
                ctx.mission_id,ctx.mission_class,ctx.target_state,ctx.runtime_mode,ctx.prompt_genome,packets,
                ctx.current_maturity,ctx.owner_effect_authority,ctx.maximum_parallelism,dict(evidence),ctx.commercial_applicable_gates,
            )
        def executor(packet):
            if packet.packet_id=="MATURITY-SECURITY":
                evidence["SECURITY"]=True
                return True,"proof:security-court"
            return True,"proof:build"
        k=AutonomicCompletionKernel(store,learn,mission_recompiler=recompiler,commercial_evidence_provider=evidence_provider)
        ctx=ExecutionContext(
            "M-COMMERCIAL-AUTO","BUILD","COMMERCIAL_READY_VERIFIED",RuntimeMode.CURRENT_RUN,
            genome(),(WorkPacket("BUILD"),),current_maturity="LOCAL_TESTED",
            commercial_evidence=dict(evidence),commercial_applicable_gates=("FUNCTIONALITY","SECURITY"),
        )
        results=k.execute_until_boundary(ctx,executor,max_cycles=5)
        assert len(results)==2
        assert results[0].recompile_required is True
        assert results[-1].terminal_state=="COMMERCIAL_READY_VERIFIED"
        assert results[-1].context.current_maturity=="COMMERCIAL_READY_VERIFIED"
        assert results[-1].telemetry.output_class==OutputClass.TERMINAL_REPORT.value
        assert all(p.done for p in results[-1].context.packets)
        ok,count=learn.verify(); assert ok and count==2




def test_owner_only_remaining_packet_surfaces_owner_decision_instead_of_looping():
    with tempfile.TemporaryDirectory() as td:
        k=AutonomicCompletionKernel(RunStore(Path(td)/"r.db"),FederationLearningLedger(Path(td)/"l.jsonl"))
        ctx=ExecutionContext(
            "M-OWNER","DEPLOY","PRODUCTION_VERIFIED",RuntimeMode.CURRENT_RUN,genome(),
            (WorkPacket("EFFECT",effect_class="EXTERNAL_EFFECT",owner_reserved=True),),
            owner_effect_authority=False,
        )
        r=k.run_cycle(ctx,cycle=1,packet_executor=lambda p:(True,"should-not-run"))
        assert r.terminal_state=="IRREDUCIBLE_OWNER_DECISION"
        assert r.telemetry.output_class==OutputClass.OWNER_DECISION.value
        assert r.telemetry.executed_packets==0
