from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Sequence


class SurfaceState(str, Enum):
    VERIFIED_OPERATIONAL = "VERIFIED_OPERATIONAL"
    CONNECTED_READ_WRITE = "CONNECTED_READ_WRITE"
    CONNECTED_READ_ONLY = "CONNECTED_READ_ONLY"
    CONTROL_PLANE_ONLY = "CONTROL_PLANE_ONLY"
    INSTALLABLE_NOT_CONNECTED = "INSTALLABLE_NOT_CONNECTED"
    OWNER_CONSENT_REQUIRED = "OWNER_CONSENT_REQUIRED"
    PROVIDER_BLOCKED = "PROVIDER_BLOCKED"
    NOT_EXPOSED = "NOT_EXPOSED"


class AuthorityClass(str, Enum):
    A0_READ = "A0_READ"
    A1_INTERNAL = "A1_INTERNAL"
    PROVIDER_ACTION = "PROVIDER_ACTION"
    OWNER_RESERVED = "OWNER_RESERVED"


@dataclass(frozen=True)
class PlatformSpecialistRole:
    role_id: str
    platform: str
    mission: str
    native_ai_interfaces: tuple[str, ...]
    capability_domains: tuple[str, ...]
    read_actions: tuple[str, ...]
    write_actions: tuple[str, ...]
    proof_actions: tuple[str, ...]
    authority_ceiling: AuthorityClass = AuthorityClass.A1_INTERNAL
    consequential_actions: tuple[str, ...] = ()
    forbidden_assumptions: tuple[str, ...] = (
        "subscription implies provider authority",
        "connector existence implies OAuth scope",
        "HTTP success implies semantic success",
        "stored registry text implies live provider execution",
        "AI consensus implies truth",
    )

    def validate(self) -> "PlatformSpecialistRole":
        if not self.role_id or not self.platform or not self.mission:
            raise ValueError("role identity, platform and mission are required")
        if not self.read_actions and not self.write_actions:
            raise ValueError("role must expose at least one usable action class")
        if not self.proof_actions:
            raise ValueError("role requires independent proof/readback actions")
        return self


@dataclass(frozen=True)
class PlatformCapabilitySnapshot:
    platform: str
    state: SurfaceState
    connector_connected: bool
    provider_identity_verified: bool
    read_verified: bool
    write_verified: bool
    semantic_readback_verified: bool
    native_ai_callable: bool
    native_ai_readback_verified: bool
    owner_consent_required: bool = False
    known_gaps: tuple[str, ...] = ()

    def maximum_safe_mode(self) -> str:
        if self.owner_consent_required:
            return "OWNER_CONSENT_REQUIRED"
        if self.state == SurfaceState.VERIFIED_OPERATIONAL and self.write_verified and self.semantic_readback_verified:
            return "BIDIRECTIONAL_VERIFIED"
        if self.connector_connected and self.read_verified and self.write_verified:
            return "BIDIRECTIONAL_UNREADBACK"
        if self.connector_connected and self.read_verified:
            return "READ_ONLY"
        if self.state == SurfaceState.CONTROL_PLANE_ONLY:
            return "CONTROL_PLANE_ONLY"
        return self.state.value


@dataclass(frozen=True)
class CapabilityRequest:
    objective: str
    required_domains: frozenset[str]
    consequential: bool = False
    native_ai_preferred: bool = False


@dataclass(frozen=True)
class SpecialistRouteDecision:
    platform: str
    role_id: str
    selected: bool
    mode: str
    missing_domains: tuple[str, ...]
    ao_cra_builds: tuple[str, ...]
    owner_gate: bool
    reason: str


