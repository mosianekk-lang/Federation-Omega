import json

from bubbles.command_bus import build_receipt


def _run(event):
    command = {
        "schema": "BUBBLES-CONTROL-COMMAND-V1",
        "adapter_id": "bubbles_command_bus",
        "action": "recover_chat_failure",
        "effect": "READ",
        "target_alias": "EVIDENCEOPS_CFRE_LOCAL",
        "payload": {"event": event},
    }
    return build_receipt(
        json.dumps(command),
        actor="mosianekk-lang",
        event_name="pull_request",
        source_ref="AAA-INTEGRATION-CANARY",
    )


def test_existing_bubbles_recovery_contract_is_preserved():
    receipt = _run({
        "message": "Connection interrupted",
        "active_directive": "continue",
        "next_pending_action": "resume",
    })
    execution = receipt["execution"]
    assert execution["kind"] == "LOCAL_CHAT_FAILURE_RECOVERY"
    assert execution["recovery"]["failure_class"] == "TRANSPORT_INTERRUPTION"
    assert execution["recovery"]["must_continue"] is True
    assert execution["recovery"]["next_automated_action"] == "RETRY_SAME_ATOMIC_ACTION"
    assert execution["aaa"]["schema"] == "EVIDENCEOPS-CHAT-FAILURE-AAA-1"
    assert len(execution["aaa"]["receipt_sha256"]) == 64


def test_aaa_suppresses_unchanged_failed_route_without_breaking_contract():
    receipt = _run({
        "message": "Connection interrupted",
        "objective": "read current source",
        "route_id": "queue-current",
        "route_fingerprint": "architron-queue",
        "precondition_fingerprint": "consumer-stale",
        "route_history": [
            {
                "route_id": "queue-prior",
                "objective": "read current source",
                "route_fingerprint": "architron-queue",
                "precondition_fingerprint": "consumer-stale",
                "outcome": "FAILURE",
                "attempted_at": "2026-08-25T08:00:00+00:00",
            }
        ],
    })
    execution = receipt["execution"]
    assert execution["kind"] == "LOCAL_CHAT_FAILURE_RECOVERY"
    assert execution["recovery"]["failure_class"] == "TRANSPORT_INTERRUPTION"
    assert execution["recovery"]["next_automated_action"] == "DISCOVER_MATERIALLY_DIFFERENT_ROUTE"
    actions = [step["action"] for step in execution["recovery"]["recovery_steps"]]
    assert "SUPPRESS_UNCHANGED_FAILED_ROUTE" in actions
    assert "DISCOVER_MATERIALLY_DIFFERENT_ROUTE" in actions
    assert execution["aaa"]["route_retry"]["retry_allowed"] is False
    assert execution["provider_effects"] is False
