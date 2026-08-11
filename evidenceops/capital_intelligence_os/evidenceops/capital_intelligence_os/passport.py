from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from .models import Claim, EvidenceStatus, stable_sha256, utc_now_iso
from .proofgraph import ProofGraph
from .tenancy import TenantContext


@dataclass(frozen=True)
class PassportFact:
    predicate: str
    claim_id: str
    status: str
    confidence: float
    fingerprint: str
    freshest_observation: str | None
    stale: bool


@dataclass(frozen=True)
class DealPassport:
    tenant_id: str
    company_id: str
    issued_at: str
    facts: tuple[PassportFact, ...]
    required_predicates: tuple[str, ...]
    missing_predicates: tuple[str, ...]
    conflicting_predicates: tuple[str, ...]
    readiness_score: float
    integrity_digest: str = ""

    def payload(self) -> dict:
        data = asdict(self)
        data.pop("integrity_digest", None)
        return data

    def validate_integrity(self) -> bool:
        return stable_sha256(self.payload()) == self.integrity_digest


class DealPassportIssuer:
    """Issues a deterministic evidence passport; it is not a legal/PKI signature."""

    def issue(
        self,
        ctx: TenantContext,
        company_id: str,
        claims: Iterable[Claim],
        required_predicates: Iterable[str],
        stale_after_days: Mapping[str, float] | None = None,
        now: datetime | None = None,
    ) -> DealPassport:
        ctx.validate()
        graph = ProofGraph()
        relevant = [c for c in claims if c.subject_id == company_id]
        for claim in relevant:
            graph.add_claim(claim)
        now = now or datetime.now(timezone.utc)
        stale_after_days = dict(stale_after_days or {})
        required = tuple(sorted(set(required_predicates)))
        facts: list[PassportFact] = []
        predicates = sorted({c.predicate for c in relevant})
        conflicts: list[str] = []
        for predicate in predicates:
            current = graph.current_claims(company_id, predicate)
            values = {c.normalized_value() for c in current}
            if len(values) > 1:
                conflicts.append(predicate)
            if not current:
                continue
            claim = max(current, key=lambda c: (self._status_rank(c.status), c.confidence, c.created_at))
            observations = [e.observed_at for e in claim.evidence if e.observed_at]
            freshest = max(observations) if observations else None
            stale = False
            threshold = stale_after_days.get(predicate)
            if threshold is not None and freshest:
                observed = datetime.fromisoformat(freshest.replace("Z", "+00:00"))
                stale = (now - observed).total_seconds() / 86400 > threshold
            elif threshold is not None and not freshest:
                stale = True
            facts.append(PassportFact(predicate, claim.claim_id, claim.status.value, claim.confidence, claim.fingerprint(), freshest, stale))
        missing = tuple(sorted(set(required) - {f.predicate for f in facts}))
        completeness = 1.0 if not required else 1.0 - len(missing) / len(required)
        freshness = 1.0 if not facts else 1.0 - sum(1 for f in facts if f.stale) / len(facts)
        verification = 1.0 if not facts else sum(1 for f in facts if f.status in {EvidenceStatus.VERIFIED.value, EvidenceStatus.CORROBORATED.value}) / len(facts)
        conflict_free = 1.0 if not predicates else 1.0 - len(conflicts) / len(predicates)
        score = max(0.0, min(1.0, 0.40 * completeness + 0.20 * freshness + 0.25 * verification + 0.15 * conflict_free))
        base = DealPassport(ctx.tenant_id, company_id, utc_now_iso(), tuple(facts), required, missing, tuple(sorted(conflicts)), score, "")
        return DealPassport(**{**asdict(base), "facts": tuple(facts), "required_predicates": required, "missing_predicates": missing, "conflicting_predicates": tuple(sorted(conflicts)), "integrity_digest": stable_sha256(base.payload())})

    @staticmethod
    def _status_rank(status: EvidenceStatus) -> int:
        return {
            EvidenceStatus.VERIFIED: 6,
            EvidenceStatus.CORROBORATED: 5,
            EvidenceStatus.USER_SUPPLIED: 4,
            EvidenceStatus.INFERENCE: 3,
            EvidenceStatus.MODEL_ESTIMATE: 2,
            EvidenceStatus.UNVERIFIED: 1,
        }[status]
