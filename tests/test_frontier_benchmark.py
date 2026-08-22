from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from benchmark_fabric.frontier_benchmark.engine import (
    BenchmarkError,
    evaluate,
    load_json,
    render_markdown,
)
from benchmark_fabric.frontier_benchmark.fetcher import (
    SourceRefreshError,
    fetch_one,
    refresh_all,
    validate_public_https_url,
)


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "benchmark_fabric" / "catalog" / "frontier_controls.json"
SOURCES = ROOT / "benchmark_fabric" / "catalog" / "official_sources.json"
BASELINE = ROOT / "benchmark_fabric" / "evidence" / "jarvis_baseline_2026-08-22.json"
FIXED_NOW = datetime(2026, 8, 22, 13, 0, tzinfo=timezone.utc)


class _Headers(dict):
    def get(self, key, default=None):  # noqa: ANN001
        return super().get(key, default)


class _Response:
    status = 200

    def __init__(self, url: str, body: bytes, content_type: str = "text/html") -> None:
        self._url = url
        self._body = body
        self.headers = _Headers({"Content-Type": content_type, "ETag": '"v1"'})
        self.closed = False

    def geturl(self):
        return self._url

    def read(self, maximum):
        return self._body[:maximum]

    def close(self):
        self.closed = True


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response

    def open(self, request, timeout):  # noqa: ANN001
        return self.response


class FrontierBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controls = load_json(CONTROLS)
        cls.sources = load_json(SOURCES)
        cls.baseline = load_json(BASELINE)

    def test_catalog_is_complete_and_deterministic(self):
        first = evaluate(self.controls, self.baseline, self.sources, as_of=FIXED_NOW)
        second = evaluate(self.controls, self.baseline, self.sources, as_of=FIXED_NOW)
        self.assertEqual(first, second)
        self.assertEqual(52, len(first["controls"]))
        self.assertEqual(13, len(first["domains"]))
        self.assertEqual("SUCCESS", first["terminalState"])
        self.assertTrue(first["reportSha256"].startswith("sha256:"))

    def test_truth_boundary_keeps_provider_and_production_unproven(self):
        report = evaluate(self.controls, self.baseline, self.sources, as_of=FIXED_NOW)
        self.assertEqual(0.0, report["scores"]["providerBoundCoveragePercent"])
        self.assertEqual(0.0, report["scores"]["productionProvenCoveragePercent"])
        self.assertNotEqual(100.0, report["scores"]["capabilityAlignmentPercent"])
        self.assertLessEqual(
            report["scores"]["evidenceAdjustedPercent"],
            report["scores"]["capabilityAlignmentPercent"],
        )

    def test_provider_maturity_fails_without_provider_proof(self):
        tampered = copy.deepcopy(self.baseline)
        record = next(row for row in tampered["evidence"] if row["controlId"] == "PO-01")
        record["maturity"] = 4
        record["evidenceRefs"] = ["configuration exists"]
        with self.assertRaisesRegex(BenchmarkError, "without provider proof"):
            evaluate(self.controls, tampered, self.sources, as_of=FIXED_NOW)

    def test_production_maturity_fails_without_production_proof(self):
        tampered = copy.deepcopy(self.baseline)
        record = next(row for row in tampered["evidence"] if row["controlId"] == "PO-01")
        record["maturity"] = 5
        record["evidenceRefs"] = ["one provider canary"]
        record["providerProof"] = True
        with self.assertRaisesRegex(BenchmarkError, "without production proof"):
            evaluate(self.controls, tampered, self.sources, as_of=FIXED_NOW)

    def test_unknown_comparator_source_fails_closed(self):
        tampered = copy.deepcopy(self.controls)
        tampered["controls"][0]["referenceSourceIds"].append("UNREGISTERED-SOURCE")
        with self.assertRaisesRegex(BenchmarkError, "unknown sources"):
            evaluate(tampered, self.baseline, self.sources, as_of=FIXED_NOW)

    def test_vendor_public_evidence_boundaries_are_explicit(self):
        for source in self.sources["sources"]:
            self.assertTrue(source["publicEvidenceBoundary"])
            if source["organization"].startswith("SoftBank"):
                self.assertIn(
                    source["evidenceClass"],
                    {"PUBLIC_OPERATIONAL_EVIDENCE", "PRESS_RELEASE", "CAREERS_PAGE"},
                )

    def test_markdown_exposes_scores_and_gates(self):
        report = evaluate(self.controls, self.baseline, self.sources, as_of=FIXED_NOW)
        rendered = render_markdown(report)
        self.assertIn("Capability alignment", rendered)
        self.assertIn("Production-proven coverage", rendered)
        self.assertIn("Highest-impact remaining evidence gates", rendered)
        self.assertIn(report["reportSha256"], rendered)

    def test_url_validator_rejects_non_https_unlisted_and_private_dns(self):
        allowed = {"docs.example.com"}
        public = lambda host: ["8.8.8.8"]
        self.assertEqual(
            "docs.example.com",
            validate_public_https_url("https://docs.example.com/page", allowed, resolver=public),
        )
        with self.assertRaisesRegex(SourceRefreshError, "NOT_HTTPS"):
            validate_public_https_url("http://docs.example.com/page", allowed, resolver=public)
        with self.assertRaisesRegex(SourceRefreshError, "NOT_ALLOWLISTED"):
            validate_public_https_url("https://evil.example/page", allowed, resolver=public)
        with self.assertRaisesRegex(SourceRefreshError, "NONPUBLIC"):
            validate_public_https_url(
                "https://docs.example.com/page", allowed, resolver=lambda host: ["127.0.0.1"]
            )

    def test_fetcher_hashes_normalized_text_without_credentials(self):
        body = b"<html><body><h1>Agent Runtime</h1><p>Evaluation and tracing.</p></body></html>"
        response = _Response("https://docs.example.com/page", body)
        source = {
            "id": "TEST",
            "url": "https://docs.example.com/page",
            "maxBytes": 10000,
            "timeoutSeconds": 5,
            "minimumTextCharacters": 10,
            "allowedContentTypes": ["text/html"],
            "watchTerms": ["agent", "evaluation"],
        }
        metadata, text = fetch_one(
            source,
            {"docs.example.com"},
            fetched_at=FIXED_NOW,
            resolver=lambda host: ["8.8.8.8"],
            opener=_Opener(response),
        )
        self.assertIn("Agent Runtime", text)
        self.assertEqual(1, metadata["watchSignals"]["agent"])
        self.assertFalse(metadata["retainedInSourceRepository"])
        self.assertTrue(metadata["snapshotSha256"].startswith("sha256:"))
        self.assertTrue(response.closed)

    def test_refresh_creates_review_proposal_but_never_mutates_catalog(self):
        payload = {
            "allowedHosts": ["docs.example.com"],
            "sources": [{
                "id": "TEST",
                "url": "https://docs.example.com/page",
                "reviewedNormalizedTextSha256": None,
                "controlIds": ["AO-01"],
            }],
        }

        def fake_fetch(source, allowed_hosts, fetched_at):  # noqa: ANN001
            metadata = {
                "sourceId": source["id"],
                "fetchedAt": "2026-08-22T13:00:00Z",
                "normalizedTextSha256": "sha256:candidate",
                "snapshotSha256": "sha256:snapshot",
            }
            return metadata, "reviewed source text"

        original = json.dumps(payload, sort_keys=True)
        with tempfile.TemporaryDirectory() as directory:
            manifest = refresh_all(payload, directory, fetched_at=FIXED_NOW, fetch=fake_fetch)
            proposal = json.loads(
                (Path(directory) / "knowledgebase" / "review-proposals.json").read_text()
            )
            self.assertEqual("SUCCESS", manifest["terminalState"])
            self.assertEqual("HUMAN_REVIEW_REQUIRED", proposal["proposals"][0]["decision"])
            self.assertFalse(proposal["proposals"][0]["automaticControlPromotion"])
            self.assertFalse(manifest["repositoryMutationAttempted"])
        self.assertEqual(original, json.dumps(payload, sort_keys=True))

    def test_workflow_is_read_only_pinned_and_scheduled(self):
        workflow_path = ROOT / ".github" / "workflows" / "frontier-benchmark.yml"
        if not workflow_path.exists():
            self.skipTest("repository workflows are intentionally excluded from standalone core exports")
        workflow = workflow_path.read_text()
        policy = json.loads((ROOT / "governance" / "github_airlock_policy.json").read_text())
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", workflow)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", workflow)
        self.assertIn(
            ".github/workflows/frontier-benchmark.yml",
            policy["active_workflow_allowlist"],
        )
        self.assertEqual(
            {"pull_request", "schedule", "workflow_dispatch"},
            set(policy["allowed_events"][".github/workflows/frontier-benchmark.yml"]),
        )


if __name__ == "__main__":
    unittest.main()
