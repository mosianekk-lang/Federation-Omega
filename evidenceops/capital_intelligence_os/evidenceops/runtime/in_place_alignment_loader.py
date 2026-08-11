from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
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
    resource_hashes: dict[str, str] = field(default_factory=dict)


class InPlaceAlignmentLoader:
    """Load the controlling EvidenceOps translator from repository resources.

    The manifest may grow additional required resources over time. Core resources
    are selected by their declared repository paths instead of by list position,
    so adding a bridge, policy, schema or receipt cannot break alignment loading.
    """

    def __init__(self, repository_root: str | Path):
        self.root = Path(repository_root)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _find_resource(resources: dict[str, Path], marker: str) -> Path:
        matches = [path for rel, path in resources.items() if marker in rel]
        if len(matches) != 1:
            raise AlignmentError(
                f"Expected exactly one required resource matching {marker!r}; "
                f"found {len(matches)}"
            )
        return matches[0]

    def load(self) -> tuple[dict[str, Any], AlignmentReceipt]:
        manifest_path = self.root / "evidenceops/runtime/ACTIVE_SOVEREIGN_TRANSLATOR.json"
        if not manifest_path.exists():
            raise AlignmentError("Active sovereign translator manifest is missing")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = list(manifest.get("required_resources") or [])
        if not declared:
            raise AlignmentError("Manifest declares no required alignment resources")

        resources = {rel: self.root / rel for rel in declared}
        missing = [str(path) for path in resources.values() if not path.exists()]
        if missing:
            raise AlignmentError(f"Required alignment resources missing: {missing}")

        doctrine_path = self._find_resource(resources, "evidenceops/doctrine/")
        contract_path = self._find_resource(resources, "evidenceops/contracts/")
        bootstrap_path = self._find_resource(resources, "evidenceops/bootstrap/")
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
            "resources": {
                rel: {
                    "path": str(path),
                    "sha256": self._sha256(path),
                }
                for rel, path in resources.items()
            },
        }
        receipt = AlignmentReceipt(
            manifest_id=manifest["runtime_manifest_id"],
            active_contract=manifest["active_contract"],
            manifest_hash=self._sha256(manifest_path),
            doctrine_hash=self._sha256(doctrine_path),
            contract_hash=self._sha256(contract_path),
            bootstrap_hash=self._sha256(bootstrap_path),
            aligned=True,
            resource_hashes={rel: self._sha256(path) for rel, path in resources.items()},
        )
        return packet, receipt


def load_active_translator(repository_root: str | Path = "."):
    return InPlaceAlignmentLoader(repository_root).load()
