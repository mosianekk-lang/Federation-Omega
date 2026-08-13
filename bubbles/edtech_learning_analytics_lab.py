from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable, Mapping


FORBIDDEN_FIELDS = {
    "name", "email", "phone", "id_number", "passport", "address",
    "race", "ethnicity", "religion", "disability", "gender", "sex",
    "health", "political_affiliation", "union_membership",
}

FORBIDDEN_AUTOMATED_DECISIONS = {
    "GRADE", "FAIL", "PASS", "EXCLUDE", "SUSPEND", "DISCIPLINE",
    "ADMIT", "REJECT_ADMISSION", "PROGRESSION_BLOCK", "SCHOLARSHIP_DENY",
}

ALLOWED_SOURCE_SYSTEMS = {"LMS", "SIS_SUPPORT", "TUTORING", "SERVICE_DESK"}
ALLOWED_RECOMMENDATIONS = {"NO_ACTION", "SUPPORT_REVIEW", "TUTORING_REVIEW", "ACCESS_SUPPORT_REVIEW"}


@dataclass(frozen=True)
class LearnerSignal:
    learner_key: str
    source_system: str
    weekly_logins: int
    submission_ratio: float
    support_wait_hours: float
    attendance_ratio: float
    source_ref: str

    def validate(self) -> None:
        if not self.learner_key.startswith("SYN-"):
            raise ValueError("Only synthetic pseudonymous learner keys are permitted")
        if self.source_system not in ALLOWED_SOURCE_SYSTEMS:
            raise ValueError("Unsupported source system")
        if not self.source_ref.strip():
            raise ValueError("Source lineage is required")
        if self.weekly_logins < 0:
            raise ValueError("weekly_logins must be non-negative")
        for value, field in ((self.submission_ratio, "submission_ratio"), (self.attendance_ratio, "attendance_ratio")):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must be between 0 and 1")
        if self.support_wait_hours < 0:
            raise ValueError("support_wait_hours must be non-negative")


@dataclass(frozen=True)
class SupportRecommendation:
    learner_key: str
    recommendation: str
    reason_codes: tuple[str, ...]
    human_review_required: bool
    automated_academic_decision: str | None = None

    def validate(self) -> None:
        if self.recommendation not in ALLOWED_RECOMMENDATIONS:
            raise ValueError("Unsupported recommendation")
        if not self.human_review_required:
            raise ValueError("Every non-trivial learning-support recommendation requires human review")
        if self.automated_academic_decision in FORBIDDEN_AUTOMATED_DECISIONS:
            raise ValueError("High-consequence academic decisions may not be automated")


@dataclass(frozen=True)
class LearningAnalyticsReceipt:
    state: str
    record_count: int
    recommendation_count: int
    support_review_count: int
    mean_submission_ratio: float
    mean_attendance_ratio: float
    mean_support_wait_hours: float
    learner_keys_sha256: str
    receipt_sha256: str
    truth_boundary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def reject_sensitive_payload(payload: Mapping[str, object]) -> None:
    lowered = {str(key).casefold() for key in payload}
    hits = sorted(FORBIDDEN_FIELDS.intersection(lowered))
    if hits:
        raise ValueError(f"Sensitive/protected fields are forbidden in this synthetic lab: {hits}")


