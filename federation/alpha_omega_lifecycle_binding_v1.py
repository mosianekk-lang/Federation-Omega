from __future__ import annotations

"""Alpha→Omega local-build receipt binding for FRCB v4.

This module verifies the current local build artifact set emitted by the existing
AlphaOmegaEngine. It creates no provider deployment and grants no authority.

A verified local build is not TEST, DEPLOY, provider VERIFY, OPERATE, semantic
readback, or F130 terminal completion.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Any, Mapping

from federation.of50_ace_v1 import AlphaOmegaPacket

SCHEMA = "FUSE-ALPHA-OMEGA-LOCAL-BUILD-RECEIPT-V1"
VERSION = "1.0.0"
PRODUCER_ID = "ALPHA-OMEGA-TURNKEY"
EXPECTED_ARTIFACTS = (
    "README.md",
    "architecture.json",
    "maintenance.json",
    "work_packets.json",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def packet_digest(packet: AlphaOmegaPacket) -> str:
    return _digest(asdict(packet))


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> str:
    raw = str(value).replace("\\", "/").strip()
    pure = PurePosixPath(raw)
    if (
        not raw
        or pure.is_absolute()
        or raw in {".", ".."}
        or raw.startswith("../")
        or "/../" in raw
    ):
        raise ValueError("ALPHA_OMEGA_BUILD_ARTIFACT_PATH_UNSAFE")
    return str(pure)


@dataclass(frozen=True, slots=True)
class AlphaOmegaLocalBuildReceipt:
    schema: str
    version: str
    producer_id: str
    mission_id: str
    packet_ref: str
    build_plan_ref: str
    system_name: str
    local_build_state: str
    build_dir: str
    packet_digest: str
    artifact_hashes: tuple[tuple[str, str], ...]
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "producer_id": self.producer_id,
            "mission_id": self.mission_id,
            "packet_ref": self.packet_ref,
            "build_plan_ref": self.build_plan_ref,
            "system_name": self.system_name,
            "local_build_state": self.local_build_state,
            "build_dir": self.build_dir,
            "packet_digest": self.packet_digest,
            "artifact_hashes": [list(item) for item in self.artifact_hashes],
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        names = tuple(item[0] for item in self.artifact_hashes)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.producer_id == PRODUCER_ID
            and self.mission_id.strip()
            and self.packet_ref.strip()
            and self.build_plan_ref.strip()
            and self.system_name == self.build_plan_ref
            and self.local_build_state == "LOCAL_OPERATIONAL_PACKAGE_BUILT"
            and self.build_dir.strip()
            and self.packet_digest.startswith("sha256:")
            and names == EXPECTED_ARTIFACTS
            and all(_HEX64.fullmatch(item[1]) for item in self.artifact_hashes)
            and boundary.get("local_build_execution_verified") is True
            and boundary.get("local_artifact_readback_verified") is True
            and boundary.get("test_stage_verified") is False
            and boundary.get("provider_deployment_verified") is False
            and boundary.get("provider_semantic_readback_verified") is False
            and boundary.get("operational_runtime_verified") is False
            and boundary.get("external_effect_created") is False
            and boundary.get("authority_widened") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


def verify_local_artifacts(receipt: AlphaOmegaLocalBuildReceipt) -> bool:
    if not receipt.verify():
        return False
    root = Path(receipt.build_dir)
    if not root.is_dir():
        return False
    observed: list[tuple[str, str]] = []
    try:
        for relative, expected_hash in receipt.artifact_hashes:
            safe = _safe_relative(relative)
            path = root / safe
            if not path.is_file():
                return False
            actual = _file_sha256(path)
            if actual != expected_hash:
                return False
            observed.append((safe, actual))
    except (OSError, ValueError):
        return False
    return tuple(observed) == receipt.artifact_hashes


def build_local_receipt(
    *,
    packet: AlphaOmegaPacket,
    build_dir: str | Path,
    local_build_state: str,
    truth_boundary: Mapping[str, Any],
) -> AlphaOmegaLocalBuildReceipt:
    errors = packet.validate()
    if errors:
        raise ValueError("ALPHA_OMEGA_PACKET_INVALID:" + ";".join(errors))
    if local_build_state != "LOCAL_OPERATIONAL_PACKAGE_BUILT":
        raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_NOT_VERIFIED")

    raw_boundary = dict(truth_boundary)
    if raw_boundary.get("artifacts_built") is not True:
        raise ValueError("ALPHA_OMEGA_ARTIFACT_BUILD_NOT_CONFIRMED")
    if raw_boundary.get("provider_deployed") is not False:
        raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_PROVIDER_CLAIM_FORBIDDEN")
    if raw_boundary.get("operational_verified") is not False:
        raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_OPERATIONAL_CLAIM_FORBIDDEN")
    if raw_boundary.get("provider_readback") is not False:
        raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_PROVIDER_READBACK_CLAIM_FORBIDDEN")

    root = Path(build_dir).resolve()
    if not root.is_dir():
        raise ValueError("ALPHA_OMEGA_BUILD_DIR_REQUIRED")
    artifacts: list[tuple[str, str]] = []
    for relative in EXPECTED_ARTIFACTS:
        path = root / relative
        if not path.is_file():
            raise ValueError("ALPHA_OMEGA_BUILD_ARTIFACT_MISSING:" + relative)
        artifacts.append((relative, _file_sha256(path)))

    boundary = MappingProxyType({
        "local_build_execution_verified": True,
        "local_artifact_readback_verified": True,
        "test_stage_verified": False,
        "provider_deployment_verified": False,
        "provider_semantic_readback_verified": False,
        "operational_runtime_verified": False,
        "external_effect_created": False,
        "authority_widened": False,
    })
    material = {
        "schema": SCHEMA,
        "version": VERSION,
        "producer_id": PRODUCER_ID,
        "mission_id": packet.mission_id,
        "packet_ref": packet.packet_ref,
        "build_plan_ref": packet.build_plan_ref,
        "system_name": packet.build_plan_ref,
        "local_build_state": local_build_state,
        "build_dir": str(root),
        "packet_digest": packet_digest(packet),
        "artifact_hashes": [list(item) for item in artifacts],
        "truth_boundary": dict(boundary),
    }
    receipt = AlphaOmegaLocalBuildReceipt(
        schema=SCHEMA,
        version=VERSION,
        producer_id=PRODUCER_ID,
        mission_id=packet.mission_id,
        packet_ref=packet.packet_ref,
        build_plan_ref=packet.build_plan_ref,
        system_name=packet.build_plan_ref,
        local_build_state=local_build_state,
        build_dir=str(root),
        packet_digest=packet_digest(packet),
        artifact_hashes=tuple(artifacts),
        receipt_digest=_digest(material),
        truth_boundary=boundary,
    )
    if not verify_local_artifacts(receipt):
        raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_RECEIPT_SELF_VERIFICATION_FAILED")
    return receipt


class AlphaOmegaLocalBuildBinder:
    def bind(
        self,
        *,
        mission_id: str,
        packet: AlphaOmegaPacket,
        receipt: AlphaOmegaLocalBuildReceipt,
    ) -> AlphaOmegaLocalBuildReceipt:
        if not verify_local_artifacts(receipt):
            raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_RECEIPT_INVALID")
        if receipt.mission_id != mission_id or packet.mission_id != mission_id:
            raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_MISSION_MISMATCH")
        if receipt.packet_ref != packet.packet_ref:
            raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_PACKET_REF_MISMATCH")
        if receipt.build_plan_ref != packet.build_plan_ref:
            raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_PLAN_REF_MISMATCH")
        if receipt.packet_digest != packet_digest(packet):
            raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_PACKET_DIGEST_MISMATCH")
        return receipt


__all__ = [
    "AlphaOmegaLocalBuildBinder",
    "AlphaOmegaLocalBuildReceipt",
    "EXPECTED_ARTIFACTS",
    "PRODUCER_ID",
    "SCHEMA",
    "VERSION",
    "build_local_receipt",
    "packet_digest",
    "verify_local_artifacts",
]
