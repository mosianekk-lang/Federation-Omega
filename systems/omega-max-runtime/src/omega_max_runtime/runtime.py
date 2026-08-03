import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .models import MutationContract

SAFE_PREFIX = Path("runtime/omega-max/state")


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def safe_target(repo_root, target):
    relative = Path(target)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".json":
        raise ValueError("unsafe target")
    try:
        relative.relative_to(SAFE_PREFIX)
    except ValueError as exc:
        raise ValueError(f"target must be under {SAFE_PREFIX}") from exc
    resolved = (repo_root / relative).resolve()
    if repo_root.resolve() not in resolved.parents:
        raise ValueError("target escapes repository")
    return resolved


class ProofWriter:
    def __init__(self, root):
        self.root = Path(root)
        self.directory = self.root / "runtime/omega-max/proofs"
        self.head = self.directory / "proof_chain_head.json"

    def write(self, event):
        previous = read_json(self.head, {"head_hash": "GENESIS"})
        record = {**event, "recorded_at": utcnow(), "previous_hash": previous["head_hash"]}
        record["record_hash"] = sha(record)
        write_json(self.directory / f'{event["proof_id"]}.json', record)
        write_json(self.head, {"head_hash": record["record_hash"], "proof_id": event["proof_id"]})
        return record


class DigitalTwin:
    def __init__(self, root):
        self.root = Path(root)

    def read(self, desired_path, actual_path):
        desired = read_json(safe_target(self.root, desired_path))
        actual = read_json(safe_target(self.root, actual_path))
        return {
            "desired_path": desired_path,
            "actual_path": actual_path,
            "desired": desired,
            "actual": actual,
            "desired_hash": sha(desired),
            "actual_hash": sha(actual),
            "drift": desired != actual,
        }


class DriftSentinel:
    def __init__(self, root):
        self.root = Path(root)

    def inspect(self, desired_path, actual_path):
        report = DigitalTwin(self.root).read(desired_path, actual_path)
        report.update({
            "checked_at": utcnow(),
            "classification": "DRIFT_DETECTED" if report["drift"] else "IN_SYNC",
        })
        write_json(self.root / "runtime/omega-max/drift/latest.json", report)
        return report


class QueueConsumer:
    def __init__(self, repo_root):
        self.root = Path(repo_root).resolve()
        self.queue = self.root / "runtime/omega-max/queue"
        self.results = self.root / "runtime/omega-max/results"
        self.snapshots = self.root / "runtime/omega-max/snapshots"
        self.proof = ProofWriter(self.root)

    def fingerprint(self, contract):
        return sha(contract.to_dict())

    def process_contract(self, contract):
        target = safe_target(self.root, contract.target)
        fingerprint = self.fingerprint(contract)
        result_path = self.results / f"{contract.contract_id}.json"
        existing = read_json(result_path)
        if existing and existing.get("contract_fingerprint") == fingerprint and existing.get("status") == "VERIFIED":
            return {**existing, "effect": "EXACTLY_ONCE_SKIP"}

        before = read_json(target)
        if before != contract.expected_before:
            result = {
                "contract_id": contract.contract_id,
                "status": "FAILED_PRECONDITION",
                "expected_before": contract.expected_before,
                "observed_before": before,
                "contract_fingerprint": fingerprint,
                "processed_at": utcnow(),
            }
            write_json(result_path, result)
            self.proof.write({
                "proof_id": f"PRF-{contract.contract_id}-PRECONDITION",
                "contract_id": contract.contract_id,
                "status": result["status"],
                "before_hash": sha(before),
            })
            return result

        snapshot = {
            "contract_id": contract.contract_id,
            "target": contract.target,
            "before": before,
            "before_hash": sha(before),
            "created_at": utcnow(),
        }
        snapshot_path = self.snapshots / f"{contract.contract_id}.json"
        write_json(snapshot_path, snapshot)

        write_json(target, contract.desired)
        applied = read_json(target) == contract.desired

        # Real rollback drill: restore the snapshot, verify it, then reapply and verify.
        write_json(target, before)
        rollback_ok = read_json(target) == before
        write_json(target, contract.desired)
        final = read_json(target)
        final_ok = final == contract.desired

        status = "VERIFIED" if applied and rollback_ok and final_ok else "FAILED_VERIFICATION"
        result = {
            "contract_id": contract.contract_id,
            "status": status,
            "effect": "APPLIED",
            "target": contract.target,
            "contract_fingerprint": fingerprint,
            "before_hash": sha(before),
            "after_hash": sha(final),
            "semantic_readback": final_ok,
            "rollback_test": rollback_ok,
            "snapshot": str(snapshot_path.relative_to(self.root)),
            "processed_at": utcnow(),
        }
        proof = self.proof.write({
            "proof_id": f"PRF-{contract.contract_id}",
            "contract_id": contract.contract_id,
            "status": status,
            "target": contract.target,
            "before_hash": result["before_hash"],
            "after_hash": result["after_hash"],
            "semantic_readback": final_ok,
            "rollback_test": rollback_ok,
            "contract_fingerprint": fingerprint,
        })
        result["proof_hash"] = proof["record_hash"]
        write_json(result_path, result)
        return result

    def process_queue(self):
        self.queue.mkdir(parents=True, exist_ok=True)
        outcomes = []
        for path in sorted(self.queue.glob("*.json")):
            try:
                outcomes.append(self.process_contract(MutationContract.from_dict(read_json(path))))
            except Exception as exc:
                failure = {
                    "queue_file": str(path.relative_to(self.root)),
                    "status": "QUARANTINED",
                    "error": f"{type(exc).__name__}: {exc}",
                    "processed_at": utcnow(),
                }
                write_json(self.results / f"QUARANTINE-{path.stem}.json", failure)
                outcomes.append(failure)

        def good(outcome):
            return outcome.get("status") == "VERIFIED" or outcome.get("effect") == "EXACTLY_ONCE_SKIP"

        heartbeat = {
            "heartbeat_id": "HB-OMEGA-MAX-GITHUB-RUNTIME",
            "recorded_at": utcnow(),
            "queue_files": len(list(self.queue.glob("*.json"))),
            "verified": sum(item.get("status") == "VERIFIED" for item in outcomes),
            "skipped": sum(item.get("effect") == "EXACTLY_ONCE_SKIP" for item in outcomes),
            "failed": sum(not good(item) for item in outcomes),
            "runtime_state": "OPERATIONAL" if all(good(item) for item in outcomes) else "DEGRADED",
        }
        write_json(self.root / "runtime/omega-max/heartbeat/latest.json", heartbeat)
        return {"results": outcomes, "heartbeat": heartbeat}
