from __future__ import annotations

import json
import unittest

from bubbles.provider_surface_probe import CommandResult, ProbeHooks, run_probe


class BubblesGcloudProviderReadbackTests(unittest.TestCase):
    @staticmethod
    def _http(url, **kwargs):
        body = kwargs.get("body")
        if "federation-omega-operator" in url and url.endswith("/health"):
            return {"http_status": 200, "body": {"ok": True, "status": "OPERATOR_READY"}}
        if "federation-omega-operator" in url and body is None:
            return {
                "http_status": 200,
                "body": {
                    "ok": True,
                    "allowedActions": ["STATUS", "READ_CLOUD_RUN_SERVICE"],
                },
            }
        if "archon-admin-plane" in url and url.endswith("openapi.yaml"):
            return {"http_status": 200, "body": {"text": "openapi: 3.1.0"}}
        if "archon-admin-plane" in url:
            return {"http_status": 404, "body": {"text": "Cannot GET /"}}
        if "script.google.com" in url:
            return {"http_status": 404, "body": {"text": "reachable"}}
        if "afeme-sovereign" in url:
            return {"http_status": 403, "body": {"text": "Forbidden"}}
        raise AssertionError(url)

    @staticmethod
    def _command_with_number(project_number: str):
        def command(args):
            joined = " ".join(args)
            if "gcloud auth list" in joined:
                return CommandResult(
                    0,
                    "bubbles-readonly@sov-hybrid-suite.iam.gserviceaccount.com\n",
                    "",
                )
            if "gcloud projects describe" in joined:
                return CommandResult(
                    0,
                    json.dumps(
                        {
                            "projectId": "sov-hybrid-suite",
                            "projectNumber": project_number,
                            "name": "sov-hybrid-suite",
                            "lifecycleState": "ACTIVE",
                        }
                    ),
                    "",
                )
            if "gcloud run services describe" in joined:
                return CommandResult(
                    0,
                    json.dumps(
                        {
                            "metadata": {"name": "architron9", "generation": 42},
                            "spec": {
                                "template": {
                                    "spec": {
                                        "serviceAccountName": "architron-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
                                        "containers": [{"image": "africa-south1-docker.pkg.dev/sov-hybrid-suite/runtime/architron@sha256:abc"}],
                                    }
                                }
                            },
                            "status": {
                                "latestReadyRevisionName": "architron9-00042-test",
                                "latestCreatedRevisionName": "architron9-00042-test",
                                "url": "https://architron9-example.a.run.app",
                                "traffic": [{"revisionName": "architron9-00042-test", "percent": 100}],
                            },
                        }
                    ),
                    "",
                )
            if "gcloud run revisions describe" in joined:
                return CommandResult(
                    0,
                    json.dumps(
                        {
                            "metadata": {
                                "name": "architron9-00042-test",
                                "labels": {"serving.knative.dev/service": "architron9"},
                            },
                            "spec": {
                                "serviceAccountName": "architron-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
                                "containers": [{"image": "africa-south1-docker.pkg.dev/sov-hybrid-suite/runtime/architron@sha256:abc"}],
                            },
                            "status": {"imageDigest": "sha256:abc", "conditions": []},
                        }
                    ),
                    "",
                )
            if "gcloud builds list" in joined:
                return CommandResult(
                    0,
                    json.dumps(
                        [
                            {
                                "id": "build-1",
                                "status": "SUCCESS",
                                "createTime": "2026-08-15T10:00:00Z",
                                "finishTime": "2026-08-15T10:01:00Z",
                                "images": ["architron@sha256:abc"],
                                "source": {"repoSource": {"repoName": "Federation-Omega"}},
                                "substitutions": {"REVISION_ID": "architron9-00042-test"},
                                "tags": ["architron9"],
                            }
                        ]
                    ),
                    "",
                )
            if "gcloud secrets versions access" in joined:
                return CommandResult(1, "", "PERMISSION_DENIED")
            if "gcloud auth print-identity-token" in joined:
                return CommandResult(1, "", "PERMISSION_DENIED")
            return CommandResult(1, "", f"unsupported command: {joined}")

        return command

    def test_matching_project_reads_live_revision_without_mutation(self):
        receipt = run_probe(
            ProbeHooks(
                http=self._http,
                command=self._command_with_number("257649435135"),
            )
        )
        cloud = receipt["google_cloud_readback"]
        self.assertEqual("PROVIDER_REVISION_READBACK_VERIFIED", cloud["classification"])
        self.assertEqual("sov-hybrid-suite", cloud["project"]["projectId"])
        self.assertEqual("257649435135", cloud["project"]["projectNumber"])
        self.assertEqual("architron9-00042-test", cloud["cloudRunService"]["latestReadyRevision"])
        self.assertEqual("sha256:abc", cloud["latestReadyRevision"]["imageDigest"])
        self.assertEqual("build-1", cloud["recentBuilds"][0]["id"])
        self.assertFalse(cloud["mutationAttempted"])
        self.assertFalse(receipt["mutation_attempted"])
        self.assertFalse(receipt["secret_values_recorded"])

    def test_project_number_mismatch_blocks_cloud_run_probe(self):
        calls = []
        base = self._command_with_number("999999999999")

        def command(args):
            calls.append(" ".join(args))
            return base(args)

        receipt = run_probe(ProbeHooks(http=self._http, command=command))
        cloud = receipt["google_cloud_readback"]
        self.assertEqual("PROJECT_IDENTITY_MISMATCH", cloud["classification"])
        self.assertFalse(any("run services describe" in call for call in calls))
        self.assertFalse(any("builds list" in call for call in calls))
        self.assertFalse(receipt["mutation_attempted"])


if __name__ == "__main__":
    unittest.main()
