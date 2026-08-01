from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .store import DurableRunStore


class StrictCanaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelReceipt:
    mission_id: str
    status: str
    output: str | None
    trace_id: str
    response_id: str | None
    requests: int
    input_tokens: int
    output_tokens: int
    state_version: int | None
    interruptions: int


class DurableAgentsBridge:
    """Run-scoped SDK bridge with encrypted pause/resume state.

    The caller supplies a run-scoped model provider built from a managed
    credential lease. No process-global ``OPENAI_API_KEY`` mutation is used.
    Tracing uses a per-run credential mapping and a caller-observable trace ID.
    """

    def __init__(
        self,
        store: DurableRunStore,
        *,
        sdk_loader: Callable[[], Any] | None = None,
    ):
        self.store = store
        self.sdk_loader = sdk_loader or self._load_sdk

    @staticmethod
    def _load_sdk():
        from agents import Agent, RunConfig, RunState, Runner
        from agents.tracing import gen_trace_id

        return {
            "Agent": Agent,
            "RunConfig": RunConfig,
            "RunState": RunState,
            "Runner": Runner,
            "gen_trace_id": gen_trace_id,
        }

    @staticmethod
    def _interruption_view(item: Any) -> dict:
        return {
            "call_id": str(getattr(item, "call_id", "")),
            "tool_name": str(getattr(item, "tool_name", "")),
            "agent_name": str(getattr(getattr(item, "agent", None), "name", "")),
        }

    @staticmethod
    def _usage(result: Any) -> tuple[int, int, int]:
        usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
        return (
            int(getattr(usage, "requests", 0) or 0),
            int(getattr(usage, "input_tokens", 0) or 0),
            int(getattr(usage, "output_tokens", 0) or 0),
        )

    @staticmethod
    def _run_config(
        sdk: dict[str, Any],
        *,
        mission_id: str,
        model_provider: Any,
        tracing_api_key: str,
        resumed: bool,
    ) -> tuple[Any, str]:
        trace_id = str(sdk["gen_trace_id"]())
        if not trace_id.startswith("trace_") or len(trace_id) < 16:
            raise RuntimeError("SDK generated an invalid trace identifier")
        config = sdk["RunConfig"](
            model_provider=model_provider,
            tracing={"api_key": tracing_api_key},
            trace_include_sensitive_data=False,
            workflow_name=(
                "EvidenceOps AI ICT model runtime resume"
                if resumed
                else "EvidenceOps AI ICT model runtime"
            ),
            trace_id=trace_id,
            group_id=mission_id,
            trace_metadata={"mission_id": mission_id, "resumed": resumed},
        )
        return config, trace_id

    async def run(
        self,
        *,
        mission_id: str,
        directive: str,
        model_provider: Any,
        tracing_api_key: str,
        expected_output: str | None = None,
        session: Any = None,
    ) -> ModelReceipt:
        sdk = self.sdk_loader()
        agent = sdk["Agent"](
            name="EvidenceOps AI ICT Mission Director",
            instructions=(
                "Execute only the supplied mission. Preserve authority limits. "
                "Never claim a side effect without readback. Pause for approval "
                "when a tool requires it."
            ),
        )
        run_config, trace_id = self._run_config(
            sdk,
            mission_id=mission_id,
            model_provider=model_provider,
            tracing_api_key=tracing_api_key,
            resumed=False,
        )
        result = await sdk["Runner"].run(
            agent, directive, run_config=run_config, session=session
        )
        interruptions = list(getattr(result, "interruptions", []) or [])
        requests, input_tokens, output_tokens = self._usage(result)
        response_id = getattr(result, "last_response_id", None)

        if interruptions:
            state = result.to_state()
            state_json = state.to_json(
                strict_context=True,
                include_tracing_api_key=False,
            )
            views = [self._interruption_view(item) for item in interruptions]
            version = self.store.save_paused(
                mission_id,
                state_json,
                views,
                session_id=getattr(session, "session_id", None),
            )
            return ModelReceipt(
                mission_id=mission_id,
                status="WAITING_APPROVAL",
                output=None,
                trace_id=trace_id,
                response_id=response_id,
                requests=requests,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                state_version=version,
                interruptions=len(views),
            )

        output = str(result.final_output)
        if expected_output is not None and output.strip() != expected_output:
            raise StrictCanaryError("strict model canary output mismatch")
        return ModelReceipt(
            mission_id=mission_id,
            status="MODEL_BACKED_COMPLETE",
            output=output,
            trace_id=trace_id,
            response_id=response_id,
            requests=requests,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            state_version=None,
            interruptions=0,
        )

    async def resume(
        self,
        *,
        mission_id: str,
        agent: Any,
        model_provider: Any,
        tracing_api_key: str,
        interruption_lookup: Callable[[Any, str], Any],
        session: Any = None,
    ) -> ModelReceipt:
        sdk = self.sdk_loader()
        stored = self.store.load(mission_id)
        state = await sdk["RunState"].from_json(
            initial_agent=agent,
            state_json=stored.state_json,
            strict_context=True,
        )
        decisions = self.store.decisions(mission_id)
        for call_id, decision in decisions.items():
            item = interruption_lookup(state, call_id)
            if decision == "APPROVE":
                state.approve(item)
            else:
                state.reject(
                    item,
                    rejection_message="Action rejected by policy authority.",
                )
        run_config, trace_id = self._run_config(
            sdk,
            mission_id=mission_id,
            model_provider=model_provider,
            tracing_api_key=tracing_api_key,
            resumed=True,
        )
        result = await sdk["Runner"].run(
            agent, state, run_config=run_config, session=session
        )
        requests, input_tokens, output_tokens = self._usage(result)
        return ModelReceipt(
            mission_id=mission_id,
            status="MODEL_BACKED_COMPLETE",
            output=str(result.final_output),
            trace_id=trace_id,
            response_id=getattr(result, "last_response_id", None),
            requests=requests,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            state_version=stored.state_version,
            interruptions=len(getattr(result, "interruptions", []) or []),
        )

    @staticmethod
    def receipt_json(receipt: ModelReceipt) -> str:
        return json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":"))