@dataclass
class PlatformSpecialistCorps:
    roles: Mapping[str, PlatformSpecialistRole]

    def __post_init__(self) -> None:
        validated = {name: role.validate() for name, role in self.roles.items()}
        object.__setattr__(self, "roles", validated)

    def route(
        self,
        request: CapabilityRequest,
        snapshots: Mapping[str, PlatformCapabilitySnapshot],
    ) -> tuple[SpecialistRouteDecision, ...]:
        decisions: list[SpecialistRouteDecision] = []
        for platform, role in self.roles.items():
            snapshot = snapshots.get(platform)
            domains = frozenset(role.capability_domains)
            missing = sorted(request.required_domains - domains)
            if missing:
                continue
            if snapshot is None:
                decisions.append(
                    SpecialistRouteDecision(
                        platform=platform,
                        role_id=role.role_id,
                        selected=False,
                        mode="UNVERIFIED",
                        missing_domains=(),
                        ao_cra_builds=(f"AO-CRA:PLATFORM:{platform}:CAPABILITY_SNAPSHOT",),
                        owner_gate=False,
                        reason="CURRENT_PLATFORM_READBACK_REQUIRED",
                    )
                )
                continue
            owner_gate = request.consequential or snapshot.owner_consent_required
            mode = snapshot.maximum_safe_mode()
            ai_gap = request.native_ai_preferred and not (
                snapshot.native_ai_callable and snapshot.native_ai_readback_verified
            )
            ao_cra: list[str] = []
            if ai_gap:
                ao_cra.append(f"AO-CRA:PLATFORM:{platform}:NATIVE_AI_BRIDGE")
            if mode in {"READ_ONLY", "CONTROL_PLANE_ONLY", "BIDIRECTIONAL_UNREADBACK"}:
                ao_cra.append(f"AO-CRA:PLATFORM:{platform}:FULL_BIDIRECTIONAL_PROOF")
            selected = mode in {"BIDIRECTIONAL_VERIFIED", "BIDIRECTIONAL_UNREADBACK", "READ_ONLY", "CONTROL_PLANE_ONLY"}
            if owner_gate and request.consequential:
                selected = False
            decisions.append(
                SpecialistRouteDecision(
                    platform=platform,
                    role_id=role.role_id,
                    selected=selected,
                    mode=mode,
                    missing_domains=(),
                    ao_cra_builds=tuple(ao_cra),
                    owner_gate=owner_gate,
                    reason=(
                        "OWNER_GATE_REQUIRED"
                        if request.consequential
                        else "MINIMUM_SUFFICIENT_VERIFIED_PLATFORM_ROUTE"
                    ),
                )
            )
        return tuple(decisions)


