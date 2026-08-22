#!/usr/bin/env python3
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from frontier_benchmark_engine import load_knowledgebase
from frontier_source_refresh import (
    normalized_text_digest,
    observe_sources,
    persist_observation,
)


BASE = Path(__file__).resolve().parent


def fake_fetch_factory(body_by_url):
    def fetch(url, timeout):
        value = body_by_url.get(url, b"<html><body>stable</body></html>")
        if isinstance(value, Exception):
            raise value
        return 200, {"Content-Type": "text/html", "ETag": "test"}, value
    return fetch


class SourceRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.knowledgebase = load_knowledgebase(BASE / "frontier_knowledgebase_v2.json")
        cls.now = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)

    def test_html_normalization_ignores_scripts_and_whitespace(self):
        first, _ = normalized_text_digest(
            b"<html><script>volatile()</script><body>Hello   world</body></html>",
            "text/html",
        )
        second, _ = normalized_text_digest(
            b"<html><script>different()</script><body> Hello world </body></html>",
            "text/html",
        )
        self.assertEqual(first, second)

    def test_first_observation_opens_review_without_score_promotion(self):
        observation = observe_sources(
            self.knowledgebase,
            observed_at=self.now,
            fetcher=fake_fetch_factory({}),
        )
        self.assertGreater(len(observation["reviewQueue"]), 0)
        self.assertFalse(observation["automaticScorePromotionAllowed"])
        self.assertTrue(
            all(
                not item["automaticScorePromotionAllowed"]
                for item in observation["reviewQueue"]
            )
        )

    def test_identical_replay_is_unchanged(self):
        first = observe_sources(
            self.knowledgebase,
            observed_at=self.now,
            fetcher=fake_fetch_factory({}),
        )
        second = observe_sources(
            self.knowledgebase,
            observed_at=datetime(2026, 8, 22, 15, 0, tzinfo=timezone.utc),
            prior=first,
            fetcher=fake_fetch_factory({}),
        )
        remote = [item for item in second["sources"] if item["url"].startswith("https://")]
        self.assertTrue(all(item["state"] == "UNCHANGED" for item in remote))
        self.assertEqual(second["changedSourceCount"], 0)
        self.assertEqual(first["observationDigest"], second["observationDigest"])

    def test_changed_source_opens_semantic_review(self):
        first = observe_sources(
            self.knowledgebase,
            observed_at=self.now,
            fetcher=fake_fetch_factory({}),
        )
        target = next(
            item for item in self.knowledgebase["sources"] if item["url"].startswith("https://")
        )
        second = observe_sources(
            self.knowledgebase,
            observed_at=datetime(2026, 8, 22, 15, 0, tzinfo=timezone.utc),
            prior=first,
            fetcher=fake_fetch_factory(
                {target["url"]: b"<html><body>material new capability</body></html>"}
            ),
        )
        changed = [item for item in second["sources"] if item["state"] == "CHANGED_REVIEW_REQUIRED"]
        self.assertEqual([item["sourceId"] for item in changed], [target["id"]])
        review = next(item for item in second["reviewQueue"] if item["sourceId"] == target["id"])
        self.assertFalse(review["automaticScorePromotionAllowed"])

    def test_fetch_failure_preserves_failure_state(self):
        target = next(
            item for item in self.knowledgebase["sources"] if item["url"].startswith("https://")
        )
        observation = observe_sources(
            self.knowledgebase,
            observed_at=self.now,
            fetcher=fake_fetch_factory({target["url"]: TimeoutError("bounded")}),
        )
        failure = next(item for item in observation["sources"] if item["sourceId"] == target["id"])
        self.assertEqual(failure["state"], "FETCH_FAILED")
        self.assertGreater(observation["failedSourceCount"], 0)

    def test_persistence_is_change_only_and_journal_is_append_only(self):
        observation = observe_sources(
            self.knowledgebase,
            observed_at=self.now,
            fetcher=fake_fetch_factory({}),
        )
        with tempfile.TemporaryDirectory() as directory:
            first = persist_observation(observation, directory)
            second = persist_observation(copy.deepcopy(observation), directory)
            self.assertEqual(first["state"], "MATERIAL_OBSERVATION_WRITTEN")
            self.assertEqual(second["state"], "NO_CHANGE_NO_SNAPSHOT_WRITE")
            index = json.loads((Path(directory) / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["snapshots"]), 1)
            journal = (Path(directory) / "refresh-journal.ndjson").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(journal), 1)


if __name__ == "__main__":
    unittest.main()
