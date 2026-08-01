from __future__ import annotations

import inspect
import json
from importlib.metadata import version

from agents import RunConfig, RunState
from agents.tracing import gen_trace_id

EXPECTED_VERSION = "0.19.2"
actual_version = version("openai-agents")
assert actual_version == EXPECTED_VERSION, (actual_version, EXPECTED_VERSION)

from_json_signature = inspect.signature(RunState.from_json)
for required in ("initial_agent", "state_json", "strict_context"):
    assert required in from_json_signature.parameters
assert inspect.iscoroutinefunction(RunState.from_json)

trace_id = gen_trace_id()
assert trace_id.startswith("trace_") and len(trace_id) >= 16
config = RunConfig(
    tracing={"api_key": "contract-probe-placeholder"},
    trace_include_sensitive_data=False,
    trace_id=trace_id,
)
assert config.trace_id == trace_id
assert config.trace_include_sensitive_data is False
assert config.tracing == {"api_key": "contract-probe-placeholder"}

print(json.dumps({
    "status": "OPENAI_AGENTS_SDK_CONTRACT_VERIFIED",
    "version": actual_version,
    "runstate_from_json_async": True,
    "runstate_from_json_required_parameters": [
        "initial_agent", "state_json", "strict_context"
    ],
    "tracing_config_type": "MAPPING",
    "trace_id_format_verified": True
}, indent=2))
