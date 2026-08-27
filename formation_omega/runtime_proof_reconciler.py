from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterable, Mapping, Sequence


class RuntimeProofStage(IntEnum):
    """Monotonic proof maturity for the BEF/ChatBridge Windows canary."""

    NO_RUNTIME_PROOF = 0
    SOURCE_ADMITTED = 1
    NATIVE_HOST_BUILT = 2
    NATIVE_HOST_REGISTERED = 3
    BROWSER_BOUND = 4
    LIVE_DELIVERY = 5
    OBSERVABLE_DPF_VERIFIED = 6
    ROLLBACK_VERIFIED = 7
    RESILIENCE_VERIFIED = 8


@dataclass(frozen=True)
class RuntimeProofSnapshot:
    stage: RuntimeProofStage
    satisfied_stages: tuple[str, ...]
    receipt_sha256s: tuple[str, ...]
    chain_head_sha256: str
    violations: tuple[str, ...]
    unsupported_schemas: tuple[str, ...]
    provider_native_complete: bool
    truth_boundary: str

    @property
    def valid(self) -> bool:
        return not self.violations


class RuntimeProofReconciler:
    """Fail-closed receipt reconciler for runtime proof maturation.

    The reconciler never executes a workstation action. It consumes explicit
    receipts/readbacks, validates their semantics, and exposes only the highest
    *contiguous* proof stage. Rendered-DOM evidence can never be promoted into
    provider-native hidden-event completeness.
    """

    SOURCE_SCHEMA = "FEDERATION-RUNTIME-PROOF-SOURCE-ADMISSION-1"
    BOOTSTRAP_SCHEMA = "SOVARA-BEF-CHATBRIDGE-WINDOWS-CANARY-BOOTSTRAP-1"
    READBACK_SCHEMA = "SOVARA-BEF-CHATBRIDGE-WINDOWS-RUNTIME-READBACK-1"
    DPF_SCHEMA = "BEF_OBSERVABLE_SCOPE_EVIDENCE"
    ROLLBACK_SCHEMA = "SOVARA-BEF-CHATBRIDGE-WINDOWS-ROLLBACK-1"
    RESILIENCE_SCHEMA = "SOVARA-BEF-CHATBRIDGE-WINDOWS-RESILIENCE-1"

    CHATBRIDGE_EXTENSION_ID = "kacbginamagliaddmlkffhcadpamomjb"
    BEF_EXTENSION_ID = "apokbhjjgiaceigelkedcelcecfmgnia"

    TRUTH_BOUNDARY = (
        "FULL_OBSERVABLE_RENDERED_CHAT_EVIDENCE_ONLY / "
        "PROVIDER_NATIVE_HIDDEN_EVENTS_NOT_INFERRED"
    )

    SUPPORTED_SCHEMAS = frozenset(
        {
            SOURCE_SCHEMA,
            BOOTSTRAP_SCHEMA,
            READBACK_SCHEMA,
            DPF_SCHEMA,
            ROLLBACK_SCHEMA,
            RESILIENCE_SCHEMA,
        }
    )

    @staticmethod
    def _canonical_bytes(receipt: Mapping[str, Any]) -> bytes:
        return json.dumps(
            receipt,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

    @classmethod
    def receipt_sha256(cls, receipt: Mapping[str, Any]) -> str:
        return hashlib.sha256(cls._canonical_bytes(receipt)).hexdigest()

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _as_bool(value: Any) -> bool:
        return value is True

    @classmethod
    def _schema(cls, receipt: Mapping[str, Any]) -> str:
        return cls._text(receipt.get("schema") or receipt.get("state"))

    @classmethod
    def _check_identity(cls, receipt: Mapping[str, Any], violations: list[str]) -> None:
        chat = cls._text(
            receipt.get("chatBridgeExtensionId")
            or receipt.get("chatbridge_extension_id")
        )
        bef = cls._text(
            receipt.get("befEdgeExtensionId")
            or receipt.get("bef_edge_extension_id")
        )
        if chat and chat != cls.CHATBRIDGE_EXTENSION_ID:
            violations.append("CHATBRIDGE_EXTENSION_IDENTITY_MISMATCH")
        if bef and bef != cls.BEF_EXTENSION_ID:
            violations.append("BEF_EXTENSION_IDENTITY_MISMATCH")

    @classmethod
    def _source_ok(cls, receipt: Mapping[str, Any], violations: list[str]) -> bool:
        if receipt.get("verified") is not True:
            violations.append("SOURCE_ADMISSION_NOT_VERIFIED")
            return False
        if not cls._text(receipt.get("commit_sha")):
            violations.append("SOURCE_ADMISSION_COMMIT_SHA_REQUIRED")
            return False
        return True

    @classmethod
    def _bootstrap_stages(
        cls, receipt: Mapping[str, Any], violations: list[str]
    ) -> set[RuntimeProofStage]:
        cls._check_identity(receipt, violations)
        stages: set[RuntimeProofStage] = set()
        state = cls._text(receipt.get("state")).upper()
        host_sha = cls._text(receipt.get("nativeHostSha256"))
        if host_sha:
            stages.add(RuntimeProofStage.NATIVE_HOST_BUILT)
        if (
            state
            in {
                "NATIVE_HOST_REGISTERED_CANARY_PROFILE_PREPARED",
                "BROWSER_EXTENSIONS_PROFILE_READBACK_VERIFIED",
            }
            and cls._text(receipt.get("nativeHostRegistrationState"))
            == "NATIVE_HOST_REGISTERED_VERIFIED"
            and host_sha
        ):
            stages.add(RuntimeProofStage.NATIVE_HOST_REGISTERED)
        if (
            state == "BROWSER_EXTENSIONS_PROFILE_READBACK_VERIFIED"
            and cls._text(receipt.get("extensionReadback"))
            == "BOTH_EXTENSIONS_PRESENT_IN_PROFILE_PREFERENCES"
        ):
            stages.add(RuntimeProofStage.BROWSER_BOUND)
        return stages

    @classmethod
    def _readback_stages(
        cls, receipt: Mapping[str, Any], violations: list[str]
    ) -> set[RuntimeProofStage]:
        cls._check_identity(receipt, violations)
        stages: set[RuntimeProofStage] = set()
        state = cls._text(receipt.get("state")).upper()
        registered = (
            cls._as_bool(receipt.get("nativeHostRegistered"))
            and cls._as_bool(receipt.get("nativeHostManifestValid"))
            and cls._as_bool(receipt.get("nativeHostExecutableValid"))
            and bool(cls._text(receipt.get("nativeHostSha256")))
        )
        if registered:
            stages.update(
                {RuntimeProofStage.NATIVE_HOST_BUILT, RuntimeProofStage.NATIVE_HOST_REGISTERED}
            )
        browser = (
            registered
            and cls._as_bool(receipt.get("chatBridgeProfilePresent"))
            and cls._as_bool(receipt.get("befEdgeProfilePresent"))
        )
        if browser:
            stages.add(RuntimeProofStage.BROWSER_BOUND)
        if state == "LIVE_ENCRYPTED_SPOOL_RECEIPT_OBSERVED":
            live = (
                browser
                and int(receipt.get("encryptedSpoolReceiptCount", 0) or 0) > 0
                and cls._as_bool(receipt.get("latestStoredEncrypted"))
                and bool(cls._text(receipt.get("latestSpoolReceiptId")))
                and bool(cls._text(receipt.get("latestEnvelopeSha256")))
            )
            if live:
                stages.add(RuntimeProofStage.LIVE_DELIVERY)
            else:
                violations.append("LIVE_DELIVERY_STATE_WITHOUT_COMPLETE_READBACK")
        return stages

    @classmethod
    def _dpf_ok(cls, receipt: Mapping[str, Any], violations: list[str]) -> bool:
        evidence = cls._mapping(receipt.get("evidence"))
        if not evidence:
            evidence = receipt
        if evidence.get("provider_native_complete") is True:
            violations.append("OBSERVABLE_SCOPE_ESCALATION_FORBIDDEN")
            return False
        if cls._text(evidence.get("capture_scope")).upper() != "RENDERED_DOM":
            violations.append("DPF_CAPTURE_SCOPE_NOT_RENDERED_DOM")
            return False
        checks = (
            cls._as_bool(evidence.get("exact_rendered_transcript_complete")),
            not list(evidence.get("missing_ranges") or []),
            not list(evidence.get("unresolved_artifacts") or []),
            cls._as_bool(evidence.get("stored_encrypted")),
            bool(cls._text(evidence.get("evidence_fingerprint"))),
            bool(cls._text(evidence.get("spool_receipt_id"))),
        )
        if not all(checks):
            violations.append("DPF_OBSERVABLE_SCOPE_PROOF_INCOMPLETE")
            return False
        boundary = cls._text(evidence.get("truth_boundary"))
        if boundary and "PROVIDER_NATIVE_HIDDEN_EVENTS_NOT_INFERRED" not in boundary:
            violations.append("DPF_TRUTH_BOUNDARY_DRIFT")
            return False
        return True

    @classmethod
    def _rollback_ok(cls, receipt: Mapping[str, Any], violations: list[str]) -> bool:
        if cls._text(receipt.get("State") or receipt.get("state")).upper() != "CANARY_RUNTIME_BINDING_ROLLED_BACK":
            violations.append("ROLLBACK_STATE_NOT_VERIFIED")
            return False
        if receipt.get("RegistryBindingRemoved") is not True:
            violations.append("ROLLBACK_REGISTRY_BINDING_STILL_PRESENT")
            return False
        if receipt.get("EncryptedSpoolPreserved") is not True:
            violations.append("ROLLBACK_EVIDENCE_SPOOL_NOT_PRESERVED")
            return False
        return True

    @classmethod
    def _resilience_ok(cls, receipt: Mapping[str, Any], violations: list[str]) -> bool:
        repetitions = int(receipt.get("successfulRepetitions", 0) or 0)
        checks = (
            repetitions >= 3,
            receipt.get("rollbackRecoveryPassed") is True,
            receipt.get("freshReadbackPassed") is True,
            receipt.get("truthBoundaryRegression") is False,
        )
        if not all(checks):
            violations.append("RESILIENCE_PROOF_INCOMPLETE")
            return False
        return True

    def reconcile(self, receipts: Iterable[Mapping[str, Any]]) -> RuntimeProofSnapshot:
        receipts_list = [dict(receipt) for receipt in receipts]
        violations: list[str] = []
        unsupported: list[str] = []
        proven: set[RuntimeProofStage] = set()
        hashes: list[str] = []
        chain_head = "0" * 64

        for receipt in receipts_list:
            schema = self._schema(receipt)
            digest = self.receipt_sha256(receipt)
            hashes.append(digest)
            chain_head = hashlib.sha256((chain_head + digest).encode("ascii")).hexdigest()

            if schema not in self.SUPPORTED_SCHEMAS:
                unsupported.append(schema or "<missing>")
                continue

            if schema == self.SOURCE_SCHEMA:
                if self._source_ok(receipt, violations):
                    proven.add(RuntimeProofStage.SOURCE_ADMITTED)
            elif schema == self.BOOTSTRAP_SCHEMA:
                proven.update(self._bootstrap_stages(receipt, violations))
            elif schema == self.READBACK_SCHEMA:
                proven.update(self._readback_stages(receipt, violations))
            elif schema == self.DPF_SCHEMA:
                if self._dpf_ok(receipt, violations):
                    proven.add(RuntimeProofStage.OBSERVABLE_DPF_VERIFIED)
            elif schema == self.ROLLBACK_SCHEMA:
                if self._rollback_ok(receipt, violations):
                    proven.add(RuntimeProofStage.ROLLBACK_VERIFIED)
            elif schema == self.RESILIENCE_SCHEMA:
                if self._resilience_ok(receipt, violations):
                    proven.add(RuntimeProofStage.RESILIENCE_VERIFIED)

        # A stage is exposable only when every lower stage has explicit proof.
        highest = RuntimeProofStage.NO_RUNTIME_PROOF
        satisfied: list[str] = []
        for stage in RuntimeProofStage:
            if stage == RuntimeProofStage.NO_RUNTIME_PROOF:
                continue
            if stage in proven:
                # NATIVE_HOST_BUILT is also established by a valid registered readback.
                highest = stage
                satisfied.append(stage.name)
                continue
            break

        if unsupported:
            violations.append("UNSUPPORTED_RECEIPT_SCHEMA_PRESENT")

        return RuntimeProofSnapshot(
            stage=highest,
            satisfied_stages=tuple(satisfied),
            receipt_sha256s=tuple(hashes),
            chain_head_sha256=chain_head,
            violations=tuple(sorted(set(violations))),
            unsupported_schemas=tuple(sorted(set(unsupported))),
            provider_native_complete=False,
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = ["RuntimeProofReconciler", "RuntimeProofSnapshot", "RuntimeProofStage"]
