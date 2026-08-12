from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


DEFAULT_PACKET = Path(__file__).resolve().parent / "sparks_provider_execution_packet.json"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_SECRET_VALUE_KEYS = {
    "secret",
    "secret_value",
    "token",
    "token_value",
    "credential",
    "credential_value",
    "api_key",
    "private_key",
    "password",
}


class SparksProviderPacket:
    def __init__(self, payload: Mapping[str, Any]):
        self.payload = dict(payload)
        sha = str(payload.get("source_main_sha", ""))
        if not _SHA.fullmatch(sha):
            raise ValueError("source_main_sha must be an exact lowercase Git SHA")
        if payload.get("authorized_execution_surface") is not False:
            raise ValueError("source packet cannot self-authorise provider execution")
        if payload.get("execution_state") != "BLOCKED_EXTERNAL_PACKET_READY":
            raise ValueError("source packet must begin BLOCKED_EXTERNAL_PACKET_READY")
        projects = [dict(item) for item in payload.get("projects", [])]
        self.projects = {str(item["project_id"]): item for item in projects}
        if set(self.projects) != {"CIOS", "ECERTIFY"}:
            raise ValueError("packet must bind exactly CIOS and ECERTIFY")
        self._reject_secret_values(payload)
        for project in self.projects.values():
            if not project.get("source_files"):
                raise ValueError("every project requires source_files")
            if not project.get("required_proof_fields"):
                raise ValueError("every project requires provider proof fields")
            if not project.get("execution_sequence"):
                raise ValueError("every project requires an execution sequence")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PACKET) -> "SparksProviderPacket":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @staticmethod
    def _reject_secret_values(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key).casefold() in _FORBIDDEN_SECRET_VALUE_KEYS:
                    raise ValueError(f"secret-bearing field forbidden: {key}")
                SparksProviderPacket._reject_secret_values(child)
        elif isinstance(value, list):
            for child in value:
                SparksProviderPacket._reject_secret_values(child)

    @property
    def source_sha(self) -> str:
        return str(self.payload["source_main_sha"])

    def verify_source_tree(self, repository_root: str | Path) -> dict[str, Any]:
        root = Path(repository_root)
        missing = []
        for project in self.projects.values():
            for relative in project["source_files"]:
                if not (root / str(relative)).is_file():
                    missing.append(str(relative))
        return {
            "source_files_present": not missing,
            "missing_source_files": sorted(set(missing)),
            "source_sha": self.source_sha,
        }

    def assess_authority(self, *, authorized_execution_surface: bool, provider_identity_readback: str = "") -> dict[str, Any]:
        if not authorized_execution_surface:
            return {
                "execution_allowed": False,
                "state": "BLOCKED_EXTERNAL_PACKET_READY",
                "reason": "AUTHORISED_PROVIDER_EXECUTION_SURFACE_REQUIRED",
            }
        if not provider_identity_readback.strip():
            return {
                "execution_allowed": False,
                "state": "BLOCKED_EXTERNAL_IDENTITY_READBACK_REQUIRED",
                "reason": "PROVIDER_IDENTITY_READBACK_REQUIRED",
            }
        return {
            "execution_allowed": True,
            "state": "AUTHORISED_CANARY_EXECUTION_READY",
            "reason": "AUTHORITY_AND_IDENTITY_READBACK_PRESENT",
        }

    def assess_receipt(self, project_id: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
        project = self.projects[project_id]
        missing = [field for field in project["required_proof_fields"] if field not in receipt]
        failures: list[str] = []
        if receipt.get("source_sha") != self.source_sha:
            failures.append("SOURCE_SHA_MISMATCH")
        for field, expected in project["acceptance"].items():
            if field == "source_sha_must_equal_packet_sha":
                continue
            if receipt.get(field) != expected:
                failures.append(f"ACCEPTANCE_FAILED:{field}")
        verified = not missing and not failures
        return {
            "project_id": project_id,
            "provider_verified": verified,
            "missing_fields": missing,
            "failures": failures,
            "state": "PROVIDER_VERIFIED" if verified else "PROVIDER_PROOF_INCOMPLETE",
            "truth_boundary": (
                "This assessment validates packet-required receipt structure and acceptance semantics. "
                "The receipt itself must still originate from provider-native readback and be independently validated by Ledger."
            ),
        }
