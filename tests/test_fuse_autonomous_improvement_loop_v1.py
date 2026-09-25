import json
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]

def _run(*args):
    p=subprocess.run(["node",str(ROOT/"fuse_runtime"/"autonomous_improvement_loop_v1.mjs"),*args],cwd=ROOT,text=True,capture_output=True,check=True,timeout=30)
    return json.loads(p.stdout)

def test_global_ten_iteration_loop():
    r=_run("selftest")
    assert r["iterations_requested"]==10
    assert r["iterations_completed"]==10
    assert r["final_state"]=="TEN_ITERATIONS_COMPLETE_VERIFIED"
    assert len(r["accepted_capabilities"])==10
    assert all(x["judge"]=="ACCEPT_NONREGRESSING" for x in r["iterations"])

def test_source_contracts_require_ten_iterations_and_history_backfill():
    s=json.loads((ROOT/"config"/"fuse-bootstrap-self-improvement-v1.json").read_text(encoding="utf-8"))
    a=json.loads((ROOT/"config"/"fuse-24x7-autonomy-v1.json").read_text(encoding="utf-8"))
    assert s["version"]=="2.0.0"
    assert s["iteration_policy"]["exact_iterations_per_cycle"]==10
    assert s["iteration_policy"]["inhouse_default"] is True
    assert s["iteration_policy"]["build_to_completion"] is True
    assert len(s["harvest10"])==10
    assert a["auto_repeat"]["iterations"]==10
    assert a["historical_chat_backfill"]["iterations_per_recovered_chat"]==10
    assert a["historical_chat_backfill"]["current_exact_recoverable_chat_records"]==37
    assert a["historical_chat_backfill"]["current_completed_chat_iterations"]==370
    assert a["historical_chat_backfill"]["recoverable_record_instances"]==129
    assert a["historical_chat_backfill"]["completed_record_iterations"]==1290
    assert a["historical_chat_backfill"]["evidence_classes"]["exact_chat_records"]["records"]==37
    assert a["historical_chat_backfill"]["evidence_classes"]["gmail_chatgpt_backup_artifacts"]["records"]==62
    assert a["historical_chat_backfill"]["evidence_classes"]["chatbridge_registry_identities"]["records"]==10
    assert a["historical_chat_backfill"]["evidence_classes"]["account_memory_incidents"]["records"]==20
    assert a["historical_chat_backfill"]["native_totality"]=="UNVERIFIED"
    assert a["historical_chat_backfill"]["no_false_totality_claim"] is True


def test_respawn_and_bootstrap_bind_live_ten_pass_contract():
    bootstrap=json.loads((ROOT/"config"/"fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8"))
    manifest=json.loads((ROOT/"respawn"/"federation_manifest.json").read_text(encoding="utf-8"))
    service=(ROOT/"respawn"/"bootstrap_service.py").read_text(encoding="utf-8")
    assert bootstrap["boot_kernel"]=="5.10.0"
    assert bootstrap["autonomous_improvement"]["exact_iterations"]==10
    assert bootstrap["autonomous_improvement"]["historical_chat_backfill"]["current_completed_iterations"]==370
    assert bootstrap["live_proof"]["bootstrap_guard_schema"]=="FUSE_BOOTSTRAP_GUARD_V4"
    assert manifest["schema_version"]=="1.5"
    assert manifest["bootstrap_self_improvement"]["iterations_per_cycle"]==10
    assert manifest["historical_chat_backfill"]["current_exact_recovered_chat_records"]==37
    assert manifest["historical_chat_backfill"]["native_account_totality"]=="UNVERIFIED"
    assert "autonomous_improvement_bootstrap_guard" in service
    assert "AUTONOMOUS_IMPROVEMENT_ITERATION_COUNT_MISMATCH" in service
    assert "HISTORICAL_CHAT_COMPLETED_ITERATIONS_MISMATCH" in service
    assert "HISTORICAL_BACKFILL_RECOVERABLE_BASELINE_REGRESSED" in service
    assert "HISTORICAL_BACKFILL_ITERATION_BASELINE_REGRESSED" in service
    assert "NATIVE_CHAT_TOTALITY_FALSE_CLAIM" in service
