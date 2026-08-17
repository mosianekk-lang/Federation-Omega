from __future__ import annotations

from dataclasses import dataclass


WORKSPACE_MINIMUM_SCOPES: dict[str, frozenset[str]] = {
    "drive.search": frozenset({"https://www.googleapis.com/auth/drive.metadata.readonly"}),
    "drive.read": frozenset({"https://www.googleapis.com/auth/drive.readonly"}),
    "drive.write": frozenset({"https://www.googleapis.com/auth/drive.file"}),
    "gmail.search": frozenset({"https://www.googleapis.com/auth/gmail.readonly"}),
    "gmail.read": frozenset({"https://www.googleapis.com/auth/gmail.readonly"}),
    "gmail.draft": frozenset({"https://www.googleapis.com/auth/gmail.compose"}),
    "gmail.send": frozenset({"https://www.googleapis.com/auth/gmail.send"}),
    "sheets.read": frozenset({"https://www.googleapis.com/auth/spreadsheets.readonly"}),
    "sheets.write": frozenset({"https://www.googleapis.com/auth/spreadsheets"}),
    "calendar.read": frozenset({"https://www.googleapis.com/auth/calendar.readonly"}),
    "calendar.schedule": frozenset({"https://www.googleapis.com/auth/calendar.events"}),
    "calendar.update": frozenset({"https://www.googleapis.com/auth/calendar.events"}),
}


@dataclass(frozen=True)
class AuthorityEnvelope:
    user_grant: bool
    oauth_scopes: frozenset[str]
    iam_authorized: bool
    mission_permit: bool
    tool_allowlisted: bool
    resource_allowed: bool

    def evaluate(self, action_id: str) -> tuple[bool, tuple[str, ...]]:
        missing: list[str] = []
        if not self.user_grant:
            missing.append("USER_GRANT_MISSING")
        required_scopes = WORKSPACE_MINIMUM_SCOPES.get(action_id, frozenset())
        if required_scopes and not required_scopes.issubset(self.oauth_scopes):
            missing.append("OAUTH_SCOPE_MISSING")
        if not self.iam_authorized:
            missing.append("IAM_AUTHORITY_MISSING")
        if not self.mission_permit:
            missing.append("MISSION_PERMIT_MISSING")
        if not self.tool_allowlisted:
            missing.append("TOOL_NOT_ALLOWLISTED")
        if not self.resource_allowed:
            missing.append("RESOURCE_BOUNDARY_DENIED")
        return not missing, tuple(missing)
