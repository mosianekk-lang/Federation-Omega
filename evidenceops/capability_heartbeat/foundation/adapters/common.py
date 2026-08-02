"""Shared observation contract and safe local-read boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..contracts import BlockerCode, CapabilityStatus, digest, enum_value, parse_utc
from ..errors import ContractError
from ..privacy import require_code, require_hash, validate_explicit_metadata
from ..scoring import CapabilityCandidate

MAX_SOURCE_BYTES = 1_048_576
OBSERVATION_METADATA_SCHEMAS = {
    "LOCAL_BIBLE": {
        "latest_transaction": "code",
        "transaction_sequence": "integer",
        "semantic_alignment": "boolean",
    },
    "LOCAL_REPO": {
        "head_hash": "hash",
        "reference_code": "code",
    },
    "FORMATION_STATE": {
        "mission_code": "code",
        "mission_version": "integer",
        "mission_state": "code",
        "control_generation": "integer",
    },
}


@dataclass(frozen=True, slots=True)
class Observation:
    source_code: str
    node_id: str
    owner_code: str
    matter_code: str
    capability_code: str
    status: CapabilityStatus
    confidence_bp: int
    freshness_seconds: int
    evidence_count: int
    blocker_code: BlockerCode
    capability_hash: str
    observed_at: str
    semantic_receipt: str

    def __post_init__(self) -> None:
        for field_name in ("source_code", "node_id", "owner_code", "matter_code", "capability_code"):
            require_code(getattr(self, field_name), field=field_name)
        object.__setattr__(self, "status", enum_value(CapabilityStatus, self.status, field="status"))
        object.__setattr__(self, "blocker_code", enum_value(BlockerCode, self.blocker_code, field="blocker_code"))
        require_hash(self.capability_hash, field="capability_hash")
        require_hash(self.semantic_receipt, field="semantic_receipt")
        parse_utc(self.observed_at, field="observed_at")
        CapabilityCandidate(
            capability_code=self.capability_code,
            status=self.status,
            confidence_bp=self.confidence_bp,
            freshness_seconds=self.freshness_seconds,
            evidence_count=self.evidence_count,
            compatible=True,
            blocker_code=self.blocker_code,
        )

    def candidate(self) -> CapabilityCandidate:
        return CapabilityCandidate(
            capability_code=self.capability_code,
            status=self.status,
            confidence_bp=self.confidence_bp,
            freshness_seconds=self.freshness_seconds,
            evidence_count=self.evidence_count,
            compatible=True,
            blocker_code=self.blocker_code,
        )


def safe_root(root: str | Path) -> Path:
    if callable(root) or not isinstance(root, (str, Path)):
        raise ContractError("LOCAL_PATH_REQUIRED_NOT_CALLABLE")
    path = Path(root)
    if not path.is_absolute():
        raise ContractError("ABSOLUTE_LOCAL_PATH_REQUIRED")
    resolved = path.resolve(strict=True)
    if not resolved.is_dir() or path.is_symlink():
        raise ContractError("SAFE_LOCAL_DIRECTORY_REQUIRED")
    return resolved


def read_local_text(root: Path, relative_name: str) -> str:
    if not isinstance(relative_name, str) or "/" in relative_name or "\\" in relative_name:
        raise ContractError("SINGLE_LOCAL_FILENAME_REQUIRED")
    target = root / relative_name
    if target.is_symlink() or not target.is_file():
        raise ContractError("LOCAL_SOURCE_FILE_UNAVAILABLE")
    if target.stat().st_size > MAX_SOURCE_BYTES:
        raise ContractError("LOCAL_SOURCE_FILE_OVERSIZED")
    return target.read_text(encoding="utf-8")


def make_observation(
    *,
    source_code: str,
    node_id: str,
    owner_code: str,
    matter_code: str,
    capability_code: str,
    status: CapabilityStatus,
    confidence_bp: int,
    freshness_seconds: int,
    evidence_count: int,
    blocker_code: BlockerCode,
    observed_at: str,
    semantic_value: dict[str, object],
) -> Observation:
    schema = OBSERVATION_METADATA_SCHEMAS.get(source_code)
    if schema is None:
        raise ContractError("UNSUPPORTED_OBSERVATION_SOURCE")
    safe_semantic_value = validate_explicit_metadata(semantic_value, schema=schema)
    capability_hash = digest(
        {
            "source_code": source_code,
            "capability_code": capability_code,
            "status": status,
            "semantic_value": safe_semantic_value,
        }
    )
    semantic_receipt = digest(
        {
            "capability_hash": capability_hash,
            "observed_at": observed_at,
            "semantic_value": safe_semantic_value,
        }
    )
    return Observation(
        source_code=source_code,
        node_id=node_id,
        owner_code=owner_code,
        matter_code=matter_code,
        capability_code=capability_code,
        status=status,
        confidence_bp=confidence_bp,
        freshness_seconds=freshness_seconds,
        evidence_count=evidence_count,
        blocker_code=blocker_code,
        capability_hash=capability_hash,
        observed_at=observed_at,
        semantic_receipt=semantic_receipt,
    )
