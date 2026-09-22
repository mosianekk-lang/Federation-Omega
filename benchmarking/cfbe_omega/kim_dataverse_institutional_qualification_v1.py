from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Sequence

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import AutonomyDebt, assess_levels
from benchmarking.cfbe_omega.kim_dataverse_persistent_carrier_contract_v1 import CarrierQualification


@dataclass(frozen=True)
class InstitutionalEvidence:
    autonomy_debt: AutonomyDebt
    owner_interruption_rate: float | None
    maintenance_self_resolution_rate: float | None
    recovery_self_resolution_rate: float | None
    observed_maintenance_episodes: int
    observed_recovery_episodes: int
    observed_no_chat_resumes: int
    observed_owner_value_pairs: int
    provider_native_receipts: tuple[str, ...]
    rollback_verified: bool
    regression_passed: bool
    sustained_value_verified: bool


@dataclass(frozen=True)
class InstitutionalQualification:
    highest_qualified_level: int
    assessments: tuple[Mapping[str, object], ...]
    empirical_holds: tuple[str, ...]
    level7_operational_claim: bool
    level8_operational_claim: bool
    receipt: str


def qualify_institution(
    *,
    source_signals: Mapping[str, bool],
    evidence: InstitutionalEvidence,
    carrier: CarrierQualification | None,
    minimum_owner_value_pairs: int = 30,
    minimum_maintenance_episodes: int = 10,
    minimum_recovery_episodes: int = 10,
    minimum_no_chat_resumes: int = 3,
) -> InstitutionalQualification:
    if evidence.owner_interruption_rate is not None and not 0.0 <= evidence.owner_interruption_rate <= 1.0:
        raise ValueError("owner_interruption_rate must be within [0,1]")
    for rate in (evidence.maintenance_self_resolution_rate, evidence.recovery_self_resolution_rate):
        if rate is not None and not 0.0 <= rate <= 1.0:
            raise ValueError("self-resolution rates must be within [0,1]")

    signals = dict(source_signals)
    signals["persistent_no_chat_continuity"] = bool(
        carrier
        and carrier.level7_continuity_candidate
        and evidence.observed_no_chat_resumes >= minimum_no_chat_resumes
    )
    signals["irreducible_owner_interruptions_only"] = bool(
        evidence.owner_interruption_rate is not None and evidence.owner_interruption_rate <= 0.05
    )
    signals["verified_value_retention"] = bool(
        evidence.observed_owner_value_pairs >= minimum_owner_value_pairs and evidence.sustained_value_verified
    )
    signals["lane_local_failure_isolation"] = bool(
        evidence.observed_maintenance_episodes >= minimum_maintenance_episodes
        and evidence.observed_recovery_episodes >= minimum_recovery_episodes
    )

    levels = assess_levels(signals)
    highest = max((level.level for level in levels if level.qualified), default=4)
    holds: list[str] = []
    if not signals["persistent_no_chat_continuity"]:
        holds.append("PERSISTENT_NO_CHAT_CONTINUITY_UNPROVEN")
    if evidence.observed_maintenance_episodes < minimum_maintenance_episodes:
        holds.append("MAINTENANCE_COHORT_INSUFFICIENT")
    if evidence.observed_recovery_episodes < minimum_recovery_episodes:
        holds.append("RECOVERY_COHORT_INSUFFICIENT")
    if evidence.observed_owner_value_pairs < minimum_owner_value_pairs or not evidence.sustained_value_verified:
        holds.append("SUSTAINED_OWNER_VALUE_UNPROVEN")
    if not evidence.rollback_verified:
        holds.append("ROLLBACK_UNVERIFIED")
    if not evidence.regression_passed:
        holds.append("REGRESSION_UNVERIFIED")

    level7_claim = highest >= 7 and not holds
    level8_claim = highest >= 8 and not holds and bool(evidence.provider_native_receipts)
    assessment_payload = tuple(
        {
            "level": level.level,
            "name": level.name,
            "qualified": level.qualified,
            "missing": level.missing,
        }
        for level in levels
    )
    payload = {
        "highest_qualified_level": highest,
        "assessments": assessment_payload,
        "empirical_holds": sorted(holds),
        "level7_operational_claim": level7_claim,
        "level8_operational_claim": level8_claim,
        "autonomy_debt_score": evidence.autonomy_debt.score,
        "external_effect": False,
        "authority_inherited": False,
    }
    receipt = "sha256:" + sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=list).encode("utf-8")
    ).hexdigest()
    return InstitutionalQualification(
        highest_qualified_level=highest,
        assessments=assessment_payload,
        empirical_holds=tuple(sorted(holds)),
        level7_operational_claim=level7_claim,
        level8_operational_claim=level8_claim,
        receipt=receipt,
    )
