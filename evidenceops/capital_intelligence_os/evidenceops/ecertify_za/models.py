from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

class AssuranceLane(str, Enum):
    DIGITAL_ORIGINAL="LANE_1_VERIFIED_DIGITAL_ORIGINAL"
    SOURCE_MATCHED_COPY="LANE_2_SOURCE_MATCHED_COPY"
    CERTIFIED_COPY="LANE_3_FORMALLY_CERTIFIED_COPY"
    AFFIDAVIT="LANE_4_AFFIDAVIT_DECLARATION"
    INSTITUTION_ACCEPTED="LANE_5_INSTITUTION_ACCEPTED_DIGITAL_ASSURANCE"
    REQUIREMENT_VERIFICATION="REQUIREMENT_VERIFICATION"

@dataclass(frozen=True)
class CertificationRoute:
    lane: AssuranceLane
    final_label: str
    commissioner_required: bool
    physical_presence_default: bool
    identity_requirement: str
    rationale: tuple[str,...]

@dataclass(frozen=True)
class VerificationRecord:
    verification_code:str
    document_sha256:str
    identity_evidence_digest:str
    lane:AssuranceLane
    legal_label:str
    status:str
    metadata:Mapping[str,str]=field(default_factory=dict)
