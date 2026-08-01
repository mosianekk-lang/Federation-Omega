from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AlignmentError(RuntimeError):
    pass


@dataclass(frozen=True)
class AlignmentReceipt:
    manifest_id: str
    active_contract: str
    manifest_hash: str
    doctrine_hash: str
    contract_hash: str
    bootstrap_hash: str
    aligned: bool


class InPlaceAlignmentLoader:
    """Loads the controlling EvidenceOps translator directly from the repository.

    This does not inject instructions into unrelated running chats. It gives every
    EvidenceOps worker, agent or runtime a deterministic in-place alignment route.
    """

    def __init__(self, repository_root: str | Path):
        self.root = Path(repository_root)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def load(self) -> tuple[dict[str, Any], AlignmentReceipt]:
        manifest_path = self.root / "evidenceops/runtime/ACTIVE_SOVEREIGN_TRANSLATOR.json"
        if not manifest_path.exists():
            raise AlignmentError("Active sovereign translator manifest is missing")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = [self.root / rel for rel in manifest["required_resources"]]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise AlignmentError(f"Required alignment resources missing: {missing}")

        doctrine_path, contract_path, bootstrap_path = required
        contract = json.loads(contract_path.read_text(encoding="utf-8"))

        if contract.get("contract_id") != manifest.get("active_contract"):
            raise AlignmentError("Manifest and contract identifiers do not match")
        if contract.get("owner") != manifest.get("owner"):
            raise AlignmentError("Manifest and contract owner do not match")
        if contract.get("mission_delta", {}).get("report_only_terminal_allowed") is not False:
            raise AlignmentError("Report-only terminal state is not prohibited")

        packet = {
            "manifest": manifest,
            "contract": contract,
            "doctrine": doctrine_path.read_text(encoding="utf-8"),
            "bootstrap": bootstrap_path.read_text(encoding="utf-8"),
        }
        receipt = AlignmentReceipt(
            manifest_id=manifest["runtime_manifest_id"],
            active_contract=manifest["active_contract"],
            manifest_hash=self._sha256(manifest_path),
            doctrine_hash=self._sha256(doctrine_path),
            contract_hash=self._sha256(contract_path),
            bootstrap_hash=self._sha256(bootstrap_path),
            aligned=True,
        )
        return packet, receipt


def load_active_translator(repository_root: str | Path = "."):
    return InPlaceAlignmentLoader(repository_root).load()
