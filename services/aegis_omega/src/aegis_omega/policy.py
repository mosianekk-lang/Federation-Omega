from dataclasses import dataclass
from .schemas import Assessment

@dataclass(frozen=True)
class ResponsePlan:
    automated: tuple[str, ...]
    approval_required: tuple[str, ...]


def plan_response(assessment: Assessment) -> ResponsePlan:
    automated = ("preserve_case_metadata", "request_additional_defensive_telemetry")
    if assessment.disposition == "containment_recommended":
        approval = ("isolate_enterprise_access", "revoke_enterprise_sessions", "begin_forensic_acquisition")
    elif assessment.disposition == "investigate":
        approval = ("begin_forensic_acquisition",)
    else:
        approval = ()
    return ResponsePlan(automated=automated, approval_required=approval)
