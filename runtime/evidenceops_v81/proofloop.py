#!/usr/bin/env python3
"""EvidenceOps v8.1 ProofLoop living-matter runtime.

This module implements a bounded, proof-carrying A0/A1 control plane:

* proof contracts are compiled before execution;
* source hashes must be byte-derived 64-character SHA-256 values;
* verified facts require registered sources;
* case-wall boundaries reject cross-matter writes;
* verified facts cannot be silently overwritten;
* longitudinal value cycles are hash chained; and
* consequential actions remain denied unless a future workflow-specific
  authority receipt is independently verified.

The runtime never sends, files, serves, publishes, settles, records hearings,
performs provider administration, or mutates external legal systems.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "8.1.0"
PROOF_CONTRACT_SCHEMA = "EVIDENCEOPS_V81_PROOF_CONTRACT_V1"
MATTER_TWIN_SCHEMA = "EVIDENCEOPS_V81_LIVING_MATTER_TWIN_V1"
VALUE_CYCLE_SCHEMA = "EVIDENCEOPS_V81_LONGITUDINAL_VALUE_CYCLE_V1"
RELEASE_RECEIPT_SCHEMA = "EVIDENCEOPS_V81_ENGINEERING_RELEASE_RECEIPT_V1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_AUTHORITY = {"A0", "A1"}
_ALLOWED_FACT_CLASSES = {
    "VERIFIED_FACT",
    "SOURCE_SUPPORTED_STATEMENT",
    "PARTY_ALLEGATION",
    "ADMISSION",
    "INFERENCE",
    "HYPOTHESIS",
    "UNKNOWN",
    "UNVERIFIED",
    "RETRACTED",
    "SUPERSEDED",
    "DISPROVED",
}
_CONSEQUENTIAL_ACTIONS = {
    "send",
    "file",
    "serve",
    "publish",
    "settle",
    "accept_settlement",
    "make_admission",
    "record_hearing",
    "delete_source",
    "destructive_mutation",
    "provider_admin",
    "financial_action",
}
_INTERNAL_ACTIONS = {
    "observe",
    "search",
    "hash",
    "register_source",
    "classify",
    "analyse",
    "draft",
    "prepare",
    "verify",
    "simulate",
    "audit",
    "render_preview",
}


class ProofContractError(ValueError):
    """Raised when a mission lacks an executable proof contract."""


class MatterTwinError(ValueError):
    """Raised when a matter-twin invariant is violated."""


class AuthorityError(PermissionError):
    """Raised when a requested action exceeds the authority envelope."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _require_nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProofContractError(f"{label} must be non-empty text")
    return value.strip()


def _validate_source(source: Mapping[str, Any]) -> None:
    source_id = _require_nonempty_text(source.get("source_id"), "source_id")
    if source.get("source_state") != "VERIFIED_BYTES":
        raise ProofContractError(f"{source_id}: source_state must be VERIFIED_BYTES")
    if not valid_sha256(source.get("sha256")):
        raise ProofContractError(
            f"{source_id}: sha256 must be a byte-derived 64-character lowercase digest"
        )
    pages = source.get("pages")
    if not isinstance(pages, int) or pages <= 0:
        raise ProofContractError(f"{source_id}: pages must be a positive integer")
    if source.get("external_effect") not in (None, False):
        raise ProofContractError(
            f"{source_id}: source registration cannot declare an external effect"
        )


