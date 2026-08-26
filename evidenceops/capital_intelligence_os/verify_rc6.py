from __future__ import annotations

from .demo_pack import CIOSDemoPackBuilder
from .qualification import InternalQualificationCourt
from .verify_rc5 import verify as verify_rc5


def verify() -> dict[str, object]:
    rc5 = verify_rc5()
    qualification = InternalQualificationCourt().run()
    demo = CIOSDemoPackBuilder().build()
    manifest = demo["manifest"]
    files = demo["files"]
    checks = {
        "rc5_regression": bool(rc5.get("passed")),
        "qualification_passes": qualification.passed
        and qualification.score == 1.0
        and not qualification.fatal_failures,
        "qualification_receipt_digest_bound": len(qualification.receipt_sha256) == 64,
        "demo_journey_passes": manifest.get("journey_passed") is True,
        "demo_is_explicitly_synthetic": manifest.get("classification") == "PUBLIC_SAFE_SYNTHETIC_DEMONSTRATION",
        "demo_preserves_visible_contradictions": int(manifest.get("contradiction_count", 0)) >= 1,
        "demo_final_decision_human_gated": manifest.get("authority", {}).get("final_acquisition") == "REQUIRE_HUMAN",
        "demo_live_order_denied": manifest.get("authority", {}).get("live_order") == "DENY",
        "demo_private_to_market_denied": manifest.get("authority", {}).get("private_to_public_market") == "DENY",
        "demo_pack_complete": {
            "manifest.json",
            "decision_brief.json",
            "qualification_receipt.json",
            "case_study.md",
            "dashboard.html",
        }.issubset(files),
        "demo_pack_digest_bound": len(str(demo.get("pack_sha256", ""))) == 64,
        "provider_maturity_not_overpromoted": rc5.get("maturity") == "PROVIDER_BINDING_READY",
        "production_claim_remains_false": rc5.get("production_claim") is False,
    }
    return {
        "passed": all(checks.values()),
        "release": "1.0.0-rc6",
        "maturity": "PROVIDER_BINDING_READY",
        "internal_product_state": "SYNTHETIC_DETERMINISTIC_QUALIFIED",
        "portfolio_state": "PORTFOLIO_DEMONSTRABLE_CANDIDATE",
        "qualification_receipt_sha256": qualification.receipt_sha256,
        "demo_pack_sha256": demo["pack_sha256"],
        "checks": checks,
        "production_claim": False,
    }
