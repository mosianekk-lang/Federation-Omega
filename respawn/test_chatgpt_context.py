import json
from pathlib import Path

import bootstrap_service as bs
import chatgpt_context as cc


def _set_state(tmp_path: Path, payload):
    path = tmp_path / "runtime_state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    bs.STATE_PATH = path
    return path


def test_current_state_does_not_promote_verified_or_proposed(tmp_path):
    _set_state(tmp_path, {
        "deltas": [
            {"delta_id": "cur", "source_system": "Federation Omega", "summary": "Total Recall context", "status": "CURRENT_READBACK_VERIFIED"},
            {"delta_id": "hist", "source_system": "Federation Omega", "summary": "Total Recall context", "status": "VERIFIED"},
            {"delta_id": "draft", "source_system": "Federation Omega", "summary": "Total Recall context", "status": "PROPOSED"},
        ],
        "patterns": [], "bibliography": [], "conflicts": []
    })
    result = cc.get_current_state_impl(query="Total Recall", system="Federation Omega")
    assert [x["delta_id"] for x in result["claimable_current"]] == ["cur"]
    assert [x["delta_id"] for x in result["supporting_verified_not_current_by_itself"]] == ["hist"]
    assert [x["delta_id"] for x in result["gated_or_historical"]] == ["draft"]
    assert result["current_state_proof"] == "CURRENT_PROVEN_STRICT_LOCAL_STATE"


def test_coverage_fails_closed_without_ledger(tmp_path):
    _set_state(tmp_path, {"deltas": [], "patterns": [], "bibliography": [{"entry_id": "1"}], "conflicts": []})
    result = cc.get_corpus_coverage_impl()
    assert result["coverage_state"] == "UNKNOWN"
    assert result["full_account_history_proven"] is False
    assert result["bibliography_entries_seen"] == 1


def test_export_level_coverage_does_not_become_account_totality(tmp_path):
    _set_state(tmp_path, {
        "deltas": [], "patterns": [], "bibliography": [], "conflicts": [],
        "coverage": {"completeness_state": "COMPLETE_FOR_PROVIDED_EXPORT", "conversations_ingested": 42}
    })
    result = cc.get_corpus_coverage_impl()
    assert result["coverage_state"] == "COMPLETE_FOR_PROVIDED_EXPORT"
    assert result["full_account_history_proven"] is False


def test_compactor_removes_full_bible_and_bounds_excerpt():
    text = "A" * 8000 + "\nTotal Recall mission checkpoint\n" + "B" * 8000
    raw = {
        "already_solved_candidates": list(range(30)),
        "recent_deltas": list(range(30)),
        "open_conflicts": list(range(30)),
        "provider_context": {
            "provider_readback": True,
            "canonical_bible_text": text,
            "recent_sync_events": list(range(30)),
            "shared_learnings": list(range(30)),
        },
    }
    out = cc.compact_bootstrap_result(raw, terms=["Total Recall"], max_bible_chars=2000)
    provider = out["provider_context"]
    assert "canonical_bible_text" not in provider
    assert provider["canonical_bible_excerpt_chars"] <= 2000
    assert provider["canonical_bible_truncated"] is True
    assert len(provider["recent_sync_events"]) == 12


def test_resume_compiles_small_packet_without_claiming_full_history(tmp_path, monkeypatch):
    _set_state(tmp_path, {
        "deltas": [{
            "delta_id": "checkpoint-1", "source_system": "Federation Omega",
            "matter": "Total Recall", "summary": "Resume Total Recall mission",
            "status": "CURRENT_READBACK_VERIFIED"
        }],
        "patterns": [], "bibliography": [], "conflicts": []
    })
    monkeypatch.setattr(bs, "provider_adapter", lambda: {"available": False, "reason": "test"})
    result = cc.resume_mission_impl(
        system="Federation Omega", mission="Resume Total Recall mission", matter="Total Recall", chat_ref="test"
    )
    assert result["continuation_mode"] == "RESUME_FROM_EXISTING_EVIDENCE"
    assert result["current_state"]["current_state_proof"] == "CURRENT_PROVEN_STRICT_LOCAL_STATE"
    assert result["coverage"]["full_account_history_proven"] is False
    assert result["next_executable_action"]
