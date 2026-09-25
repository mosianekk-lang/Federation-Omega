from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RESPAWN = ROOT / "respawn"
if str(RESPAWN) not in sys.path:
    sys.path.insert(0, str(RESPAWN))

import bootstrap_service as bs
import chatgpt_context as cc

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector

POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
BASE = "1" * 40
HEAD = "2" * 40


class RespawnChatGPTContextContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_state_path = bs.STATE_PATH
        self._tmp = tempfile.TemporaryDirectory()
        bs.STATE_PATH = Path(self._tmp.name) / "runtime_state.json"

    def tearDown(self) -> None:
        bs.STATE_PATH = self._original_state_path
        self._tmp.cleanup()

    def _set_state(self, payload: dict) -> None:
        bs.STATE_PATH.write_text(json.dumps(payload), encoding="utf-8")

    def test_current_state_does_not_promote_verified_or_proposed(self) -> None:
        self._set_state(
            {
                "deltas": [
                    {
                        "delta_id": "cur",
                        "source_system": "Federation Omega",
                        "summary": "Total Recall context",
                        "status": "CURRENT_READBACK_VERIFIED",
                    },
                    {
                        "delta_id": "hist",
                        "source_system": "Federation Omega",
                        "summary": "Total Recall context",
                        "status": "VERIFIED",
                    },
                    {
                        "delta_id": "draft",
                        "source_system": "Federation Omega",
                        "summary": "Total Recall context",
                        "status": "PROPOSED",
                    },
                ],
                "patterns": [],
                "bibliography": [],
                "conflicts": [],
            }
        )
        result = cc.get_current_state_impl(
            query="Total Recall", system="Federation Omega"
        )
        self.assertEqual(
            [item["delta_id"] for item in result["claimable_current"]], ["cur"]
        )
        self.assertEqual(
            [item["delta_id"] for item in result["supporting_verified_not_current_by_itself"]],
            ["hist"],
        )
        self.assertEqual(
            [item["delta_id"] for item in result["gated_or_historical"]], ["draft"]
        )
        self.assertEqual(
            result["current_state_proof"], "CURRENT_PROVEN_STRICT_LOCAL_STATE"
        )

    def test_coverage_fails_closed_without_ledger(self) -> None:
        self._set_state(
            {
                "deltas": [],
                "patterns": [],
                "bibliography": [{"entry_id": "1"}],
                "conflicts": [],
            }
        )
        result = cc.get_corpus_coverage_impl()
        self.assertEqual(result["coverage_state"], "UNKNOWN")
        self.assertFalse(result["full_account_history_proven"])
        self.assertEqual(result["bibliography_entries_seen"], 1)

    def test_export_coverage_does_not_become_account_totality(self) -> None:
        self._set_state(
            {
                "deltas": [],
                "patterns": [],
                "bibliography": [],
                "conflicts": [],
                "coverage": {
                    "completeness_state": "COMPLETE_FOR_PROVIDED_EXPORT",
                    "conversations_ingested": 42,
                },
            }
        )
        result = cc.get_corpus_coverage_impl()
        self.assertEqual(result["coverage_state"], "COMPLETE_FOR_PROVIDED_EXPORT")
        self.assertFalse(result["full_account_history_proven"])

    def test_compactor_removes_full_bible_and_bounds_excerpt(self) -> None:
        text = "A" * 8000 + "\nTotal Recall mission checkpoint\n" + "B" * 8000
        raw = {
            "already_solved_candidates": list(range(30)),
            "recent_deltas": list(range(30)),
            "open_conflicts": list(range(30)),
            "provider_context": {
                "provider_readback": True,
                "canonical_bible_text": text,
                "recent_sync_events": list(range(30)),
                "shared_learnings": list(range(30)),
            },
        }
        out = cc.compact_bootstrap_result(
            raw, terms=["Total Recall"], max_bible_chars=2000
        )
        provider = out["provider_context"]
        self.assertNotIn("canonical_bible_text", provider)
        self.assertLessEqual(provider["canonical_bible_excerpt_chars"], 2000)
        self.assertTrue(provider["canonical_bible_truncated"])
        self.assertEqual(len(provider["recent_sync_events"]), 12)

    def test_resume_compiles_small_packet_without_claiming_full_history(self) -> None:
        self._set_state(
            {
                "deltas": [
                    {
                        "delta_id": "checkpoint-1",
                        "source_system": "Federation Omega",
                        "matter": "Total Recall",
                        "summary": "Resume Total Recall mission",
                        "status": "CURRENT_READBACK_VERIFIED",
                    }
                ],
                "patterns": [],
                "bibliography": [],
                "conflicts": [],
            }
        )
        with mock.patch.object(
            bs, "provider_adapter", return_value={"available": False, "reason": "test"}
        ):
            result = cc.resume_mission_impl(
                system="Federation Omega",
                mission="Resume Total Recall mission",
                matter="Total Recall",
                chat_ref="test",
            )
        self.assertEqual(
            result["continuation_mode"], "RESUME_FROM_EXISTING_EVIDENCE"
        )
        self.assertEqual(
            result["current_state"]["current_state_proof"],
            "CURRENT_PROVEN_STRICT_LOCAL_STATE",
        )
        self.assertFalse(result["coverage"]["full_account_history_proven"])
        self.assertTrue(result["next_executable_action"])

    def test_bootstrap_exposes_runtime_sovereignty_contract(self) -> None:
        self._set_state({"deltas": [], "patterns": [], "bibliography": [], "conflicts": []})
        with mock.patch.object(
            bs, "provider_adapter", return_value={"available": False, "reason": "test"}
        ):
            result = bs.bootstrap(bs.SpawnRequest(system="Federation Omega"))
        self.assertIn("INSTRUCTION_WITHOUT_ENFORCEMENT_IS_NOT_CONTROL", result["bootstrap_invariants"])
        self.assertEqual(
            result["runtime_sovereignty"]["contract_id"],
            "FUSE-SOL62-RUNTIME-SOVEREIGNTY-V1",
        )
        self.assertEqual(
            result["runtime_sovereignty"]["chatgpt_role"],
            "Replaceable intelligence/execution provider and detachable client; not FUSE mission owner or sovereign terminal-delivery authority.",
        )
        self.assertIn("run_output_mirror", result["bootstrap_order"])
        self.assertIn("terminal_delivery_gate", result["bootstrap_order"])
        self.assertTrue(result["delivery_rule"])

    def test_respawn_paths_select_scoped_court_without_full_fallback(self) -> None:
        policy = ProofPolicy.from_path(POLICY)
        changed = [
            "respawn/DEPLOYMENT.md",
            "respawn/Dockerfile",
            "respawn/README.md",
            "respawn/chatgpt_context.py",
            "respawn/mcp_server.py",
            "respawn/test_chatgpt_context.py",
            "governance/proofos_omega_policy_extension_respawn_v1.json",
            "tests/test_respawn_chatgpt_context_contract.py",
        ]
        impact = ImpactCompiler(policy).assess(changed)
        manifest = ProofSelector(policy).compile_manifest(
            base_sha=BASE, head_sha=HEAD, impact=impact
        )
        selected = {entry.test_id for entry in manifest.selected_tests}
        self.assertIn("RESPAWN", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("respawn_chatgpt_context_contract", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])
        self.assertTrue(manifest.selector_state["omission_proof_complete"])

    def test_unknown_future_production_path_still_fails_safe(self) -> None:
        policy = ProofPolicy.from_path(POLICY)
        impact = ImpactCompiler(policy).assess(["future_plane/new_runtime.py"])
        manifest = ProofSelector(policy).compile_manifest(
            base_sha=BASE, head_sha=HEAD, impact=impact
        )
        selected = {entry.test_id for entry in manifest.selected_tests}
        self.assertEqual(
            tuple(impact.unmapped_production_paths), ("future_plane/new_runtime.py",)
        )
        self.assertIn("full_federation_fallback", selected)
        self.assertTrue(manifest.selector_state["fallback_full_suite_activated"])


if __name__ == "__main__":
    unittest.main()
