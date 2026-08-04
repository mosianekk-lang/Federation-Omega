from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "phoenix" / "ops-template"
PHOENIX = ROOT / "phoenix"
SOURCE_SHA = "b" * 40
MOVED_SHA = "c" * 40
NOW = datetime(2026, 8, 4, 21, 0, tzinfo=timezone.utc)


class GuardedLauncherTests(unittest.TestCase):
    def stage_ops(self, directory: str) -> Path:
        stage = Path(directory) / "ops"
        (stage / "governance").mkdir(parents=True)
        copies = {
            TEMPLATE / "provider_cutover_guarded.py": stage / "provider_cutover_guarded.py",
            TEMPLATE / "provider_cutover_v3_live_guard.py": stage / "provider_cutover_v3_live_guard.py",
            TEMPLATE / "governance" / "APPLY_ENTRYPOINT.json": stage / "governance" / "APPLY_ENTRYPOINT.json",
            PHOENIX / "provider_cutover_authorized_executor.py": stage / "provider_cutover.py",
            PHOENIX / "provider_cutover_authorization_use.py": stage / "provider_cutover_authorization_use.py",
            PHOENIX / "provider_cutover_v3_1.py": stage / "provider_cutover_v3_1.py",
            PHOENIX / "provider_cutover_v3.py": stage / "provider_cutover_v3_base.py",
        }
        for source, destination in copies.items():
            self.assertTrue(source.is_file(), source)
            shutil.copy2(source, destination)
        return stage

    def load_launcher(self, stage: Path):
        name = f"guarded_launcher_test_{id(stage)}"
        spec = importlib.util.spec_from_file_location(
            name, stage / "provider_cutover_guarded.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def decision(self, core: Path, ops: Path) -> dict[str, object]:
        return {
            "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-1",
            "status": "AUTHORIZED_APPLY",
            "authorization_id": "AO-PHX-AUTH-GUARD-001",
            "authorization_sha256": "a" * 64,
            "source_sha": SOURCE_SHA,
            "core_archive_sha256": hashlib.sha256(core.read_bytes()).hexdigest(),
            "ops_archive_sha256": hashlib.sha256(ops.read_bytes()).hexdigest(),
            "authority_mode": "INSTALLATION_TEMPLATE",
            "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
            "owner_authority_preserved": True,
            "credential_value_recorded": False,
            "external_commercial_gates_advanced": False,
        }

    def test_moved_source_is_rejected_before_authorization_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stage = self.stage_ops(directory)
            launcher = self.load_launcher(stage)
            core = Path(directory) / "core.tar.gz"
            ops = Path(directory) / "ops.tar.gz"
            core.write_bytes(b"core")
            ops.write_bytes(b"ops")
            state = Path(directory) / "state"
            with self.assertRaisesRegex(
                launcher.GuardError, "moved after authorization"
            ):
                launcher.execute_guarded_cutover(
                    self.decision(core, ops),
                    state_dir=state,
                    execution_id="guard-execution-001",
                    source_sha=SOURCE_SHA,
                    core_archive=core,
                    ops_archive=ops,
                    provider_receipt_path=Path(directory) / "receipt.json",
                    now=NOW,
                    provider_authority_available=True,
                    source_head_reader=lambda _owner, _legacy: MOVED_SHA,
                )
            self.assertFalse(state.exists())

    def test_post_apply_started_runner_rechecks_and_forwards_expected_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stage = self.stage_ops(directory)
            launcher = self.load_launcher(stage)
            calls: list[tuple[list[str], dict[str, str]]] = []

            def fake_run(command, env, check):
                calls.append((list(command), dict(env)))
                return types.SimpleNamespace(returncode=0)

            launcher.subprocess.run = fake_run
            command = [
                sys.executable,
                str(stage / "provider_cutover_v3_1.py"),
                "--apply",
            ]
            result = launcher.guarded_runner(
                SOURCE_SHA,
                "mosianekk-lang",
                "Federation-Omega",
                lambda _owner, _legacy: SOURCE_SHA,
            )(command)
            self.assertEqual(0, result)
            self.assertEqual(1, len(calls))
            guarded, environment = calls[0]
            self.assertEqual(
                "provider_cutover_v3_live_guard.py", Path(guarded[1]).name
            )
            self.assertEqual(["--expected-source-sha", SOURCE_SHA], guarded[-2:])
            self.assertEqual("1", environment["FEDOMEGA_GUARDED_APPLY"])

    def test_provider_controller_checks_head_after_authority_before_mutation(self) -> None:
        text = (TEMPLATE / "provider_cutover_v3_live_guard.py").read_text(
            encoding="utf-8"
        )
        authority = text.index("authority = ORIGINAL_DETECT")
        live_ref = text.index("/git/ref/heads/main")
        dispatch = text.index("return V31.main()")
        self.assertLess(authority, live_ref)
        self.assertLess(live_ref, dispatch)
        self.assertIn("Legacy main moved after authorization", text)
        self.assertIn('payload["source_sha"] = EXPECTED_SOURCE_SHA', text)

    def test_contract_names_canonical_route_without_false_block_claim(self) -> None:
        contract = json.loads(
            (TEMPLATE / "governance" / "APPLY_ENTRYPOINT.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "provider_cutover_authority_bound.py",
            contract["canonical_apply_entrypoint"],
        )
        self.assertEqual(
            "provider_cutover_candidate.py", contract["candidate_entrypoint"]
        )
        self.assertEqual(
            "INTERNAL_COMPONENT_DO_NOT_INVOKE_DIRECTLY",
            contract["candidate_entrypoint_status"],
        )
        self.assertTrue(contract["provider_authority_receipt_required"])
        self.assertEqual(
            "DEPRECATED_NON_CANONICAL_DO_NOT_APPLY_DIRECTLY",
            contract["legacy_entrypoint_status"],
        )
        self.assertFalse(contract["legacy_entrypoint_technically_blocked"])
        self.assertTrue(contract["pre_reservation_live_source_check"])
        self.assertTrue(contract["post_apply_started_live_source_recheck"])
        self.assertTrue(contract["pre_mutation_provider_head_check"])
        self.assertTrue(contract["provider_receipt_source_sha_binding"])

    def test_guarded_receipt_requires_authorized_source_sha(self) -> None:
        text = (TEMPLATE / "provider_cutover_guarded.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'receipt.get("source_sha") != preflight.get("source_sha")', text
        )
        self.assertIn(
            "provider receipt source_sha does not match authorized source", text
        )


if __name__ == "__main__":
    unittest.main()