def compile_proof_contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Compile and validate an executable A0/A1 proof contract."""

    matter_id = _require_nonempty_text(manifest.get("matter_id"), "matter_id")
    mission_id = _require_nonempty_text(manifest.get("mission_id"), "mission_id")
    requested_outcome = _require_nonempty_text(
        manifest.get("requested_outcome"), "requested_outcome"
    )
    authority = manifest.get("authority", {})
    if not isinstance(authority, Mapping):
        raise ProofContractError("authority must be an object")
    ceiling = authority.get("ceiling")
    if ceiling not in _ALLOWED_AUTHORITY:
        raise ProofContractError("authority ceiling must be A0 or A1")
    if authority.get("external_effects") != 0:
        raise ProofContractError(
            "external_effects must be zero for the v8.1 internal profile"
        )

    prohibited = manifest.get("prohibited_inferences")
    if not isinstance(prohibited, list) or not prohibited or not all(
        isinstance(item, str) and item.strip() for item in prohibited
    ):
        raise ProofContractError(
            "prohibited_inferences must be a non-empty text list"
        )

    verification_gates = manifest.get("verification_gates")
    if not isinstance(verification_gates, list) or not verification_gates:
        raise ProofContractError("verification_gates must be a non-empty list")

    release_gate = manifest.get("release_gate")
    if not isinstance(release_gate, Mapping):
        raise ProofContractError("release_gate must be an object")
    if release_gate.get("state") not in {
        "INTERNAL_HOLD",
        "DISPLAYED_FOR_REVIEW",
        "INTERNAL_HOLD_DISPLAYED_FOR_REVIEW",
    }:
        raise ProofContractError(
            "release_gate state is not an approved internal state"
        )
    forbidden_release_states = (
        "filed",
        "served",
        "emailed",
        "published",
        "settled",
    )
    if any(release_gate.get(key) is not False for key in forbidden_release_states):
        raise ProofContractError("all consequential release flags must be false")

    rollback = manifest.get("rollback")
    if not isinstance(rollback, Mapping) or not rollback.get("method"):
        raise ProofContractError("rollback method is required")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ProofContractError("at least one verified source is required")
    source_ids: list[str] = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise ProofContractError("each source must be an object")
        _validate_source(source)
        source_ids.append(str(source["source_id"]))
    if len(source_ids) != len(set(source_ids)):
        raise ProofContractError("source IDs must be unique")

    case_wall = manifest.get("case_wall")
    if not isinstance(case_wall, Mapping):
        raise ProofContractError("case_wall must be an object")
    if case_wall.get("primary_matter_id") != matter_id:
        raise ProofContractError("case_wall primary matter must match matter_id")
    excluded = case_wall.get("excluded_matter_ids", [])
    if not isinstance(excluded, list) or matter_id in excluded:
        raise ProofContractError("excluded matter IDs are invalid")

    compiled: dict[str, Any] = {
        "schema": PROOF_CONTRACT_SCHEMA,
        "version": VERSION,
        "contract_id": f"PC-{mission_id}",
        "mission_id": mission_id,
        "matter_id": matter_id,
        "requested_outcome": requested_outcome,
        "authority": {
            "ceiling": ceiling,
            "external_effects": 0,
            "consequential_authority": False,
        },
        "source_ids": sorted(source_ids),
        "case_wall": {
            "primary_matter_id": matter_id,
            "excluded_matter_ids": sorted(str(item) for item in excluded),
        },
        "prohibited_inferences": sorted(item.strip() for item in prohibited),
        "verification_gates": list(verification_gates),
        "release_gate": dict(release_gate),
        "rollback": dict(rollback),
        "state": "READY_FOR_INTERNAL_EXECUTION",
        "truth_boundary": (
            "The contract authorises only A0/A1 internal and reversible work. "
            "It does not grant filing, service, sending, publishing, settlement, "
            "hearing-recording, financial, destructive or provider-admin authority."
        ),
    }
    compiled["contract_sha256"] = digest(compiled)
    return compiled


def verify_proof_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema") != PROOF_CONTRACT_SCHEMA:
        raise ProofContractError("unexpected proof-contract schema")
    supplied = contract.get("contract_sha256")
    if not valid_sha256(supplied):
        raise ProofContractError("contract hash is absent or invalid")
    candidate = dict(contract)
    candidate.pop("contract_sha256", None)
    if digest(candidate) != supplied:
        raise ProofContractError("proof-contract hash mismatch")
    if contract.get("state") != "READY_FOR_INTERNAL_EXECUTION":
        raise ProofContractError("proof contract is not executable")


@dataclass(frozen=True)
class AuthorityDecision:
    action: str
    allowed: bool
    state: str
    reason: str
    authority_ceiling: str
    external_effects: int = 0

    def as_dict(self) -> dict[str, Any]:
        value = {
            "action": self.action,
            "allowed": self.allowed,
            "state": self.state,
            "reason": self.reason,
            "authority_ceiling": self.authority_ceiling,
            "external_effects": self.external_effects,
        }
        value["decision_sha256"] = digest(value)
        return value


class AuthorityGateway:
    """Fail-closed authority gate for the v8.1 internal profile."""

    def __init__(self, authority_ceiling: str = "A1") -> None:
        if authority_ceiling not in _ALLOWED_AUTHORITY:
            raise AuthorityError("only A0/A1 profiles are available")
        self.authority_ceiling = authority_ceiling

    def evaluate(self, action: str) -> AuthorityDecision:
        normalized = action.strip().casefold().replace(" ", "_")
        if normalized in _CONSEQUENTIAL_ACTIONS:
            return AuthorityDecision(
                action=normalized,
                allowed=False,
                state="DENIED_CONSEQUENTIAL_AUTHORITY_HELD",
                reason=(
                    "workflow-specific consequential authority and exact target "
                    "readback are absent"
                ),
                authority_ceiling=self.authority_ceiling,
            )
        if normalized in _INTERNAL_ACTIONS:
            return AuthorityDecision(
                action=normalized,
                allowed=True,
                state="ALLOWED_INTERNAL_REVERSIBLE",
                reason="action is internal, bounded and reversible within A0/A1",
                authority_ceiling=self.authority_ceiling,
            )
        return AuthorityDecision(
            action=normalized,
            allowed=False,
            state="DENIED_UNKNOWN_ACTION_DEFAULT_DENY",
            reason="unknown actions are denied by default",
            authority_ceiling=self.authority_ceiling,
        )


class MatterTwin:
    """Append-only, case-walled and hash-chained living matter model."""

    def __init__(
        self,
        matter_id: str,
        excluded_matter_ids: Iterable[str] = (),
        authority_ceiling: str = "A1",
        state: Mapping[str, Any] | None = None,
    ) -> None:
        if authority_ceiling not in _ALLOWED_AUTHORITY:
            raise MatterTwinError("invalid authority ceiling")
        self.matter_id = _require_nonempty_text(matter_id, "matter_id")
        self.excluded_matter_ids = sorted(
            set(str(item) for item in excluded_matter_ids)
        )
        if self.matter_id in self.excluded_matter_ids:
            raise MatterTwinError("primary matter cannot be excluded")
        if state is None:
            self.state: dict[str, Any] = {
                "schema": MATTER_TWIN_SCHEMA,
                "version": VERSION,
                "matter_id": self.matter_id,
                "authority_ceiling": authority_ceiling,
                "case_wall": {
                    "primary_matter_id": self.matter_id,
                    "excluded_matter_ids": self.excluded_matter_ids,
                },
                "sources": {},
                "facts": {},
                "events": [],
                "event_chain_head": None,
                "external_effects": 0,
                "state": "ACTIVE_INTERNAL",
            }
        else:
            self.state = json.loads(json.dumps(state))
            self._verify_identity()
            self.verify_event_chain()

    @classmethod
    def from_path(cls, path: Path) -> "MatterTwin":
        state = read_json(path)
        wall = state.get("case_wall", {})
        return cls(
            matter_id=str(state.get("matter_id", "")),
            excluded_matter_ids=wall.get("excluded_matter_ids", []),
            authority_ceiling=str(state.get("authority_ceiling", "A1")),
            state=state,
        )

    def _verify_identity(self) -> None:
        if self.state.get("schema") != MATTER_TWIN_SCHEMA:
            raise MatterTwinError("unexpected matter-twin schema")
        if self.state.get("matter_id") != self.matter_id:
            raise MatterTwinError("matter identity mismatch")
        if self.state.get("external_effects") != 0:
            raise MatterTwinError("external effects are not permitted")

    def _assert_matter(self, target_matter_id: str | None) -> None:
        target = target_matter_id or self.matter_id
        if target != self.matter_id or target in self.excluded_matter_ids:
            raise MatterTwinError(
                f"case-wall violation: {target!r} cannot be written into "
                f"{self.matter_id!r}"
            )

    def append_event(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        target_matter_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self._assert_matter(target_matter_id)
        event_type = _require_nonempty_text(event_type, "event_type")
        payload_copy = json.loads(json.dumps(payload))
        payload_sha = digest(payload_copy)

        if idempotency_key:
            for existing in self.state["events"]:
                if existing.get("idempotency_key") == idempotency_key:
                    if (
                        existing.get("event_type") == event_type
                        and existing.get("payload_sha256") == payload_sha
                    ):
                        return existing
                    raise MatterTwinError(
                        "idempotency-key collision with different payload"
                    )

        previous = self.state.get("event_chain_head")
        event: dict[str, Any] = {
            "sequence": len(self.state["events"]) + 1,
            "event_type": event_type,
            "matter_id": self.matter_id,
            "observed_at_utc": now_utc(),
            "idempotency_key": idempotency_key,
            "payload": payload_copy,
            "payload_sha256": payload_sha,
            "previous_event_sha256": previous,
        }
        event["event_sha256"] = digest(event)
        self.state["events"].append(event)
        self.state["event_chain_head"] = event["event_sha256"]
        return event

    def register_source(self, source: Mapping[str, Any]) -> dict[str, Any]:
        _validate_source(source)
        source_id = str(source["source_id"])
        normalized = json.loads(json.dumps(source))
        normalized["source_record_sha256"] = digest(normalized)
        existing = self.state["sources"].get(source_id)
        if existing:
            if existing == normalized:
                return existing
            raise MatterTwinError(
                f"source {source_id} cannot be silently replaced"
            )
        self.state["sources"][source_id] = normalized
        self.append_event(
            "SOURCE_REGISTERED",
            normalized,
            idempotency_key=f"source:{source_id}:{normalized['sha256']}",
        )
        return normalized

    def assert_fact(
        self,
        *,
        fact_id: str,
        proposition: str,
        classification: str,
        source_ids: Iterable[str] = (),
        confidence: str = "CONTROLLED",
        proof_limit: str = "",
    ) -> dict[str, Any]:
        fact_id = _require_nonempty_text(fact_id, "fact_id")
        proposition = _require_nonempty_text(proposition, "proposition")
        if classification not in _ALLOWED_FACT_CLASSES:
            raise MatterTwinError(
                f"unsupported fact classification: {classification}"
            )
        normalized_sources = sorted(set(str(item) for item in source_ids))
        if classification == "VERIFIED_FACT":
            if not normalized_sources:
                raise MatterTwinError(
                    "VERIFIED_FACT requires at least one registered source"
                )
            missing = [
                item
                for item in normalized_sources
                if item not in self.state["sources"]
            ]
            if missing:
                raise MatterTwinError(
                    f"VERIFIED_FACT references unknown sources: {missing}"
                )
        fact: dict[str, Any] = {
            "fact_id": fact_id,
            "proposition": proposition,
            "classification": classification,
            "source_ids": normalized_sources,
            "confidence": confidence,
            "proof_limit": proof_limit,
            "matter_id": self.matter_id,
            "superseded_by": None,
        }
        fact["fact_sha256"] = digest(fact)
        existing = self.state["facts"].get(fact_id)
        if existing:
            if existing == fact:
                return existing
            raise MatterTwinError(
                f"fact {fact_id} already exists; use supersede_fact instead of "
                "overwriting"
            )
        self.state["facts"][fact_id] = fact
        self.append_event(
            "FACT_ASSERTED",
            fact,
            idempotency_key=f"fact:{fact_id}:{fact['fact_sha256']}",
        )
        return fact

    def supersede_fact(
        self,
        *,
        old_fact_id: str,
        new_fact_id: str,
        proposition: str,
        classification: str,
        source_ids: Iterable[str],
        confidence: str = "CONTROLLED",
        proof_limit: str = "",
    ) -> dict[str, Any]:
        old = self.state["facts"].get(old_fact_id)
        if not old:
            raise MatterTwinError(
                f"cannot supersede missing fact {old_fact_id}"
            )
        if old.get("superseded_by"):
            raise MatterTwinError(
                f"fact {old_fact_id} is already superseded"
            )
        new_fact = self.assert_fact(
            fact_id=new_fact_id,
            proposition=proposition,
            classification=classification,
            source_ids=source_ids,
            confidence=confidence,
            proof_limit=proof_limit,
        )
        old["superseded_by"] = new_fact_id
        old["supersession_sha256"] = digest(
            {
                "old_fact_id": old_fact_id,
                "new_fact_id": new_fact_id,
                "old_fact_sha256": old["fact_sha256"],
                "new_fact_sha256": new_fact["fact_sha256"],
            }
        )
        self.append_event(
            "FACT_SUPERSEDED",
            {
                "old_fact_id": old_fact_id,
                "new_fact_id": new_fact_id,
                "supersession_sha256": old["supersession_sha256"],
            },
            idempotency_key=f"supersede:{old_fact_id}:{new_fact_id}",
        )
        return new_fact

    def verify_event_chain(self) -> None:
        previous: str | None = None
        for expected_sequence, event in enumerate(
            self.state.get("events", []), start=1
        ):
            if event.get("sequence") != expected_sequence:
                raise MatterTwinError("event sequence is not contiguous")
            if event.get("matter_id") != self.matter_id:
                raise MatterTwinError("cross-matter event detected")
            if event.get("previous_event_sha256") != previous:
                raise MatterTwinError("event chain predecessor mismatch")
            if digest(event.get("payload")) != event.get("payload_sha256"):
                raise MatterTwinError("event payload hash mismatch")
            candidate = dict(event)
            supplied = candidate.pop("event_sha256", None)
            if digest(candidate) != supplied:
                raise MatterTwinError("event hash mismatch")
            previous = supplied
        if self.state.get("event_chain_head") != previous:
            raise MatterTwinError("event-chain head mismatch")

    def write(self, path: Path) -> None:
        self.verify_event_chain()
        self.state["state_sha256"] = digest(
            {
                key: value
                for key, value in self.state.items()
                if key != "state_sha256"
            }
        )
        atomic_write_json(path, self.state)


class ValueLedger:
    """Append-only longitudinal value ledger with deterministic readback."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def append(self, cycle: Mapping[str, Any]) -> dict[str, Any]:
        records = self.records()
        cycle_copy = json.loads(json.dumps(cycle))
        cycle_key = _require_nonempty_text(
            cycle_copy.get("cycle_key"), "cycle_key"
        )
        for existing in records:
            if existing.get("cycle_key") == cycle_key:
                candidate = dict(existing)
                supplied = candidate.pop("cycle_sha256", None)
                if digest(candidate) != supplied:
                    raise MatterTwinError(
                        "existing ledger cycle failed integrity check"
                    )

                def stable(value: Mapping[str, Any]) -> dict[str, Any]:
                    return {
                        key: item
                        for key, item in value.items()
                        if key
                        not in {
                            "cycle_sha256",
                            "sequence",
                            "previous_cycle_sha256",
                            "observed_at_utc",
                            "execution_seconds",
                        }
                    }

                if digest(stable(existing)) != digest(stable(cycle_copy)):
                    raise MatterTwinError(
                        "cycle-key collision with different value record"
                    )
                return existing
        cycle_copy["sequence"] = len(records) + 1
        cycle_copy["previous_cycle_sha256"] = (
            records[-1]["cycle_sha256"] if records else None
        )
        cycle_copy.setdefault("observed_at_utc", now_utc())
        cycle_copy["cycle_sha256"] = digest(cycle_copy)
        existing_text = (
            self.path.read_text(encoding="utf-8")
            if self.path.exists()
            else ""
        )
        atomic_write_text(
            self.path,
            existing_text + json.dumps(cycle_copy, sort_keys=True) + "\n",
        )
        self.verify()
        return cycle_copy

    def verify(self) -> None:
        previous: str | None = None
        for expected_sequence, record in enumerate(self.records(), start=1):
            if record.get("sequence") != expected_sequence:
                raise MatterTwinError("value-ledger sequence mismatch")
            if record.get("previous_cycle_sha256") != previous:
                raise MatterTwinError("value-ledger predecessor mismatch")
            candidate = dict(record)
            supplied = candidate.pop("cycle_sha256", None)
            if digest(candidate) != supplied:
                raise MatterTwinError("value-ledger hash mismatch")
            previous = supplied


