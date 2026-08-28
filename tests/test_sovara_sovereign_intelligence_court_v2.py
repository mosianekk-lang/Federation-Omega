import importlib.util
import json
from pathlib import Path
import sys
import tempfile

MODULE = Path(__file__).resolve().parents[1] / "ops" / "sovara_sovereign_intelligence_court_v2.py"
spec = importlib.util.spec_from_file_location("sovara_sovereign_intelligence_court_v2", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
assert spec.loader is not None
spec.loader.exec_module(mod)


def fake_openrouter_key():
    return "sk-" + "or-v1-" + ("A" * 36)


class FakeExternalRunner:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def __call__(self, code, *, api_key, language, objective, max_models):
        self.calls.append({"code": code, "api_key": api_key, "language": language, "objective": objective, "max_models": max_models})
        if self.fail:
            raise mod.EvalError("provider policy boundary")
        round2 = "Cross-examine" in objective
        if round2:
            proposals = [
                {
                    "summary": "Proposal A is safer, but a hybrid should retain B's recovery path.",
                    "strengths": [],
                    "defects": [],
                    "hidden_risks": [],
                    "unconventional_ideas": ["Use a reversible hybrid challenger."],
                    "redesign_options": ["Hybrid A+B"],
                    "tests_to_add": ["rollback test"],
                    "confidence": 0.8,
                    "assumptions": [],
                },
                {
                    "summary": "Shared assumption: neither proposal proves regression safety.",
                    "strengths": [],
                    "defects": [],
                    "hidden_risks": ["regression safety unproven"],
                    "unconventional_ideas": [],
                    "redesign_options": [],
                    "tests_to_add": ["full regression"],
                    "confidence": 0.9,
                    "assumptions": [],
                },
            ]
        else:
            proposals = [
                {
                    "summary": "Architecture is sound but recovery needs stronger proof.",
                    "strengths": ["clear boundary"],
                    "defects": ["recovery proof missing"],
                    "hidden_risks": ["shared state dependency"],
                    "unconventional_ideas": ["event-sourced mission ledger"],
                    "redesign_options": ["lease-based workers"],
                    "tests_to_add": ["restart test"],
                    "confidence": 0.8,
                    "assumptions": [],
                },
                {
                    "summary": "Correctness is good but durability is the main risk.",
                    "strengths": ["proposal-only boundary"],
                    "defects": ["recovery proof missing"],
                    "hidden_risks": ["shared state dependency"],
                    "unconventional_ideas": ["content-addressed checkpoints"],
                    "redesign_options": ["durable queue"],
                    "tests_to_add": ["crash recovery"],
                    "confidence": 0.85,
                    "assumptions": [],
                },
            ]
        reviews = []
        for index, payload in enumerate(proposals, start=1):
            proposal = json.dumps(payload, sort_keys=True)
            reviews.append(
                {
                    "receipt": {
                        "status": "PROVIDER_RESPONSE_RECEIVED_PROPOSAL_ONLY",
                        "resolved_model": f"provider-{index}/model-{index}",
                        "output_sha256": mod._sha256_text(proposal),
                        "error_class": None,
                        "error_message": None,
                    },
                    "proposal": proposal,
                }
            )
        return {
            "schema": "TEST-ENVELOPE",
            "reviews": reviews,
            "successful_reviews": len(reviews),
            "failed_reviews": 0,
            "terminal_state": "PROPOSALS_RECEIVED_REQUIRES_INDEPENDENT_VALIDATION",
        }


def test_secret_preflight_blocks_external_transmission():
    result = mod.privacy_preflight("OPENROUTER_API_KEY='" + fake_openrouter_key() + "'")
    assert result["status"] == "BLOCK_EXTERNAL_TRANSMISSION"
    assert result["external_transmission_allowed"] is False
    assert "OPENROUTER_KEY" in result["secret_shape_findings"]


def test_deterministic_lane_never_executes_code():
    receipt = mod.deterministic_source_reviewer("raise RuntimeError('must not execute')", "python", "review")
    assert receipt.status == mod.LaneStatus.SUCCESS.value
    assert receipt.lane_type == "DETERMINISTIC_STATIC"
    assert receipt.metadata["code_executed"] is False


def test_provider_failure_degrades_to_deterministic_and_preserves_mission(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    fake = FakeExternalRunner(fail=True)
    with tempfile.TemporaryDirectory() as root:
        store = mod.FileMissionStore(root)
        court = mod.SovereignIntelligenceCourt(store=store, external_runner=fake)
        result = court.evaluate("def f():\n    return 1\n", language="python")
        assert result.degradation_mode == mod.DegradationMode.DEGRADED_DETERMINISTIC_ONLY.value
        assert result.zero_dilution["canonical_source_modified"] is False
        snapshot = store.load_snapshot(result.mission_id)
        assert snapshot is not None
        assert any(event["kind"] == "PROVIDER_POLICY_OR_TRANSPORT_BOUNDARY" for event in snapshot.boundary_events)
        assert snapshot.result_sha256 == result.result_sha256


def test_external_round1_and_round2_execute_as_one_transaction(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    fake = FakeExternalRunner()
    with tempfile.TemporaryDirectory() as root:
        court = mod.SovereignIntelligenceCourt(store=mod.FileMissionStore(root), external_runner=fake)
        result = court.evaluate("def f(x):\n    return x + 1\n", language="python", mode="CREATIVE")
        assert len(fake.calls) == 2
        assert "blind independent review" in fake.calls[0]["objective"]
        assert "Cross-examine" in fake.calls[1]["objective"]
        assert result.degradation_mode == mod.DegradationMode.FULL.value
        assert result.panel_summary["round1_external_success"] == 2
        assert result.panel_summary["round2_external_success"] == 2
        assert "recovery proof missing" in result.consensus_findings
        assert "shared state dependency" in result.consensus_findings
        assert result.adversarial_findings
        assert result.ao5_assessment["signed_slos_canonical_authority_claimed"] is False
        assert result.cfbe_assessment["superiority_claimed"] is False
        assert result.zero_dilution["promotion_allowed"] is False


def test_exact_retry_returns_sealed_result_without_provider_reentry(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    fake = FakeExternalRunner()
    with tempfile.TemporaryDirectory() as root:
        store = mod.FileMissionStore(root)
        court = mod.SovereignIntelligenceCourt(store=store, external_runner=fake)
        first = court.evaluate("x = 1\n", language="python", objective="review")
        calls_after_first = len(fake.calls)
        second = court.evaluate("x = 1\n", language="python", objective="review")
        assert first.mission_id == second.mission_id
        assert first.result_sha256 == second.result_sha256
        assert len(fake.calls) == calls_after_first


def test_secret_shaped_source_blocks_external_but_keeps_deterministic_lane(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    fake = FakeExternalRunner()
    code = "TOKEN='" + fake_openrouter_key() + "'\nprint('x')\n"
    with tempfile.TemporaryDirectory() as root:
        court = mod.SovereignIntelligenceCourt(store=mod.FileMissionStore(root), external_runner=fake)
        result = court.evaluate(code, language="python")
        assert fake.calls == []
        assert result.degradation_mode == mod.DegradationMode.DEGRADED_DETERMINISTIC_ONLY.value
        assert result.panel_summary["privacy_preflight"]["external_transmission_allowed"] is False
        assert result.panel_summary["provider_connectivity_claimed"] is False


def test_file_store_detects_tampered_sealed_result(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with tempfile.TemporaryDirectory() as root:
        store = mod.FileMissionStore(root)
        court = mod.SovereignIntelligenceCourt(store=store)
        result = court.evaluate("x = 1\n")
        path = Path(root) / result.mission_id / "sealed-result.json"
        data = json.loads(path.read_text())
        data["recommendation"] = "tampered"
        path.write_text(json.dumps(data))
        try:
            store.load_result(result.mission_id)
        except RuntimeError as exc:
            assert str(exc) == "SEALED_RESULT_HASH_MISMATCH"
        else:
            raise AssertionError("tampered result must fail closed")


def test_unsupported_mode_fails_closed():
    with tempfile.TemporaryDirectory() as root:
        court = mod.SovereignIntelligenceCourt(store=mod.FileMissionStore(root))
        try:
            court.evaluate("x=1", mode="NO_LIMITS")
        except ValueError as exc:
            assert "UNSUPPORTED_MODE" in str(exc)
        else:
            raise AssertionError("unsupported mode must fail closed")
