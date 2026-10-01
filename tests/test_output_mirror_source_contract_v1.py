import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_output_mirror_policy_contract():
    policy = json.loads((ROOT / "config" / "fuse-output-mirror-v1.json").read_text(encoding="utf-8"))
    assert policy["schema"] == "FUSE_OUTPUT_MIRROR_POLICY_V1"
    assert policy["version"] == "1.1.0"
    assert policy["enabled"] is True
    assert policy["release_requires_yes"] is True
    assert policy["deterministic_challenge_first"] is True
    assert "best and most powerful solution" in policy["question"]
    assert policy["failure_state"] == "FAIL_RECOMPILE_OUTPUT"
    assert set(policy["pass_states"]) == {
        "PASS_BEST_AVAILABLE_RESULT",
        "PASS_BEST_AVAILABLE_WITH_HARD_BOUNDARY",
    }

def test_output_mirror_source_contains_fail_closed_release_gate():
    src = (ROOT / "fuse_runtime" / "output_mirror_v1.mjs").read_text(encoding="utf-8")
    required = [
        "FUSE_OUTPUT_MIRROR_V1",
        "release_allowed",
        "FAIL_RECOMPILE_OUTPUT",
        "PASS_BEST_AVAILABLE_RESULT",
        "PASS_BEST_AVAILABLE_WITH_HARD_BOUNDARY",
        "OUTPUT_MIRROR_RECOMPILE_REQUIRED",
        "DETERMINISTIC_CHALLENGE_TOURNAMENT",
        "compileTournamentPacket",
    ]
    for token in required:
        assert token in src
