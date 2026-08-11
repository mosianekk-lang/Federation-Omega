from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from commercial_assurance import digest, utc_now


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify_payload_hash(payload: dict[str, Any], hash_field: str) -> bool:
    expected = payload.get(hash_field)
    body = {key: value for key, value in payload.items() if key != hash_field}
    return bool(expected) and digest(body) == expected


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_ledger(path: Path) -> dict[str, Any]:
    rows = _read_jsonl(path)
    previous = "GENESIS"
    for index, row in enumerate(rows):
        body = {key: value for key, value in row.items() if key != "entry_sha256"}
        if row.get("previous_sha256") != previous or digest(body) != row.get("entry_sha256"):
            return {"pass": False, "failed_index": index, "entries": len(rows)}
        previous = row["entry_sha256"]
    return {"pass": True, "entries": len(rows), "head_sha256": previous}


class CommercialReceiptIntegrityReconciler:
    """Make the C15 succession receipt self-consistent and reversibly verifiable.

    The original C10-C15 proof produced its succession package before recording the
    succession export in durable state. The final maturity snapshot therefore had
    C15 ready while the embedded package snapshot still had C15 false. This
    reconciler repairs the canonical artifact transactionally, preserves the
    original files for rollback, updates the hash-linked ledger and proves exact
    readback without changing any external commercial or provider maturity gate.
    """

    def __init__(self, artifact_root: str | Path) -> None:
        self.root = Path(artifact_root)
        self.receipt_path = self.root / "commercial-c10-c15-receipt.json"
        self.maturity_path = self.root / "commercial-maturity.json"
        self.state_path = self.root / "reference-state" / "commercial_assurance_state.json"
        self.ledger_path = self.root / "reference-state" / "commercial_assurance_ledger.jsonl"
        self.integrity_path = self.root / "canonical-receipt-integrity.json"
        self.backup_root = self.root / "receipt-integrity-backup"
        self.backup_manifest_path = self.backup_root / "manifest.json"
        self.rollback_receipt_path = self.root / "canonical-receipt-rollback.json"

    def _required_paths(self, package_path: Path) -> dict[str, Path]:
        return {
            "commercial-c10-c15-receipt.json": self.receipt_path,
            "commercial-maturity.json": self.maturity_path,
            "commercial_assurance_state.json": self.state_path,
            "commercial_assurance_ledger.jsonl": self.ledger_path,
            package_path.name: package_path,
        }

    def _capture_backup(self, package_path: Path) -> dict[str, Any]:
        if self.backup_manifest_path.exists():
            manifest = _read_json(self.backup_manifest_path)
            if manifest.get("status") == "ROLLBACK_SNAPSHOT_CAPTURED":
                return manifest
        self.backup_root.mkdir(parents=True, exist_ok=True)
        files: dict[str, dict[str, Any]] = {}
        for name, source in self._required_paths(package_path).items():
            if not source.is_file():
                raise FileNotFoundError(source)
            destination = self.backup_root / name
            shutil.copyfile(source, destination)
            files[name] = {
                "source": str(source.relative_to(self.root)),
                "backup": str(destination.relative_to(self.root)),
                "sha256": _sha256_bytes(source.read_bytes()),
            }
        manifest = {
            "status": "ROLLBACK_SNAPSHOT_CAPTURED",
            "captured_at": utc_now(),
            "files": files,
        }
        manifest["manifest_sha256"] = digest(manifest)
        _atomic_json(self.backup_manifest_path, manifest)
        return manifest

    def _append_integrity_ledger(self, package_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = _read_jsonl(self.ledger_path)
        previous = rows[-1]["entry_sha256"] if rows else "GENESIS"
        body = {
            "stage": "C15",
            "action": "succession.integrity.reconcile",
            "object_id": package_id,
            "payload_sha256": digest(payload),
            "previous_sha256": previous,
            "recorded_at": utc_now(),
        }
        row = {**body, "entry_sha256": digest(body)}
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return row

    def reconcile(self) -> dict[str, Any]:
        receipt = _read_json(self.receipt_path)
        maturity = _read_json(self.maturity_path)
        package_id = receipt["stages"]["C15"]["proof"]["package_id"]
        package_path = self.root / "reference-state" / "receipts" / f"succession-{package_id}.json"
        package = _read_json(package_path)
        state = _read_json(self.state_path)

        if not _verify_payload_hash(package, "package_sha256"):
            raise ValueError("pre-reconciliation succession package hash is invalid")
        if not maturity["technical_gates"].get("C15_succession_ready"):
            raise ValueError("final maturity does not prove C15 succession readiness")
        if not maturity.get("technical_reference_ready"):
            raise ValueError("final technical maturity is not ready")

        existing = package.get("receipt_integrity", {})
        if existing.get("status") == "CANONICAL_RECEIPT_SELF_CONSISTENT":
            return self.verify()

        backup = self._capture_backup(package_path)
        prior_package_sha = package["package_sha256"]
        package.pop("package_sha256", None)
        package["maturity"] = maturity
        package["receipt_integrity"] = {
            "status": "CANONICAL_RECEIPT_SELF_CONSISTENT",
            "reconciled_at": utc_now(),
            "prior_package_sha256": prior_package_sha,
            "maturity_sha256": digest(maturity),
            "rollback_manifest_sha256": backup["manifest_sha256"],
        }
        package["package_sha256"] = digest(package)
        _atomic_json(package_path, package)

        verification = {
            "package_id": package_id,
            "path": str(package_path),
            "readback_pass": _read_json(package_path)["package_sha256"] == package["package_sha256"],
            "package_sha256": package["package_sha256"],
            "status": "SUCCESSION_PACKAGE_VERIFIED_SELF_CONSISTENT",
        }
        state["succession_exports"][package_id] = verification
        _atomic_json(self.state_path, state)
        ledger_row = self._append_integrity_ledger(package_id, verification)
        ledger = verify_ledger(self.ledger_path)
        if not ledger["pass"]:
            raise RuntimeError("ledger integrity failed after reconciliation")

        preliminary = {
            "status": "CANONICAL_RECEIPT_INTEGRITY_VERIFIED",
            "package_id": package_id,
            "package_sha256": package["package_sha256"],
            "prior_package_sha256": prior_package_sha,
            "maturity_sha256": digest(maturity),
            "ledger_entry_sha256": ledger_row["entry_sha256"],
            "rollback_manifest_sha256": backup["manifest_sha256"],
            "checks": {
                "embedded_maturity_matches_final": package["maturity"] == maturity,
                "embedded_c15_ready": package["maturity"]["technical_gates"]["C15_succession_ready"],
                "package_hash_valid": _verify_payload_hash(package, "package_sha256"),
                "state_readback_matches_package": state["succession_exports"][package_id]["package_sha256"] == package["package_sha256"],
                "ledger_chain_valid": ledger["pass"],
                "rollback_snapshot_available": self.backup_manifest_path.is_file(),
            },
            "truth_boundary": "Receipt reconciliation proves internal canonical consistency only; all external commercial maturity gates remain unchanged.",
        }
        if not all(preliminary["checks"].values()):
            raise RuntimeError("canonical receipt integrity checks failed")

        receipt["stages"]["C15"]["proof"] = verification
        receipt["stages"]["C15"]["maturity"] = maturity
        receipt["ledger"] = ledger
        receipt["canonical_receipt_integrity"] = preliminary
        receipt.pop("receipt_sha256", None)
        receipt["receipt_sha256"] = digest(receipt)
        _atomic_json(self.receipt_path, receipt)

        integrity = self.verify()
        _atomic_json(self.integrity_path, integrity)
        return integrity

    def verify(self) -> dict[str, Any]:
        receipt = _read_json(self.receipt_path)
        maturity = _read_json(self.maturity_path)
        package_id = receipt["stages"]["C15"]["proof"]["package_id"]
        package_path = self.root / "reference-state" / "receipts" / f"succession-{package_id}.json"
        package = _read_json(package_path)
        state = _read_json(self.state_path)
        ledger = verify_ledger(self.ledger_path)
        receipt_hash_valid = _verify_payload_hash(receipt, "receipt_sha256")
        checks = {
            "embedded_maturity_matches_final": package.get("maturity") == maturity,
            "embedded_c15_ready": bool(package.get("maturity", {}).get("technical_gates", {}).get("C15_succession_ready")),
            "package_hash_valid": _verify_payload_hash(package, "package_sha256"),
            "state_readback_matches_package": state["succession_exports"][package_id]["package_sha256"] == package["package_sha256"],
            "top_level_maturity_matches_final": receipt["stages"]["C15"]["maturity"] == maturity,
            "top_level_package_matches_state": receipt["stages"]["C15"]["proof"]["package_sha256"] == package["package_sha256"],
            "top_receipt_hash_valid": receipt_hash_valid,
            "ledger_chain_valid": ledger["pass"],
            "rollback_snapshot_available": self.backup_manifest_path.is_file(),
        }
        result = {
            "status": "CANONICAL_RECEIPT_INTEGRITY_VERIFIED" if all(checks.values()) else "CANONICAL_RECEIPT_INTEGRITY_FAILED",
            "verified_at": utc_now(),
            "package_id": package_id,
            "package_sha256": package["package_sha256"],
            "commercial_receipt_sha256": receipt["receipt_sha256"],
            "maturity_sha256": digest(maturity),
            "ledger": ledger,
            "checks": checks,
            "truth_boundary": "No customer, revenue, payment, contract, cloud, partner, assurance or production-scale claim is created by this repair.",
        }
        result["integrity_receipt_sha256"] = digest(result)
        return result

    def rollback(self) -> dict[str, Any]:
        manifest = _read_json(self.backup_manifest_path)
        restored: dict[str, bool] = {}
        for name, record in manifest["files"].items():
            source = self.root / record["source"]
            backup = self.root / record["backup"]
            shutil.copyfile(backup, source)
            restored[name] = _sha256_bytes(source.read_bytes()) == record["sha256"]
        result = {
            "status": "CANONICAL_RECEIPT_ROLLBACK_VERIFIED" if all(restored.values()) else "CANONICAL_RECEIPT_ROLLBACK_FAILED",
            "rolled_back_at": utc_now(),
            "manifest_sha256": manifest["manifest_sha256"],
            "restored": restored,
        }
        result["rollback_receipt_sha256"] = digest(result)
        _atomic_json(self.rollback_receipt_path, result)
        return result
