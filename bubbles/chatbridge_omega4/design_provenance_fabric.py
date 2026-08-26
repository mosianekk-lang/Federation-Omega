from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Protocol, Sequence, Tuple


class DPFError(RuntimeError):
    """Base error for the Design Provenance Fabric bridge."""


class CaptureNotReconstructable(DPFError):
    pass


class ReconciliationTrigger(str, Enum):
    END_OF_CHAT = "END_OF_CHAT"
    END_OF_MATERIAL_SESSION = "END_OF_MATERIAL_SESSION"
    DAILY_RECONCILIATION = "DAILY_RECONCILIATION"
    PRE_PROMOTION = "PRE_PROMOTION"
    PRE_MIGRATION = "PRE_MIGRATION"
    PRE_DEPLOYMENT = "PRE_DEPLOYMENT"


class CaptureState(str, Enum):
    FULL_CAPTURE_VERIFIED = "FULL_CAPTURE_VERIFIED"
    CAPTURE_INCOMPLETE = "CAPTURE_INCOMPLETE"
    CAPTURE_EMPTY = "CAPTURE_EMPTY"
    CAPTURE_REJECTED_TAMPER = "CAPTURE_REJECTED_TAMPER"


class CleanupDisposition(str, Enum):
    PRESERVE_CANONICAL_RAW = "PRESERVE_CANONICAL_RAW"
    KEEP_ACTIVE = "KEEP_ACTIVE"
    ARCHIVE_DERIVED = "ARCHIVE_DERIVED"
    DEDUPE_DERIVED = "DEDUPE_DERIVED"
    DELETE_DERIVED_ALLOWED = "DELETE_DERIVED_ALLOWED"
    HOLD_RECONSTRUCTABILITY = "HOLD_RECONSTRUCTABILITY"


class LedgerLike(Protocol):
    def verify(self, conversation_key: str) -> Dict[str, Any]: ...
    def reconstruct(self, conversation_key: str, *, require_exact: bool = False) -> Dict[str, Any]: ...


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _nonblank(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} cannot be blank")
    return text


@dataclass(frozen=True)
class RawCaptureManifest:
    manifest_id: str
    lab_id: str
    conversation_key: str
    namespace_key: str
    source_provider: str
    source_locator: str
    source_kind: str
    capture_state: CaptureState
    event_count: int
    first_sequence: Optional[int]
    last_sequence: Optional[int]
    expected_first_sequence: Optional[int]
    expected_last_sequence: Optional[int]
    exact_context_complete: bool
    integrity_state: str
    restore_mode: str
    missing_ranges: Tuple[Mapping[str, int], ...] = field(default_factory=tuple)
    unavailable_sequences: Tuple[int, ...] = field(default_factory=tuple)
    unresolved_artifacts: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    chain_head_hash: str = ""
    merkle_root: str = ""
    terminal_observed: bool = False
    closure_reason: str = ""
    privacy_class: str = "P3_RESTRICTED"
    created_at: str = ""
    proof_fingerprint: str = ""
    truth_boundary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["capture_state"] = self.capture_state.value
        payload["missing_ranges"] = [dict(x) for x in self.missing_ranges]
        payload["unavailable_sequences"] = list(self.unavailable_sequences)
        payload["unresolved_artifacts"] = [dict(x) for x in self.unresolved_artifacts]
        return payload


@dataclass(frozen=True)
class ReconciliationReceipt:
    receipt_id: str
    lab_id: str
    conversation_key: str
    trigger: ReconciliationTrigger
    raw_manifest_id: str
    raw_manifest_fingerprint: str
    event_count: int
    material_decision_sequences: Tuple[int, ...]
    failure_sequences: Tuple[int, ...]
    correction_sequences: Tuple[int, ...]
    tool_activity_sequences: Tuple[int, ...]
    artifact_sequences: Tuple[int, ...]
    unresolved_gates: Tuple[str, ...]
    design_gene_candidates: Tuple[Mapping[str, Any], ...]
    reconciliation_fingerprint: str
    reconciled_at: str
    truth_boundary: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["trigger"] = self.trigger.value
        payload["material_decision_sequences"] = list(self.material_decision_sequences)
        payload["failure_sequences"] = list(self.failure_sequences)
        payload["correction_sequences"] = list(self.correction_sequences)
        payload["tool_activity_sequences"] = list(self.tool_activity_sequences)
        payload["artifact_sequences"] = list(self.artifact_sequences)
        payload["unresolved_gates"] = list(self.unresolved_gates)
        payload["design_gene_candidates"] = [dict(x) for x in self.design_gene_candidates]
        return payload


