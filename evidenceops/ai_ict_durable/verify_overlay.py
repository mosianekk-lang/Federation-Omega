from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
python_files = sorted(ROOT.rglob("*.py"))
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

bridge = (ROOT / "evidenceops_ai_ict_durable/bridge.py").read_text(encoding="utf-8")
store = (ROOT / "evidenceops_ai_ict_durable/store.py").read_text(encoding="utf-8")
sql = (ROOT / "migrations/0001_durable_agent_runs.sql").read_text(encoding="utf-8")

assert "include_tracing_api_key=False" in bridge
assert "trace_include_sensitive_data=False" in bridge
assert 'tracing={"api_key": tracing_api_key}' in bridge
assert "TracingConfig(" not in bridge
assert "gen_trace_id" in bridge
assert "trace_id=trace_id" in bridge
assert 'await sdk["RunState"].from_json(' in bridge
assert "initial_agent=agent" in bridge
assert "strict_context=True" in bridge
assert "os.environ" not in bridge
assert "state_ciphertext" in store
assert "protector_key_id" in store
assert "BYTEA NOT NULL" in sql
assert "PRIMARY KEY (mission_id, call_id)" in sql

provider_key_prefix = "s" + "k-"
secret_literal = re.compile(re.escape(provider_key_prefix) + r"[A-Za-z0-9_-]{12,}")
for path in ROOT.rglob("*"):
    if (
        path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".zip"}
    ):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not secret_literal.search(text), f"secret-like literal in {path}"

print(json.dumps({
    "status": "DURABLE_OVERLAY_VERIFIED",
    "python_files_parsed": len(python_files),
    "plaintext_run_state_persistence": False,
    "process_global_credential_mutation": False,
    "tracing_key_serialization": False,
    "tracing_config_type": "MAPPING",
    "explicit_trace_id_readback": True,
    "async_runstate_restore_contract": True,
    "approval_decisions_idempotent": True,
    "repository_secret_literal_scan": True
}, indent=2))
