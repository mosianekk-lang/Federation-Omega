from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Any, Iterable, Mapping

from .authority import AuthorityGuard
from .autopilot import Autopilot
from .models import ActionRequest, Claim, Event, stable_sha256
from .proofgraph import ProofGraph
from .restricted import RestrictedListRegistry
from .store import SqliteStateStore
from .tenancy import TenantBoundaryGuard, TenantContext


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


class DurableAutopilotRuntime:
    """Tenant-scoped, idempotent, replayable reference runtime."""

    def __init__(self, store: SqliteStateStore) -> None:
        self.store = store
        self.restrictions = RestrictedListRegistry(store)
        self._autopilots: dict[str, Autopilot] = {}

    def _build_autopilot(self, tenant_id: str) -> Autopilot:
        graph = ProofGraph()
        for source, dependent in self.store.load_dependencies(tenant_id):
            graph.add_dependency(source, dependent)
        for claim in self.store.load_claims(tenant_id):
            graph.add_claim(claim)
        authority = AuthorityGuard(restriction_lookup=self.restrictions, tenant_id=tenant_id)
        return Autopilot(graph=graph, authority=authority)

    def autopilot(self, tenant_id: str) -> Autopilot:
        if tenant_id not in self._autopilots:
            self._autopilots[tenant_id] = self._build_autopilot(tenant_id)
        return self._autopilots[tenant_id]

    def register_dependency(self, ctx: TenantContext, source_subject: str, dependent_subject: str) -> None:
        ctx.validate()
        self.store.add_dependency(ctx.tenant_id, source_subject, dependent_subject)
        self.autopilot(ctx.tenant_id).graph.add_dependency(source_subject, dependent_subject)

    def process(
        self,
        ctx: TenantContext,
        event: Event,
        claims: Iterable[Claim] = (),
        actions: Iterable[ActionRequest] = (),
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        ctx.validate()
        TenantBoundaryGuard.assert_domain(ctx, event.domain)
        key = idempotency_key or f"event:{event.event_id}"
        claim_list = list(claims)
        action_list = list(actions)
        request_hash = stable_sha256({"event": _plain(event), "claims": _plain(claim_list), "actions": _plain(action_list)})
        cached_record = self.store.get_idempotency_record(ctx.tenant_id, key)
        if cached_record is not None:
            if cached_record["request_hash"] and cached_record["request_hash"] != request_hash:
                raise ValueError("IDEMPOTENCY_KEY_REUSE_MISMATCH")
            return {**cached_record["result"], "replayed": True}
        with self.store.transaction():
            inserted = self.store.append_event(ctx.tenant_id, event)
            if not inserted:
                cached_record = self.store.get_idempotency_record(ctx.tenant_id, f"event:{event.event_id}")
                if cached_record is not None:
                    if cached_record["request_hash"] and cached_record["request_hash"] != request_hash:
                        raise ValueError("EVENT_ID_REUSE_MISMATCH")
                    return {**cached_record["result"], "replayed": True}
                raise RuntimeError("DUPLICATE_EVENT_WITHOUT_RECEIPT")
            result = self.autopilot(ctx.tenant_id).process(event, claim_list, action_list)
            for claim in claim_list:
                self.store.save_claim(ctx.tenant_id, claim)
            persistent_learning = self.store.append_learning(ctx.tenant_id, "SUCCESS", "DURABLE_AUTOPILOT_EVENT", {
                "event_id": event.event_id,
                "claim_count": len(result.claim_ids),
                "contradiction_count": len(result.contradiction_ids),
                "impact_count": len(result.impacted_subjects),
                "action_dispositions": [d.disposition.value for d in result.action_decisions],
            })
            plain_result = _plain(result)
            plain_result["learning_event_hash"] = persistent_learning.event_hash
            receipt = {
                "tenant_id": ctx.tenant_id,
                "event_id": event.event_id,
                "replayed": False,
                "result": plain_result,
                "state_digest": self.store.tenant_state_digest(ctx.tenant_id),
            }
            receipt["receipt_hash"] = stable_sha256(receipt)
            self.store.save_idempotent_result(ctx.tenant_id, key, receipt, request_hash=request_hash)
            if key != f"event:{event.event_id}":
                self.store.save_idempotent_result(ctx.tenant_id, f"event:{event.event_id}", receipt, request_hash=request_hash)
        return receipt

    def restart(self, tenant_id: str) -> None:
        self._autopilots.pop(tenant_id, None)
        self.autopilot(tenant_id)

    def health(self, tenant_id: str) -> dict[str, Any]:
        return {
            "database_quick_check": self.store.quick_check(),
            "learning_chain_valid": self.store.verify_learning_chain(tenant_id),
            "claim_count": self.store.count_rows("claims", tenant_id),
            "event_count": self.store.count_rows("events", tenant_id),
            "tenant_state_digest": self.store.tenant_state_digest(tenant_id),
        }
