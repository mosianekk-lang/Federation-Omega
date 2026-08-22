from __future__ import annotations

from dataclasses import dataclass


WORKSPACE_MINIMUM_SCOPES: dict[str, frozenset[str]] = {
    "drive.search": frozenset({"https://www.googleapis.com/auth/drive.metadata.readonly"}),
    "drive.read": frozenset({"https://www.googleapis.com/auth/drive.readonly"}),
    "drive.write": frozenset({"https://www.googleapis.com/auth/drive.file"}),
    "drive.share": frozenset({"https://www.googleapis.com/auth/drive.file"}),
    "drive.move": frozenset({"https://www.googleapis.com/auth/drive.file"}),
    "gmail.search": frozenset({"https://www.googleapis.com/auth/gmail.readonly"}),
    "gmail.read": frozenset({"https://www.googleapis.com/auth/gmail.readonly"}),
    "gmail.draft": frozenset({"https://www.googleapis.com/auth/gmail.compose"}),
    "gmail.send": frozenset({"https://www.googleapis.com/auth/gmail.send"}),
    "gmail.forward": frozenset({"https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"}),
    "gmail.archive": frozenset({"https://www.googleapis.com/auth/gmail.modify"}),
    "sheets.read": frozenset({"https://www.googleapis.com/auth/spreadsheets.readonly"}),
    "sheets.write": frozenset({"https://www.googleapis.com/auth/spreadsheets"}),
    "calendar.read": frozenset({"https://www.googleapis.com/auth/calendar.readonly"}),
    "calendar.schedule": frozenset({"https://www.googleapis.com/auth/calendar.events"}),
    "calendar.update": frozenset({"https://www.googleapis.com/auth/calendar.events"}),
}


@dataclass(frozen=True)
class AuthorityEnvelope:
    subject_id: str
    user_grants: frozenset[str]
    oauth_scopes: frozenset[str]
    iam_actions: frozenset[str]
    mission_actions: frozenset[str]
    tool_allowlist: frozenset[str]
    resource_allowlist: frozenset[str]

    def evaluate(self, action_id: str, resource: str, mission_permit: bool) -> tuple[bool, tuple[str, ...]]:
        missing: list[str] = []
        if not self.subject_id.strip():
            missing.append("AUTHORITY_SUBJECT_REQUIRED")
        if action_id not in self.user_grants:
            missing.append("USER_GRANT_MISSING")
        required_scopes = WORKSPACE_MINIMUM_SCOPES.get(action_id, frozenset())
        if required_scopes and not required_scopes.issubset(self.oauth_scopes):
            missing.append("OAUTH_SCOPE_MISSING")
        if action_id not in self.iam_actions:
            missing.append("IAM_AUTHORITY_MISSING")
        if action_id not in self.mission_actions or not mission_permit:
            missing.append("MISSION_PERMIT_MISSING")
        if action_id not in self.tool_allowlist:
            missing.append("TOOL_NOT_ALLOWLISTED")
        if resource not in self.resource_allowlist:
            missing.append("RESOURCE_BOUNDARY_DENIED")
        return not missing, tuple(missing)
