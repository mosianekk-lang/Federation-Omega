from __future__ import annotations

import inspect
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from authority_snapshot import digest
from authority_snapshot_control_plane import (
    LIVE_PROFILE,
    REQUIRED_SCOPE,
    AuthoritySnapshotCommercialControlPlane,
)
from commercial_assurance import EvidenceReference, _OWNER_RESERVED_SERVICE_REQUESTS
from external_evidence import ExternalEvidenceAdmissionController
from governed_commercial_assurance import utc_now


class AtomicAuthoritySnapshotCommercialControlPlane(
    AuthoritySnapshotCommercialControlPlane
):
    """Canonical v6 control plane with atomic authority-bound action commits.

    The v5 control plane bound consequential objects to the latest durable provider
    authority acceptance. This wrapper closes the remaining partial-commit gap:
    provider authority is held stable for the whole action, all local state surfaces
    are restored exactly if any binding or persistence step fails, and successful
    actions receive a hash-linked transaction receipt.
    """

    TRANSACTION_FILE = "authority_action_transaction_ledger.jsonl"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.transaction_file = self.state_dir / self.TRANSACTION_FILE
        self._active_acceptance_entry: dict[str, Any] | None = None
        self._active_transaction: dict[str, Any] | None = None
        self._verify_transaction_ledger()

    @classmethod
    def canonical_public_signatures(cls) -> dict[str, str]:
        methods = (
            "submit_service_request",
            "approve_quote",
            "register_outcome_study",
            "register_verified_revenue_event",
        )
        return {
            name: str(inspect.signature(getattr(cls, name)))
            for name in methods
        }

    def _transaction_events(self) -> list[dict[str, Any]]:
        if not self.transaction_file.exists():
            return []
        return [
            json.loads(line)
            for line in self.transaction_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _verify_transaction_ledger(self) -> bool:
        previous = "GENESIS"
        prepared: set[str] = set()
        terminal: set[str] = set()
        for index, event in enumerate(self._transaction_events(), start=1):
            if event.get("sequence") != index:
                raise RuntimeError("authority action transaction sequence invalid")
            if event.get("previous_event_sha256") != previous:
                raise RuntimeError("authority action transaction chain invalid")
            payload = dict(event)
            observed_hash = payload.pop("event_sha256", None)
            if observed_hash != digest(payload):
                raise RuntimeError("authority action transaction hash invalid")
            transaction_id = str(event.get("transaction_id", ""))
            event_type = event.get("event")
            if event_type == "ACTION_PREPARED":
                if not transaction_id or transaction_id in prepared:
                    raise RuntimeError("authority action transaction prepare invalid")
                prepared.add(transaction_id)
            elif event_type in {"ACTION_COMMITTED", "ACTION_ROLLED_BACK"}:
                if transaction_id not in prepared or transaction_id in terminal:
                    raise RuntimeError("authority action transaction terminal invalid")
                terminal.add(transaction_id)
            else:
                raise RuntimeError("authority action transaction event invalid")
            previous = str(event["event_sha256"])
        return True

    def _append_transaction_event(
        self,
        event_type: str,
        transaction: dict[str, Any],
        *,
        result_sha256: str | None = None,
        failure_class: str | None = None,
    ) -> dict[str, Any]:
        self._verify_transaction_ledger()
        events = self._transaction_events()
        event: dict[str, Any] = {
            "sequence": len(events) + 1,
            "event": event_type,
            "transaction_id": transaction["transaction_id"],
            "stage": transaction["stage"],
            "action": transaction["action"],
            "object_id": transaction["object_id"],
            "snapshot_id": transaction["snapshot_id"],
            "snapshot_sha256": transaction["snapshot_sha256"],
            "acceptance_sequence": transaction["acceptance_sequence"],
            "acceptance_entry_sha256": transaction["acceptance_entry_sha256"],
            "domains": transaction["domains"],
            "recorded_at": transaction["recorded_at"],
            "previous_event_sha256": (
                events[-1]["event_sha256"] if events else "GENESIS"
            ),
        }
        if result_sha256 is not None:
            event["result_sha256"] = result_sha256
        if failure_class is not None:
            event["failure_class"] = failure_class
        event["event_sha256"] = digest(event)
        with self.transaction_file.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def _transaction_paths(self) -> tuple[Path, ...]:
        return (
            self.state_file,
            self.ledger_file,
            self.governance_state_file,
            self.governance_ledger_file,
            self.external_controller.state_file,
            self.external_controller.ledger_file,
        )

    def _capture_transaction_files(self) -> dict[Path, bytes | None]:
        return {
            path: path.read_bytes() if path.exists() else None
            for path in self._transaction_paths()
        }

    @staticmethod
    def _restore_file(path: Path, content: bytes | None) -> None:
        if content is None:
            if path.exists():
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".rollback.tmp")
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def _reload_external_controller(self) -> None:
        self.external_controller = ExternalEvidenceAdmissionController(
            self.state_dir / "governed_external_evidence",
            self.authority,
            owner_receipts=self.owner_receipts,
        )

    def _latest_locked_acceptance(self, *, now: str) -> dict[str, Any]:
        ledger = self.authority_snapshot_acceptance
        ledger._refresh()
        snapshot = self.authority_snapshot_validator.snapshot
        decision = ledger._preview_current(
            snapshot,
            self.authority_snapshot_validator,
            required_scope=REQUIRED_SCOPE,
            now=now,
        )
        if not decision.valid:
            raise PermissionError(
                "authority action transaction failed: "
                + ",".join(decision.reasons)
            )
        if snapshot is None or not ledger.entries:
            raise PermissionError(
                "authority action transaction failed: AUTHORITY_SNAPSHOT_NOT_ACCEPTED"
            )
        latest = ledger.entries[-1]
        if latest["snapshot_sha256"] != snapshot.snapshot_sha256:
            raise PermissionError(
                "authority action transaction failed: "
                "AUTHORITY_SNAPSHOT_NOT_LATEST_ACCEPTED"
            )
        return dict(latest)

    @contextmanager
    def _atomic_action(
        self,
        *,
        stage: str,
        action: str,
        object_id: str,
        domains: tuple[str, ...],
        now: str,
    ) -> Iterator[dict[str, Any]]:
        if self.authority_profile != LIVE_PROFILE:
            yield {}
            return
        if self._active_transaction is not None:
            raise RuntimeError("nested authority action transactions are not allowed")

        self.accept_authority_snapshot(now=now)

        ledger = self.authority_snapshot_acceptance
        with ledger._locked():
            entry = self._latest_locked_acceptance(now=now)
            snapshot = self.authority_snapshot_validator.snapshot
            assert snapshot is not None
            missing = sorted(set(domains) - set(snapshot.domains))
            if missing:
                raise PermissionError(
                    "authority action transaction failed: AUTHORITY_DOMAINS_MISSING:"
                    + ",".join(missing)
                )
            events = self._transaction_events()
            transaction: dict[str, Any] = {
                "transaction_id": f"AO-ACTION-{len(events) + 1:08d}",
                "stage": stage,
                "action": action,
                "object_id": object_id,
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_sha256": snapshot.snapshot_sha256,
                "acceptance_sequence": entry["sequence"],
                "acceptance_entry_sha256": entry["entry_sha256"],
                "domains": sorted(set(domains)),
                "recorded_at": now,
            }
            backup = self._capture_transaction_files()
            self._append_transaction_event("ACTION_PREPARED", transaction)
            self._active_acceptance_entry = entry
            self._active_transaction = transaction
            try:
                yield transaction
                current = self._latest_locked_acceptance(now=now)
                if current["entry_sha256"] != entry["entry_sha256"]:
                    raise RuntimeError(
                        "authority action transaction acceptance changed"
                    )
                transaction["result_sha256"] = self._transaction_result_sha256(
                    transaction
                )
                self._append_transaction_event(
                    "ACTION_COMMITTED",
                    transaction,
                    result_sha256=transaction["result_sha256"],
                )
            except Exception as exc:
                for path, content in backup.items():
                    self._restore_file(path, content)
                self._reload_external_controller()
                self._append_transaction_event(
                    "ACTION_ROLLED_BACK",
                    transaction,
                    failure_class=exc.__class__.__name__,
                )
                raise
            finally:
                self._active_transaction = None
                self._active_acceptance_entry = None

    def _transaction_result_sha256(self, transaction: dict[str, Any]) -> str:
        target = self._transaction_target(transaction)
        return digest(
            {
                "transaction_id": transaction["transaction_id"],
                "target": target,
                "snapshot_sha256": transaction["snapshot_sha256"],
                "acceptance_entry_sha256": transaction[
                    "acceptance_entry_sha256"
                ],
            }
        )

    def _transaction_target(self, transaction: dict[str, Any]) -> dict[str, Any]:
        mapping = {
            "service_request": "service_requests",
            "quote_approval": "quotes",
            "outcome_study": "case_studies",
            "revenue_event": "revenue_events",
        }
        collection = mapping.get(transaction["action"])
        if collection is None:
            return {
                "kind": transaction["action"],
                "object_id": transaction["object_id"],
            }
        state = self._read_state()
        try:
            stored = state[collection][transaction["object_id"]]
        except KeyError as exc:
            raise RuntimeError(
                "authority action transaction target missing after action"
            ) from exc
        return {
            "kind": transaction["action"],
            "object_id": transaction["object_id"],
            "record_sha256": digest(stored),
        }

    def _seal_state_object(
        self,
        *,
        stage: str,
        event: str,
        collection: str,
        object_id: str,
        transaction: dict[str, Any],
    ) -> dict[str, Any]:
        state = self._read_state()
        try:
            stored = state[collection][object_id]
        except KeyError as exc:
            raise RuntimeError(
                f"authority action commit target missing: {collection}/{object_id}"
            ) from exc
        seal = {
            "transaction_id": transaction["transaction_id"],
            "state": "ATOMIC_AUTHORITY_ACTION_COMMITTED",
            "snapshot_sha256": transaction["snapshot_sha256"],
            "acceptance_entry_sha256": transaction["acceptance_entry_sha256"],
            "domains": transaction["domains"],
        }
        seal["seal_sha256"] = digest(seal)
        stored["authority_action_commit"] = seal
        self._write_state(state)
        self._ledger(stage, event, object_id, stored)
        return stored

    def _require_snapshot_domain(
        self,
        domain: str,
        *,
        now: str,
        required_scope: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        if self._active_acceptance_entry is None:
            return super()._require_snapshot_domain(
                domain,
                now=now,
                required_scope=required_scope,
            )
        decision = self._snapshot_decision(
            domain,
            now=now,
            required_scope=required_scope,
        )
        if not decision.valid:
            raise PermissionError(
                "authority snapshot validation failed: "
                + ",".join(decision.reasons)
            )
        snapshot = self.authority_snapshot_validator.snapshot
        if (
            snapshot is None
            or snapshot.snapshot_sha256
            != self._active_acceptance_entry["snapshot_sha256"]
        ):
            raise PermissionError(
                "authority action transaction snapshot mismatch"
            )
        return dict(self._active_acceptance_entry)

    def _live_authority_verified(self, domain: str) -> bool:
        if self._active_acceptance_entry is None:
            return super()._live_authority_verified(domain)
        decision = self._snapshot_decision(domain, now=utc_now())
        snapshot = self.authority_snapshot_validator.snapshot
        return bool(
            decision.valid
            and snapshot is not None
            and snapshot.snapshot_sha256
            == self._active_acceptance_entry["snapshot_sha256"]
        )

    def _latest_acceptance_binding(
        self,
        domains: tuple[str, ...],
        *,
        now: str,
    ) -> dict[str, Any]:
        if self._active_acceptance_entry is None:
            return super()._latest_acceptance_binding(domains, now=now)
        snapshot = self.authority_snapshot_validator.snapshot
        assert snapshot is not None
        missing = sorted(set(domains) - set(snapshot.domains))
        if missing:
            raise PermissionError(
                "authority snapshot binding failed: AUTHORITY_DOMAINS_MISSING:"
                + ",".join(missing)
            )
        entry = self._active_acceptance_entry
        binding: dict[str, Any] = {
            "binding_state": "EXACT_LATEST_ACCEPTED_SNAPSHOT",
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_sha256": snapshot.snapshot_sha256,
            "acceptance_sequence": entry["sequence"],
            "acceptance_entry_sha256": entry["entry_sha256"],
            "domains": sorted(set(domains)),
            "domain_evidence_sha256": {
                domain: snapshot.domains[domain].evidence_sha256
                for domain in sorted(set(domains))
            },
            "bound_at": now,
            "atomic_transaction_id": self._active_transaction["transaction_id"],
        }
        binding["binding_sha256"] = digest(binding)
        return binding

    def submit_service_request(
        self,
        request_id: str,
        tenant_id: str,
        request_type: str,
        payload: dict[str, Any],
        requested_by: str,
        *,
        owner_decision_receipt_id: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        if (
            self.authority_profile == LIVE_PROFILE
            and request_type in _OWNER_RESERVED_SERVICE_REQUESTS
        ):
            with self._atomic_action(
                stage="C11",
                action="service_request",
                object_id=request_id,
                domains=("owner_decision",),
                now=current,
            ) as transaction:
                super().submit_service_request(
                    request_id,
                    tenant_id,
                    request_type,
                    payload,
                    requested_by,
                    owner_decision_receipt_id=owner_decision_receipt_id,
                    now=current,
                )
                return self._seal_state_object(
                    stage="C11",
                    event="service.atomic-authority-commit",
                    collection="service_requests",
                    object_id=request_id,
                    transaction=transaction,
                )
        return super().submit_service_request(
            request_id,
            tenant_id,
            request_type,
            payload,
            requested_by,
            owner_decision_receipt_id=owner_decision_receipt_id,
            now=current,
        )

    def approve_quote(
        self,
        quote_id: str,
        *,
        owner_decision_receipt_id: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        if self.authority_profile == LIVE_PROFILE:
            with self._atomic_action(
                stage="C13",
                action="quote_approval",
                object_id=quote_id,
                domains=("owner_decision",),
                now=current,
            ) as transaction:
                super().approve_quote(
                    quote_id,
                    owner_decision_receipt_id=owner_decision_receipt_id,
                    now=current,
                )
                return self._seal_state_object(
                    stage="C13",
                    event="quote.atomic-authority-commit",
                    collection="quotes",
                    object_id=quote_id,
                    transaction=transaction,
                )
        return super().approve_quote(
            quote_id,
            owner_decision_receipt_id=owner_decision_receipt_id,
            now=current,
        )

    def admit_external_evidence(
        self,
        evidence: Any,
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        gate_domain = {
            "payment_provider_revenue": "payment_provider",
            "external_case_study": "customer_market",
        }.get(evidence.gate)
        if self.authority_profile == LIVE_PROFILE and gate_domain:
            domains = (gate_domain,)
            if evidence.gate in {
                "payment_provider_revenue",
                "external_case_study",
            }:
                domains = tuple(sorted({gate_domain, "owner_decision"}))
            with self._atomic_action(
                stage="C12" if evidence.gate == "external_case_study" else "C13",
                action="external_evidence_admission",
                object_id=evidence.evidence_id,
                domains=domains,
                now=current,
            ) as transaction:
                decision = super().admit_external_evidence(evidence, now=current)
                decision = dict(decision)
                decision["authority_action_commit"] = {
                    "transaction_id": transaction["transaction_id"],
                    "state": "ATOMIC_AUTHORITY_ACTION_COMMITTED",
                    "snapshot_sha256": transaction["snapshot_sha256"],
                    "acceptance_entry_sha256": transaction[
                        "acceptance_entry_sha256"
                    ],
                    "domains": transaction["domains"],
                }
                return decision
        return super().admit_external_evidence(evidence, now=current)

    def register_outcome_study(
        self,
        study_id: str,
        tenant_id: str,
        metric: str,
        baseline: float,
        outcome: float,
        unit: str,
        lower_is_better: bool,
        evidence: list[EvidenceReference],
        *,
        external_evidence_id: str | None = None,
    ) -> dict[str, Any]:
        if self.authority_profile == LIVE_PROFILE and external_evidence_id:
            current = utc_now()
            with self._atomic_action(
                stage="C12",
                action="outcome_study",
                object_id=study_id,
                domains=("customer_market", "owner_decision"),
                now=current,
            ) as transaction:
                super().register_outcome_study(
                    study_id,
                    tenant_id,
                    metric,
                    baseline,
                    outcome,
                    unit,
                    lower_is_better,
                    evidence,
                    external_evidence_id=external_evidence_id,
                )
                return self._seal_state_object(
                    stage="C12",
                    event="study.atomic-authority-commit",
                    collection="case_studies",
                    object_id=study_id,
                    transaction=transaction,
                )
        return super().register_outcome_study(
            study_id,
            tenant_id,
            metric,
            baseline,
            outcome,
            unit,
            lower_is_better,
            evidence,
            external_evidence_id=external_evidence_id,
        )

    def register_verified_revenue_event(
        self,
        event_id: str,
        contract_id: str,
        amount: float,
        currency: str,
        provider_evidence: Any,
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        if self.authority_profile == LIVE_PROFILE:
            with self._atomic_action(
                stage="C13",
                action="revenue_event",
                object_id=event_id,
                domains=("payment_provider", "owner_decision"),
                now=current,
            ) as transaction:
                super().register_verified_revenue_event(
                    event_id,
                    contract_id,
                    amount,
                    currency,
                    provider_evidence,
                    now=current,
                )
                return self._seal_state_object(
                    stage="C13",
                    event="revenue.atomic-authority-commit",
                    collection="revenue_events",
                    object_id=event_id,
                    transaction=transaction,
                )
        return super().register_verified_revenue_event(
            event_id,
            contract_id,
            amount,
            currency,
            provider_evidence,
            now=current,
        )

    def authority_action_transaction_readback(self) -> dict[str, Any]:
        self._verify_transaction_ledger()
        events = self._transaction_events()
        prepared = [event for event in events if event["event"] == "ACTION_PREPARED"]
        committed = [
            event for event in events if event["event"] == "ACTION_COMMITTED"
        ]
        rolled_back = [
            event for event in events if event["event"] == "ACTION_ROLLED_BACK"
        ]
        terminal_ids = {
            event["transaction_id"] for event in committed + rolled_back
        }
        return {
            "ledger_file": self.TRANSACTION_FILE,
            "integrity": "VERIFIED",
            "events": len(events),
            "prepared": len(prepared),
            "committed": len(committed),
            "rolled_back": len(rolled_back),
            "unterminated": sorted(
                event["transaction_id"]
                for event in prepared
                if event["transaction_id"] not in terminal_ids
            ),
            "partial_state_visible_after_rollback": False,
            "provider_authority_held_for_full_action": True,
            "exact_file_restoration_on_failure": True,
        }

    def governed_authority_readback(self) -> dict[str, Any]:
        result = super().governed_authority_readback()
        result["canonical_class"] = self.__class__.__name__
        result["predecessor_class"] = (
            "AuthoritySnapshotCommercialControlPlane"
        )
        result["authority_action_transactions"] = (
            self.authority_action_transaction_readback()
        )
        return result
