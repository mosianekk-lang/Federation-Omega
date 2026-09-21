from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from fuse_sovereign.update import FuseUpdateClient, LLMUpdateBridge, UpdateError, _sha


def manifest(sequence=1):
    value = {
        "schema": "FUSE_UPDATE_MANIFEST_V1",
        "channel": "stable",
        "sequence": sequence,
        "issued_at": "2026-09-20T00:00:00Z",
        "valid_until": "2099-10-21T23:59:59Z",
        "min_client_version": "0.3.0",
        "authority_class": "DATA_ONLY_NO_EFFECT_AUTHORITY",
        "summary": "test",
        "capability_deltas": ["a"],
        "route_deltas": ["b"],
        "warnings": ["c"],
        "artifacts": [],
        "llm_context": {"operating_rule": "fresh wins", "effect_rule": "no authority"},
    }
    value["llm_context_sha256"] = _sha(value["llm_context"])
    body = dict(value)
    value["manifest_body_sha256"] = _sha(body)
    return value


class UpdateTests(TestCase):
    def make(self, td):
        return FuseUpdateClient(cache_dir=td, require_verified_commit=True)

    def test_valid_fetch_and_model_allowlist(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            m = manifest()
            with patch.object(c, "_get_json", side_effect=[
                {"commit": {"sha": "a"*40}},
                {"commit": {"verification": {"verified": True}}},
            ]), patch.object(c, "_get_text", return_value=json.dumps(m)):
                s = c.fetch()
            ctx = s.model_context()
            self.assertEqual(ctx["authority_boundary"], "DATA_ONLY_NO_EFFECT_AUTHORITY")
            self.assertNotIn("artifacts", ctx)
            self.assertEqual(ctx["sequence"], 1)

    def test_unverified_commit_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            with patch.object(c, "_get_json", side_effect=[
                {"commit": {"sha": "a"*40}},
                {"commit": {"verification": {"verified": False}}},
            ]):
                with self.assertRaisesRegex(UpdateError, "UNVERIFIED"):
                    c.fetch()

    def test_manifest_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            m = manifest(); m["summary"] = "tampered"
            with self.assertRaisesRegex(UpdateError, "BODY_HASH"):
                c._validate_manifest(m, source_commit="a"*40, verified_commit=True)

    def test_context_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            m = manifest(); m["llm_context"]["x"] = "tampered"
            with self.assertRaisesRegex(UpdateError, "CONTEXT_HASH"):
                c._validate_manifest(m, source_commit="a"*40, verified_commit=True)

    def test_rollback_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            Path(td, "state.json").write_text(json.dumps({"highest_sequence": 5, "last_commit": "b"*40}))
            with self.assertRaisesRegex(UpdateError, "ROLLBACK"):
                c._validate_manifest(manifest(sequence=4), source_commit="a"*40, verified_commit=True)

    def test_same_sequence_different_commit_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            Path(td, "state.json").write_text(json.dumps({"highest_sequence": 1, "last_commit": "b"*40}))
            with self.assertRaisesRegex(UpdateError, "SEQUENCE_REUSE"):
                c._validate_manifest(manifest(sequence=1), source_commit="a"*40, verified_commit=True)

    def test_cached_snapshot_on_network_failure(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            Path(td, "llm_snapshot.json").write_text(json.dumps({"schema": "FUSE_LLM_UPDATE_SNAPSHOT_V1", "sequence": 1}))
            with patch.object(c, "fetch", side_effect=UpdateError("DOWN")):
                value = c.fetch_for_llm()
            self.assertEqual(value["freshness"], "STALE_CACHED")
            self.assertEqual(value["update_error"], "DOWN")

    def test_bridge_returns_data_only_context(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.make(td)
            with patch.object(c, "fetch_for_llm", return_value={"authority_boundary": "DATA_ONLY_NO_EFFECT_AUTHORITY"}):
                self.assertEqual(LLMUpdateBridge(c).fetch_context()["authority_boundary"], "DATA_ONLY_NO_EFFECT_AUTHORITY")
