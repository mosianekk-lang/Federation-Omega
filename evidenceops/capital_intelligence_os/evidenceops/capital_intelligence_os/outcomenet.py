from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Mapping
import json
import uuid

from .models import canonical_json, utc_now_iso
from .store import SqliteStateStore


@dataclass(frozen=True)
class DataUseConsent:
    tenant_id: str
    share_aggregated_outcomes: bool
    minimum_cohort: int = 5

    def validate(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if self.minimum_cohort < 5:
            raise ValueError("minimum_cohort cannot be below 5")


@dataclass(frozen=True)
class OutcomeObservation:
    tenant_id: str
    cohort: str
    metric: str
    predicted: float
    actual: float
    metadata: Mapping[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=utc_now_iso)
    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class CohortAggregate:
    cohort: str
    metric: str
    tenant_count: int
    observation_count: int
    mean_predicted: float
    mean_actual: float
    mean_error: float
    mean_absolute_error: float
    rmse: float


class OutcomeNet:
    """Opt-in, cohort-gated outcome learning without raw cross-tenant export."""

    def __init__(self, store: SqliteStateStore, system_minimum_cohort: int = 5) -> None:
        if system_minimum_cohort < 5:
            raise ValueError("system_minimum_cohort cannot be below 5")
        self.store = store
        self.system_minimum_cohort = system_minimum_cohort

    def set_consent(self, consent: DataUseConsent) -> None:
        consent.validate()
        self.store._connection.execute(
            "INSERT INTO outcome_consents(tenant_id,share_aggregated,minimum_cohort,updated_at) VALUES (?,?,?,?) ON CONFLICT(tenant_id) DO UPDATE SET share_aggregated=excluded.share_aggregated,minimum_cohort=excluded.minimum_cohort,updated_at=excluded.updated_at",
            (consent.tenant_id, int(consent.share_aggregated_outcomes), consent.minimum_cohort, utc_now_iso()),
        )

    def record(self, observation: OutcomeObservation) -> None:
        row = self.store._connection.execute("SELECT share_aggregated FROM outcome_consents WHERE tenant_id=?", (observation.tenant_id,)).fetchone()
        if not row or not bool(row[0]):
            raise PermissionError("OUTCOME_SHARING_NOT_CONSENTED")
        self.store._connection.execute(
            "INSERT INTO outcomes(observation_id,tenant_id,cohort,metric,predicted,actual,observed_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)",
            (observation.observation_id, observation.tenant_id, observation.cohort, observation.metric, float(observation.predicted), float(observation.actual), observation.observed_at, canonical_json(dict(observation.metadata))),
        )

    def aggregate(self, cohort: str, metric: str) -> CohortAggregate | None:
        rows = self.store._connection.execute(
            """SELECT o.tenant_id,o.predicted,o.actual,c.minimum_cohort
               FROM outcomes o JOIN outcome_consents c ON c.tenant_id=o.tenant_id
               WHERE o.cohort=? AND o.metric=? AND c.share_aggregated=1""",
            (cohort, metric),
        ).fetchall()
        if not rows:
            return None
        tenant_count = len({r["tenant_id"] for r in rows})
        threshold = max([self.system_minimum_cohort] + [int(r["minimum_cohort"]) for r in rows])
        if tenant_count < threshold:
            return None
        # Equal tenant weighting bounds contribution from prolific tenants. This is
        # privacy/risk reduction, not a formal differential-privacy guarantee.
        by_tenant: dict[str, list[tuple[float, float]]] = {}
        for r in rows:
            by_tenant.setdefault(r["tenant_id"], []).append((float(r["predicted"]), float(r["actual"])))
        tenant_pairs = []
        for tenant_id in sorted(by_tenant):
            observations = by_tenant[tenant_id]
            tenant_pairs.append((
                sum(p for p, _ in observations) / len(observations),
                sum(a for _, a in observations) / len(observations),
            ))
        predicted = [p for p, _ in tenant_pairs]
        actual = [a for _, a in tenant_pairs]
        errors = [a - p for p, a in tenant_pairs]
        n = len(tenant_pairs)
        return CohortAggregate(
            cohort=cohort,
            metric=metric,
            tenant_count=tenant_count,
            observation_count=len(rows),
            mean_predicted=sum(predicted) / n,
            mean_actual=sum(actual) / n,
            mean_error=sum(errors) / n,
            mean_absolute_error=sum(abs(e) for e in errors) / n,
            rmse=sqrt(sum(e * e for e in errors) / n),
        )

    def tenant_observations(self, tenant_id: str) -> list[OutcomeObservation]:
        rows = self.store._connection.execute("SELECT * FROM outcomes WHERE tenant_id=? ORDER BY observed_at,observation_id", (tenant_id,)).fetchall()
        return [OutcomeObservation(
            tenant_id=r["tenant_id"], cohort=r["cohort"], metric=r["metric"], predicted=float(r["predicted"]), actual=float(r["actual"]),
            metadata=json.loads(r["metadata_json"]), observed_at=r["observed_at"], observation_id=r["observation_id"]
        ) for r in rows]
