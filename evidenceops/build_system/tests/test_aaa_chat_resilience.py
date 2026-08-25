from evidenceops.build_system.aaa_chat_resilience import evaluate_failure_with_aaa


def test_unchanged_failed_route_changes_effective_recovery_to_distinct_route():
    receipt = evaluate_failure_with_aaa(
        {
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
        }
    )
    assert receipt["base_recovery"]["next_automated_action"] == "RETRY_SAME_ATOMIC_ACTION"
    assert receipt["effective_recovery"]["next_automated_action"] == "DISCOVER_MATERIALLY_DIFFERENT_ROUTE"
    actions = [step["action"] for step in receipt["effective_recovery"]["recovery_steps"]]
    assert "SUPPRESS_UNCHANGED_FAILED_ROUTE" in actions
    assert "DISCOVER_MATERIALLY_DIFFERENT_ROUTE" in actions
    assert receipt["aaa_route_retry"]["retry_allowed"] is False
    assert receipt["aaa_learning_genes"][0]["category"] == "UNCHANGED_ROUTE_FAILURE"


def test_changed_preconditions_keep_bounded_retry_available():
    receipt = evaluate_failure_with_aaa(
        {
            "message": "Too many requests",
            "http_status": 429,
            "objective": "provider status",
            "route_fingerprint": "provider-status",
            "precondition_fingerprint": "quota-window-new",
            "route_history": [
                {
                    "objective": "provider status",
                    "route_fingerprint": "provider-status",
                    "precondition_fingerprint": "quota-window-old",
                    "outcome": "FAILURE",
                    "attempted_at": "2026-08-25T08:00:00+00:00",
                }
            ],
        }
    )
    assert receipt["aaa_route_retry"]["retry_allowed"] is True
    assert receipt["aaa_route_retry"]["material_precondition_change"] is True
    assert receipt["effective_recovery"]["next_automated_action"] == "RETRY_SAME_ATOMIC_ACTION"


def test_checkpoint_memory_makes_second_unchanged_failure_self_suppressing():
    event = {
        "message": "Connection interrupted",
        "objective": "read current source",
        "route_id": "drive-export",
        "route_fingerprint": "drive-raw-export",
        "precondition_fingerprint": "connector-state-a",
        "attempted_at": "2026-08-25T09:00:00+00:00",
    }
    first = evaluate_failure_with_aaa(event)
    assert first["aaa_route_retry"]["retry_allowed"] is True
    assert first["aaa_route_memory_count"] == 1
    checkpoint = first["effective_recovery"]["checkpoint"]
    assert checkpoint["aaa_route_history"][0]["route_fingerprint"] == "drive-raw-export"

    second = evaluate_failure_with_aaa(
        {**event, "route_id": "drive-export-retry", "attempted_at": "2026-08-25T09:05:00+00:00"},
        previous_checkpoint=checkpoint,
    )
    assert second["aaa_route_retry"]["retry_allowed"] is False
    assert second["effective_recovery"]["next_automated_action"] == "DISCOVER_MATERIALLY_DIFFERENT_ROUTE"
    assert second["aaa_route_memory_count"] == 1


def test_no_route_metadata_preserves_existing_cfre_behavior():
    receipt = evaluate_failure_with_aaa({"message": "Connection interrupted"})
    assert receipt["aaa_route_retry"] is None
    assert receipt["aaa_route_memory_count"] == 0
    assert receipt["effective_recovery"]["next_automated_action"] == receipt["base_recovery"]["next_automated_action"]
    assert [step["action"] for step in receipt["effective_recovery"]["recovery_steps"]] == [
        step["action"] for step in receipt["base_recovery"]["recovery_steps"]
    ]
    assert receipt["provider_effects"] is False