@dataclass(frozen=True)
class CleanupPlan:
    plan_id: str
    lab_id: str
    conversation_key: str
    raw_manifest_id: str
    reconciliation_receipt_id: str
    canonical_raw_disposition: CleanupDisposition
    derived_disposition: CleanupDisposition
    duplicate_groups: Tuple[Mapping[str, Any], ...]
    protected_sequences: Tuple[int, ...]
    cleanup_eligible: bool
    archive_pointer_required: bool
    reconstruction_required: bool
    reason: str
    plan_fingerprint: str
    planned_at: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["canonical_raw_disposition"] = self.canonical_raw_disposition.value
        payload["derived_disposition"] = self.derived_disposition.value
        payload["duplicate_groups"] = [dict(x) for x in self.duplicate_groups]
        payload["protected_sequences"] = list(self.protected_sequences)
        return payload


@dataclass(frozen=True)
class DPFCycleResult:
    manifest: RawCaptureManifest
    reconciliation: ReconciliationReceipt
    cleanup_plan: CleanupPlan

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "cleanup_plan": self.cleanup_plan.to_dict(),
        }


class DesignProvenanceBridge:
    """Provider-neutral ChatBridge -> DPF controller.

    ChatBridge remains the raw provenance authority. This bridge reads the ledger,
    emits immutable manifest/reconciliation receipts, and proposes cleanup only for
    derived/working copies. It never deletes or rewrites the canonical raw ledger.
    """

    VERSION = "FEDERATION-DPF-CHATBRIDGE-BRIDGE-1.0"
    CAPTURE_LAW = "FULL_CAPTURE_FIRST_RECONCILE_THEN_COMPACT"
    CANONICAL_RAW_LAW = "RAW_LEDGER_IMMUTABLE_ARCHIVE_PRESERVE"
    PROTECTED_EVENT_TYPES = frozenset(
        {"MESSAGE", "DECISION", "CORRECTION", "ATTACHMENT", "TERMINAL_WARNING", "MIGRATION"}
    )

    def __init__(
        self,
        ledger: LedgerLike,
        *,
        manifest_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
        reconciliation_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
        cleanup_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
        design_gene_extractor: Optional[
            Callable[[Sequence[Mapping[str, Any]]], Iterable[Mapping[str, Any]]]
        ] = None,
    ) -> None:
        self.ledger = ledger
        self.manifest_sink = manifest_sink
        self.reconciliation_sink = reconciliation_sink
        self.cleanup_sink = cleanup_sink
        self.design_gene_extractor = design_gene_extractor

    @staticmethod
    def daily_reconciliation_due(
        last_reconciled_at: Optional[str],
        *,
        now: Optional[datetime] = None,
        cadence: timedelta = timedelta(days=1),
    ) -> bool:
        current = now or datetime.now(timezone.utc)
        if not last_reconciled_at:
            return True
        parsed = datetime.fromisoformat(last_reconciled_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return current - parsed >= cadence

    def build_raw_manifest(
        self,
        *,
        lab_id: str,
        conversation_key: str,
        source_locator: str,
        source_kind: str = "CHATBRIDGE_FULL_FIDELITY_LEDGER",
        privacy_class: str = "P3_RESTRICTED",
        created_at: Optional[str] = None,
    ) -> RawCaptureManifest:
        lab = _nonblank(lab_id, "lab_id")
        conversation = _nonblank(conversation_key, "conversation_key")
        proof = self.ledger.verify(conversation)
        integrity = str(proof.get("integrity_state", ""))
        event_count = int(proof.get("event_count", 0) or 0)
        exact = bool(proof.get("exact_context_complete", False))
        if integrity == "FAIL_HASH_CHAIN":
            state = CaptureState.CAPTURE_REJECTED_TAMPER
        elif event_count == 0:
            state = CaptureState.CAPTURE_EMPTY
        elif exact:
            state = CaptureState.FULL_CAPTURE_VERIFIED
        else:
            state = CaptureState.CAPTURE_INCOMPLETE

        proof_material = {
            "conversation_key": conversation,
            "namespace_key": proof.get("namespace_key", ""),
            "source_provider": proof.get("source_provider", ""),
            "event_count": event_count,
            "expected_first_sequence": proof.get("expected_first_sequence"),
            "expected_last_sequence": proof.get("expected_last_sequence"),
            "missing_ranges": proof.get("missing_ranges", []),
            "unavailable_sequences": proof.get("unavailable_sequences", []),
            "unresolved_artifacts": proof.get("unresolved_artifacts", []),
            "chain_head_hash": proof.get("chain_head_hash", ""),
            "merkle_root": proof.get("merkle_root", ""),
            "integrity_state": integrity,
            "restore_mode": proof.get("restore_mode", ""),
            "exact_context_complete": exact,
        }
        fingerprint = _sha256(proof_material)
        manifest_id = f"dpf-raw-{lab}-{conversation}-{fingerprint[:16]}"
        manifest = RawCaptureManifest(
            manifest_id=manifest_id,
            lab_id=lab,
            conversation_key=conversation,
            namespace_key=str(proof.get("namespace_key", "")),
            source_provider=str(proof.get("source_provider", "")),
            source_locator=str(source_locator or ""),
            source_kind=str(source_kind or "CHATBRIDGE_FULL_FIDELITY_LEDGER"),
            capture_state=state,
            event_count=event_count,
            first_sequence=proof.get("first_sequence"),
            last_sequence=proof.get("last_sequence"),
            expected_first_sequence=proof.get("expected_first_sequence"),
            expected_last_sequence=proof.get("expected_last_sequence"),
            exact_context_complete=exact,
            integrity_state=integrity,
            restore_mode=str(proof.get("restore_mode", "")),
            missing_ranges=tuple(proof.get("missing_ranges", []) or []),
            unavailable_sequences=tuple(
                int(x) for x in proof.get("unavailable_sequences", []) or []
            ),
            unresolved_artifacts=tuple(proof.get("unresolved_artifacts", []) or []),
            chain_head_hash=str(proof.get("chain_head_hash", "")),
            merkle_root=str(proof.get("merkle_root", "")),
            terminal_observed=bool(proof.get("terminal_observed", False)),
            closure_reason=str(proof.get("closure_reason", "")),
            privacy_class=privacy_class,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            proof_fingerprint=fingerprint,
            truth_boundary=(
                "FULL_CAPTURE_VERIFIED_FROM_CHATBRIDGE_LEDGER"
                if state == CaptureState.FULL_CAPTURE_VERIFIED
                else "CAPTURE_STATE_REFLECTS_CHATBRIDGE_LEDGER_PROOF_GAPS_NO_GAPS_INFERRED"
            ),
        )
        if self.manifest_sink:
            self.manifest_sink(manifest.to_dict())
        return manifest

    def reconcile(
        self,
        manifest: RawCaptureManifest,
        *,
        trigger: ReconciliationTrigger,
        reconciled_at: Optional[str] = None,
    ) -> ReconciliationReceipt:
        if manifest.capture_state == CaptureState.CAPTURE_REJECTED_TAMPER:
            raise CaptureNotReconstructable("tampered raw capture cannot be reconciled")
        reconstruction = self.ledger.reconstruct(
            manifest.conversation_key, require_exact=False
        )
        events = list(reconstruction.get("transcript", []) or [])
        decisions, failures, corrections, tool_activity, artifact_sequences = [], [], [], [], []
        unresolved_gates = []
        for event in events:
            sequence = int(event.get("sequence", 0) or 0)
            event_type = str(event.get("event_type", "OTHER"))
            execution_state = str(event.get("execution_state", "UNVERIFIED"))
            if event_type == "DECISION":
                decisions.append(sequence)
            if execution_state == "FAILED_VERIFIED":
                failures.append(sequence)
            if event_type == "CORRECTION":
                corrections.append(sequence)
            if event_type in {"TOOL_CALL", "TOOL_RESULT"}:
                tool_activity.append(sequence)
            if event.get("artifacts"):
                artifact_sequences.append(sequence)

        context_manifest = reconstruction.get("context_manifest", {}) or {}
        if context_manifest.get("missing_ranges"):
            unresolved_gates.append("RAW_CAPTURE_MISSING_RANGES")
        if context_manifest.get("unavailable_sequences"):
            unresolved_gates.append("RAW_PAYLOAD_UNAVAILABLE_SEQUENCES")
        if context_manifest.get("unresolved_artifacts"):
            unresolved_gates.append("UNRESOLVED_REQUIRED_ARTIFACTS")
        if not manifest.exact_context_complete:
            unresolved_gates.append("FULL_CAPTURE_NOT_YET_VERIFIED")

        candidates: Tuple[Mapping[str, Any], ...] = tuple()
        if self.design_gene_extractor:
            candidates = tuple(dict(item) for item in (self.design_gene_extractor(events) or []))

        core = {
            "lab_id": manifest.lab_id,
            "conversation_key": manifest.conversation_key,
            "trigger": trigger.value,
            "raw_manifest_id": manifest.manifest_id,
            "raw_manifest_fingerprint": manifest.proof_fingerprint,
            "event_count": len(events),
            "material_decision_sequences": decisions,
            "failure_sequences": failures,
            "correction_sequences": corrections,
            "tool_activity_sequences": tool_activity,
            "artifact_sequences": artifact_sequences,
            "unresolved_gates": unresolved_gates,
            "design_gene_candidates": candidates,
        }
        fingerprint = _sha256(core)
        receipt = ReconciliationReceipt(
            receipt_id=f"dpf-rec-{manifest.lab_id}-{fingerprint[:16]}",
            lab_id=manifest.lab_id,
            conversation_key=manifest.conversation_key,
            trigger=trigger,
            raw_manifest_id=manifest.manifest_id,
            raw_manifest_fingerprint=manifest.proof_fingerprint,
            event_count=len(events),
            material_decision_sequences=tuple(decisions),
            failure_sequences=tuple(failures),
            correction_sequences=tuple(corrections),
            tool_activity_sequences=tuple(tool_activity),
            artifact_sequences=tuple(artifact_sequences),
            unresolved_gates=tuple(unresolved_gates),
            design_gene_candidates=candidates,
            reconciliation_fingerprint=fingerprint,
            reconciled_at=reconciled_at or datetime.now(timezone.utc).isoformat(),
            truth_boundary="DETERMINISTIC_INDEX_AND_PROJECTION_ONLY_DESIGN_GENE_PROMOTION_SEPARATE",
        )
        if self.reconciliation_sink:
            self.reconciliation_sink(receipt.to_dict())
        return receipt

    def plan_compaction(
        self,
        manifest: RawCaptureManifest,
        reconciliation: ReconciliationReceipt,
        *,
        archive_pointer_available: bool,
        planned_at: Optional[str] = None,
    ) -> CleanupPlan:
        reconstruction = self.ledger.reconstruct(
            manifest.conversation_key, require_exact=False
        )
        events = list(reconstruction.get("transcript", []) or [])
        protected_sequences = []
        hashes: Dict[str, list[int]] = {}
        for event in events:
            seq = int(event.get("sequence", 0) or 0)
            event_type = str(event.get("event_type", "OTHER"))
            if event_type in self.PROTECTED_EVENT_TYPES:
                protected_sequences.append(seq)
            content_hash = str(event.get("content_hash", ""))
            if content_hash:
                hashes.setdefault(content_hash, []).append(seq)

        duplicate_groups = tuple(
            {"content_hash": digest, "sequences": sequences}
            for digest, sequences in sorted(hashes.items())
            if len(sequences) > 1
        )
        cleanup_eligible = bool(
            manifest.capture_state == CaptureState.FULL_CAPTURE_VERIFIED
            and archive_pointer_available
            and reconciliation.raw_manifest_fingerprint == manifest.proof_fingerprint
        )
        if cleanup_eligible:
            derived = (
                CleanupDisposition.DEDUPE_DERIVED
                if duplicate_groups
                else CleanupDisposition.ARCHIVE_DERIVED
            )
            reason = "FULL_RAW_CAPTURE_AND_ARCHIVE_POINTER_VERIFIED_DERIVED_COMPACTION_ALLOWED"
        else:
            derived = CleanupDisposition.HOLD_RECONSTRUCTABILITY
            reason = "COMPACTION_HELD_UNTIL_FULL_CAPTURE_AND_ARCHIVE_RECONSTRUCTABILITY_ARE_VERIFIED"

        core = {
            "lab_id": manifest.lab_id,
            "conversation_key": manifest.conversation_key,
            "manifest": manifest.manifest_id,
            "reconciliation": reconciliation.receipt_id,
            "duplicate_groups": duplicate_groups,
            "protected_sequences": protected_sequences,
            "cleanup_eligible": cleanup_eligible,
            "archive_pointer_available": archive_pointer_available,
            "reason": reason,
        }
        fingerprint = _sha256(core)
        plan = CleanupPlan(
            plan_id=f"dpf-clean-{manifest.lab_id}-{fingerprint[:16]}",
            lab_id=manifest.lab_id,
            conversation_key=manifest.conversation_key,
            raw_manifest_id=manifest.manifest_id,
            reconciliation_receipt_id=reconciliation.receipt_id,
            canonical_raw_disposition=CleanupDisposition.PRESERVE_CANONICAL_RAW,
            derived_disposition=derived,
            duplicate_groups=duplicate_groups,
            protected_sequences=tuple(protected_sequences),
            cleanup_eligible=cleanup_eligible,
            archive_pointer_required=True,
            reconstruction_required=True,
            reason=reason,
            plan_fingerprint=fingerprint,
            planned_at=planned_at or datetime.now(timezone.utc).isoformat(),
        )
        if self.cleanup_sink:
            self.cleanup_sink(plan.to_dict())
        return plan

    def run_cycle(
        self,
        *,
        lab_id: str,
        conversation_key: str,
        source_locator: str,
        trigger: ReconciliationTrigger,
        archive_pointer_available: bool,
        source_kind: str = "CHATBRIDGE_FULL_FIDELITY_LEDGER",
        privacy_class: str = "P3_RESTRICTED",
    ) -> DPFCycleResult:
        manifest = self.build_raw_manifest(
            lab_id=lab_id,
            conversation_key=conversation_key,
            source_locator=source_locator,
            source_kind=source_kind,
            privacy_class=privacy_class,
        )
        reconciliation = self.reconcile(manifest, trigger=trigger)
        cleanup = self.plan_compaction(
            manifest,
            reconciliation,
            archive_pointer_available=archive_pointer_available,
        )
        return DPFCycleResult(manifest, reconciliation, cleanup)

    @classmethod
    def contract(cls) -> Dict[str, Any]:
        return {
            "version": cls.VERSION,
            "capture_law": cls.CAPTURE_LAW,
            "canonical_raw_law": cls.CANONICAL_RAW_LAW,
            "raw_authority": "CHATBRIDGE_FULL_FIDELITY_LEDGER",
            "reconciliation": "END_OF_CHAT_OR_DAILY_OR_PRE_PROMOTION_DETERMINISTIC_INDEX",
            "cleanup": "DERIVED_COPIES_ONLY_UNLESS_SEPARATE_VERIFIED_GC_AUTHORITY_EXISTS",
            "design_gene": "CANDIDATE_ONLY_UNTIL_CFBE_JARVIS_RECEIVER_SPECIFIC_PROOF",
            "provider_boundary": "NO_PROVIDER_AUTHORITY_OR_RUNTIME_MATURITY_INHERITANCE",
        }


__all__ = [
    "CaptureNotReconstructable",
    "CaptureState",
    "CleanupDisposition",
    "CleanupPlan",
    "DesignProvenanceBridge",
    "DPFCycleResult",
    "DPFError",
    "RawCaptureManifest",
    "ReconciliationReceipt",
    "ReconciliationTrigger",
]
