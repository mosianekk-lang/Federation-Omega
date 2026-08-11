from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class TruthGridViolation(ValueError):
    """Raised when a proposed TruthGrid action violates a hard control."""


class MissionLockDecision(str, Enum):
    STAY_ON_FOUNDATION = "STAY_ON_FOUNDATION"
    ALLOW_DOWNSTREAM = "ALLOW_DOWNSTREAM"
    OVERRIDE_ALLOWED = "OVERRIDE_ALLOWED"


@dataclass(frozen=True)
class Mission:
    mission_id: str
    complete: bool
    mandatory_open_dependencies: tuple[str, ...] = ()
    downstream_missions: tuple[str, ...] = ()
    explicit_user_override: bool = False
    external_deadline_override: bool = False
    legal_preservation_override: bool = False
    safety_override: bool = False


@dataclass(frozen=True)
class MutationIntent:
    sheet: str
    operation: str
    target_key: str | None
    row_identity_resolved_by_key: bool
    values: Mapping[str, object]
    source_ids: tuple[str, ...] = ()
    receipt_ids: tuple[str, ...] = ()
    current_revision_id: str | None = None
    target_revision_id: str | None = None
    source_classifications: tuple[str, ...] = ()
    provider_readback_planned: bool = True


@dataclass
class TruthGridGuard:
    """Deterministic pre-mutation and pre-promotion guard."""

    integrity_manifest_sheet: str = "INTEGRITY MANIFEST"
    release_gate_sheet: str = "RELEASE GATES"
    raw_integrity_fields: frozenset[str] = frozenset(
        {"Hash", "SHA256", "SHA-256", "Byte_Size", "Size", "Raw_Hash", "Raw_Byte_Size"}
    )
    durable_identity_fields: frozenset[str] = frozenset(
        {"Source_ID", "Native_ID", "Provider_Object_ID", "Attachment_Object_ID"}
    )
    role_authority_fields: frozenset[str] = frozenset(
        {"Authority_Status", "Appointment_Status", "Delegation_Status"}
    )
    release_words: frozenset[str] = frozenset(
        {"PASS", "CLOSED", "COMPLETE", "RELEASE_VERIFIED", "RELEASE_CLEARED", "FILING_READY", "VERIFIED"}
    )
    ephemeral_identity_markers: frozenset[str] = frozenset(
        {"attachment_id", "GMAIL_ATTACHMENT_ID", "EPHEMERAL_ACQUISITION_HANDLE"}
    )
    receipt_required_fields: tuple[str, ...] = (
        "Gate_Receipt_ID",
        "Object_Claim_ID",
        "Gate_ID",
        "Gate_Name",
        "Input_Source_IDs",
        "Test_Performed",
        "Expected",
        "Observed",
        "Result",
        "Unresolved_Limitations",
        "Tool_Parser",
        "Version",
        "Executed_At",
        "Executed_By",
        "Independent_Second_Pass",
        "Release_Effect",
    )

    def validate_mutation(self, intent: MutationIntent) -> None:
        self._require_key_bound_target(intent)
        self._enforce_integrity_manifest_only(intent)
        self._reject_ephemeral_identity_promotion(intent)
        self._enforce_revision_binding(intent)
        self._enforce_role_authority_boundary(intent)
        self._enforce_release_receipts(intent)
        self._enforce_receipt_schema(intent)
        if not intent.provider_readback_planned:
            raise TruthGridViolation("PROVIDER_READBACK_REQUIRED")

    def _require_key_bound_target(self, intent: MutationIntent) -> None:
        if intent.operation.upper() in {"UPDATE", "DELETE", "UPSERT", "PROMOTE"}:
            if not intent.target_key or not intent.row_identity_resolved_by_key:
                raise TruthGridViolation("KEY_BOUND_TARGET_REQUIRED")

    def _enforce_integrity_manifest_only(self, intent: MutationIntent) -> None:
        if intent.sheet == self.integrity_manifest_sheet:
            return
        forbidden = self.raw_integrity_fields.intersection(intent.values.keys())
        populated = [k for k in forbidden if intent.values.get(k) not in (None, "")]
        if populated:
            raise TruthGridViolation("RAW_INTEGRITY_OUTSIDE_MANIFEST:" + ",".join(sorted(populated)))

    def _reject_ephemeral_identity_promotion(self, intent: MutationIntent) -> None:
        for field_name in self.durable_identity_fields:
            value = intent.values.get(field_name)
            if value in (None, ""):
                continue
            text = str(value).upper()
            if any(marker.upper() in text for marker in self.ephemeral_identity_markers):
                raise TruthGridViolation("EPHEMERAL_GMAIL_HANDLE_CANNOT_BE_DURABLE_ID")
        for key, value in intent.values.items():
            if "ATTACHMENT_ID" in key.upper() and value not in (None, ""):
                classification = str(intent.values.get("Identity_Type", "")).upper()
                if classification not in {"EPHEMERAL_ACQUISITION_HANDLE", "CONNECTOR_RUNTIME_HANDLE"}:
                    raise TruthGridViolation("GMAIL_ATTACHMENT_ID_TYPE_REQUIRED")

    def _enforce_revision_binding(self, intent: MutationIntent) -> None:
        if intent.target_revision_id is None:
            return
        if intent.current_revision_id is None:
            raise TruthGridViolation("CURRENT_REVISION_READBACK_REQUIRED")
        if intent.current_revision_id != intent.target_revision_id:
            raise TruthGridViolation("STALE_REVISION_TARGET")

    def _enforce_role_authority_boundary(self, intent: MutationIntent) -> None:
        authority_promoted = any(
            str(intent.values.get(field_name, "")).upper()
            in {"VERIFIED", "APPOINTED", "DELEGATED", "AUTHORISED", "AUTHORIZED"}
            for field_name in self.role_authority_fields
        )
        if not authority_promoted:
            return
        source_classes = {s.upper() for s in intent.source_classifications}
        if not source_classes.intersection(
            {"APPOINTMENT_INSTRUMENT", "DELEGATION_INSTRUMENT", "AUTHORITY_INSTRUMENT", "PROVIDER_NATIVE_AUTHORITY_RECORD"}
        ):
            raise TruthGridViolation("ROLE_REPRESENTATION_IS_NOT_AUTHORITY")

    def _enforce_release_receipts(self, intent: MutationIntent) -> None:
        promoted = False
        for key, value in intent.values.items():
            key_upper = key.upper()
            value_upper = str(value).upper()
            if "RELEASE" in key_upper or "STATUS" in key_upper or "GATE" in key_upper:
                if any(word in value_upper for word in self.release_words):
                    promoted = True
                    break
        if promoted and not intent.receipt_ids:
            raise TruthGridViolation("RELEASE_PROMOTION_REQUIRES_RECEIPTS")

    def _enforce_receipt_schema(self, intent: MutationIntent) -> None:
        if intent.sheet != self.release_gate_sheet:
            return
        missing = [field_name for field_name in self.receipt_required_fields if field_name not in intent.values]
        if missing:
            raise TruthGridViolation("RELEASE_RECEIPT_SCHEMA_MISSING:" + ",".join(missing))
        if not intent.values.get("Gate_Receipt_ID"):
            raise TruthGridViolation("RELEASE_RECEIPT_KEY_REQUIRED")
        if str(intent.values.get("Independent_Second_Pass", "")).upper() not in {"YES", "TRUE", "PASS", "N/A"}:
            raise TruthGridViolation("INDEPENDENT_SECOND_PASS_REQUIRED")

    @staticmethod
    def mission_lock(parent: Mission, requested_mission_id: str) -> MissionLockDecision:
        if requested_mission_id == parent.mission_id:
            return MissionLockDecision.STAY_ON_FOUNDATION
        override = any(
            (parent.explicit_user_override, parent.external_deadline_override, parent.legal_preservation_override, parent.safety_override)
        )
        if override:
            return MissionLockDecision.OVERRIDE_ALLOWED
        if not parent.complete and parent.mandatory_open_dependencies:
            if requested_mission_id in parent.downstream_missions:
                return MissionLockDecision.STAY_ON_FOUNDATION
        return MissionLockDecision.ALLOW_DOWNSTREAM

    @staticmethod
    def assert_downstream_allowed(parent: Mission, requested_mission_id: str) -> None:
        decision = TruthGridGuard.mission_lock(parent, requested_mission_id)
        if decision == MissionLockDecision.STAY_ON_FOUNDATION and requested_mission_id != parent.mission_id:
            raise TruthGridViolation("FOUNDATION_COMPLETION_LOCK:" + parent.mission_id)

    @staticmethod
    def completion_gate(
        *,
        global_revalidation_closed: bool,
        p0_closed: bool,
        p1_closed: bool,
        p2_closed: bool,
        unresolved_gap_count: int,
        undispositioned_contradiction_count: int,
        genesis_parent_audits_passed: bool,
        writer_canaries_passed: bool,
        dashboard_generated_from_live_matrix: bool,
    ) -> bool:
        return all(
            (
                global_revalidation_closed,
                p0_closed,
                p1_closed,
                p2_closed,
                unresolved_gap_count == 0,
                undispositioned_contradiction_count == 0,
                genesis_parent_audits_passed,
                writer_canaries_passed,
                dashboard_generated_from_live_matrix,
            )
        )
