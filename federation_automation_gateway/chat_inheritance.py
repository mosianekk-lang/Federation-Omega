from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

SHARED_FABRIC_ID = "17WRSvjj98RbOKZrnTefcZkfK-z9gZYdZX_pACm8VuOQ"
PROFILE_SCHEMA = "FED-AUTOMATION-CHAT-INHERITANCE-V1"

ENGINE_ALLOWLIST = frozenset(
    {
        "SUPERIOR_LOGIC",
        "SOVARA",
        "REALITYGUARD",
        "FAILURE_WIN_AUTOFIX",
        "SENTINEL",
        "CFBE",
        "FORMATION_ARCHON",
        "KIOAS",
        "EVIDENCEOPS_CIOS",
        "AIU",
    }
)

# A chat may expose a more specific runtime label while still inheriting the
# canonical engine's authority ceiling. Only explicit delimiters are accepted;
# arbitrary startswith matches are intentionally rejected.
ENGINE_PROFILE_DELIMITERS = (":", "/", "@")


def canonical_engine(engine: str) -> str | None:
    candidate = str(engine or "").strip().upper()
    if candidate in ENGINE_ALLOWLIST:
        return candidate
    for family in ENGINE_ALLOWLIST:
        if any(candidate.startswith(family + delimiter) for delimiter in ENGINE_PROFILE_DELIMITERS):
            return family
    return None


def engine_allowed(engine: str) -> bool:
    return canonical_engine(engine) is not None


@dataclass(frozen=True)
class SharedAutomationProfile:
    chat_session_id: str
    requested_engine: str
    canonical_engine: str
    fabric_id: str = SHARED_FABRIC_ID
    command_queue: str = "COMMAND_QUEUE"
    receipt_log: str = "COMMAND_RECEIPTS"
    authority_leases: str = "AUTHORITY_LEASES"
    runtime_heartbeat: str = "RUNTIME_HEARTBEAT"
    default_autonomy: str = "READ_AND_NON_SERVING_LAB_AUTO"
    control_plane_authority: str = "ACTIVE_MISSION_LEASE_REQUIRED"
    destructive_authority: str = "ONE_USE_EXACT_TARGET_ONLY"
    communication_authority: str = "EXPLICIT_USER_DIRECTIVE_ONLY"
    continuation_rule: str = "CONTINUE_UNTIL_SEMANTIC_TERMINAL_RECEIPT_OR_EXACT_EXTERNAL_GATE"
    credential_inheritance: bool = False
    authority_inheritance: str = "SHARED_FABRIC_ONLY"

    def canonical_payload(self) -> dict[str, object]:
        return {"schema": PROFILE_SCHEMA, **asdict(self)}

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


def build_profile(*, chat_session_id: str, engine: str) -> SharedAutomationProfile:
    session = str(chat_session_id or "").strip()
    if not session:
        raise ValueError("chat_session_id is required")
    canonical = canonical_engine(engine)
    if canonical is None:
        raise ValueError(f"engine profile is not admitted: {engine!r}")
    return SharedAutomationProfile(
        chat_session_id=session,
        requested_engine=str(engine).strip(),
        canonical_engine=canonical,
    )
