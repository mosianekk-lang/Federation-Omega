import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "ops" / "gns4_hosted_queue_drain.py"
spec = importlib.util.spec_from_file_location("gns4_hosted_queue_drain", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_column_letter_boundaries():
    assert mod._column_letter(1) == "A"
    assert mod._column_letter(26) == "Z"
    assert mod._column_letter(27) == "AA"
    assert mod._column_letter(52) == "AZ"


def test_find_candidate_is_fail_closed_to_exact_executor_handler_status():
    headers = [
        "dispatch_id", "created_at_utc", "task_id", "title", "period_key",
        "executor", "handler", "status", "prompt", "schedule", "timezone",
        "timing_mode", "processed_at_utc", "result_json",
    ]
    wrong = [
        "OLD", "", "", "", "", "EXTERNAL_ADAPTER", "GNS4_HOSTED_STATUS_CANARY",
        "QUEUED_EXTERNAL_ADAPTER", "", "", "", "", "", "",
    ]
    right = [
        "GNS4-CANARY", "", "", "", "", "GNS4_HOSTED_WIF", "GNS4_HOSTED_STATUS_CANARY",
        "QUEUED_EXTERNAL_ADAPTER", "", "", "", "", "", "",
    ]
    candidate = mod._find_candidate([headers, wrong, right])
    assert candidate is not None
    sheet_row, row, idx = candidate
    assert sheet_row == 3
    assert row[idx["dispatch_id"]] == "GNS4-CANARY"


def test_find_candidate_ignores_claimed_or_unrelated_work():
    headers = [
        "dispatch_id", "created_at_utc", "task_id", "title", "period_key",
        "executor", "handler", "status", "prompt", "schedule", "timezone",
        "timing_mode", "processed_at_utc", "result_json",
    ]
    claimed = [
        "A", "", "", "", "", "GNS4_HOSTED_WIF", "GNS4_HOSTED_STATUS_CANARY",
        "CLAIMED_GNS4_HOSTED", "", "", "", "", "", "",
    ]
    unrelated = [
        "B", "", "", "", "", "GNS4_HOSTED_WIF", "FEDERATION_SURFACE_SENTINEL",
        "QUEUED_EXTERNAL_ADAPTER", "", "", "", "", "", "",
    ]
    assert mod._find_candidate([headers, claimed, unrelated]) is None


def test_missing_queue_schema_fails_closed():
    try:
        mod._find_candidate([["dispatch_id", "status"], ["x", "QUEUED_EXTERNAL_ADAPTER"]])
    except RuntimeError as exc:
        assert "QUEUE_SCHEMA_MISMATCH" in str(exc)
    else:
        raise AssertionError("expected schema mismatch")
