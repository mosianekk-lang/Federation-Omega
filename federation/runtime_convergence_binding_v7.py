from __future__ import annotations

"""FUSE Runtime Convergence Binding v7.

V7 compiles current durable mission truth into the existing F130 snapshot
contract and binds the V6 provider-execution receipt into that projection.

The V7 convergence receipt proves authoritative snapshot compilation. It does not
claim F130 terminal completion until the existing F130 two-phase terminal court
actually commits.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from bubbles.mission_proof_passport import MissionProofPassport
from federation.f130_authoritative_snapshot_compiler_v1 import (
    AuthoritativeSnapshotCompilation,
    AuthoritativeTerminalPrepare,
    F130AuthoritativeSnapshotCompiler,
    F130AuthoritativeTerminalBinder,
)
from federation.fuse_mission_runtime_interlock_v1 import RuntimeAction
from federation.runtime_convergence_binding_v6 import RuntimeConvergenceReceiptV6
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1

SCHEMA = "FUSE-RUNTIME-CONVERGENCE-BINDING-V7"
VERSION = "7.0.0"
CAPABILITY_ID = "FUSE-FRCB-007"


class StageStateV7(str, Enum):
    AUTHORITATIVE_SNAPSHOT_VERIFIED = "AUTHORITATIVE_SNAPSHOT_VERIFIED"
    F130_PREPARED = "F130_PREPARED"
    F130_COMPLETE_VERIFIED = "F130_COMPLETE_VERIFIED"


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceReceiptV7:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    snapshot_compiler_receipt_digest: str
    ledger_head_hash: str
    projection_sha256: str
    passport_sha256: str
    v6_receipt_digest: str
    epoch_id: str
    contract_epoch: int
    ledger_tail: int
    authoritative_snapshot_verified: bool
    provider_execution_verified: bool
    provider_semantic_readback_verified: bool
    f130_terminal_completion_verified: bool
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    @property
    def completion_verified(self) -> bool:
        return self.f130_terminal_completion_verified

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "capability_id": self.capability_id,
            "mission_id": self.mission_id,
            "snapshot_compiler_receipt_digest": self.snapshot_compiler_receipt_digest,
            "ledger_head_hash": self.ledger_head_hash,
            "projection_sha256": self.projection_sha256,
            "passport_sha256": self.passport_sha256,
            "v6_receipt_digest": self.v6_receipt_digest,
            "epoch_id": self.epoch_id,
            "contract_epoch": self.contract_epoch,
            "ledger_tail": self.ledger_tail,
            "authoritative_snapshot_verified": self.authoritative_snapshot_verified,
            "provider_execution_verified": self.provider_execution_verified,
            "provider_semantic_readback_verified": self.provider_semantic_readback_verified,
            "f130_terminal_completion_verified": self.f130_terminal_completion_verified,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.capability_id == CAPABILITY_ID
            and self.mission_id.strip()
            and self.snapshot_compiler_receipt_digest.startswith("sha256:")
            and self.ledger_head_hash.strip()
            and self.projection_sha256.startswith("sha256:")
            and self.passport_sha256.startswith("sha256:")
            and self.v6_receipt_digest.startswith("sha256:")
            and self.epoch_id.startswith("mission-epoch:")
            and self.contract_epoch >= 1
            and self.ledger_tail >= 1
            and self.authoritative_snapshot_verified is True
            and self.provider_execution_verified is True
            and self.provider_semantic_readback_verified is True
            and boundary.get("whole_mission_snapshot_authoritatively_compiled") is True
            and boundary.get("caller_supplied_terminal_snapshot_rejected") is True
            and boundary.get("pre_commit_recompile_required") is True
            and boundary.get("f130_remains_terminal_authority") is True
            and boundary.get("native_chatgpt_interception_proven") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceResultV7:
    compilation: AuthoritativeSnapshotCompilation
    convergence_receipt: RuntimeConvergenceReceiptV7


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceTerminalResultV7:
    prepare: AuthoritativeTerminalPrepare
    f130_action: str
    f130_receipt_digest: str
    completion_verified: bool
    terminal_receipt_digest: str


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


class RuntimeConvergenceBinderV7:
    """Bind durable mission truth into F130 without creating a second terminal court."""

    def __init__(
        self,
        *,
        compiler: F130AuthoritativeSnapshotCompiler | None = None,
        terminal: F130AuthoritativeTerminalBinder | None = None,
    ) -> None:
        self.compiler = compiler or F130AuthoritativeSnapshotCompiler()
        self.terminal = terminal or F130AuthoritativeTerminalBinder(
            compiler=self.compiler
        )

    def evaluate(
        self,
        *,
        runtime: DurableMissionRuntimeV1,
        passport: MissionProofPassport,
        mission_id: str,
        v6_receipt: RuntimeConvergenceReceiptV6,
    ) -> RuntimeConvergenceResultV7:
        compiled = self.compiler.compile(
            runtime=runtime,
            passport=passport,
            mission_id=mission_id,
            v6_receipt=v6_receipt,
            completion_claim_requested=True,
        )
        source = compiled.receipt
        truth_boundary = MappingProxyType({
            "whole_mission_snapshot_authoritatively_compiled": True,
            "caller_supplied_terminal_snapshot_rejected": True,
            "pre_commit_recompile_required": True,
            "provider_execution_verified": True,
            "provider_semantic_readback_verified": True,
            "f130_remains_terminal_authority": True,
            "native_chatgpt_interception_proven": False,
        })
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "capability_id": CAPABILITY_ID,
            "mission_id": mission_id,
            "snapshot_compiler_receipt_digest": source.receipt_digest,
            "ledger_head_hash": source.ledger_head_hash,
            "projection_sha256": source.projection_sha256,
            "passport_sha256": source.passport_sha256,
            "v6_receipt_digest": v6_receipt.receipt_digest,
            "epoch_id": source.epoch_id,
            "contract_epoch": source.contract_epoch,
            "ledger_tail": source.ledger_tail,
            "authoritative_snapshot_verified": True,
            "provider_execution_verified": True,
            "provider_semantic_readback_verified": True,
            "f130_terminal_completion_verified": False,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = RuntimeConvergenceReceiptV7(
            schema=SCHEMA,
            version=VERSION,
            capability_id=CAPABILITY_ID,
            mission_id=mission_id,
            snapshot_compiler_receipt_digest=source.receipt_digest,
            ledger_head_hash=source.ledger_head_hash,
            projection_sha256=source.projection_sha256,
            passport_sha256=source.passport_sha256,
            v6_receipt_digest=v6_receipt.receipt_digest,
            epoch_id=source.epoch_id,
            contract_epoch=source.contract_epoch,
            ledger_tail=source.ledger_tail,
            authoritative_snapshot_verified=True,
            provider_execution_verified=True,
            provider_semantic_readback_verified=True,
            f130_terminal_completion_verified=False,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("FRCB_V7_RECEIPT_SELF_VERIFICATION_FAILED")
        return RuntimeConvergenceResultV7(
            compilation=compiled,
            convergence_receipt=receipt,
        )

    def prepare_terminal(
        self,
        *,
        runtime: DurableMissionRuntimeV1,
        passport: MissionProofPassport,
        mission_id: str,
        v6_receipt: RuntimeConvergenceReceiptV6,
        now_epoch: float,
    ) -> AuthoritativeTerminalPrepare:
        return self.terminal.prepare(
            runtime=runtime,
            passport=passport,
            mission_id=mission_id,
            v6_receipt=v6_receipt,
            now_epoch=now_epoch,
        )

    def commit_terminal(
        self,
        *,
        runtime: DurableMissionRuntimeV1,
        passport: MissionProofPassport,
        mission_id: str,
        v6_receipt: RuntimeConvergenceReceiptV6,
        prepared: AuthoritativeTerminalPrepare,
        now_epoch: float,
    ) -> RuntimeConvergenceTerminalResultV7:
        decision = self.terminal.commit(
            runtime=runtime,
            passport=passport,
            mission_id=mission_id,
            v6_receipt=v6_receipt,
            prepared=prepared,
            now_epoch=now_epoch,
        )
        completion = bool(
            decision.action is RuntimeAction.COMPLETE_VERIFIED
            and decision.completion_verified
        )
        material = {
            "prepare_receipt_digest": prepared.receipt_digest,
            "f130_action": decision.action.value,
            "f130_receipt_digest": decision.receipt_digest,
            "completion_verified": completion,
        }
        return RuntimeConvergenceTerminalResultV7(
            prepare=prepared,
            f130_action=decision.action.value,
            f130_receipt_digest=decision.receipt_digest,
            completion_verified=completion,
            terminal_receipt_digest=_digest(material),
        )


__all__ = [
    "CAPABILITY_ID",
    "RuntimeConvergenceBinderV7",
    "RuntimeConvergenceReceiptV7",
    "RuntimeConvergenceResultV7",
    "RuntimeConvergenceTerminalResultV7",
    "SCHEMA",
    "StageStateV7",
    "VERSION",
]
