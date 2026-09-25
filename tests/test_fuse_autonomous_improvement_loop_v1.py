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
    assert a["historical_chat_backfill"]["native_totality"]=="UNVERIFIED"
    assert a["historical_chat_backfill"]["no_false_totality_claim"] is True
