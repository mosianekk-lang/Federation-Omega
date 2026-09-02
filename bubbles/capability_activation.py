from __future__ import annotations

"""Fresh-proof Bubbles capability activation reconciler.

This module does not create provider authority, credentials, a scheduler, a
second memory root, or a promotion court. It composes current Bubbles/Federation
proof into one fail-closed operational projection so stale historical success
cannot silently override fresher provider readback.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import argparse
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "BUBBLES-CAPABILITY-ACTIVATION-V1"
OPENAI_OBSERVATION_SCHEMA = "BUBBLES-OPENAI-PROVIDER-TRUST-OBSERVATION-1"
DEFAULT_OPENAI_OBSERVATION = Path("governance/bubbles_openai_provider_trust_observation_v1.json")
OPENAI_OBSERVATION_MAX_AGE_SECONDS = 604800


class ActivationState(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    HOSTED_VERIFIED = "HOSTED_VERIFIED"
    SOURCE_READY = "SOURCE_READY"
    SHADOW_VERIFIED = "SHADOW_VERIFIED"
    PROVIDER_GATED = "PROVIDER_GATED"
    AUTHORITY_GATED = "AUTHORITY_GATED"
    CREDENTIAL_GATED = "CREDENTIAL_GATED"
    DATA_GATED = "DATA_GATED"


@dataclass(frozen=True, slots=True)
class ActivationLane:
    lane_id: str
    state: ActivationState
    evidence_refs: tuple[str, ...]
    reason: str
    next_gate: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


def _load(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    source = Path(path)
    if not source.exists():
        return {}
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"EXPECTED_JSON_OBJECT:{source}")
    return raw


def _load_fresh_openai_trust(path: str | Path | None) -> dict[str, Any]:
    observation = _load(path)
    if not observation:
        return {}
    if observation.get("schema") != OPENAI_OBSERVATION_SCHEMA:
        return {}
    if observation.get("secret_value_recorded") is not False:
        return {}
    if observation.get("provider_mutation_attempted") is not False:
        return {}
    raw_observed = observation.get("observed_at")
    try:
        observed = datetime.fromisoformat(str(raw_observed).replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    except Exception:
        return {}
    max_age = int(observation.get("max_age_seconds") or OPENAI_OBSERVATION_MAX_AGE_SECONDS)
    if not (-300 <= age_seconds <= max_age):
        return {}
    trust = observation.get("provider_trust")
    if not isinstance(trust, Mapping):
        return {}
    if trust.get("provider") != "openai" or trust.get("secret_value_recorded") is not False:
        return {}
    payload = dict(trust)
    payload["observation_source_ref"] = observation.get("source_ref")
    payload["observation_age_seconds"] = age_seconds
    return payload


def _surface(receipt: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    surfaces = receipt.get("surfaces", {})
    if isinstance(surfaces, Mapping):
        value = surfaces.get(name, {})
        if isinstance(value, Mapping):
            return value
    return {}


def _http_200(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("http_status") == 200


def _http_semantic_ok(value: Any) -> bool:
    if not _http_200(value):
        return False
    if value.get("body_ok") is True:
        return True
    body = value.get("body")
    return isinstance(body, Mapping) and body.get("ok") is True


def _sha(payload: Mapping[str, Any]) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _resolve_openai_lane(trust: Mapping[str, Any]) -> tuple[ActivationState, tuple[str, ...], str, str | None]:
    base_refs = ["chatbridge-omega4:openai-provider", "caseforge:openai-provider-adapter"]
    receipt_sha = trust.get("receipt_sha256")
    if isinstance(receipt_sha, str) and receipt_sha:
        base_refs.append(f"provider-trust-receipt:{receipt_sha}")
    source_ref = trust.get("observation_source_ref")
    if isinstance(source_ref, str) and source_ref:
        base_refs.append(source_ref)

    reference_found = trust.get("credential_reference_found") is True
    runtime_bound = trust.get("runtime_bound") is True
    authenticated = trust.get("provider_authenticated") is True
    live = trust.get("provider_live_verified") is True
    state = str(trust.get("state") or "")
    error_code = str(trust.get("provider_error_code") or "")

    if live and authenticated and runtime_bound:
        return (
            ActivationState.HOSTED_VERIFIED,
            tuple(base_refs),
            "Fresh provider trust proves the existing OpenAI credential is runtime-bound, authenticated and provider-live.",
            None,
        )
    if authenticated and runtime_bound:
        if state == "BLOCKED_PROVIDER_BILLING" or error_code == "credit_balance_exhausted":
            return (
                ActivationState.PROVIDER_GATED,
                tuple(base_refs),
                "OpenAI credential reference, runtime binding and provider authentication are proven; live execution is blocked by provider billing/credit.",
                "RESTORE_PROVIDER_BILLING",
            )
        return (
            ActivationState.PROVIDER_GATED,
            tuple(base_refs),
            "OpenAI credential is runtime-bound and authenticated, but provider-live execution remains blocked by a provider-side condition.",
            str(trust.get("next_action") or "RESOLVE_PROVIDER_BLOCK_AND_RERUN_PROVIDER_LIVE_CANARY"),
        )
    if reference_found and runtime_bound:
        return (
            ActivationState.PROVIDER_GATED,
            tuple(base_refs),
            "OpenAI credential reference and runtime binding are proven, but provider authentication/live proof is absent.",
            "RESTORE_PROVIDER_AUTHENTICATION_AND_RERUN_PROVIDER_LIVE_CANARY",
        )
    if reference_found:
        return (
            ActivationState.CREDENTIAL_GATED,
            tuple(base_refs),
            "An OpenAI credential reference is known, but fresh runtime binding is not proven.",
            "BIND_EXISTING_CREDENTIAL_REFERENCE_AND_RUN_PROVIDER_LIVE_CANARY",
        )
    return (
        ActivationState.CREDENTIAL_GATED,
        tuple(base_refs),
        "OpenAI provider adapters exist; no fresh safe provider-trust receipt proves a credential reference or provider-live execution.",
        "FRESH_SAFE_PROVIDER_TRUST_RECEIPT_OR_SECURE_CREDENTIAL_BINDING",
    )


def build_activation_snapshot(
    *,
    source_sha: str,
    event_name: str,
    provider_surface_receipt: Mapping[str, Any] | None = None,
    provider_authority_receipt: Mapping[str, Any] | None = None,
    openai_provider_trust_receipt: Mapping[str, Any] | None = None,
    schedule_configured: bool = True,
    schedule_provider_verified: bool = False,
) -> dict[str, Any]:
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha.lower()):
        raise ValueError("SOURCE_SHA_REQUIRED")

    surface = dict(provider_surface_receipt or {})
    authority = dict(provider_authority_receipt or {})
    openai_trust = dict(openai_provider_trust_receipt or {})
    operator = _surface(surface, "federation_omega_operator")
    archon = _surface(surface, "archon_admin_plane_v5")
    apps = _surface(surface, "archon_apps_script_exact_deployment") or _surface(
        surface, "archon_apps_script_translator"
    )

    surface_operator_public_ok = (
        _http_200(operator.get("public_health"))
        and _http_200(operator.get("public_contract"))
    )
    surface_operator_authenticated = operator.get("classification") == "AUTHENTICATED_READBACK_VERIFIED"
    surface_operator_token = operator.get("trusted_token_available") is True
    surface_archon_authenticated = archon.get("classification") == "AUTHENTICATED_READBACK_VERIFIED"
    surface_archon_token = archon.get("trusted_token_available") is True

    authority_authenticated = authority.get("provider_authenticated") is True
    authority_classification = str(authority.get("classification") or "")
    current_authority_failed = authority_classification in {
        "TRUSTED_PROVIDER_AUTHORITY_STILL_BLOCKED",
        "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
    } or (
        isinstance(authority.get("access_token_test"), Mapping)
        and authority["access_token_test"].get("ok") is False
    )

    authority_operator_public_ok = (
        _http_200(authority.get("operator_public_health"))
        and _http_200(authority.get("operator_public_contract"))
    )
    authority_operator_authenticated = (
        authority.get("fo_token_available") is True
        and _http_semantic_ok(authority.get("operator_authenticated_status"))
        and _http_semantic_ok(authority.get("operator_architron_read"))
    )
    authority_archon_authenticated = (
        authority.get("archon_token_available") is True
        and authority.get("archon_authenticated_readback") is True
    )
    authority_cloud_read_ok = (
        authority_authenticated
        and _http_semantic_ok(authority.get("operator_architron_read"))
        and not current_authority_failed
    )

    operator_public_ok = surface_operator_public_ok or authority_operator_public_ok
    operator_authenticated = surface_operator_authenticated or authority_operator_authenticated
    operator_token = surface_operator_token or authority.get("fo_token_available") is True
    archon_authenticated = surface_archon_authenticated or authority_archon_authenticated
    archon_token = surface_archon_token or authority.get("archon_token_available") is True
    cloud_read_ok = operator_public_ok or authority_cloud_read_ok
    openai_state, openai_evidence, openai_reason, openai_gate = _resolve_openai_lane(openai_trust)

    if event_name == "schedule":
        scheduled_state = ActivationState.OPERATIONAL
        scheduled_reason = "This Bubbles/Federation closure executed from a provider-hosted schedule event."
        scheduled_gate = None
        scheduled_evidence = ("workflow:superior-logic-maturation-shadow", "current-event:schedule")
    elif schedule_provider_verified:
        scheduled_state = ActivationState.OPERATIONAL
        scheduled_reason = "The bound provider-hosted scheduler has independent successful natural schedule-event readback."
        scheduled_gate = None
        scheduled_evidence = (
            "workflow:superior-logic-maturation-shadow",
            "github-actions:schedule:provider-verified",
        )
    elif schedule_configured:
        scheduled_state = ActivationState.SOURCE_READY
        scheduled_reason = "Provider-hosted schedule is configured; natural schedule-event readback is not supplied to this projection."
        scheduled_gate = "NATURAL_SCHEDULE_EVENT_READBACK"
        scheduled_evidence = ("workflow:superior-logic-maturation-shadow",)
    else:
        scheduled_state = ActivationState.PROVIDER_GATED
        scheduled_reason = "No admitted provider-hosted schedule is bound."
        scheduled_gate = "BIND_EXISTING_ADMITTED_SCHEDULER"
        scheduled_evidence = ("workflow:superior-logic-maturation-shadow",)

    if operator_authenticated and operator_token and authority_authenticated and not current_authority_failed:
        cloud_write_state = ActivationState.HOSTED_VERIFIED
        cloud_write_reason = "Fresh authenticated operator/provider authority is present; mutation remains action-specific and unproven."
        cloud_write_gate = "ACTION_SPECIFIC_MUTATION_PLUS_TARGET_READBACK"
    else:
        cloud_write_state = ActivationState.AUTHORITY_GATED
        cloud_write_reason = (
            "Cloud operator is reachable, but current trusted token/WIF authority is not fresh-verified."
            if operator_public_ok
            else "Cloud operator reachability/authority is not fresh-verified."
        )
        cloud_write_gate = "RESTORE_TRUSTED_OPERATOR_TOKEN_OR_VALID_WIF_AND_READ_BACK_TARGET"

    apps_classification = str(apps.get("overall_classification") or apps.get("classification") or "")
    apps_reachable = bool(apps) and "UNVERIFIED" not in apps_classification
    apps_state = ActivationState.HOSTED_VERIFIED if apps_reachable else ActivationState.PROVIDER_GATED
    apps_gate = "ACTION_SEMANTIC_AUTHORITY_AND_MUTATION_READBACK" if apps_reachable else "FRESH_DEPLOYMENT_SEMANTIC_READBACK"

    lanes = (
        ActivationLane(
            "CORE_ORCHESTRATION",
            ActivationState.OPERATIONAL,
            (f"source:{source_sha}", "workflow:bubbles-command-bus", "workflow:phoenix-freeze"),
            "Current Bubbles orchestration/control spine is source-admitted and provider-hosted.",
        ),
        ActivationLane(
            "COMMAND_BUS",
            ActivationState.OPERATIONAL,
            (f"source:{source_sha}", "bubbles-command-bus:contract"),
            "Hosted command validation and bounded internal execution are active.",
        ),
        ActivationLane(
            "FAILURE_RECOVERY",
            ActivationState.OPERATIONAL,
            ("bubbles:recover_chat_failure", "failure-win-v2", "formation-aaa"),
            "Failure isolation/reroute and local recovery receipts are bound.",
        ),
        ActivationLane(
            "DURABLE_CONTINUITY",
            ActivationState.HOSTED_VERIFIED,
            ("workflow:bco-provider-readback-continuity", "durable-mission-runtime-v1"),
            "Restart-safe mission/readback continuity is hosted and independently witnessed.",
        ),
        ActivationLane(
            "SCHEDULED_MISSIONS",
            scheduled_state,
            scheduled_evidence,
            scheduled_reason,
            scheduled_gate,
        ),
        ActivationLane(
            "CONDITION_MONITORING",
            ActivationState.HOSTED_VERIFIED if schedule_configured else ActivationState.PROVIDER_GATED,
            ("provider-edge-watch-v1", "provider-surface-readback"),
            "Periodic no-effect readback can detect provider/authority edges without freezing safe work."
            if schedule_configured
            else "No admitted periodic monitor is bound.",
            None if schedule_configured else "BIND_EXISTING_ADMITTED_SCHEDULER",
        ),
        ActivationLane(
            "SANDBOXED_CODE_EXECUTION",
            ActivationState.HOSTED_VERIFIED,
            ("github-actions:ubuntu-24.04", "phoenix:source-clean-export"),
            "Bounded disposable GitHub Actions code/test execution is live; this is not a universal sandbox pool.",
            "UNIVERSAL_PROVIDER_SANDBOX_POOL_REMAINS_SEPARATE",
        ),
        ActivationLane(
            "GOOGLE_CLOUD_READ",
            ActivationState.HOSTED_VERIFIED if cloud_read_ok else ActivationState.PROVIDER_GATED,
            ("bubbles-provider-surface-readback", "provider-authority-recovery"),
            "Fresh semantic Cloud operator/provider readback is verified."
            if cloud_read_ok
            else "Fresh Cloud operator readback is absent.",
            None if cloud_read_ok else "FRESH_OPERATOR_HEALTH_AND_CONTRACT_READBACK",
        ),
        ActivationLane(
            "GOOGLE_CLOUD_EFFECTS",
            cloud_write_state,
            ("federation-omega-operator", "provider-authority-recovery"),
            cloud_write_reason,
            cloud_write_gate,
        ),
        ActivationLane(
            "APPS_SCRIPT_READBACK",
            apps_state,
            ("archon-apps-script-deployment-probe",),
            "Current deployment route is reachable but action semantics remain separately gated."
            if apps_reachable
            else "Current Apps Script deployment semantics are not fresh-verified.",
            apps_gate,
        ),
        ActivationLane(
            "APPS_SCRIPT_EFFECTS",
            ActivationState.AUTHORITY_GATED,
            ("apps-script-authorization-gate",),
            "Apps Script mutation requires exact human OAuth/API-executable authority and provider readback.",
            "RESTORE_ACTION_SPECIFIC_APPS_SCRIPT_OAUTH_AUTHORITY",
        ),
        ActivationLane(
            "ARCHON_ADMIN",
            ActivationState.HOSTED_VERIFIED if archon_authenticated and archon_token else ActivationState.CREDENTIAL_GATED,
            ("archon-admin-plane-v5", "provider-authority-recovery"),
            "Fresh authenticated ARCHON admin readback is available."
            if archon_authenticated and archon_token
            else "ARCHON public OpenAPI is reachable but trusted admin-token binding is absent.",
            None if archon_authenticated and archon_token else "BIND_TRUSTED_ARCHON_ADMIN_TOKEN_OR_EQUIVALENT_AUTHORITY",
        ),
        ActivationLane(
            "GOOGLE_AI_STUDIO",
            ActivationState.PROVIDER_GATED,
            ("adapter:google_ai_studio", "provider-edge-watch:google_ai_studio_provider"),
            "Provider adapter/control plane exists; fresh provider inventory and execution readback remain required.",
            "FRESH_AI_STUDIO_PROVIDER_CANARY_AND_READBACK",
        ),
        ActivationLane(
            "OPENAI_PROVIDER_LIVE",
            openai_state,
            openai_evidence,
            openai_reason,
            openai_gate,
        ),
        ActivationLane(
            "BROWSER_COMPUTER_AUTOMATION",
            ActivationState.PROVIDER_GATED,
            ("bubbles-digital-twin:AP24-AP25",),
            "No current Bubbles-owned browser/computer provider executor is proven in this runtime.",
            "BIND_PROVIDER_BROWSER_OR_COMPUTER_RUNTIME_WITH_IDENTITY_POLICY_AND_READBACK",
        ),
        ActivationLane(
            "AUTOSCALING_WARM_POOLS",
            ActivationState.PROVIDER_GATED,
            ("bubbles-digital-twin:HP21-HP23",),
            "Autoscaling/warm/sandbox pools remain provider-hosting concerns, not source-only claims.",
            "PROVIDER_HOSTED_CAPACITY_CANARY_AND_READBACK",
        ),
        ActivationLane(
            "PREDICTIVE_ANTICIPATORY_INTELLIGENCE",
            ActivationState.SHADOW_VERIFIED,
            ("edpf-shadow-host", "living-state-transition-lineage", "bco-prime-v4"),
            "Prospective shadow forecasting and resolution are live; stable superiority/weighting remains data-gated.",
            "LARGER_PROSPECTIVE_COHORT_PLUS_CALIBRATION_VALUE_COURT",
        ),
        ActivationLane(
            "SELF_LEARNING_CALIBRATION",
            ActivationState.DATA_GATED,
            ("edpf-predictor-projection", "cfbe-champion-challenger"),
            "Learning/calibration logic is bound but cannot promote from a small cohort or source presence.",
            "MEASURED_MULTI_OUTCOME_COHORT_AND_NO_REGRESSION_PROMOTION",
        ),
        ActivationLane(
            "EMPIRICAL_OWNER_VALUE",
            ActivationState.DATA_GATED,
            ("owner-value-deployment-court-v2", "sentinel-owner-value-ingress"),
            "Owner-value promotion requires measured matched real missions; it cannot be synthesized by CI.",
            "MINIMUM_10_COURT_VERIFIED_OWNER_VALUE_PAIRS",
        ),
        ActivationLane(
            "FULL_GOVERNED_DIGITAL_TWIN",
            ActivationState.DATA_GATED,
            ("bubbles-digital-twin-convergence-v1",),
            "DT4/DT5 require provider authority, privacy-scoped private-state ingestion and sustained outcome/value proof.",
            "CLOSE_PROVIDER_PRIVACY_AND_EMPIRICAL_VALUE_GATES",
        ),
    )

    counts = {state.value: 0 for state in ActivationState}
    for lane in lanes:
        counts[lane.state.value] += 1
    green_states = {ActivationState.OPERATIONAL, ActivationState.HOSTED_VERIFIED, ActivationState.SHADOW_VERIFIED}
    green = sum(1 for lane in lanes if lane.state in green_states)
    residual = [lane.lane_id for lane in lanes if lane.state not in green_states]

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "event_name": event_name,
        "lane_count": len(lanes),
        "green_count": green,
        "all_green": not residual,
        "residual_gates": residual,
        "state_counts": counts,
        "lanes": [lane.to_dict() for lane in lanes],
        "freshness_rules": {
            "current_provider_readback_overrides_historical_provider_success": True,
            "provider_hosted_scheduler_proof_can_be_reused_when_same_workflow_identity_is_preserved": True,
            "source_presence_does_not_prove_provider_effect": True,
            "credential_absence_does_not_cancel_unaffected_work": True,
            "fresh_safe_openai_provider_trust_overrides_credential_guess": True,
            "stale_openai_provider_trust_does_not_promote": True,
            "shadow_prediction_does_not_prove_superiority": True,
            "owner_value_is_never_inferred": True,
        },
        "schedule_proof": {
            "configured": schedule_configured,
            "current_event_is_schedule": event_name == "schedule",
            "provider_verified_prior_schedule": schedule_provider_verified,
        },
        "provider_authority_conflict": {
            "historical_provider_success_may_exist": True,
            "current_authority_failed": current_authority_failed,
            "current_provider_authenticated": authority_authenticated,
            "current_classification": authority_classification or None,
        },
        "openai_provider_trust": {
            "receipt_supplied": bool(openai_trust),
            "credential_reference_found": openai_trust.get("credential_reference_found") is True,
            "runtime_bound": openai_trust.get("runtime_bound") is True,
            "provider_authenticated": openai_trust.get("provider_authenticated") is True,
            "provider_live_verified": openai_trust.get("provider_live_verified") is True,
            "provider_error_code": openai_trust.get("provider_error_code"),
            "state": openai_trust.get("state"),
            "secret_value_recorded": openai_trust.get("secret_value_recorded") if openai_trust else None,
        },
    }
    payload["activation_sha256"] = _sha(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a fresh Bubbles capability activation snapshot")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--provider-surface-receipt")
    parser.add_argument("--provider-authority-receipt")
    parser.add_argument("--openai-provider-trust-receipt")
    parser.add_argument("--schedule-configured", action="store_true")
    parser.add_argument("--schedule-provider-verified", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    openai_trust = (
        _load(args.openai_provider_trust_receipt)
        if args.openai_provider_trust_receipt
        else _load_fresh_openai_trust(DEFAULT_OPENAI_OBSERVATION)
    )
    snapshot = build_activation_snapshot(
        source_sha=args.source_sha.lower(),
        event_name=args.event_name,
        provider_surface_receipt=_load(args.provider_surface_receipt),
        provider_authority_receipt=_load(args.provider_authority_receipt),
        openai_provider_trust_receipt=openai_trust,
        schedule_configured=args.schedule_configured,
        schedule_provider_verified=args.schedule_provider_verified,
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": snapshot["schema"],
        "green_count": snapshot["green_count"],
        "lane_count": snapshot["lane_count"],
        "all_green": snapshot["all_green"],
        "residual_gates": snapshot["residual_gates"],
        "activation_sha256": snapshot["activation_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