class EdTechLearningAnalyticsLab:
    """Privacy-safe synthetic learning analytics and support-routing reference.

    The lab demonstrates learning-support analytics, lineage, privacy controls and
    human oversight. It never automates grades, progression, admissions, discipline
    or other high-consequence academic decisions and never processes real student data.
    """

    state = "SYNTHETIC_LOCAL_DETERMINISTICALLY_TESTED"

    @staticmethod
    def _reason_codes(signal: LearnerSignal) -> tuple[str, ...]:
        reasons: list[str] = []
        if signal.submission_ratio < 0.75:
            reasons.append("LOW_SUBMISSION_ENGAGEMENT")
        if signal.attendance_ratio < 0.75:
            reasons.append("LOW_ATTENDANCE_ENGAGEMENT")
        if signal.weekly_logins < 2:
            reasons.append("LOW_PLATFORM_ENGAGEMENT")
        if signal.support_wait_hours > 24:
            reasons.append("SUPPORT_DELAY")
        return tuple(reasons)

    def recommend(self, signal: LearnerSignal) -> SupportRecommendation:
        signal.validate()
        reasons = self._reason_codes(signal)
        if "SUPPORT_DELAY" in reasons:
            recommendation = "ACCESS_SUPPORT_REVIEW"
        elif "LOW_SUBMISSION_ENGAGEMENT" in reasons and "LOW_ATTENDANCE_ENGAGEMENT" in reasons:
            recommendation = "TUTORING_REVIEW"
        elif reasons:
            recommendation = "SUPPORT_REVIEW"
        else:
            recommendation = "NO_ACTION"
        result = SupportRecommendation(
            learner_key=signal.learner_key,
            recommendation=recommendation,
            reason_codes=reasons,
            human_review_required=True,
            automated_academic_decision=None,
        )
        result.validate()
        return result

    def run(self, records: Iterable[LearnerSignal]) -> tuple[LearningAnalyticsReceipt, tuple[SupportRecommendation, ...]]:
        signals = tuple(records)
        if not signals:
            raise ValueError("At least one synthetic signal is required")
        for signal in signals:
            signal.validate()
        if len({signal.learner_key for signal in signals}) != len(signals):
            raise ValueError("Duplicate learner keys are not permitted in one run")

        recommendations = tuple(self.recommend(signal) for signal in signals)
        keys = sorted(signal.learner_key for signal in signals)
        keys_hash = hashlib.sha256("|".join(keys).encode("utf-8")).hexdigest()
        payload = {
            "state": self.state,
            "record_count": len(signals),
            "recommendation_count": len(recommendations),
            "support_review_count": sum(item.recommendation != "NO_ACTION" for item in recommendations),
            "mean_submission_ratio": round(sum(item.submission_ratio for item in signals) / len(signals), 4),
            "mean_attendance_ratio": round(sum(item.attendance_ratio for item in signals) / len(signals), 4),
            "mean_support_wait_hours": round(sum(item.support_wait_hours for item in signals) / len(signals), 2),
            "learner_keys_sha256": keys_hash,
            "truth_boundary": (
                "Synthetic, pseudonymous local proof only. Recommendations are support-review prompts requiring "
                "human review. No real learner data, protected attributes, automated academic decisions, provider "
                "deployment or measured learning-outcome improvement is claimed."
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        receipt = LearningAnalyticsReceipt(
            receipt_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            **payload,
        )
        return receipt, recommendations

    @staticmethod
    def recruiter_demo() -> dict[str, object]:
        lab = EdTechLearningAnalyticsLab()
        records = (
            LearnerSignal("SYN-001", "LMS", 5, 0.95, 2.0, 0.92, "synthetic:lms:week-1"),
            LearnerSignal("SYN-002", "LMS", 1, 0.55, 6.0, 0.58, "synthetic:lms:week-1"),
            LearnerSignal("SYN-003", "SERVICE_DESK", 3, 0.88, 31.0, 0.85, "synthetic:service:week-1"),
        )
        receipt, recommendations = lab.run(records)
        return {
            "receipt": receipt.to_dict(),
            "recommendations": [asdict(item) for item in recommendations],
            "safe_claim": (
                "Designed and deterministically tested a privacy-safe synthetic learning-analytics reference that "
                "combines engagement/support signals, lineage, data minimisation and human-reviewed support routing."
            ),
            "forbidden_claims": [
                "deployed a production learning analytics platform",
                "improved real student retention or grades",
                "automated academic progression or grading decisions",
                "processed real student data",
                "served as a university Director of Educational Technology",
            ],
        }
