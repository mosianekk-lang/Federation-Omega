from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "fuse-mobile"


def read(relative: str) -> str:
    return (MOBILE / relative).read_text(encoding="utf-8")


def test_runtime_converts_every_outcome_class_into_alpha_omega_plan() -> None:
    runtime = read("src/evolutionRuntime.ts")
    engine = read("src/anthropicCfbeV4.ts")
    assert "captureEvolutionOutcome" in runtime
    assert "compileAlphaOmegaFormationEvolution" in runtime
    for kind in ["SUCCESS", "PARTIAL", "FAILURE", "BLOCKED"]:
        assert kind in engine
    assert "55" in runtime
    assert "maxParallelAgents: 6" in runtime


def test_runtime_ledger_is_bounded_and_local_only() -> None:
    runtime = read("src/evolutionRuntime.ts")
    assert "MAX_LOCAL_EVOLUTION_RECEIPTS = 32" in runtime
    assert "localReceipts" in runtime
    assert "splice(MAX_LOCAL_EVOLUTION_RECEIPTS)" in runtime
    assert "does not mutate provider authority" in runtime
    assert "secrets" in runtime
    assert "repository source" in runtime
    for forbidden in ["fetch(", "axios", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]:
        assert forbidden not in runtime


def test_owner_connection_success_and_failure_both_feed_evolution() -> None:
    owner = read("src/ownerConnection.ts")
    assert "captureEvolutionOutcome" in owner
    assert "captureOwnerEvolution" in owner
    assert "OWNER_ENROLLED" in owner
    assert "OWNER_CONNECT_FAILED" in owner
    assert "kind: 'SUCCESS'" in owner
    assert "kind: 'FAILURE'" in owner
    assert "kind: cancelled ? 'BLOCKED' : 'FAILURE'" in owner


def test_fuse_request_outcome_hook_wraps_final_retry_result_once() -> None:
    owner = read("src/ownerConnection.ts")
    assert "sendOwnerFuseMessageWithRefresh" in owner
    assert "const response = await sendOwnerFuseMessageWithRefresh" in owner
    assert "PROVIDER:CHAT_READBACK" in owner
    assert "TRACE:${response.trace_id}" in owner
    assert "REQUEST_FAILED" in owner
    assert "REQUEST_CANCELLED" in owner


def test_outcome_learning_does_not_persist_user_prompt_or_provider_secrets() -> None:
    runtime = read("src/evolutionRuntime.ts")
    owner = read("src/ownerConnection.ts")
    assert "request.intent" not in runtime
    assert "request.intent" not in owner
    assert "accessToken" not in runtime
    assert "deviceToken" not in runtime
    assert "iapIdentityToken" not in runtime


def test_evolution_capture_failure_cannot_break_user_operation() -> None:
    owner = read("src/ownerConnection.ts")
    assert "try {\n    lastEvolutionReceipt = captureEvolutionOutcome(input);" in owner
    assert "} catch {\n    return null;\n  }" in owner


def test_owner_can_read_latest_evolution_receipt_without_new_authority() -> None:
    owner = read("src/ownerConnection.ts")
    runtime = read("src/evolutionRuntime.ts")
    assert "getLastOwnerEvolutionReceipt" in owner
    assert "latestEvolutionReceipt" in runtime
    assert "EvolutionReceipt" in owner
