from __future__ import annotations

from bubbles.platform_specialist_corps import (
    AuthorityClass,
    PlatformSpecialistCorps,
    PlatformSpecialistRole,
    build_default_corps,
)


PROVIDER_SURFACE_ROLES: dict[str, PlatformSpecialistRole] = {
    "Federation Omega Operator": PlatformSpecialistRole(
        role_id="BUB-PLAT-FO-OPERATOR",
        platform="Federation Omega Operator",
        mission=(
            "Operate the dedicated Federation Omega Cloud Run operator as the narrow, proof-bound provider bridge for "
            "status, action-specific Cloud Run readback and separately gated reversible deployment actions."
        ),
        native_ai_interfaces=("Federation provider/operator routing",),
        capability_domains=("cloud", "operator", "runtime", "deployment", "readback", "automation"),
        read_actions=("public health", "public contract", "authenticated STATUS", "authenticated READ_CLOUD_RUN_SERVICE"),
        write_actions=("DEPLOY_SOLUTION5_LOCKED only after exact provider/owner gates",),
        proof_actions=("operator response receipt", "target provider readback", "rollback receipt when mutation is authorised"),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
        consequential_actions=("deployment", "IAM/secret effects", "traffic promotion"),
    ),
    "ARCHON Admin Plane V5": PlatformSpecialistRole(
        role_id="BUB-PLAT-ARCHON-ADMIN",
        platform="ARCHON Admin Plane V5",
        mission=(
            "Operate the dedicated ARCHON Cloud Run administrative surface for current capability audit, provider inventory "
            "and owner-gated cloud administration without treating historic audit results as current proof."
        ),
        native_ai_interfaces=("ARCHON administrative command intelligence",),
        capability_domains=("cloud", "admin", "runtime", "services", "builds", "scheduler", "secrets_metadata", "storage", "automation"),
        read_actions=("public endpoint/OpenAPI", "capability_audit", "provider inventory"),
        write_actions=("owner-confirmed administrative command only after current authentication and rollback proof",),
        proof_actions=("endpoint/OpenAPI readback", "capability_audit semantic result", "exact provider target readback"),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
        consequential_actions=("cloud mutation", "IAM/secret mutation", "traffic change"),
    ),
    "ARCHON Apps Script Translator": PlatformSpecialistRole(
        role_id="BUB-PLAT-ARCHON-SCRIPT",
        platform="ARCHON Apps Script Translator",
        mission=(
            "Operate the deployed ARCHON Federation Surface Translator script/web-app as a Workspace translation and "
            "automation surface with explicit deployment identity and semantic readback."
        ),
        native_ai_interfaces=("Gemini-assisted scripting when separately provider-exposed",),
        capability_domains=("apps_script", "web_app", "workspace", "translator", "automation", "integration"),
        read_actions=("Drive script metadata", "deployed web-app read probe", "deployment identity when human OAuth is available"),
        write_actions=("source/deployment/trigger/property mutation only through human OAuth/provider-authorised route",),
        proof_actions=("web-app semantic response", "script/deployment identity", "source/version readback"),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
        consequential_actions=("source deployment", "trigger mutation", "ScriptProperties mutation"),
        forbidden_assumptions=(
            "subscription implies provider authority",
            "connector existence implies OAuth scope",
            "HTTP success implies semantic success",
            "stored registry text implies live provider execution",
            "AI consensus implies truth",
            "sharing a script to a service account enables the Apps Script API for that service account",
        ),
    ),
    "AFEME v4": PlatformSpecialistRole(
        role_id="BUB-PLAT-AFEME-V4",
        platform="AFEME v4",
        mission=(
            "Operate AFEME v4 as a protected sovereign AI/control-plane runtime only after current identity, endpoint semantics "
            "and provider-native model/action readback are proven."
        ),
        native_ai_interfaces=("AFEME v4 sovereign AI runtime",),
        capability_domains=("ai", "runtime", "control_plane", "federation", "model", "automation"),
        read_actions=("IAM-protected endpoint probe", "runtime/model metadata when callable"),
        write_actions=("bounded provider experiment only after exact action authority",),
        proof_actions=("identity-token acceptance", "semantic endpoint result", "model/action/config receipt"),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
        consequential_actions=("provider/model mutation", "external effects"),
    ),
}


def build_provider_extended_corps() -> PlatformSpecialistCorps:
    base = build_default_corps()
    collisions = set(base.roles).intersection(PROVIDER_SURFACE_ROLES)
    if collisions:
        raise ValueError(f"Provider specialist platform collision: {sorted(collisions)}")
    return PlatformSpecialistCorps({**base.roles, **PROVIDER_SURFACE_ROLES})
