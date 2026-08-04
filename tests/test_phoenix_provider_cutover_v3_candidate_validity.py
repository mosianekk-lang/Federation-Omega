from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "phoenix" / "ops-template"
PHOENIX = ROOT / "phoenix"
SOURCE_SHA = "b" * 40
MOVED_SHA = "c" * 40
NOW = datetime(2026, 8, 5, 0, 0, tzinfo=timezone.utc)


class CandidateValidityTests(unittest.TestCase):
    def stage_ops(self, directory: str) -> Path:
        stage = Path(directory) / "ops"
        (stage / "governance").mkdir(parents=True)
        copies = {
            TEMPLATE / "provider_cutover_candidate.py": stage / "provider_cutover_candidate.py",
            TEMPLATE / "provider_cutover_guarded.py": stage / "provider_cutover_guarded.py",
            TEMPLATE / "provider_cutover_v3_live_guard.py": stage / "provider_cutover_v3_live_guard.py",
            TEMPLATE / "governance" / "CUTOVER_CANDIDATE_CONTRACT.json": stage / "governance" / "CUTOVER_CANDIDATE_CONTRACT.json",
            TEMPLATE / "governance" / "APPLY_ENTRYPOINT.json": stage / "governance" / "APPLY_ENTRYPOINT.json",
            PHOENIX / "provider_cutover_authorized_executor.py": stage / "provider_cutover.py",
            PHOENIX / "provider_cutover_authorization_use.py": stage / "provider_cutover_authorization_use.py",
            PHOENIX / "provider_cutover_v3_1.py": stage / "provider_cutover_v3_1.py",
            PHOENIX / "provider_cutover_v3.py": stage / "provider_cutover_v3_base.py",
            PHOENIX / "provider_cutover_outcome_reconciler.py": stage / "provider_cutover_outcome_reconciler.py",
        }
        for source, destination in copies.items():
            self.assertTrue(source.is_file(), source)
            shutil.copy2(source, destination)
        return stage

    def load_candidate(self, stage: Path):
        name = f"candidate_validity_test_{id(stage)}"
        spec = importlib.util.spec_from_file_location(name, stage / "provider_cutover_candidate.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def write_export_receipt(self, directory: Path, core: Path, ops: Path) -> Path:
        receipt = {
            "schema": "FEDOMEGA-PHOENIX-EXPORT-MANIFEST-1",
            "status": "VERIFIED",
            "source_sha": SOURCE_SHA,
            "core": {"sha256": hashlib.sha256(core.read_bytes()).hexdigest()},
            "ops": {"sha256": hashlib.sha256(ops.read_bytes()).hexdigest()},
        }
        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
        path = directory / "export-receipt.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return path

    def decision(self, candidate: dict[str, object]) -> dict[str, object]:
        return {
            "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-1",
            "status": "AUTHORIZED_APPLY",
            "authorization_id": "AO-PHX-AUTH-CANDIDATE-001",
            "authorization_sha256": "a" * 64,
            "source_sha": candidate["source_sha"],
            "core_archive_sha256": candidate["core_archive_sha256"],
            "ops_archive_sha256": candidate["ops_archive_sha256"],
            "authority_mode": "INSTALLATION_TEMPLATE",
            "expires_at": "2026-08-05T01:00:00+00:00",
            "owner_authority_preserved": True,
            "credential_value_recorded": False,
            "external_commercial_gates_advanced": False,
        }

    def make_candidate(self, module, directory: Path, core: Path, ops: Path):
        receipt = self.write_export_receipt(directory, core, ops)
        return module.build_candidate(
            source_sha=SOURCE_SHA,
            core_archive=core,
            ops_archive=ops,
            export_receipt_path=receipt,
            issue_number=166,
            provider_run_id=123,
            cutover_artifact_id=456,
            freeze_artifact_id=789,
            generated_at=NOW,
        )

    def test_candidate_generation_is_hash_bound_and_non_circular(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.stage_ops(directory)
            module = self.load_candidate(stage)
            core = Path(directory) / "core.tar.gz"
            ops = Path(directory) / "ops.tar.gz"
            core.write_bytes(b"core")
            ops.write_bytes(b"ops")
            candidate = self.make_candidate(module, Path(directory), core, ops)
            module.verify_candidate_integrity(candidate)
            self.assertEqual("COMPUTED_NOT_STORED", candidate["validity_semantics"])
            self.assertEqual("PROPOSED_FOR_PROVIDER_APPLY", candidate["candidate_state"])
            self.assertFalse(candidate["provider_apply_performed"])

    def test_source_drift_invalidates_before_authorization_state(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.stage_ops(directory)
            module = self.load_candidate(stage)
            core = Path(directory) / "core.tar.gz"
            ops = Path(directory) / "ops.tar.gz"
            core.write_bytes(b"core")
            ops.write_bytes(b"ops")
            candidate = self.make_candidate(module, Path(directory), core, ops)
            state = Path(directory) / "state"
            result = module.execute_candidate_cutover(
                candidate,
                self.decision(candidate),
                state_dir=state,
                execution_id="candidate-execution-001",
                core_archive=core,
                ops_archive=ops,
                provider_receipt_path=Path(directory) / "provider.json",
                now=NOW,
                provider_authority_available=True,
                source_head_reader=lambda _owner, _legacy: MOVED_SHA,
            )
            self.assertEqual("CANDIDATE_INVALIDATED", result["status"])
            self.assertEqual("SUPERSEDED_SOURCE_CHANGED", result["candidate_validity"]["status"])
            self.assertFalse(state.exists())
            self.assertFalse(result["provider_apply_invoked"])

    def test_archive_drift_invalidates_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.stage_ops(directory)
            module = self.load_candidate(stage)
            core = Path(directory) / "core.tar.gz"
            ops = Path(directory) / "ops.tar.gz"
            core.write_bytes(b"core")
            ops.write_bytes(b"ops")
            candidate = self.make_candidate(module, Path(directory), core, ops)
            core.write_bytes(b"changed")
            validity = module.validate_candidate(candidate, core_archive=core, ops_archive=ops, decision=self.decision(candidate))
            self.assertEqual("SUPERSEDED_CORE_ARCHIVE_CHANGED", validity["status"])
            self.assertFalse(validity["provider_apply_allowed"])

    def test_decision_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.stage_ops(directory)
            module = self.load_candidate(stage)
            core = Path(directory) / "core.tar.gz"
            ops = Path(directory) / "ops.tar.gz"
            core.write_bytes(b"core")
            ops.write_bytes(b"ops")
            candidate = self.make_candidate(module, Path(directory), core, ops)
            decision = self.decision(candidate)
            decision["ops_archive_sha256"] = "f" * 64
            validity = module.validate_candidate(candidate, core_archive=core, ops_archive=ops, decision=decision)
            self.assertEqual("INVALID_DECISION_OPS_BINDING", validity["status"])

    def test_candidate_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.stage_ops(directory)
            module = self.load_candidate(stage)
            core = Path(directory) / "core.tar.gz"
            ops = Path(directory) / "ops.tar.gz"
            core.write_bytes(b"core")
            ops.write_bytes(b"ops")
            candidate = self.make_candidate(module, Path(directory), core, ops)
            candidate["source_sha"] = MOVED_SHA
            with self.assertRaisesRegex(module.CandidateValidityError, "embedded SHA"):
                module.verify_candidate_integrity(candidate)

    def test_contract_names_candidate_launcher_as_canonical(self):
        contract = json.loads((TEMPLATE / "governance" / "CUTOVER_CANDIDATE_CONTRACT.json").read_text())
        entrypoint = json.loads((TEMPLATE / "governance" / "APPLY_ENTRYPOINT.json").read_text())
        self.assertEqual("provider_cutover_candidate.py", contract["canonical_apply_entrypoint"])
        self.assertTrue(contract["candidate_generated_after_merge"])
        self.assertTrue(contract["validity_computed_not_stored"])
        self.assertEqual("provider_cutover_candidate.py", entrypoint["canonical_apply_entrypoint"])
        self.assertEqual("INTERNAL_COMPONENT_DO_NOT_INVOKE_DIRECTLY", entrypoint["guarded_entrypoint_status"])


if __name__ == "__main__":
    unittest.main()
