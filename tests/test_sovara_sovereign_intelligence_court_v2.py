import importlib.util
import json
from pathlib import Path
import tempfile

MODULE_PATH = Path(__file__).resolve().parents[1] / "ops" / "sovara_sovereign_intelligence_court_v2.py"
spec = importlib.util.spec_from_file_location("sovara_sovereign_intelligence_court_v2", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class FakeExternalPanel:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def __call__(self, code, *, api_key, language, objective, max_models):
        self.calls += 1
        if self.fail:
            raise mod.EvalError("provider policy boundary")
        return {
            "reviews": [
                {
                    "receipt": {
                        "status": "PROVIDER_RESPONSE_RECEIVED_PROPOSAL_ONLY",
                        "resolved_model": "provider-a/model-a",
                        "output_sha256": "a" * 64,
                    },
                    "output": '{"summary":"A"}',
                },
                {
                    "receipt": {
                        "status": "PROVIDER_RESPONSE_RECEIVED_PROPOSAL_ONLY",
                        "resolved_model": "provider-b/model-b",
                        "output_sha256": "b" * 64,
                    },
                    "output": '{"summary":"B"}',
                },
            ],
            "terminal_state": "PROPOSALS_RECEIVED_REQUIRES_INDEPENDENT_VALIDATION",
        }


def local_reviewer(code, language, objective):
    return mod.LaneReceipt(
        lane_id="local-1",
        lane_type="LOCAL_MODEL",
        status=mod.LaneStatus.SUCCESS.value,
        provider="local",
        model="local/test",
        output_sha256=mod._sha256_text("local proposal"),
        proposal="local proposal",
    )


def test_secret_preflight_blocks_external_transmission():
    result = mod.privacy_preflight("OPENROUTER_API_KEY='sk-or-v1-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456'")
    assert result["status"] == "BLOCK_EXTERNAL_TRANSMISSION"
    assert result["external_transmission_allowed"] is False
    assert "OPENROUTER_KEY" in result["secret_shape_findings"]


def test_mission_id_is_stable_for_exact_input():
    source_sha = mod._sha256_text("print('x')")
    a = mod._mission_id(source_sha, "review", "AUTO")
    b = mod._mission_id(source_sha, "review", "AUTO")
    assert a == b


def test_atomic_mission_store_round_trip():
    with tempfile.TemporaryDirectory() as root:
        store = mod.MissionStore(root)
        snapshot = mod.MissionSnapshot(
            schema=mod.MISSION_SCHEMA,
            mission_id="SOV-EVAL-TEST",
            created_at_utc="2026-08-28T00:00:00+00:00",
            updated_at_utc="2026-08-28T00:00:00+00:00",
            state=mod.MissionState.RECEIVED.value,
            source_sha256="0" * 64,
            source_bytes=1,
            language="python",
            objective="review",
            mode="AUTO",
            degradation_mode=mod.DegradationMode.FULL.value,
            checkpoint_seq=1,
            completed_states=[mod.MissionState.RECEIVED.value],
            boundary_events=[],
            lane_receipts=[],
        )
        store.save(snapshot)
        loaded = store.load(snapshot.mission_id)
        assert loaded is not None
        assert loaded.mission_id == snapshot.mission_id
        assert loaded.source_sha256 == snapshot.source_sha256


def test_provider_failure_does_not_terminate_local_lane(monkeypatch):
    fake = FakeExternalPanel(fail=True)
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    with tempfile.TemporaryDirectory() as root:
        court = mod.SovereignIntelligenceCourt(
            mission_store=mod.MissionStore(root),
            external_panel=fake,
            local_reviewers=(local_reviewer,),
        )
        result = court.evaluate("def f():\n    return 1\n", language="python")
        assert fake.calls == 1
        assert result.degradation_mode == mod.DegradationMode.DEGRADED_LOCAL_ONLY.value
        assert result.terminal_state == "PROPOSALS_RECEIVED_REQUIRES_INDEPENDENT_VALIDATION"
        state = court.store.load(result.mission_id)
        assert state is not None
        assert any(event["kind"] == "PROVIDER_BOUNDARY" for event in state.boundary_events)


def test_external_panel_plus_local_lane_is_full(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    with tempfile.TemporaryDirectory() as root:
        court = mod.SovereignIntelligenceCourt(
            mission_store=mod.MissionStore(root),
            external_panel=FakeExternalPanel(),
            local_reviewers=(local_reviewer,),
        )
        result = court.evaluate("def f(x):\n    return x + 1\n", language="python")
        assert result.degradation_mode == mod.DegradationMode.FULL.value
        assert result.panel_summary["external_success"] == 2
        assert result.panel_summary["sovereign_success"] == 1
        assert result.zero_dilution["canonical_source_modified"] is False
        assert result.zero_dilution["incumbent_preserved"] is True
        assert result.zero_dilution["promotion_allowed"] is False


def test_resume_is_idempotent_for_same_mission(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with tempfile.TemporaryDirectory() as root:
        store = mod.MissionStore(root)
        court = mod.SovereignIntelligenceCourt(mission_store=store, local_reviewers=(local_reviewer,))
        first = court.evaluate("x = 1\n", language="python", objective="review")
        second = court.evaluate("x = 1\n", language="python", objective="review")
        assert first.mission_id == second.mission_id
        loaded = store.load(first.mission_id)
        assert loaded is not None
        assert loaded.source_sha256 == first.source_sha256


def test_external_outputs_remain_proposal_only(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    with tempfile.TemporaryDirectory() as root:
        court = mod.SovereignIntelligenceCourt(
            mission_store=mod.MissionStore(root),
            external_panel=FakeExternalPanel(),
        )
        result = court.evaluate("x = 1\n")
        assert result.ao5_assessment["external_outputs_proposal_only"] is True
        assert result.ao5_assessment["promotion_allowed"] is False
        assert all(item["state"] == "PROPOSAL_ONLY" for item in result.cfbe_ranking)
