from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .recipient_acceptance import RecipientAcceptanceAssessment, RecipientAcceptanceDecision

class LaunchRoute(str, Enum):
    SELF_SERVICE_INTEGRITY = "SELF_SERVICE_INTEGRITY"
    SELF_SERVICE_VERIFIED_ORIGINAL = "SELF_SERVICE_VERIFIED_ORIGINAL"
    RECIPIENT_ACCEPTED_ASSURANCE = "RECIPIENT_ACCEPTED_ASSURANCE"
    ASSISTED_CERTIFICATION_DISPATCH = "ASSISTED_CERTIFICATION_DISPATCH"
    ASSISTED_AFFIDAVIT_DISPATCH = "ASSISTED_AFFIDAVIT_DISPATCH"
    REQUIREMENT_RESOLUTION = "REQUIREMENT_RESOLUTION"

@dataclass(frozen=True)
class LaunchDecision:
    route: LaunchRoute
    public_label: str
    launchable_without_idv_contract: bool
    commissioner_required: bool
    physical_presence_default: bool
    citizen_experience: str
    platform_action: str
    hard_truth_boundary: tuple[str, ...]

class LaunchNowEngine:
    """Launch eCertify without making statutory or identity claims that require unbound providers.

    The product remains useful immediately for technical document-integrity assurance and
    recipient-approved digital assurance. Where South African law or a recipient requires
    formal certification/commissioning, the platform owns the orchestration burden and
    dispatches an independently verified commissioner instead of asking the citizen to find one.
    """
    def route(
        self,
        requested_status: str,
        *,
        issuer_or_source_verified: bool = False,
        recipient_acceptance: RecipientAcceptanceAssessment | None = None,
    ) -> LaunchDecision:
        req = requested_status.strip().lower().replace("-", "_").replace(" ", "_")

        if recipient_acceptance is not None and recipient_acceptance.decision == RecipientAcceptanceDecision.VERIFIED:
            return LaunchDecision(
                LaunchRoute.RECIPIENT_ACCEPTED_ASSURANCE,
                "INSTITUTION_ACCEPTED_DIGITAL_ASSURANCE",
                True,
                False,
                False,
                "Upload once; EvidenceOps prepares and verifies the accepted digital assurance package.",
                "Issue the exact recipient-approved assurance object and verification receipt.",
                ("RECIPIENT_ACCEPTANCE_EVIDENCE_REQUIRED", "NO_STATUTORY_CERTIFICATION_LABEL_CREATED"),
            )

        if req in {"digital_original", "electronic_original", "original"}:
            if issuer_or_source_verified:
                return LaunchDecision(
                    LaunchRoute.SELF_SERVICE_VERIFIED_ORIGINAL,
                    "VERIFIED_DIGITAL_ORIGINAL",
                    True,
                    False,
                    False,
                    "Upload the digital original and receive a verification receipt.",
                    "Bind issuer/source proof, document fingerprint and verification record.",
                    ("ISSUER_OR_SOURCE_PROOF_MUST_BE_CONCRETE",),
                )
            return LaunchDecision(
                LaunchRoute.SELF_SERVICE_INTEGRITY,
                "EVIDENCEOPS_DOCUMENT_INTEGRITY_RECEIPT",
                True,
                False,
                False,
                "Upload the document and receive an integrity/provenance receipt immediately.",
                "Hash, timestamp and record document integrity without claiming issuer or statutory certification.",
                ("NOT_A_CERTIFIED_COPY", "NOT_ISSUER_VERIFIED", "NO_GOVERNMENT_AFFILIATION"),
            )

        if req in {"copy", "document_copy", "scan"}:
            return LaunchDecision(
                LaunchRoute.SELF_SERVICE_INTEGRITY,
                "EVIDENCEOPS_COPY_INTEGRITY_ASSURANCE",
                True,
                False,
                False,
                "Upload the copy; EvidenceOps creates a tamper-evident copy assurance receipt.",
                "Record copy integrity/provenance and route to stronger verification only when the recipient requires it.",
                ("TECHNICAL_ASSURANCE_IS_NOT_STATUTORY_CERTIFICATION",),
            )

        if req in {"certified", "certified_copy"}:
            return LaunchDecision(
                LaunchRoute.ASSISTED_CERTIFICATION_DISPATCH,
                "CERTIFICATION_PENDING_COMMISSIONER_EVENT",
                True,
                True,
                False,
                "Upload the document and choose where the commissioner should meet you; the platform finds and assigns the commissioner.",
                "Auto-match an authority-verified commissioner, schedule the physical original inspection, capture the legal event and release the certified label only after proof.",
                ("CITIZEN_DOES_NOT_SELF_CERTIFY", "COMMISSIONER_AUTHORITY_AND_ORIGINAL_INSPECTION_REQUIRED"),
            )

        if req in {"affidavit", "sworn_statement", "declaration"}:
            return LaunchDecision(
                LaunchRoute.ASSISTED_AFFIDAVIT_DISPATCH,
                "COMMISSIONING_PENDING_COMMISSIONER_EVENT",
                True,
                True,
                True,
                "Prepare the affidavit digitally; the platform assigns a commissioner and arranges the required in-person commissioning event.",
                "Generate the declaration pack, dispatch an authority-verified commissioner, capture presence/signature/conflict evidence and release only after the event passes.",
                ("PHYSICAL_PRESENCE_DEFAULT", "NO_ROUTINE_REMOTE_COMMISSIONING_CLAIM", "COMMISSIONER_ACT_FEE_RULES_APPLY"),
            )

        return LaunchDecision(
            LaunchRoute.REQUIREMENT_RESOLUTION,
            "REQUIREMENT_NOT_YET_CLASSIFIED",
            True,
            False,
            False,
            "Tell EvidenceOps where the document is going; the platform determines the minimum acceptable route.",
            "Resolve the recipient requirement and choose the lowest lawful assurance lane.",
            ("DO_NOT_UPSELL_CERTIFICATION_WHEN_NOT_REQUIRED",),
        )
