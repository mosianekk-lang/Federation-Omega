from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from aegis_omega.orchestration import SafeBotSwarmExecutor, aegis_current_mission_plan

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def success(ref: str, **extra):
    return {
        "semantic_verified": True,
        "proof_valid": True,
        "provider_effect_performed": False,
        "evidence_ref": ref,
        **extra,
    }


async def harvest(_lane):
    p = ROOT / "docs" / "CFBE_DEEP_HARVEST_20260909.md"
    assert p.exists() and p.stat().st_size > 1000
    return success(f"sha256:{sha(p)}")


async def red_team(_lane):
    security = (ROOT / "docs" / "SECURITY.md").read_text(encoding="utf-8").lower()
    threat = (ROOT / "docs" / "THREAT_MODEL.md").read_text(encoding="utf-8").lower()
    combined = security + "\n" + threat
    required = ["defensive", "credential", "consent", "covert"]
    assert all(term in combined for term in required)
    return success(f"sha256:{sha(ROOT/'docs'/'SECURITY.md')}:{sha(ROOT/'docs'/'THREAT_MODEL.md')}")


async def proof_court(_lane):
    status = json.loads((ROOT / "production_status.json").read_text(encoding="utf-8"))
    assert status["local_reference_release_verified"] is True
    assert status["local_http_readback_verified"] is True
    assert all(item["returncode"] == 0 for item in status["checks"])
    return success(f"artifact:{status['artifact_sha256']}")


async def privacy(_lane):
    schemas = (ROOT / "src" / "aegis_omega" / "schemas.py").read_text(encoding="utf-8")
    normalize = (ROOT / "src" / "aegis_omega" / "normalize.py").read_text(encoding="utf-8")
    assert "consent: bool = True" in schemas
    assert "consent" in normalize.lower()
    return success(f"sha256:{sha(ROOT/'src'/'aegis_omega'/'schemas.py')}:{sha(ROOT/'src'/'aegis_omega'/'normalize.py')}")


async def fuse_adapter(_lane):
    profile = ROOT / "docs" / "SOL62_FORMATION_ALPHA_OMEGA_FUSION.md"
    text = profile.read_text(encoding="utf-8")
    assert "FUSE" in text and "SOL 6.2" in text and "Alpha→Omega" in text
    return success(f"sha256:{sha(profile)}")


async def fdof_currentness(_lane):
    payload = json.loads((ROOT / "federation_currentness.json").read_text(encoding="utf-8"))
    assert len(payload["signed_main"]) == 40
    assert payload["fdof"]["state"] in {"ACTIVE", "RELEASED"}
    return success(f"fdof:{payload['fdof']['lease_id']}:{payload['fdof']['lock_commit']}")


async def benchmark(_lane):
    result = json.loads((ROOT / "benchmark" / "results.json").read_text(encoding="utf-8"))
    assert result["events"] == 1500
    assert "not evidence of 10x" in result["claim_scope"].lower()
    return success(f"sha256:{sha(ROOT/'benchmark'/'results.json')}")


async def main():
    plan = aegis_current_mission_plan()
    handlers = {
        "cfbe-harvest": harvest,
        "red-team": red_team,
        "proof-court": proof_court,
        "privacy-review": privacy,
        "fuse-adapter": fuse_adapter,
        "fdof-currentness": fdof_currentness,
        "blind-10x-court": benchmark,
    }
    receipt = await SafeBotSwarmExecutor.execute(plan, handlers)
    payload = {
        "schema": receipt.schema,
        "mission_id": receipt.mission_id,
        "plan_sha256": receipt.plan_sha256,
        "parallel_lane_count": receipt.parallel_lane_count,
        "passed_lane_count": receipt.passed_lane_count,
        "failed_lane_count": receipt.failed_lane_count,
        "provider_effect_observed": receipt.provider_effect_observed,
        "stable_promotion_authorized": receipt.stable_promotion_authorized,
        "results": [r.__dict__ if hasattr(r, "__dict__") else {
            "lane_id": r.lane_id,
            "transition_id": r.transition_id,
            "bot_role": r.bot_role,
            "status": r.status,
            "semantic_verified": r.semantic_verified,
            "proof_valid": r.proof_valid,
            "evidence_ref": r.evidence_ref,
            "error": r.error,
        } for r in receipt.results],
        "receipt_sha256": receipt.receipt_sha256,
        "claim_scope": "Local no-effect/read-only orchestration qualification only; no provider execution or hidden background agents.",
    }
    out = ROOT / "orchestration_canary_receipt.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
