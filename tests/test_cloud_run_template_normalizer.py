from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "ops/federation_omega_operator/scripts/cloud_run_template_normalizer.py"
)
SPEC = importlib.util.spec_from_file_location("cloud_run_template_normalizer", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CloudRunTemplateNormalizerTests(unittest.TestCase):
    def test_v1_knative_secret_is_detected_without_raw_direct_values(self) -> None:
        document = {
            "metadata": {"name": "federation-omega-operator"},
            "spec": {"template": {"spec": {"containers": [{"env": [
                {"name": "OPERATOR_AUDIENCE", "value": "private-value"},
                {"name": "FO_ADMIN_TOKEN", "valueFrom": {"secretKeyRef": {
                    "name": "fo-operator-admin-token", "key": "latest"
                }}},
            ]}]}}},
        }
        result = MODULE.normalize(document, "federation-omega-operator")
        self.assertEqual(["FO_ADMIN_TOKEN"], result["secret_backed_names"])
        self.assertEqual(["OPERATOR_AUDIENCE"], result["direct_names"])
        self.assertFalse(result["raw_values_emitted"])
        self.assertNotIn("private-value", json.dumps(result))

    def test_v2_value_source_secret_is_detected(self) -> None:
        document = {
            "name": "federation-omega-operator",
            "template": {"containers": [{"env": [{
                "name": "FO_ADMIN_TOKEN",
                "valueSource": {"secretKeyRef": {
                    "secret": "fo-operator-admin-token", "version": "7"
                }},
            }]}]},
        }
        result = MODULE.normalize(document, "federation-omega-operator")
        binding = result["bindings"][0]
        self.assertEqual("secret", binding["kind"])
        self.assertEqual("fo-operator-admin-token", binding["secret_name"])
        self.assertEqual("7", binding["secret_version"])

    def test_nested_revision_shape_is_detected(self) -> None:
        document = {
            "metadata": {"name": "federation-omega-operator"},
            "status": {"latestCreatedRevision": {"spec": {"containers": [{"env": [{
                "name": "FO_ADMIN_TOKEN",
                "value_from": {"secret_key_ref": {
                    "name": "fo-operator-admin-token", "key": "latest"
                }},
            }]}]}}},
        }
        result = MODULE.normalize(document, "federation-omega-operator")
        self.assertEqual(1, result["secret_backed_count"])

    def test_unknown_secret_shape_fails_closed(self) -> None:
        document = {
            "metadata": {"name": "federation-omega-operator"},
            "spec": {"template": {"spec": {"containers": [{"env": [{
                "name": "FO_ADMIN_TOKEN",
                "valueFrom": {"futureSecret": {"id": "opaque"}},
            }]}]}}},
        }
        with self.assertRaisesRegex(
            MODULE.TemplateNormalizationError, "UNRECOGNIZED_SECRET_BINDING"
        ):
            MODULE.normalize(document, "federation-omega-operator")

    def test_service_identity_mismatch_fails_closed(self) -> None:
        document = {
            "metadata": {"name": "wrong-service"},
            "spec": {"template": {"spec": {"containers": [{"env": []}]}}},
        }
        with self.assertRaisesRegex(
            MODULE.TemplateNormalizationError, "SERVICE_IDENTITY_MISMATCH"
        ):
            MODULE.normalize(document, "federation-omega-operator")

    def test_semantic_digest_is_deterministic(self) -> None:
        document = {
            "metadata": {"name": "federation-omega-operator"},
            "spec": {"template": {"spec": {"containers": [
                {"env": [{"name": "A", "value": "one"}]},
                {"env": [{"name": "B", "value": "two"}]},
            ]}}},
        }
        first = MODULE.normalize(document, "federation-omega-operator")
        second = MODULE.normalize(document, "federation-omega-operator")
        self.assertEqual(first["semantic_sha256"], second["semantic_sha256"])

    def test_output_does_not_persist_provider_source(self) -> None:
        document = {
            "metadata": {"name": "federation-omega-operator"},
            "spec": {"template": {"spec": {"containers": [{"env": [{
                "name": "FO_ADMIN_TOKEN",
                "valueFrom": {"secretKeyRef": {
                    "name": "fo-operator-admin-token", "key": "latest"
                }},
            }]}]}}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "provider.json"
            output = Path(tmp) / "normalized.json"
            source.write_text(json.dumps(document), encoding="utf-8")
            result = MODULE.normalize(
                json.loads(source.read_text(encoding="utf-8")),
                "federation-omega-operator",
            )
            output.write_text(json.dumps(result), encoding="utf-8")
            emitted = output.read_text(encoding="utf-8")
            self.assertIn("FO_ADMIN_TOKEN", emitted)
            self.assertNotIn('"valueFrom"', emitted)
            self.assertNotIn('"value"', emitted)


if __name__ == "__main__":
    unittest.main()
