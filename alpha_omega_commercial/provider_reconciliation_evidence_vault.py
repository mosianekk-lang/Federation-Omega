from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from authority_snapshot import digest, valid_sha256
from provider_reconciliation_challenge_safe import (
    ChallengeBoundMockProviderAdapter,
    ChallengeBoundProviderDispatchCommercialControlPlane,
)

RECONCILIATION_EVIDENCE_PACKAGE_CLASS = (
    "LOCAL_PROVIDER_RECONCILIATION_EVIDENCE_PACKAGE_V16"
)


class VaultedProviderDispatchCommercialControlPlane(
    ChallengeBoundProviderDispatchCommercialControlPlane
):
    """V16 durably retains every reconciliation proof before state resolution.

    V15 binds a one-time challenge to an uncertain provider attempt and records the
    reconciliation SHA-256 in the claim history. V16 closes the remaining local
    durability gap by publishing the complete verified evidence as a content-
    addressed, hash-bound file before the outcome state can be resolved. Live
    provider reconciliation remains blocked without fresh provider-native authority.
    """

    CAPABILITY_REVISION = "AO-COMMERCIAL-PROVIDER-RECONCILIATION-EVIDENCE-VAULT-V16"
    STAGE_SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.provider_reconciliation_evidence_dir = (
            Path(self.state_dir) / "provider_reconciliation_evidence"
        )
        self.provider_reconciliation_evidence_dir.mkdir(parents=True, exist_ok=True)
        self._remove_incomplete_publications()
        self._verify_provider_reconciliation_evidence_state()

    @staticmethod
    def _canonical_bytes(value: Any) -> bytes:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _remove_incomplete_publications(self) -> None:
        removed = False
        for path in self.provider_reconciliation_evidence_dir.glob(".publish-*.tmp"):
            if path.is_file():
                path.unlink()
                removed = True
        if removed:
            self._fsync_directory(self.provider_reconciliation_evidence_dir)

    def _package_path(self, reconciliation_sha256: str) -> Path:
        if not valid_sha256(reconciliation_sha256):
            raise ValueError("provider reconciliation evidence SHA-256 invalid")
        destination = (
            self.provider_reconciliation_evidence_dir
            / f"{reconciliation_sha256}.json"
        )
        if destination.parent.resolve() != self.provider_reconciliation_evidence_dir.resolve():
            raise RuntimeError("provider reconciliation evidence path invalid")
        return destination

    def _build_evidence_package(self, evidence: dict[str, Any]) -> dict[str, Any]:
        verified = self._verify_evidence(evidence)
        reconciliation_sha256 = str(verified["reconciliation_sha256"])
        package: dict[str, Any] = {
            "package_class": RECONCILIATION_EVIDENCE_PACKAGE_CLASS,
            "reconciliation_sha256": reconciliation_sha256,
            "evidence": verified,
        }
        package["package_sha256"] = digest(package)
        return package

    def _verify_evidence_package(
        self,
        package: Any,
        *,
        expected_reconciliation_sha256: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(package, dict):
            raise RuntimeError("provider reconciliation evidence package invalid")
        payload = dict(package)
        observed_package_sha256 = payload.pop("package_sha256", None)
        if observed_package_sha256 != digest(payload):
            raise RuntimeError("provider reconciliation evidence package hash invalid")
        if package.get("package_class") != RECONCILIATION_EVIDENCE_PACKAGE_CLASS:
            raise RuntimeError("provider reconciliation evidence package class invalid")
        evidence = package.get("evidence")
        if not isinstance(evidence, dict):
            raise RuntimeError("provider reconciliation evidence payload invalid")
        verified_evidence = self._verify_evidence(evidence)
        reconciliation_sha256 = str(package.get("reconciliation_sha256", ""))
        if reconciliation_sha256 != verified_evidence.get("reconciliation_sha256"):
            raise RuntimeError("provider reconciliation evidence package binding invalid")
        if (
            expected_reconciliation_sha256 is not None
            and reconciliation_sha256 != expected_reconciliation_sha256
        ):
            raise RuntimeError("provider reconciliation evidence reference mismatch")
        return dict(package)

    def _load_evidence_package(self, reconciliation_sha256: str) -> dict[str, Any]:
        destination = self._package_path(reconciliation_sha256)
        if not destination.is_file():
            raise RuntimeError("referenced provider reconciliation evidence missing")
        try:
            package = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "provider reconciliation evidence package unreadable"
            ) from exc
        return self._verify_evidence_package(
            package,
            expected_reconciliation_sha256=reconciliation_sha256,
        )

    def _persist_provider_reconciliation_evidence(
        self, evidence: dict[str, Any]
    ) -> dict[str, Any]:
        package = self._build_evidence_package(evidence)
        reconciliation_sha256 = str(package["reconciliation_sha256"])
        destination = self._package_path(reconciliation_sha256)
        if destination.exists():
            existing = self._load_evidence_package(reconciliation_sha256)
            if existing != package:
                raise RuntimeError("provider reconciliation evidence package conflict")
            return existing

        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".publish-",
                suffix=".tmp",
                dir=self.provider_reconciliation_evidence_dir,
                delete=False,
            ) as stream:
                temporary_name = stream.name
                stream.write(self._canonical_bytes(package))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, destination)
            temporary_name = None
            self._fsync_directory(self.provider_reconciliation_evidence_dir)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

        return self._load_evidence_package(reconciliation_sha256)

    @staticmethod
    def _referenced_evidence_hashes(state: dict[str, Any]) -> set[str]:
        referenced: set[str] = set()
        for history in state.get("provider_dispatch_claim_history", {}).values():
            if not isinstance(history, list):
                continue
            for event in history:
                if not isinstance(event, dict):
                    continue
                value = event.get("outcome_reconciliation_sha256")
                if isinstance(value, str) and value:
                    referenced.add(value)
        return referenced

    def _available_evidence_hashes(self) -> set[str]:
        available: set[str] = set()
        for path in self.provider_reconciliation_evidence_dir.glob("*.json"):
            reconciliation_sha256 = path.stem
            package = self._load_evidence_package(reconciliation_sha256)
            if package["reconciliation_sha256"] != reconciliation_sha256:
                raise RuntimeError("provider reconciliation evidence filename mismatch")
            available.add(reconciliation_sha256)
        return available

    def _verify_provider_reconciliation_evidence_state(self) -> dict[str, Any]:
        super()._verify_provider_dispatch_attempt_state()
        state = self._read_state()
        referenced = self._referenced_evidence_hashes(state)
        available = self._available_evidence_hashes()
        missing = sorted(referenced - available)
        if missing:
            raise RuntimeError(
                "referenced provider reconciliation evidence missing: "
                + ",".join(missing)
            )
        return {
            "referenced": referenced,
            "available": available,
            "orphaned": available - referenced,
        }

    def provider_reconciliation_evidence_package(
        self, reconciliation_sha256: str
    ) -> dict[str, Any]:
        with self._action_coordination_locked():
            return self._load_evidence_package(reconciliation_sha256)

    def resolve_provider_dispatch_outcome(
        self,
        dispatch_id: str,
        evidence: dict[str, Any],
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        with self._action_coordination_locked():
            package = self._persist_provider_reconciliation_evidence(evidence)
            result = super().resolve_provider_dispatch_outcome(
                dispatch_id,
                evidence,
                now=now,
            )
            result["evidence_package"] = {
                "package_class": package["package_class"],
                "reconciliation_sha256": package["reconciliation_sha256"],
                "package_sha256": package["package_sha256"],
                "path": self._package_path(
                    str(package["reconciliation_sha256"])
                ).name,
            }
            return result

    def prune_orphaned_provider_reconciliation_evidence(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            integrity = self._verify_provider_reconciliation_evidence_state()
            removed = sorted(integrity["orphaned"])
            for reconciliation_sha256 in removed:
                self._package_path(reconciliation_sha256).unlink()
            if removed:
                self._fsync_directory(self.provider_reconciliation_evidence_dir)
            receipt = {
                "removed_count": len(removed),
                "removed_reconciliation_sha256": removed,
                "external_mutation_performed": False,
            }
            self._ledger(
                "C06",
                "provider_reconciliation.evidence_orphans_pruned",
                digest(receipt),
                receipt,
            )
            return receipt

    def provider_reconciliation_evidence_readback(self) -> dict[str, Any]:
        base = super().provider_reconciliation_challenge_readback()
        with self._action_coordination_locked():
            integrity = self._verify_provider_reconciliation_evidence_state()
            return {
                **base,
                "capability_revision": self.CAPABILITY_REVISION,
                "stage_scope": list(self.STAGE_SCOPE),
                "evidence_package_class": RECONCILIATION_EVIDENCE_PACKAGE_CLASS,
                "evidence_packages": len(integrity["available"]),
                "referenced_evidence_packages": len(integrity["referenced"]),
                "orphaned_evidence_packages": len(integrity["orphaned"]),
                "content_addressed_evidence_publication": True,
                "evidence_published_before_resolution": True,
                "resolution_event_hash_binding_verified": True,
                "restart_requires_referenced_evidence": True,
                "orphan_quarantine_and_prune_supported": True,
                "provider_native_reconciliation_authority": (
                    "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
                ),
                "provider_native_reconciliation_proven": False,
                "external_mutation_performed": False,
                "live_provider_operation_proven": False,
            }

    def governed_authority_readback(self) -> dict[str, Any]:
        result = super().governed_authority_readback()
        result["canonical_class"] = self.__class__.__name__
        result["predecessor_class"] = (
            "ChallengeBoundProviderDispatchCommercialControlPlane"
        )
        result["provider_reconciliation_evidence_vault"] = (
            self.provider_reconciliation_evidence_readback()
        )
        return result


__all__ = [
    "VaultedProviderDispatchCommercialControlPlane",
    "ChallengeBoundMockProviderAdapter",
    "RECONCILIATION_EVIDENCE_PACKAGE_CLASS",
]
