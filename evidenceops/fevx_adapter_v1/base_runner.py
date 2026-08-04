from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Protocol

from .core import digest
from .mapping import build_base_inputs


class BaseRunner(Protocol):
    def run(
        self,
        packet: dict[str, Any],
        repo_root: Path,
        work_dir: Path,
    ) -> dict[str, Any]: ...


class ActualCSEBaseRunner:
    """Invoke the exact installed CSE v1.1 command-line runtime."""

    def _ensure_migration_compatibility(self) -> dict[str, Any]:
        import fevx_cse  # type: ignore

        package = Path(fevx_cse.__file__).resolve().parent
        source = package / "sql/sqlite_001_bootstrap.sql"
        target = (
            Path(fevx_cse.__file__).resolve().parents[2]
            / "migrations/sqlite/001_bootstrap.sql"
        )
        if not source.is_file():
            raise FileNotFoundError(f"CSE packaged migration not found: {source}")
        payload = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != payload:
            target.write_bytes(payload)
        if target.read_bytes() != payload:
            raise RuntimeError("CSE migration compatibility readback failed")
        return {
            "state": "VERIFIED",
            "source_sha256": digest(payload),
            "target_sha256": digest(target.read_bytes()),
            "ephemeral_compatibility_copy": True,
            "source_code_modified": False,
        }

    @staticmethod
    def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode:
            raise RuntimeError(
                json.dumps(
                    {
                        "command": command,
                        "returncode": completed.returncode,
                        "stdout": completed.stdout[-12000:],
                        "stderr": completed.stderr[-12000:],
                    },
                    indent=2,
                )
            )
        return completed

    def run(
        self,
        packet: dict[str, Any],
        repo_root: Path,
        work_dir: Path,
    ) -> dict[str, Any]:
        compatibility = self._ensure_migration_compatibility()
        work_dir.mkdir(parents=True, exist_ok=True)
        mission, genome = build_base_inputs(packet, repo_root)
        mission_path = work_dir / "mission.json"
        genome_path = work_dir / "intent_genome.json"
        output_path = work_dir / "base_analysis.json"
        database_path = work_dir / "base_cse.db"
        mission_path.write_text(
            json.dumps(mission, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        genome_path.write_text(
            json.dumps(genome, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._run(
            [
                sys.executable,
                "-m",
                "fevx_cse",
                "--database",
                str(database_path),
                "init",
            ]
        )
        self._run(
            [
                sys.executable,
                "-m",
                "fevx_cse",
                "--database",
                str(database_path),
                "analyse",
                "--mission",
                str(mission_path),
                "--genome",
                str(genome_path),
                "--run-id",
                f"EVIDENCEOPS-FEVX-{packet['packet_id']}",
                "--output",
                str(output_path),
            ]
        )
        analysis = json.loads(output_path.read_text(encoding="utf-8"))
        module_order = list(analysis.get("module_order", []))
        if len(module_order) != 10:
            raise RuntimeError(
                f"expected 10 base CSE modules, received {len(module_order)}"
            )
        return {
            "runtime": "fevx_cse_1_1_installed_wheel",
            "module_count": len(module_order),
            "module_order": module_order,
            "output_hash": analysis.get("output_hash") or digest(analysis),
            "final_recommendation": analysis.get("final_recommendation"),
            "maturity_state": analysis.get("maturity_state"),
            "authority_boundary": analysis.get("authority_boundary"),
            "module_results": analysis.get("module_results", []),
            "compatibility": compatibility,
        }


class FixtureBaseRunner:
    """Deterministic dependency-injection runner for boundary unit tests only."""

    MODULE_ORDER = [
        "TELOS", "KAIROS", "GALILEO", "PARALLAX", "SOCIUS",
        "PACTUM", "SEMIOTICA", "ARGUS", "PROMETHEUS", "PRAXIS",
    ]

    def run(
        self,
        packet: dict[str, Any],
        repo_root: Path,
        work_dir: Path,
    ) -> dict[str, Any]:
        payload = {
            "objective": packet["mission"]["objective"],
            "requested_outcome": packet["mission"]["requested_outcome"],
            "case_wall_id": packet["case_wall_id"],
            "source_ids": [row["source_id"] for row in packet["sources"]],
            "fact_ids": [row["fact_id"] for row in packet["verified_facts"]],
        }
        return {
            "runtime": "fixture_boundary_test_only",
            "module_count": 10,
            "module_order": self.MODULE_ORDER,
            "output_hash": digest(payload),
            "final_recommendation": "HELD_FOR_EVIDENCEOPS_REVIEW",
            "maturity_state": "UNIT_TEST_FIXTURE",
            "authority_boundary": "A1_INTERNAL",
            "module_results": [
                {"system": name, "state": "FIXTURE_ONLY"}
                for name in self.MODULE_ORDER
            ],
            "compatibility": {"state": "NOT_APPLICABLE_TO_FIXTURE"},
        }
