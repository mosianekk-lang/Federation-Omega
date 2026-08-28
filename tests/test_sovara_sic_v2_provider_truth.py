from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"
for p in (OPS, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sovara_sovereign_intelligence_court_v2 import FileMissionStore, SovereignIntelligenceCourt


class AllFailedExternalRunner:
    def __call__(self, code, *, api_key, language, objective, max_models):
        del code, api_key, language, objective, max_models
        return {
            "schema": "TEST-FAILED-ENVELOPE",
            "successful_reviews": 0,
            "failed_reviews": 2,
            "reviews": [
                {
                    "receipt": {
                        "status": "FAILED",
                        "resolved_model": None,
                        "output_sha256": None,
                        "error_class": "ProviderError",
                        "error_message": "held",
                    },
                    "proposal": None,
                },
                {
                    "receipt": {
                        "status": "FAILED",
                        "resolved_model": None,
                        "output_sha256": None,
                        "error_class": "ProviderError",
                        "error_message": "held",
                    },
                    "proposal": None,
                },
            ],
        }


def test_failed_receipts_do_not_claim_provider_connectivity(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-reference-only")
    with tempfile.TemporaryDirectory() as root:
        court = SovereignIntelligenceCourt(
            store=FileMissionStore(root),
            external_runner=AllFailedExternalRunner(),
        )
        result = court.evaluate("x = 1\n", language="python")
        assert result.panel_summary["round1_external_lanes"] == 2
        assert result.panel_summary["round1_external_success"] == 0
        assert result.panel_summary["provider_connectivity_claimed"] is False
        assert "EXTERNAL_PROVIDER_REVIEW_NOT_PROVEN_FOR_THIS_MISSION" in result.unresolved_unknowns
