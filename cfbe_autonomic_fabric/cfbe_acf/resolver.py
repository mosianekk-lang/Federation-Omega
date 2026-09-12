from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .models import ProviderDescriptor, proof_rank
from .util import parse_utc


_AUTHORITY = {f"A{index}": index for index in range(6)}
_STRATEGY = {"REUSE": 4, "REPAIR": 3, "ADAPT": 2, "FORGE": 1}
_COST = {"ZERO": 3, "INCLUDED": 2}


class CapabilityResolver:
    def resolve(
        self,
        compiled_intent: dict[str, Any],
        providers: Iterable[dict[str, Any] | ProviderDescriptor],
        now: datetime | None = None,
        verified_proof_stages: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        constraints = compiled_intent["constraints"]
        required = set(compiled_intent["required_capabilities"])
        accepted, rejected = [], []
        for raw in providers:
            provider = raw if isinstance(raw, ProviderDescriptor) else ProviderDescriptor.from_mapping(raw)
            reasons = []
            missing = sorted(required - set(provider.capabilities))
            if missing:
                reasons.append("MISSING_CAPABILITIES:" + ",".join(missing))
            if provider.state not in {"VERIFIED_LIVE", "ACTIVE_PARTIAL"}:
                reasons.append("STATE_NOT_ADMISSIBLE:" + provider.state)
            if provider.effectful != constraints["effectful"]:
                reasons.append("EFFECTFUL_DECLARATION_MISMATCH")
            effective_effectful = provider.effectful or constraints["effectful"]
            if effective_effectful and provider.state != "VERIFIED_LIVE":
                reasons.append("EFFECTFUL_ROUTE_REQUIRES_VERIFIED_LIVE")
            if _AUTHORITY[provider.authority_ceiling] < _AUTHORITY[constraints["authority_class"]]:
                reasons.append("AUTHORITY_INSUFFICIENT")
            if provider.cost_class not in _COST:
                reasons.append("COST_UNKNOWN_OR_UNAPPROVED")
            if constraints["require_semantic_readback"] and not provider.semantic_readback:
                reasons.append("SEMANTIC_READBACK_MISSING")
            if constraints["require_reversible"] and not provider.reversible:
                reasons.append("ROLLBACK_MISSING")
            if proof_rank(provider.proof_stage) < proof_rank(constraints["minimum_proof_stage"]):
                reasons.append("PROOF_STAGE_INSUFFICIENT")
            verified_stage = (verified_proof_stages or {}).get(provider.id)
            if proof_rank(provider.proof_stage) > proof_rank("DISCOVERED"):
                if not provider.proof_refs:
                    reasons.append("PROOF_REFERENCES_MISSING")
                if verified_stage is None:
                    reasons.append("VALIDATED_PROOF_CHAIN_MISSING")
                elif proof_rank(verified_stage) < proof_rank(provider.proof_stage):
                    reasons.append("PROOF_STAGE_NOT_DERIVED_FROM_RECEIPTS")
            age = (now - parse_utc(provider.observed_at)).total_seconds()
            if age < -300:
                reasons.append("OBSERVATION_FROM_FUTURE")
            age = max(0.0, age)
            if age > constraints["maximum_age_seconds"]:
                reasons.append("PROOF_STALE")
            if provider.owner_burden > constraints["maximum_user_burden"]:
                reasons.append("USER_BURDEN_EXCEEDED")
            if reasons:
                rejected.append({"provider_id": provider.id, "reasons": sorted(reasons)})
                continue
            score = (
                proof_rank(provider.proof_stage) * 10
                + _STRATEGY[provider.strategy] * 6
                + _COST[provider.cost_class] * 3
                + (5 if provider.semantic_readback else 0)
                + (4 if provider.reversible else 0)
                - provider.risk * 5
                - provider.owner_burden * 10
                - min(age / 3600, 24) * 0.1
            )
            accepted.append(
                {
                    "provider_id": provider.id,
                    "strategy": provider.strategy,
                    "score": round(score, 6),
                    "proof_stage": provider.proof_stage.value,
                    "failure_domain": provider.failure_domain,
                    "effectful": effective_effectful,
                    "proof_refs": list(provider.proof_refs),
                }
            )
        accepted.sort(key=lambda row: (-row["score"], row["provider_id"]))
        winner = accepted[0] if accepted else None
        return {
            "schema": "CFBE-ACF-RESOLUTION-V1",
            "mission_id": compiled_intent["mission_id"],
            "decision": "ROUTE_SELECTED" if winner else "NO_ADMISSIBLE_ROUTE",
            "winner": winner,
            "alternatives": accepted[1:3],
            "rejected": sorted(rejected, key=lambda row: row["provider_id"]),
            "effectful_paths_allowed": 1 if winner and winner["effectful"] else 0,
            "provider_authority_inherited": False,
        }
