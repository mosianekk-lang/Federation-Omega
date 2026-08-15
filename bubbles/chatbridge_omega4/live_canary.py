from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Sequence

from .models import ApprovalState, GovernanceCapsule
from .openai_provider import OpenAIConversationProvider
from .provider_state import ProviderRunStateConflict, ProviderStateStore
from .runtime import ChatBridgeOmega4
from .store import ChatBridgeStore, NamespaceNotFound


DEFAULT_MODEL = "gpt-5.4-mini"


class ChildPhaseFailure(RuntimeError):
    """Redacted child-process failure that preserves only safe phase diagnostics."""

    def __init__(self, phase: str, payload: Dict[str, Any]) -> None:
        self.phase = phase
        self.payload = dict(payload)
        super().__init__(
            f"child phase failed:{phase}:{payload.get('error_type', 'UNKNOWN')}:"
            f"{payload.get('error_sha256', '')}"
        )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_out(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _safe_error(exc: Exception) -> Dict[str, Any]:
    """Return diagnostics useful for repair without leaking raw provider content or secrets."""
    payload: Dict[str, Any] = {
        "state": "CANARY_FAILED",
        "diagnostic_schema": "CHATBRIDGE-LIVE-CANARY-SAFE-DIAGNOSTIC-1",
        "error_type": type(exc).__name__,
        "error_sha256": _digest(str(exc)),
        "secret_values_recorded": False,
    }
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        payload["status_code"] = status_code
    error_code = getattr(exc, "code", None)
    if isinstance(error_code, (str, int)):
        payload["error_code"] = str(error_code)
    if isinstance(exc, ChildPhaseFailure):
        child = exc.payload
        payload.update(
            {
                "phase": exc.phase,
                "child_state": child.get("state", ""),
                "child_error_type": child.get("error_type", ""),
                "child_error_sha256": child.get("error_sha256", ""),
                "child_status_code": child.get("status_code"),
                "child_error_code": child.get("error_code", ""),
                "child_returncode": child.get("returncode"),
                "child_stderr_sha256": child.get("stderr_sha256", ""),
            }
        )
    return payload


def _require_runtime_env(model: str) -> None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError(
            "OPENAI_API_KEY is not present in this process environment; use an approved secret-injection path"
        )
    if not model.strip():
        raise RuntimeError("an explicit OpenAI model is required")


def _bridge(db: str) -> tuple[ChatBridgeOmega4, ProviderStateStore]:
    return ChatBridgeOmega4(ChatBridgeStore(db)), ProviderStateStore(db)


def _capsule(namespace: str) -> GovernanceCapsule:
    return GovernanceCapsule(
        owner=os.getenv("CHATBRIDGE_OWNER", "Kim Kagiso Mosiane"),
        project="ChatBridge Ω4 Live Provider Canary",
        workstream=namespace,
        adapter="chatbridge-openai-conversations-live-canary",
        objective="Prove provider-native durable continuation with exact readback.",
        exact_next_action="Complete the next live provider canary phase.",
        approval_gates=(ApprovalState.SCREEN_FIRST,),
        external_effects_allowed=False,
        notes="Synthetic canary only; no real-world consequential tool effect is permitted.",
    )


def _ensure_namespace(bridge: ChatBridgeOmega4, namespace: str) -> None:
    try:
        bridge.status(namespace)
    except NamespaceNotFound:
        bridge.backup(
            namespace,
            _capsule(namespace),
            hot_state={"phase": "LIVE_CANARY_PREPARED"},
            warm_pointers=["github:issue:455", "drive:chatbridge-canonical-control"],
            cold_pointers=[],
        )


def _approval_tool() -> Any:
    try:
        from agents import function_tool
    except Exception as exc:  # pragma: no cover - requires provider environment
        raise RuntimeError("openai-agents is required for the live canary") from exc

    @function_tool(needs_approval=True)
    async def synthetic_approval_canary(marker: str) -> str:
        """Harmless approval-gated canary; returns only a marker digest and has no external effect."""
        return f"SYNTHETIC_APPROVAL_EXECUTED:{_digest(marker)[:16]}"

    return synthetic_approval_canary


def _provider(db: str, model: str) -> tuple[ChatBridgeOmega4, ProviderStateStore, OpenAIConversationProvider]:
    _require_runtime_env(model)
    bridge, state = _bridge(db)
    return bridge, state, OpenAIConversationProvider(bridge, state, model=model)


def _redacted_result(result: Dict[str, Any], *, marker: str = "") -> Dict[str, Any]:
    output = str(result.get("final_output", ""))
    return {
        "state": result.get("state", ""),
        "namespace": result.get("namespace", ""),
        "namespace_id": result.get("namespace_id", ""),
        "generation_id": result.get("generation_id", ""),
        "generation_number": result.get("generation_number", 0),
        "handoff_id": result.get("handoff_id", ""),
        "checkpoint_fingerprint": result.get("checkpoint_fingerprint", ""),
        "conversation_id": result.get("conversation_id", ""),
        "response_id": result.get("response_id", ""),
        "run_state_id": result.get("run_state_id", ""),
        "provider_readback": result.get("provider_readback", {}),
        "output_sha256": _digest(output),
        "marker_observed": bool(marker and marker in output),
        "receipt_id": (result.get("receipt") or {}).get("receipt_id", ""),
    }


async def phase_bootstrap(args: argparse.Namespace) -> Dict[str, Any]:
    bridge, _state, provider = _provider(args.db, args.model)
    _ensure_namespace(bridge, args.namespace)
    result = await provider.run_turn(
        args.namespace,
        (
            "This is a synthetic continuity canary. Remember this exact marker for later turns: "
            f"{args.marker}. Reply only with CANARY_STORED."
        ),
        destination_session_key=f"live-canary-bootstrap:{uuid.uuid4().hex}",
        instructions=(
            "Follow the synthetic canary instructions exactly. Preserve the marker in conversation state. "
            "Do not call tools unless explicitly instructed."
        ),
    )
    out = _redacted_result(result)
    out["phase"] = "BOOTSTRAP"
    out["marker_sha256"] = _digest(args.marker)
    if not out["conversation_id"]:
        raise RuntimeError("bootstrap did not return a provider conversation identity")
    return out


async def phase_continue(args: argparse.Namespace) -> Dict[str, Any]:
    bridge, _state, provider = _provider(args.db, args.model)
    _ensure_namespace(bridge, args.namespace)
    result = await provider.run_turn(
        args.namespace,
        "Return the exact synthetic canary marker you were previously asked to remember. Return only the marker.",
        destination_session_key=f"live-canary-continue:{uuid.uuid4().hex}",
        instructions=(
            "Use the existing server-managed conversation state. Return the remembered canary marker exactly."
        ),
    )
    out = _redacted_result(result, marker=args.marker)
    out["phase"] = "CONTINUE_NEW_PROCESS"
    out["marker_sha256"] = _digest(args.marker)
    if not out["marker_observed"]:
        raise RuntimeError("new-process continuation did not reproduce the expected canary marker")
    return out


async def phase_pause(args: argparse.Namespace) -> Dict[str, Any]:
    bridge, _state, provider = _provider(args.db, args.model)
    _ensure_namespace(bridge, args.namespace)
    tool = _approval_tool()
    result = await provider.run_turn(
        args.namespace,
        (
            "APPROVAL_CANARY: call synthetic_approval_canary exactly once with marker "
            f"{args.marker}. Do not substitute a text answer for the tool call."
        ),
        destination_session_key=f"live-canary-pause:{uuid.uuid4().hex}",
        tools=[tool],
        instructions=(
            "For APPROVAL_CANARY input, you must call synthetic_approval_canary exactly once using the supplied marker. "
            "The tool requires human approval and has no external effect."
        ),
    )
    out = _redacted_result(result)
    out["phase"] = "PAUSE_FOR_APPROVAL"
    out["marker_sha256"] = _digest(args.marker)
    if result.get("state") != "INTERRUPTED_WAITING_APPROVAL" or not result.get("run_state_id"):
        raise RuntimeError("live canary did not persist an approval interruption")
    return out


async def phase_resume(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.run_state_id:
        raise RuntimeError("--run-state-id is required for resume")
    bridge, _state, provider = _provider(args.db, args.model)
    _ensure_namespace(bridge, args.namespace)
    tool = _approval_tool()
    result = await provider.resume_approval(
        args.namespace,
        args.run_state_id,
        [bool(args.approve)],
        destination_session_key=f"live-canary-resume:{uuid.uuid4().hex}",
        tools=[tool],
        instructions=(
            "Resume the persisted synthetic approval canary faithfully. Do not perform any external action."
        ),
    )
    out = _redacted_result(result)
    out["phase"] = "RESUME_NEW_PROCESS"
    out["decision"] = "APPROVE" if args.approve else "REJECT"
    if result.get("state") not in {
        "APPROVAL_RESUME_COMPLETE_READBACK_VERIFIED",
        "RESUMED_THEN_INTERRUPTED_WAITING_APPROVAL",
    }:
        raise RuntimeError("approval resume did not reach a verified provider semantic state")
    return out


async def phase_branch(args: argparse.Namespace) -> Dict[str, Any]:
    bridge, _state, provider = _provider(args.db, args.model)
    _ensure_namespace(bridge, args.namespace)
    target = args.branch_namespace or f"{args.namespace}-branch"
    try:
        bridge.status(target)
    except NamespaceNotFound:
        branch = bridge.clone(args.namespace, target)
    else:
        branch = {"state": "BRANCH_ALREADY_EXISTS"}
    result = await provider.run_turn(
        target,
        "Reply only with BRANCH_PROVIDER_BOUND.",
        destination_session_key=f"live-canary-branch:{uuid.uuid4().hex}",
        allow_restore_preview=True,
        instructions="This is a synthetic branch-lineage canary. Do not perform external actions.",
    )
    source_env = bridge.store.restore(args.namespace, destination_session_key="branch-source-inspect")
    target_env = bridge.store.restore(target, destination_session_key="branch-target-inspect")
    independent = (
        source_env.provider_ref.conversation_id
        and target_env.provider_ref.conversation_id
        and source_env.provider_ref.conversation_id != target_env.provider_ref.conversation_id
    )
    if not independent:
        raise RuntimeError("branch did not obtain an independent provider conversation identity")
    out = _redacted_result(result)
    out.update(
        {
            "phase": "BRANCH_INDEPENDENCE",
            "branch_namespace": target,
            "branch_state": branch.get("state", ""),
            "source_conversation_id": source_env.provider_ref.conversation_id,
            "branch_conversation_id": target_env.provider_ref.conversation_id,
            "provider_lineage_independent": True,
        }
    )
    return out


def _child_base(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "-m",
        "bubbles.chatbridge_omega4.live_canary",
        "--db",
        args.db,
        "--namespace",
        args.namespace,
        "--model",
        args.model,
        "--marker",
        args.marker,
    ]


def _child_phase(cmd: Sequence[str]) -> str:
    phases = {"bootstrap", "continue", "pause", "resume", "branch"}
    for token in reversed(list(cmd)):
        if token in phases:
            return token.upper()
    return "UNKNOWN"


def _run_child(cmd: Sequence[str], *, expect_success: bool = True) -> Dict[str, Any]:
    completed = subprocess.run(
        list(cmd),
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    stdout = completed.stdout.strip().splitlines()
    payload: Dict[str, Any] = {}
    if stdout:
        try:
            payload = json.loads(stdout[-1])
        except Exception:
            payload = {"raw_stdout_sha256": _digest(completed.stdout)}
    payload["returncode"] = completed.returncode
    payload["stderr_sha256"] = _digest(completed.stderr)
    if expect_success and completed.returncode != 0:
        raise ChildPhaseFailure(_child_phase(cmd), payload)
    if not expect_success and completed.returncode == 0:
        raise RuntimeError("negative canary unexpectedly succeeded")
    return payload


def prove(args: argparse.Namespace) -> Dict[str, Any]:
    _require_runtime_env(args.model)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    base = _child_base(args)

    bootstrap = _run_child(base + ["bootstrap"])
    continuation = _run_child(base + ["continue"])
    if bootstrap.get("conversation_id") != continuation.get("conversation_id"):
        raise RuntimeError("process-restart continuation changed provider conversation identity")

    paused = _run_child(base + ["pause"])
    run_state_id = str(paused.get("run_state_id", ""))
    if not run_state_id:
        raise RuntimeError("pause phase returned no persisted RunState identity")

    resumed = _run_child(base + ["resume", "--run-state-id", run_state_id, "--approve"])
    duplicate = _run_child(
        base + ["resume", "--run-state-id", run_state_id, "--approve"],
        expect_success=False,
    )
    branched = _run_child(base + ["branch", "--branch-namespace", args.branch_namespace])

    bridge, state = _bridge(args.db)
    envelope = bridge.store.restore(args.namespace, destination_session_key="prove-final-readback")
    latest = state.latest_receipt(envelope.namespace_id, envelope.generation_id) or {}

    receipt = {
        "schema": "CHATBRIDGE-OMEGA4-LIVE-CANARY-1",
        "state": "PROVIDER_LIVE_CANARY_PHASES_VERIFIED",
        "namespace": args.namespace,
        "namespace_id": envelope.namespace_id,
        "generation_id": envelope.generation_id,
        "generation_number": envelope.generation_number,
        "handoff_id": envelope.handoff_id,
        "checkpoint_fingerprint": envelope.checkpoint_fingerprint,
        "conversation_id": envelope.provider_ref.conversation_id,
        "marker_sha256": _digest(args.marker),
        "bootstrap_receipt_id": bootstrap.get("receipt_id", ""),
        "continue_receipt_id": continuation.get("receipt_id", ""),
        "pause_receipt_id": paused.get("receipt_id", ""),
        "resume_receipt_id": resumed.get("receipt_id", ""),
        "duplicate_resume_rejected": duplicate.get("returncode", 0) != 0,
        "branch_provider_lineage_independent": bool(branched.get("provider_lineage_independent")),
        "latest_provider_receipt_id": latest.get("receipt_id", ""),
        "model": args.model,
        "api_key_logged": False,
    }
    receipt["receipt_sha256"] = _digest(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChatBridge Ω4 provider-native durable-continuation canary")
    parser.add_argument("--db", default=os.getenv("CHATBRIDGE_CANARY_DB", ".chatbridge/live_canary.sqlite3"))
    parser.add_argument("--namespace", default=os.getenv("CHATBRIDGE_CANARY_NAMESPACE", "omega4-provider-canary"))
    parser.add_argument("--model", default=os.getenv("CHATBRIDGE_OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--marker", default=os.getenv("CHATBRIDGE_CANARY_MARKER", f"cb4-{uuid.uuid4().hex}"))
    sub = parser.add_subparsers(dest="phase", required=True)
    sub.add_parser("bootstrap")
    sub.add_parser("continue")
    sub.add_parser("pause")
    resume = sub.add_parser("resume")
    resume.add_argument("--run-state-id", required=True)
    resume.add_argument("--approve", action="store_true")
    branch = sub.add_parser("branch")
    branch.add_argument("--branch-namespace", default="")
    prove_parser = sub.add_parser("prove")
    prove_parser.add_argument("--branch-namespace", default="")
    return parser


async def _amain(args: argparse.Namespace) -> Dict[str, Any]:
    if args.phase == "bootstrap":
        return await phase_bootstrap(args)
    if args.phase == "continue":
        return await phase_continue(args)
    if args.phase == "pause":
        return await phase_pause(args)
    if args.phase == "resume":
        return await phase_resume(args)
    if args.phase == "branch":
        return await phase_branch(args)
    raise RuntimeError(f"unsupported async phase: {args.phase}")


def main() -> int:
    args = _parser().parse_args()
    try:
        result = prove(args) if args.phase == "prove" else asyncio.run(_amain(args))
        _json_out(result)
        return 0
    except ProviderRunStateConflict as exc:
        _json_out({"state": "DUPLICATE_RESUME_REJECTED", "error_type": type(exc).__name__})
        return 3
    except Exception as exc:
        _json_out(_safe_error(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())