CORE_PLATFORM_ROLES: dict[str, PlatformSpecialistRole] = {
    "ChatGPT": PlatformSpecialistRole(
        "BUB-PLAT-CHATGPT",
        "ChatGPT",
        "Orchestrate the Federation through the strongest available ChatGPT reasoning, tools, Work/Tasks and connected-app surfaces without inventing hidden memory or provider authority.",
        ("GPT-5.6 Sol", "ChatGPT Tasks", "connected apps"),
        ("reasoning", "orchestration", "automation", "artifact", "cross_surface"),
        ("read conversation context", "read connected-source results", "inspect task state"),
        ("invoke connected tools", "create/update tasks", "produce governed artifacts"),
        ("tool result readback", "task readback", "provider connector receipts"),
    ),
    "Gmail": PlatformSpecialistRole(
        "BUB-PLAT-GMAIL", "Gmail", "Operate Gmail as a provenance-aware communications and evidence surface.",
        ("Gemini for Workspace when provider-exposed",),
        ("email", "evidence", "communications", "search", "automation"),
        ("search mail", "read threads", "read attachments/labels"),
        ("draft/send/label/archive when authorised",),
        ("message/thread ID readback", "label/state readback"),
        consequential_actions=("send external email", "delete mail"),
    ),
    "Google Drive": PlatformSpecialistRole(
        "BUB-PLAT-DRIVE", "Google Drive", "Operate Drive/Docs/Sheets/Slides as the durable Kim Dataverse corpus and transaction ledger.",
        ("Gemini for Workspace when provider-exposed",),
        ("files", "documents", "spreadsheets", "slides", "evidence", "automation", "storage"),
        ("search/read files", "read revisions", "read metadata/comments"),
        ("create/update/move files", "bounded Docs/Sheets/Slides writes"),
        ("exact content readback", "revision/metadata readback", "parent/permission readback"),
    ),
    "Google Calendar": PlatformSpecialistRole(
        "BUB-PLAT-GCAL", "Google Calendar", "Manage time, availability and event workflows with explicit attendee/change controls.",
        ("Gemini for Workspace when provider-exposed",),
        ("calendar", "scheduling", "availability", "automation"),
        ("search events", "read event details", "free/busy"),
        ("create/update/delete/respond when authorised",),
        ("event ID/state readback", "free/busy verification"),
        consequential_actions=("invite attendees", "delete external event"),
    ),
    "Google Contacts": PlatformSpecialistRole(
        "BUB-PLAT-GCONTACTS", "Google Contacts", "Resolve people and organisation identities for connected workflows without broadening recipient scope.",
        ("Gemini for Workspace when provider-exposed",),
        ("contacts", "identity_resolution", "communications"),
        ("find contacts", "read contact details"),
        ("write only when provider action is exposed and required",),
        ("contact identity readback",),
    ),
    "Canva": PlatformSpecialistRole(
        "BUB-PLAT-CANVA", "Canva", "Operate Canva as the governed visual-design and creative-production surface, including Canva AI where exposed.",
        ("Canva AI/Magic Studio", "Canva design generation"),
        ("design", "visual", "presentation", "creative_ai", "export", "automation"),
        ("search/read designs", "inspect pages/content/assets"),
        ("generate/edit/copy/resize designs", "manage assets/folders"),
        ("provider design/content readback", "preview/commit receipts", "export receipt when exposed"),
        consequential_actions=("public publish",),
    ),
    "Adobe": PlatformSpecialistRole(
        "BUB-PLAT-ADOBE", "Adobe", "Operate Adobe Creative Cloud/Acrobat actions for governed document and creative transformation.",
        ("Adobe Firefly/Acrobat AI where exposed",),
        ("pdf", "creative", "document", "image", "automation"),
        ("read supported Adobe assets/documents",),
        ("invoke exposed Acrobat/Creative Cloud transformations",),
        ("result asset/document readback",),
    ),
    "GitHub": PlatformSpecialistRole(
        "BUB-PLAT-GITHUB", "GitHub", "Operate GitHub as the Federation engineering, CI, provenance and release-control plane.",
        ("GitHub Copilot when provider-exposed", "GitHub Actions"),
        ("code", "ci", "issues", "pull_requests", "automation", "provenance", "runtime"),
        ("read repos/code/issues/PRs/actions",),
        ("branch/commit/file/issue/PR mutations within exposed scope",),
        ("commit SHA", "CI/Airlock/Leak Guard", "post-merge main readback"),
        consequential_actions=("merge consequential change", "repository settings mutation"),
    ),
    "OpenAI Platform": PlatformSpecialistRole(
        "BUB-PLAT-OPENAI", "OpenAI Platform", "Manage OpenAI provider configuration and model-execution bridges only to the extent provider-native actions are actually exposed.",
        ("OpenAI API", "Responses API", "OpenAI models"),
        ("ai", "model", "api", "provider", "automation"),
        ("read provider/setup state where exposed",),
        ("secure key setup/creation where authorised",),
        ("provider-native model/response/config readback when callable",),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
        consequential_actions=("create/revoke credentials", "paid model execution"),
    ),
    "Outlook Email": PlatformSpecialistRole(
        "BUB-PLAT-OUTLOOK-MAIL", "Outlook Email", "Operate Microsoft Outlook mail through exposed Graph actions with the same provenance and external-send gates as Gmail.",
        ("Microsoft Copilot when provider-exposed",),
        ("email", "communications", "search", "automation"),
        ("search/read messages",),
        ("mail mutations only within exposed Graph scope",),
        ("message/state readback",),
        consequential_actions=("send external email", "delete mail"),
    ),
    "Outlook Calendar": PlatformSpecialistRole(
        "BUB-PLAT-OUTLOOK-CAL", "Outlook Calendar", "Operate Microsoft calendar/free-busy and event workflows through exposed Graph actions.",
        ("Microsoft Copilot when provider-exposed",),
        ("calendar", "scheduling", "availability", "automation"),
        ("search/read events", "read availability"),
        ("event mutation only when connected action and consent are verified",),
        ("event/readback proof",),
        consequential_actions=("invite attendees", "delete external event"),
    ),
    "Booking.com": PlatformSpecialistRole(
        "BUB-PLAT-BOOKING", "Booking.com", "Use Booking.com as a current travel-discovery surface and persist only selected provenance-bound outputs into KDV.",
        ("Booking.com recommendation/search systems",),
        ("travel", "accommodation", "attractions", "cars", "discovery"),
        ("search stays/attractions/cars", "read property Q&A"),
        (),
        ("provider result/reference readback",),
    ),
    "Google Apps Script": PlatformSpecialistRole(
        "BUB-PLAT-GAS", "Google Apps Script", "Operate FO-GAS/Apps Script as a Workspace automation control plane only when source/runtime authority is proven.",
        ("Gemini-assisted scripting where provider-exposed",),
        ("automation", "workspace", "triggers", "integration", "runtime"),
        ("read control-plane state", "inspect healthy FO-GAS bridge"),
        ("source/trigger/deployment mutation only after provider authority proof",),
        ("source hash", "trigger/runtime receipt", "semantic action readback", "rollback"),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
    ),
    "Google Cloud": PlatformSpecialistRole(
        "BUB-PLAT-GCP", "Google Cloud", "Operate Cloud Run, Secret Manager, IAM/WIF, storage, queues and observability through least-privilege provider-native routes when available.",
        ("Gemini for Google Cloud when provider-exposed",),
        ("cloud", "runtime", "secrets", "iam", "storage", "queues", "observability", "automation"),
        ("provider metadata/readback when route exists",),
        ("bounded reversible cloud mutation only under exact authority",),
        ("project/identity/service/revision/config/rollback readback",),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
        consequential_actions=("IAM mutation", "secret mutation", "traffic promotion"),
    ),
    "Google AI Studio": PlatformSpecialistRole(
        "BUB-PLAT-AISTUDIO", "Google AI Studio", "Use Google AI Studio/Gemini as an experimental model-diversity surface, never as canonical truth.",
        ("Gemini", "Google AI Studio"),
        ("ai", "model", "experimentation", "evaluation", "multimodal"),
        ("inventory/readback when provider connector exists",),
        ("public/synthetic no-effect experiments when authorised",),
        ("provider model/run/config readback",),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
    ),
    "Microsoft Teams": PlatformSpecialistRole(
        "BUB-PLAT-TEAMS", "Microsoft Teams", "Operate Teams collaboration and channel workflows once the connector is installed and live actions are verified.",
        ("Microsoft Copilot when provider-exposed",),
        ("chat", "collaboration", "meetings", "files", "automation"),
        ("read channels/messages when connected",),
        ("post/manage collaboration only when connected and authorised",),
        ("message/channel/action readback",),
    ),
    "Microsoft SharePoint": PlatformSpecialistRole(
        "BUB-PLAT-SHAREPOINT", "Microsoft SharePoint", "Operate SharePoint as a governed Microsoft content/workspace surface once connector authority is verified.",
        ("Microsoft Copilot when provider-exposed",),
        ("files", "sites", "lists", "knowledge", "automation"),
        ("read sites/files/lists when connected",),
        ("write/update when connected and authorised",),
        ("site/item/version readback",),
    ),
    "Microsoft Dataverse": PlatformSpecialistRole(
        "BUB-PLAT-MS-DATAVERSE", "Microsoft Dataverse", "Own the future provider-native Microsoft Dataverse control surface and keep the logical Kim Dataverse distinct from it until direct authority exists.",
        ("Microsoft Copilot/Power Platform AI when provider-exposed",),
        ("database", "crm", "power_platform", "automation", "structured_data"),
        ("provider inventory when connector exists",),
        ("record/schema/workflow mutation only after provider authority",),
        ("record/schema/action readback",),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
    ),
    "Power Automate": PlatformSpecialistRole(
        "BUB-PLAT-POWER-AUTOMATE", "Power Automate", "Own the future Microsoft workflow-automation surface and integrate flows with Federation proof/readback gates.",
        ("Microsoft Copilot/Power Automate AI when provider-exposed",),
        ("automation", "flows", "power_platform", "integration"),
        ("inventory/read flow definitions when connector exists",),
        ("create/update/run flows only after provider authority",),
        ("run history", "flow state", "connector/action readback"),
        authority_ceiling=AuthorityClass.PROVIDER_ACTION,
    ),
}


def build_default_corps() -> PlatformSpecialistCorps:
    return PlatformSpecialistCorps(CORE_PLATFORM_ROLES)
