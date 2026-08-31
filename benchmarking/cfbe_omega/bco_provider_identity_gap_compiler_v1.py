from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping, Sequence

_SCHEMA = "BCO-PROVIDER-IDENTITY-GAP-REPORT-V1"
_EXPECTED_PFRD_SCHEMA = "SOVARA-OPERATOR-AUTH-RECOVERY-V3"
_EXPECTED_WIF_RECEIPT = "FEDOMEGA-WIF-CLOUD-VERIFIED"
_EXPECTED_ADC_FAILURE_RECEIPT = "FEDOMEGA-GEMINI-ADC-VERIFICATION-FAILED"
_CANONICAL_PROVIDER_WORKFLOW = (
    "mosianekk-lang/Federation-Omega/.github/workflows/"
    "sovara-litellm-v2-3-provider-admission.yml@refs/heads/main"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


class RouteState(str, Enum):
    PROVEN = "PROVEN"
    AVAILABLE_UNPROVEN = "AVAILABLE_UNPROVEN"
    HISTORICALLY_PROVEN_FRESHNESS_OPEN = "HISTORICALLY_PROVEN_FRESHNESS_OPEN"
    BLOCKED = "BLOCKED"
    HOLD = "HOLD"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class GapFinding:
    gap_id: str
    state: str
    reason: str
    proof_refs: tuple[str, ...] = ()
    missing_controls: tuple[str, ...] = ()
    authority_required_to_change: bool = False


@dataclass(frozen=True, slots=True)
class RouteAssessment:
    route_id: str
    state: RouteState
    blockers: tuple[str, ...]
    proof_refs: tuple[str, ...]
    requesting_workflows: tuple[str, ...] = ()
    eligible_workflows: tuple[str, ...] = ()
    ineligible_workflows: tuple[str, ...] = ()
    provider_effect_authorized: bool = False


@dataclass(frozen=True, slots=True)
class ProviderIdentityGapReport:
    schema: str
    state: str
    historical_wif_verified: bool
    current_wif_freshness: str
    canonical_wif_workflow_ref: str
    requesting_workflow_eligibility: tuple[tuple[str, bool], ...]
    direct_operator_token_present: bool
    google_machine_authenticated: bool
    runtime_adc_verified: bool
    action_specific_authenticated_read_proven: bool
    routes: tuple[RouteAssessment, ...]
    gaps: tuple[GapFinding, ...]
    next_safe_proof_actions: tuple[str, ...]
    evidence_digest: str
    provider_effect_authorized: bool = False
    financial_effect_authorized: bool = False
    publication_authorized: bool = False
    truth_boundary: tuple[str, ...] = (
        "historical_identity_proof_is_not_current_freshness_proof",
        "a_wif_provider_can_be_verified_while_a_requesting_workflow_is_ineligible",
        "credential_presence_is_not_authenticated_semantic_readback",
        "google_machine_identity_is_separate_from_operator_application_token_authority",
        "runtime_adc_readiness_is_separate_from_canonical_wif_identity",
        "this_report_is_read_only_and_grants_no_credentials_iam_or_provider_effect_authority",
    )

    def canonical_mapping(self) -> dict[str, Any]:
        return asdict(self)


def _validate_no_effect_receipt(
    receipt: Mapping[str, Any],
    *,
    mutation_field: str,
    secret_field: str,
    label: str,
) -> None:
    if receipt.get(mutation_field) is True:
        raise ValueError(f"BCO_IDENTITY_RECEIPT_MUTATION_BOUNDARY:{label}")
    if receipt.get(secret_field) is True:
        raise ValueError(f"BCO_IDENTITY_RECEIPT_SECRET_BOUNDARY:{label}")


def _historical_wif_verified(receipt: Mapping[str, Any]) -> bool:
    _validate_no_effect_receipt(
        receipt,
        mutation_field="mutation_performed",
        secret_field="secret_payload_accessed",
        label="historical_wif",
    )
    return (
        receipt.get("receipt") == _EXPECTED_WIF_RECEIPT
        and receipt.get("state") == "VERIFIED"
        and receipt.get("provider_state") == "ACTIVE"
        and bool(receipt.get("active_account"))
        and bool(receipt.get("project"))
        and bool(receipt.get("project_number_observed"))
    )


def _current_wif_freshness(receipt: Mapping[str, Any]) -> str:
    scope = str(receipt.get("execution_scope") or "")
    if scope != "G0_READ_ONLY_VERIFY":
        return "CURRENT_HEAD_NOT_REFRESHED"
    if receipt.get("wif_verified") is True:
        return "CURRENT_HEAD_VERIFIED"
    return "CURRENT_HEAD_NOT_VERIFIED"


def _workflow_condition(provider_readback: Mapping[str, Any]) -> str:
    condition = str(provider_readback.get("attributeCondition") or "")
    if not condition:
        raise ValueError("BCO_WIF_PROVIDER_ATTRIBUTE_CONDITION_REQUIRED")
    return condition


def _workflow_eligible(condition: str, workflow_ref: str) -> bool:
    workflow = str(workflow_ref).strip()
    if not workflow:
        return False
    exact_patterns = (
        f"assertion.job_workflow_ref=='{workflow}'",
        f'assertion.job_workflow_ref=="{workflow}"',
        f"assertion.workflow=='{workflow}'",
        f'assertion.workflow=="{workflow}"',
    )
    return any(item in condition for item in exact_patterns)


def _current_pfrd_state(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != _EXPECTED_PFRD_SCHEMA:
        raise ValueError("BCO_PFRD_RECEIPT_SCHEMA_MISMATCH")
    _validate_no_effect_receipt(
        receipt,
        mutation_field="mutation_attempted",
        secret_field="secret_values_recorded",
        label="pfrd",
    )
    aliases = receipt.get("credential_alias_presence")
    if not isinstance(aliases, Mapping):
        raise ValueError("BCO_PFRD_CREDENTIAL_ALIAS_STATE_REQUIRED")
    machine = receipt.get("google_machine_auth")
    operator = receipt.get("operator")
    secret_manager = receipt.get("secret_manager")
    if not all(isinstance(item, Mapping) for item in (machine, operator, secret_manager)):
        raise ValueError("BCO_PFRD_IDENTITY_SECTIONS_REQUIRED")
    static_aliases = (
        "GCP_SA_KEY",
        "GCP_SERVICE_ACCOUNT_KEY",
        "GOOGLE_CREDENTIALS",
        "GOOGLE_SERVICE_ACCOUNT_KEY",
        "GCP_CREDENTIALS",
        "GOOGLE_GHA_CREDS_JSON",
        "GOOGLE_CLOUD_CREDENTIALS",
    )
    return {
        "direct_operator_token": bool(aliases.get("FO_ADMIN_TOKEN") or operator.get("token_present")),
        "gemini_key": bool(aliases.get("GEMINI_API_KEY")),
        "static_google_credential": any(bool(aliases.get(item)) for item in static_aliases),
        "configured_wif_pair": bool(
            aliases.get("GCP_WIF_PAIR_CONFIGURED_NOT_USED")
            or aliases.get("GENERIC_WIF_PAIR_CONFIGURED_NOT_USED")
        ),
        "google_machine_authenticated": bool(machine.get("authenticated")),
        "google_machine_route": str(machine.get("source_alias") or ""),
        "operator_classification": str(operator.get("classification") or ""),
        "operator_token_source": str(operator.get("token_source") or "none"),
        "secret_manager_operator_accessible": bool(
            isinstance(secret_manager.get("operator_token"), Mapping)
            and secret_manager["operator_token"].get("accessible") is True
        ),
        "overall_classification": str(receipt.get("overall_classification") or ""),
    }


def _adc_state(receipt: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    _validate_no_effect_receipt(
        receipt,
        mutation_field="mutation_performed",
        secret_field="secret_payload_accessed",
        label="adc",
    )
    verified = receipt.get("state") == "VERIFIED"
    missing = _clean(receipt.get("missing_controls") or ())
    if not verified and receipt.get("receipt") not in {_EXPECTED_ADC_FAILURE_RECEIPT, None}:
        raise ValueError("BCO_ADC_RECEIPT_STATE_UNRECOGNIZED")
    return verified, missing


def _readback_level(receipt: Mapping[str, Any] | None) -> str:
    if not receipt:
        return "UNVERIFIED"
    level = str(receipt.get("observed_level") or receipt.get("level") or "UNVERIFIED").strip().upper()
    allowed = {
        "UNVERIFIED",
        "PUBLIC_REACHABILITY",
        "AUTHENTICATED_SURFACE_READ",
        "ACTION_SPECIFIC_AUTHENTICATED_READ",
    }
    if level not in allowed:
        raise ValueError("BCO_PROVIDER_READBACK_LEVEL_INVALID")
    return level


def compile_provider_identity_gap_graph(
    *,
    historical_wif_receipt: Mapping[str, Any],
    historical_wif_provider_readback: Mapping[str, Any],
    historical_adc_receipt: Mapping[str, Any],
    current_provider_workflow_receipt: Mapping[str, Any],
    current_pfrd_receipt: Mapping[str, Any],
    requesting_workflow_refs: Sequence[str],
    current_bco_readback_receipt: Mapping[str, Any] | None = None,
    proof_refs: Mapping[str, str] | None = None,
) -> ProviderIdentityGapReport:
    refs = {str(k): str(v).strip() for k, v in dict(proof_refs or {}).items() if str(v).strip()}
    wif_history = _historical_wif_verified(historical_wif_receipt)
    freshness = _current_wif_freshness(current_provider_workflow_receipt)
    condition = _workflow_condition(historical_wif_provider_readback)
    pfrd = _current_pfrd_state(current_pfrd_receipt)
    adc_verified, adc_missing = _adc_state(historical_adc_receipt)
    readback_level = _readback_level(current_bco_readback_receipt)
    action_read = readback_level == "ACTION_SPECIFIC_AUTHENTICATED_READ"

    workflows = _clean(requesting_workflow_refs)
    eligibility = tuple((item, _workflow_eligible(condition, item)) for item in workflows)
    eligible = tuple(item for item, allowed in eligibility if allowed)
    ineligible = tuple(item for item, allowed in eligibility if not allowed)

    gaps: list[GapFinding] = []
    routes: list[RouteAssessment] = []

    if pfrd["direct_operator_token"]:
        direct_state = RouteState.AVAILABLE_UNPROVEN if not action_read else RouteState.PROVEN
        direct_blockers: tuple[str, ...] = () if action_read else ("ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN",)
    else:
        direct_state = RouteState.BLOCKED
        direct_blockers = ("DIRECT_OPERATOR_TOKEN_UNAVAILABLE",)
        gaps.append(
            GapFinding(
                "DIRECT_OPERATOR_TOKEN_UNAVAILABLE",
                "OPEN",
                "Fresh PFRD evidence contains no FO_ADMIN_TOKEN and no recovered operator token.",
                proof_refs=_clean((refs.get("pfrd", ""),)),
                authority_required_to_change=True,
            )
        )
    routes.append(
        RouteAssessment(
            "DIRECT_OPERATOR_TOKEN",
            direct_state,
            direct_blockers,
            _clean((refs.get("pfrd", ""), refs.get("bco_readback", ""))),
        )
    )

    if pfrd["google_machine_authenticated"]:
        machine_state = RouteState.PROVEN
        machine_blockers: tuple[str, ...] = ()
    elif pfrd["static_google_credential"]:
        machine_state = RouteState.AVAILABLE_UNPROVEN
        machine_blockers = ("GOOGLE_MACHINE_AUTH_NOT_PROVEN",)
    else:
        machine_state = RouteState.BLOCKED
        machine_blockers = ("STATIC_GOOGLE_MACHINE_CREDENTIAL_UNAVAILABLE",)
        gaps.append(
            GapFinding(
                "STATIC_GOOGLE_MACHINE_CREDENTIAL_UNAVAILABLE",
                "OPEN",
                "Fresh PFRD evidence contains no admitted static Google credential alias and no authenticated machine identity.",
                proof_refs=_clean((refs.get("pfrd", ""),)),
                authority_required_to_change=True,
            )
        )
    routes.append(
        RouteAssessment(
            "STATIC_GOOGLE_MACHINE_AUTH",
            machine_state,
            machine_blockers,
            _clean((refs.get("pfrd", ""),)),
        )
    )

    if wif_history:
        if freshness == "CURRENT_HEAD_VERIFIED":
            canonical_state = RouteState.PROVEN
            canonical_blockers: tuple[str, ...] = ()
        else:
            canonical_state = RouteState.HISTORICALLY_PROVEN_FRESHNESS_OPEN
            canonical_blockers = ("CANONICAL_WIF_FRESHNESS_UNPROVEN",)
            gaps.append(
                GapFinding(
                    "CANONICAL_WIF_FRESHNESS_UNPROVEN",
                    "OPEN",
                    "Canonical WIF has provider-native historical proof, but the current-head provider workflow did not refresh WIF identity proof.",
                    proof_refs=_clean((refs.get("historical_wif", ""), refs.get("current_provider", ""))),
                )
            )
    else:
        canonical_state = RouteState.BLOCKED
        canonical_blockers = ("CANONICAL_WIF_NOT_PROVEN",)
        gaps.append(
            GapFinding(
                "CANONICAL_WIF_NOT_PROVEN",
                "OPEN",
                "No valid historical canonical WIF proof was supplied.",
                proof_refs=_clean((refs.get("historical_wif", ""),)),
            )
        )

    if ineligible:
        canonical_blockers = tuple(dict.fromkeys((*canonical_blockers, "REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION")))
        gaps.append(
            GapFinding(
                "REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION",
                "OPEN",
                "The verified WIF provider condition is workflow-identity scoped; one or more requesting workflows are not admitted by that condition.",
                proof_refs=_clean((refs.get("wif_provider", ""),)),
                missing_controls=ineligible,
                authority_required_to_change=True,
            )
        )
    routes.append(
        RouteAssessment(
            "CANONICAL_WIF",
            canonical_state,
            canonical_blockers,
            _clean((refs.get("historical_wif", ""), refs.get("wif_provider", ""), refs.get("current_provider", ""))),
            requesting_workflows=workflows,
            eligible_workflows=eligible,
            ineligible_workflows=ineligible,
        )
    )

    if pfrd["secret_manager_operator_accessible"]:
        secret_state = RouteState.AVAILABLE_UNPROVEN if not action_read else RouteState.PROVEN
        secret_blockers = () if action_read else ("ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN",)
    elif not pfrd["google_machine_authenticated"]:
        secret_state = RouteState.BLOCKED
        secret_blockers = ("SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN", "GOOGLE_MACHINE_AUTH_NOT_PROVEN")
        gaps.append(
            GapFinding(
                "SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN",
                "OPEN",
                "Secret Manager operator-token recovery was not proven because the fresh PFRD lane had no Google machine authentication.",
                proof_refs=_clean((refs.get("pfrd", ""),)),
            )
        )
    else:
        secret_state = RouteState.HOLD
        secret_blockers = ("SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN",)
        gaps.append(
            GapFinding(
                "SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN",
                "OPEN",
                "Google machine authentication exists, but fresh operator-token recovery from Secret Manager is not proven.",
                proof_refs=_clean((refs.get("pfrd", ""),)),
            )
        )
    routes.append(
        RouteAssessment(
            "SECRET_MANAGER_OPERATOR_TOKEN_RECOVERY",
            secret_state,
            secret_blockers,
            _clean((refs.get("pfrd", ""),)),
        )
    )

    if adc_verified:
        adc_state = RouteState.PROVEN
        adc_blockers: tuple[str, ...] = ()
    else:
        adc_state = RouteState.BLOCKED
        adc_blockers = ("RUNTIME_GOOGLE_ADC_UNVERIFIED", *adc_missing)
        gaps.append(
            GapFinding(
                "RUNTIME_GOOGLE_ADC_UNVERIFIED",
                "OPEN",
                "The direct ADC verification receipt is NOT_VERIFIED; runtime ADC must not be inferred from canonical WIF proof.",
                proof_refs=_clean((refs.get("historical_adc", ""),)),
                missing_controls=adc_missing,
                authority_required_to_change=bool(adc_missing),
            )
        )
    routes.append(
        RouteAssessment(
            "GEMINI_RUNTIME_ADC",
            adc_state,
            adc_blockers,
            _clean((refs.get("historical_adc", ""),)),
        )
    )

    if action_read:
        read_state = RouteState.PROVEN
        read_blockers: tuple[str, ...] = ()
    else:
        read_state = RouteState.HOLD
        read_blockers = ("ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN",)
        gaps.append(
            GapFinding(
                "ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN",
                "OPEN",
                f"Current BCΩ provider evidence is {readback_level}; the required action-specific authenticated read floor is not proven.",
                proof_refs=_clean((refs.get("bco_readback", ""),)),
            )
        )
    routes.append(
        RouteAssessment(
            "ACTION_SPECIFIC_AUTHENTICATED_READBACK",
            read_state,
            read_blockers,
            _clean((refs.get("bco_readback", ""), refs.get("pfrd", ""))),
        )
    )

    next_actions: list[str] = []
    if freshness != "CURRENT_HEAD_VERIFIED" and wif_history:
        next_actions.append("REFRESH_CANONICAL_WIF_VIA_ALREADY_ADMITTED_READ_ONLY_PROVIDER_WORKFLOW")
    if ineligible:
        next_actions.append("KEEP_BCO_AND_BUBBLES_OFF_CANONICAL_WIF_UNLESS_PROVIDER_CONDITION_IS_EXPLICITLY_AUTHORIZED_TO_CHANGE")
    if not pfrd["direct_operator_token"]:
        next_actions.append("TREAT_DIRECT_OPERATOR_TOKEN_BINDING_AS_AUTHORITY_GATED_NOT_AUTOFIX")
    if not adc_verified:
        next_actions.append("KEEP_GEMINI_RUNTIME_ADC_SEPARATE_AND_HELD_UNTIL_MISSING_IAM_CONTROLS_ARE_PROVIDER_PROVEN")
    if not action_read:
        next_actions.append("REQUIRE_FRESH_ACTION_SPECIFIC_AUTHENTICATED_READBACK_BEFORE_PROVIDER_READ_PROMOTION")

    evidence_payload = {
        "historical_wif": historical_wif_receipt,
        "wif_provider": historical_wif_provider_readback,
        "historical_adc": historical_adc_receipt,
        "current_provider": current_provider_workflow_receipt,
        "current_pfrd": current_pfrd_receipt,
        "current_bco_readback": current_bco_readback_receipt or {},
        "requesting_workflows": workflows,
    }
    gaps_sorted = tuple(sorted(gaps, key=lambda item: item.gap_id))
    state = "PROVIDER_IDENTITY_AND_READBACK_READY" if not gaps_sorted else "HOLD_PROVIDER_IDENTITY_GAPS"
    return ProviderIdentityGapReport(
        schema=_SCHEMA,
        state=state,
        historical_wif_verified=wif_history,
        current_wif_freshness=freshness,
        canonical_wif_workflow_ref=_CANONICAL_PROVIDER_WORKFLOW,
        requesting_workflow_eligibility=eligibility,
        direct_operator_token_present=bool(pfrd["direct_operator_token"]),
        google_machine_authenticated=bool(pfrd["google_machine_authenticated"]),
        runtime_adc_verified=adc_verified,
        action_specific_authenticated_read_proven=action_read,
        routes=tuple(routes),
        gaps=gaps_sorted,
        next_safe_proof_actions=tuple(next_actions),
        evidence_digest=_digest(evidence_payload),
    )


def report_json(report: ProviderIdentityGapReport) -> str:
    return json.dumps(report.canonical_mapping(), indent=2, sort_keys=True) + "\n"