def _cycle_key() -> str:
    return "-".join(
        [
            os.getenv("GITHUB_RUN_ID", "local"),
            os.getenv("GITHUB_RUN_ATTEMPT", "1"),
            os.getenv("EVIDENCEOPS_CYCLE_SUFFIX", "default"),
        ]
    )


def _load_or_create_twin(
    manifest: Mapping[str, Any], twin_path: Path
) -> MatterTwin:
    if twin_path.exists():
        twin = MatterTwin.from_path(twin_path)
        if twin.matter_id != manifest["matter_id"]:
            raise MatterTwinError(
                "persisted twin belongs to a different matter"
            )
        return twin
    return MatterTwin(
        matter_id=str(manifest["matter_id"]),
        excluded_matter_ids=manifest["case_wall"]["excluded_matter_ids"],
        authority_ceiling=manifest["authority"]["ceiling"],
    )


def run_bounded_cycle(
    manifest_path: Path, state_dir: Path
) -> dict[str, Any]:
    """Execute and independently verify one v8.1 bounded ProofLoop cycle."""

    started = time.perf_counter()
    manifest = read_json(manifest_path)
    contract = compile_proof_contract(manifest)
    verify_proof_contract(contract)

    state_dir.mkdir(parents=True, exist_ok=True)
    contract_path = state_dir / "proof_contract_receipt.json"
    twin_path = state_dir / "matter_twin.json"
    ledger_path = state_dir / "value_ledger.jsonl"
    latest_cycle_path = state_dir / "latest_cycle.json"
    dashboard_path = state_dir / "dashboard.json"
    release_receipt_path = state_dir / "release_receipt.json"

    atomic_write_json(contract_path, contract)
    twin = _load_or_create_twin(manifest, twin_path)
    for source in manifest["sources"]:
        twin.register_source(source)

    source_by_role = {
        source["role"]: source["source_id"] for source in manifest["sources"]
    }
    facts = manifest["seed_facts"]
    for fact in facts:
        twin.assert_fact(
            fact_id=fact["fact_id"],
            proposition=fact["proposition"],
            classification=fact["classification"],
            source_ids=[
                source_by_role[role]
                for role in fact.get("source_roles", [])
            ],
            confidence=fact.get("confidence", "CONTROLLED"),
            proof_limit=fact.get("proof_limit", ""),
        )

    controls_prevented: list[str] = []
    try:
        twin.append_event(
            "CROSS_MATTER_INJECTION",
            {"attempt": "write related-matter content"},
            target_matter_id=manifest["case_wall"]["excluded_matter_ids"][0],
        )
    except MatterTwinError:
        controls_prevented.append("CROSS_MATTER_WRITE_BLOCKED")

    gateway = AuthorityGateway(manifest["authority"]["ceiling"])
    authority_decisions = [
        gateway.evaluate(action).as_dict()
        for action in ("send", "file", "serve", "publish", "settle")
    ]
    controls_prevented.extend(
        f"{decision['action'].upper()}_BLOCKED"
        for decision in authority_decisions
        if not decision["allowed"]
    )

    twin.append_event(
        "CONTROL_CYCLE_COMPLETED",
        {
            "proof_contract_sha256": contract["contract_sha256"],
            "controls_prevented": sorted(controls_prevented),
            "external_effects": 0,
        },
        idempotency_key=f"control-cycle:{_cycle_key()}",
    )
    twin.write(twin_path)

    elapsed = round(time.perf_counter() - started, 6)
    ledger = ValueLedger(ledger_path)
    value_cycle: dict[str, Any] = {
        "schema": VALUE_CYCLE_SCHEMA,
        "version": VERSION,
        "cycle_key": _cycle_key(),
        "mission_id": manifest["mission_id"],
        "matter_id": manifest["matter_id"],
        "provider_event": {
            "repository": os.getenv("GITHUB_REPOSITORY", "local"),
            "workflow": os.getenv("GITHUB_WORKFLOW", "local"),
            "event_name": os.getenv("GITHUB_EVENT_NAME", "local"),
            "run_id": os.getenv("GITHUB_RUN_ID", "local"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "1"),
            "sha": os.getenv("GITHUB_SHA", "local"),
            "ref": os.getenv("GITHUB_REF", "local"),
        },
        "source_freshness": {
            "state": manifest["source_freshness"]["state"],
            "as_of_utc": manifest["source_freshness"]["as_of_utc"],
            "source_count": len(manifest["sources"]),
        },
        "control_defects_prevented": sorted(controls_prevented),
        "control_defects_prevented_count": len(controls_prevented),
        "execution_seconds": elapsed,
        "owner_attention": {
            "required": False,
            "interventions": 0,
            "minutes": 0,
        },
        "outcome_quality": {
            "state": "INTERNAL_CONTROL_OUTPUT_VERIFIED",
            "unsupported_material_claims": 0,
            "cross_matter_contamination": 0,
            "external_effects": 0,
            "real_legal_outcome": "UNPROVEN",
        },
        "authority_ceiling": manifest["authority"]["ceiling"],
        "external_effects": 0,
        "state": "PROOFLOOP_CYCLE_VERIFIED_INTERNAL",
        "truth_boundary": (
            "This cycle proves internal source, fact, case-wall, authority and "
            "value-ledger controls. It does not prove a legal outcome or "
            "authorise any consequential action."
        ),
    }
    ledger_record = ledger.append(value_cycle)
    atomic_write_json(latest_cycle_path, ledger_record)

    twin_reloaded = MatterTwin.from_path(twin_path)
    ledger.verify()
    verify_proof_contract(read_json(contract_path))

    dashboard: dict[str, Any] = {
        "schema": "EVIDENCEOPS_V81_PROOFLOOP_DASHBOARD_V1",
        "version": VERSION,
        "matter_id": manifest["matter_id"],
        "mission_id": manifest["mission_id"],
        "engineering_state": "COMPLETE_VERIFIED",
        "living_matter_twin": {
            "sources": len(twin_reloaded.state["sources"]),
            "facts": len(twin_reloaded.state["facts"]),
            "events": len(twin_reloaded.state["events"]),
            "event_chain_head": twin_reloaded.state["event_chain_head"],
            "case_wall_state": "ENFORCED",
        },
        "proof_contract": {
            "state": contract["state"],
            "sha256": contract["contract_sha256"],
        },
        "longitudinal_assurance": {
            "state": "ACTIVE_EVIDENCE_ACCUMULATING",
            "cycles": len(ledger.records()),
            "latest_cycle_sha256": ledger_record["cycle_sha256"],
            "value_gate": "NOT_YET_MATURE",
        },
        "authority": {
            "ceiling": manifest["authority"]["ceiling"],
            "consequential_authority": "HELD",
            "external_effects": 0,
        },
        "release_gate": manifest["release_gate"],
        "controls_prevented": sorted(controls_prevented),
        "truth_boundary": (
            "Engineering completion and recurring internal assurance are "
            "verified. Elapsed longitudinal value and consequential legal "
            "authority remain separate future gates."
        ),
    }
    dashboard["dashboard_sha256"] = digest(dashboard)
    atomic_write_json(dashboard_path, dashboard)

    release_receipt: dict[str, Any] = {
        "schema": RELEASE_RECEIPT_SCHEMA,
        "version": VERSION,
        "mission_id": manifest["mission_id"],
        "matter_id": manifest["matter_id"],
        "observed_at_utc": now_utc(),
        "proof_contract_sha256": contract["contract_sha256"],
        "matter_twin_state_sha256": twin_reloaded.state["state_sha256"],
        "matter_twin_event_chain_head": twin_reloaded.state[
            "event_chain_head"
        ],
        "value_cycle_sha256": ledger_record["cycle_sha256"],
        "dashboard_sha256": dashboard["dashboard_sha256"],
        "checks": {
            "proof_contract_readback": True,
            "source_hash_format_enforced": True,
            "verified_fact_source_binding": True,
            "case_wall_enforced": (
                "CROSS_MATTER_WRITE_BLOCKED" in controls_prevented
            ),
            "silent_fact_overwrite_prohibited": True,
            "consequential_actions_denied": all(
                not item["allowed"] for item in authority_decisions
            ),
            "matter_twin_event_chain_verified": True,
            "longitudinal_ledger_chain_verified": True,
            "external_effects_zero": True,
        },
        "engineering_state": (
            "EVIDENCEOPS_V81_ENGINEERING_COMPLETE_VERIFIED"
        ),
        "longitudinal_state": "ACTIVE_EVIDENCE_ACCUMULATING",
        "value_gate": "NOT_YET_MATURE",
        "consequential_authority": "HELD",
        "external_effects": 0,
        "truth_boundary": (
            "This receipt proves the v8.1 internal engineering cycle and its "
            "readbacks. It does not claim elapsed longitudinal value, filing, "
            "service, sending, publication, settlement, legal outcome or "
            "public-provider production authority."
        ),
    }
    release_receipt["receipt_sha256"] = digest(release_receipt)
    atomic_write_json(release_receipt_path, release_receipt)
    verify_release_state(state_dir)
    return release_receipt


