"""Private-data-safe central fault-book manager for RealityGuard."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .capability import canonical_json
from .schema import InputError


REGISTRY_SCHEMA = "realityguard.faultbook-registry.v1"
IMPORT_SCHEMA = "realityguard.faultbook-import.v1"
RECEIPT_SCHEMA = "realityguard.faultbook-receipt.v1"
PUBLIC_MANIFEST_SCHEMA = "realityguard.faultbook-public-manifest.v1"
CONSUMER_STATES = {"VERIFIED_SOURCE", "VERIFIED_INVOCATION", "VERIFIED_HOST_BOUND", "ADAPTER_REQUIRED", "BLOCKED", "UNKNOWN"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def event_hash(event: dict[str, Any]) -> str:
    previous = event.get("prev_hash")
    if not isinstance(previous, str) or not previous:
        raise InputError("fault-book event prev_hash is required")
    payload = {key: value for key, value in event.items() if key not in {"prev_hash", "event_hash"}}
    return hashlib.sha256(previous.encode() + b"\n" + canonical_json(payload).encode()).hexdigest()


def verify_event_stream(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise InputError(f"cannot read fault-book ledger: {exc}") from exc
    events: list[dict[str, Any]] = []
    previous = "GENESIS"
    event_ids: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InputError(f"invalid JSONL event at line {line_number}: {exc}") from exc
        if not isinstance(event, dict):
            raise InputError(f"fault-book event at line {line_number} must be an object")
        for field in ("event_id", "event_type", "prev_hash", "event_hash", "content"):
            if not isinstance(event.get(field), str) or not event[field]:
                raise InputError(f"fault-book event at line {line_number} requires {field}")
        if event["event_id"] in event_ids:
            raise InputError(f"duplicate fault-book event_id: {event['event_id']}")
        if event["prev_hash"] != previous:
            raise InputError(f"fault-book chain parent mismatch at {event['event_id']}")
        if event["event_hash"] != event_hash(event):
            raise InputError(f"fault-book event hash mismatch at {event['event_id']}")
        event_ids.add(event["event_id"])
        previous = event["event_hash"]
        events.append(event)
    if not events:
        raise InputError("fault-book ledger must contain at least one event")
    return {"events": events, "event_count": len(events), "head_hash": previous, "sha256": sha256_file(path)}


def fault_fingerprint(fault: dict[str, Any]) -> str:
    identity = {key: fault.get(key) for key in ("fault_id", "title", "classification", "root_mechanism")}
    return hashlib.sha256(canonical_json(identity).encode()).hexdigest()


def _validate_consumer(consumer: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(consumer, dict) or not isinstance(consumer.get("consumer_id"), str) or not consumer["consumer_id"]:
        raise InputError("each consumer requires consumer_id")
    state = consumer.get("state")
    if state not in CONSUMER_STATES:
        raise InputError(f"invalid consumer state for {consumer['consumer_id']}: {state}")
    proof_refs = consumer.get("proof_refs", [])
    if not isinstance(proof_refs, list) or not all(isinstance(item, str) and item for item in proof_refs):
        raise InputError(f"consumer {consumer['consumer_id']} proof_refs must be non-empty strings")
    if state.startswith("VERIFIED_") and not proof_refs:
        raise InputError(f"consumer {consumer['consumer_id']} requires proof_refs for {state}")
    if state == "VERIFIED_HOST_BOUND" and (consumer.get("current_invocation") is not True or consumer.get("semantic_readback") is not True):
        raise InputError("VERIFIED_HOST_BOUND requires current_invocation and semantic_readback")
    return {"consumer_id": consumer["consumer_id"], "surface": str(consumer.get("surface", "unspecified")), "state": state,
            "proof_refs": sorted(set(proof_refs)), "current_invocation": bool(consumer.get("current_invocation", False)),
            "semantic_readback": bool(consumer.get("semantic_readback", False)), "notes": str(consumer.get("notes", ""))}


class FaultbookManager:
    """Own an atomic, collision-safe registry of verified fault books."""

    schema_version = REGISTRY_SCHEMA
    manager_id = "RealityGuard"

    def __init__(self, path: Path):
        self.path = Path(path)

    @classmethod
    def empty(cls) -> dict[str, Any]:
        return {"schema_version": cls.schema_version, "manager_id": cls.manager_id,
                "manager_role": "CENTRAL_FAULTBOOK_MANAGER", "system_status": "SYSTEMIC_OPEN",
                "faultbooks": {}, "consumers": {}}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.empty()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputError(f"fault-book registry is unreadable: {exc}") from exc
        if value.get("schema_version") != self.schema_version:
            raise InputError("fault-book registry schema is invalid")
        if value.get("manager_id") != self.manager_id or value.get("manager_role") != "CENTRAL_FAULTBOOK_MANAGER":
            raise InputError("fault-book registry manager binding is invalid")
        if not isinstance(value.get("faultbooks"), dict) or not isinstance(value.get("consumers"), dict):
            raise InputError("fault-book registry collections are invalid")
        return value

    def _atomic_write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".realityguard-faultbooks-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def import_faultbook(self, ledger_path: Path, metadata: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        if not isinstance(metadata, dict) or metadata.get("schema_version") != IMPORT_SCHEMA:
            raise InputError(f"metadata must bind {IMPORT_SCHEMA}")
        for field in ("faultbook_id", "title", "status"):
            if not isinstance(metadata.get(field), str) or not metadata[field]:
                raise InputError(f"metadata.{field} is required")
        stream = verify_event_stream(ledger_path)
        if metadata.get("expected_ledger_sha256") and metadata["expected_ledger_sha256"] != stream["sha256"]:
            raise InputError("fault-book ledger file digest mismatch")
        faults = metadata.get("faults", [])
        if not isinstance(faults, list) or not faults:
            raise InputError("metadata.faults must be a non-empty array")
        normalized_faults, fault_ids = [], set()
        for fault in faults:
            if not isinstance(fault, dict):
                raise InputError("each fault must be an object")
            for field in ("fault_id", "title", "classification", "status", "root_mechanism"):
                if not isinstance(fault.get(field), str) or not fault[field]:
                    raise InputError(f"fault requires {field}")
            if fault["fault_id"] in fault_ids:
                raise InputError(f"duplicate fault_id: {fault['fault_id']}")
            fault_ids.add(fault["fault_id"])
            row = dict(fault)
            row["fingerprint"] = fault_fingerprint(fault)
            normalized_faults.append(row)
        artifacts = []
        for item in metadata.get("artifacts", []):
            if not isinstance(item, dict) or not item.get("kind") or not item.get("sha256"):
                raise InputError("each artifact requires kind and sha256")
            stored_sha, local_path = str(item["sha256"]), item.get("local_path")
            if local_path and sha256_file(Path(local_path)) != stored_sha:
                raise InputError(f"artifact digest mismatch: {item['kind']}")
            artifacts.append({"kind": str(item["kind"]), "sha256": stored_sha, "storage_ref": str(item.get("storage_ref", "")),
                              "file_name": str(item.get("file_name", Path(local_path).name if local_path else ""))})
        consumers = [_validate_consumer(item) for item in metadata.get("consumers", [])]
        if len({item["consumer_id"] for item in consumers}) != len(consumers):
            raise InputError("duplicate consumer_id in import metadata")
        open_tests = sorted(set(map(str, metadata.get("open_regression_tests", []))))
        if metadata["status"] == "CLOSED" and open_tests:
            raise InputError("a fault book with open regression tests cannot be CLOSED")
        identity = {"faultbook_id": metadata["faultbook_id"], "ledger_sha256": stream["sha256"], "ledger_head": stream["head_hash"],
                    "artifact_sha256": sorted(item["sha256"] for item in artifacts),
                    "fault_fingerprints": sorted(item["fingerprint"] for item in normalized_faults)}
        import_id = hashlib.sha256(canonical_json(identity).encode()).hexdigest()
        value = self._read()
        prior = value["faultbooks"].get(metadata["faultbook_id"])
        if prior and prior.get("import_id") == import_id:
            metadata_changed = prior.get("artifacts") != artifacts
            if metadata_changed:
                prior["artifacts"] = artifacts
            for consumer in consumers:
                if value["consumers"].get(consumer["consumer_id"]) != consumer:
                    value["consumers"][consumer["consumer_id"]] = consumer
                    metadata_changed = True
            value["system_status"] = self._system_status(value)
            if metadata_changed and not dry_run:
                self._atomic_write(value)
            return self._receipt(value, prior, duplicate_suppressed=True, registry_written=metadata_changed and not dry_run)
        revisions = list(prior.get("revisions", [])) if prior else []
        if prior:
            revisions.append({"import_id": prior["import_id"], "ledger_sha256": prior["ledger"]["sha256"],
                              "ledger_head": prior["ledger"]["head_hash"], "event_count": prior["ledger"]["event_count"]})
        record = {"faultbook_id": metadata["faultbook_id"], "title": metadata["title"], "status": metadata["status"],
                  "import_id": import_id, "imported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                  "ledger": {"sha256": stream["sha256"], "head_hash": stream["head_hash"], "event_count": stream["event_count"], "events": stream["events"]},
                  "artifacts": artifacts, "faults": normalized_faults, "open_regression_tests": open_tests, "revisions": revisions}
        value["faultbooks"][metadata["faultbook_id"]] = record
        for consumer in consumers:
            value["consumers"][consumer["consumer_id"]] = consumer
        value["system_status"] = self._system_status(value)
        if not dry_run:
            self._atomic_write(value)
        return self._receipt(value, record, duplicate_suppressed=False, registry_written=not dry_run)

    @staticmethod
    def _system_status(value: dict[str, Any]) -> str:
        if not value["faultbooks"]:
            return "SYSTEMIC_OPEN"
        if any(record.get("status") != "CLOSED" or record.get("open_regression_tests") for record in value["faultbooks"].values()):
            return "SYSTEMIC_OPEN"
        if any(item.get("state") != "VERIFIED_HOST_BOUND" for item in value["consumers"].values()):
            return "INTEGRATION_OPEN"
        return "PROVEN_CLOSED"

    def _receipt(self, value: dict[str, Any], record: dict[str, Any], *, duplicate_suppressed: bool, registry_written: bool) -> dict[str, Any]:
        consumers = value["consumers"]
        return {"schema_version": RECEIPT_SCHEMA, "manager_id": self.manager_id, "manager_role": "CENTRAL_FAULTBOOK_MANAGER",
                "faultbook_id": record["faultbook_id"], "import_id": record["import_id"], "ledger_sha256": record["ledger"]["sha256"],
                "ledger_head": record["ledger"]["head_hash"], "event_count": record["ledger"]["event_count"],
                "fault_count": len(record["faults"]), "duplicate_suppressed": duplicate_suppressed,
                "registry_written": registry_written, "system_status": value["system_status"],
                "all_consumers_host_bound": bool(consumers) and all(item["state"] == "VERIFIED_HOST_BOUND" for item in consumers.values()),
                "consumer_states": {key: item["state"] for key, item in sorted(consumers.items())}}

    def verify(self) -> dict[str, Any]:
        value, failures = self._read(), []
        for faultbook_id, record in value["faultbooks"].items():
            previous = "GENESIS"
            for event in record.get("ledger", {}).get("events", []):
                if event.get("prev_hash") != previous or event.get("event_hash") != event_hash(event):
                    failures.append(f"{faultbook_id}:invalid-event:{event.get('event_id', 'unknown')}")
                    break
                previous = event["event_hash"]
            if previous != record.get("ledger", {}).get("head_hash"):
                failures.append(f"{faultbook_id}:head-mismatch")
            for fault in record.get("faults", []):
                if fault.get("fingerprint") != fault_fingerprint(fault):
                    failures.append(f"{faultbook_id}:fault-fingerprint:{fault.get('fault_id', 'unknown')}")
        computed_status = self._system_status(value)
        if value.get("system_status") != computed_status:
            failures.append("system-status-mismatch")
        return {"schema_version": "realityguard.faultbook-verification.v1", "valid": not failures, "failures": failures,
                "faultbook_count": len(value["faultbooks"]), "consumer_count": len(value["consumers"]), "system_status": computed_status}

    def public_manifest(self) -> dict[str, Any]:
        value = self._read()
        return {"schema_version": PUBLIC_MANIFEST_SCHEMA, "manager_id": self.manager_id, "manager_role": "CENTRAL_FAULTBOOK_MANAGER",
                "system_status": value["system_status"],
                "privacy": {"raw_events_included": False, "artifact_paths_included": False, "storage_refs_included": False,
                            "consumer_proof_refs_included": False},
                "faultbooks": [{"faultbook_id": item["faultbook_id"], "title": item["title"], "status": item["status"], "import_id": item["import_id"],
                                "ledger": {key: item["ledger"][key] for key in ("sha256", "head_hash", "event_count")},
                                "artifact_digests": sorted(artifact["sha256"] for artifact in item["artifacts"]),
                                "faults": [{key: fault[key] for key in ("fault_id", "title", "classification", "status", "fingerprint")} for fault in item["faults"]],
                                "open_regression_tests": item["open_regression_tests"]} for item in value["faultbooks"].values()],
                "consumers": [{"consumer_id": item["consumer_id"], "surface": item["surface"], "state": item["state"],
                               "proof_available": bool(item["proof_refs"]), "proof_count": len(item["proof_refs"])}
                              for item in value["consumers"].values()],
                "universal_sync_claim_allowed": bool(value["consumers"]) and all(item["state"] == "VERIFIED_HOST_BOUND" for item in value["consumers"].values())}