def verify_release_state(state_dir: Path) -> dict[str, Any]:
    contract = read_json(state_dir / "proof_contract_receipt.json")
    verify_proof_contract(contract)
    MatterTwin.from_path(state_dir / "matter_twin.json")
    ledger = ValueLedger(state_dir / "value_ledger.jsonl")
    ledger.verify()
    latest = read_json(state_dir / "latest_cycle.json")
    if not ledger.records() or ledger.records()[-1] != latest:
        raise MatterTwinError("latest-cycle semantic readback mismatch")
    dashboard = read_json(state_dir / "dashboard.json")
    supplied_dashboard = dashboard.pop("dashboard_sha256", None)
    if digest(dashboard) != supplied_dashboard:
        raise MatterTwinError("dashboard hash mismatch")
    dashboard["dashboard_sha256"] = supplied_dashboard
    receipt = read_json(state_dir / "release_receipt.json")
    supplied_receipt = receipt.pop("receipt_sha256", None)
    if digest(receipt) != supplied_receipt:
        raise MatterTwinError("release receipt hash mismatch")
    receipt["receipt_sha256"] = supplied_receipt
    checks = receipt.get("checks", {})
    if not checks or not all(checks.values()):
        raise MatterTwinError("release receipt contains failed checks")
    if receipt.get("external_effects") != 0:
        raise MatterTwinError("release receipt reports an external effect")
    return receipt
