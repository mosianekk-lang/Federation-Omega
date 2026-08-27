from __future__ import annotations

from contextlib import contextmanager
import json
import tempfile
import unittest
from pathlib import Path

from evidenceops.capital_intelligence_os.postgres_audit import PostgresAuditLedger
from evidenceops.capital_intelligence_os.postgres_store import PostgresStateStore
from evidenceops.capital_intelligence_os.provider_runtime import (
    ProviderRuntimeApplication,
    ProviderRuntimeConfig,
)


SHA = "c" * 40
TOKEN = "cios-production-lane-test-token-000001"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _Result:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return list(self._rows)


class _Connection:
    def __init__(self):
        self.statements: list[tuple[str, tuple | None]] = []

    def execute(self, statement, parameters=None):
        self.statements.append((statement, parameters))
        if "to_regclass" in statement:
            return _Result({"events": "cios_events", "idempotency": "cios_idempotency"})
        if "COUNT(*)" in statement:
            return _Result({"count": 0})
        return _Result()

    @contextmanager
    def transaction(self):
        yield self


class _Pool:
    def __init__(self):
        self.connection_value = _Connection()
        self.closed = False

    @contextmanager
    def connection(self):
        yield self.connection_value

    def close(self):
        self.closed = True


class CIOSRC8ProductionLaneTests(unittest.TestCase):
    def source_file(self, relative_path: str) -> Path:
        path = REPOSITORY_ROOT / relative_path
        if not path.is_file():
            self.skipTest(
                f"source-only CIOS assertion is not applicable to this reduced export: {relative_path}"
            )
        return path

    def test_postgres_provider_configuration_is_distinct_bounded_and_fail_closed(self) -> None:
        config = ProviderRuntimeConfig(
            bearer_token=TOKEN,
            storage_backend="postgres",
            database_url="postgresql://state-runtime@db/cios_state",
            audit_database_url="postgresql://audit-runtime@db/cios_audit",
            pool_max_size=8,
            expected_source_sha=SHA,
            runtime_source_sha=SHA,
            runtime_identity="cios-runtime@example.invalid",
            tenant_id="TENANT-PRODUCTION",
            runtime_user_id="CIOS-PROVIDER",
        )
        self.assertEqual("postgres", config.storage_backend)
        self.assertEqual(8, config.pool_max_size)
        with self.assertRaisesRegex(ValueError, "must differ"):
            ProviderRuntimeConfig(
                bearer_token=TOKEN,
                storage_backend="postgres",
                database_url="postgresql://same/db",
                audit_database_url="postgresql://same/db",
                expected_source_sha=SHA,
                runtime_source_sha=SHA,
                runtime_identity="runtime",
                tenant_id="tenant",
                runtime_user_id="user",
            )
        with self.assertRaisesRegex(ValueError, "between 1 and 16"):
            ProviderRuntimeConfig(
                bearer_token=TOKEN,
                storage_backend="postgres",
                database_url="postgresql://state/db",
                audit_database_url="postgresql://audit/db",
                pool_max_size=100,
                expected_source_sha=SHA,
                runtime_source_sha=SHA,
                runtime_identity="runtime",
                tenant_id="tenant",
                runtime_user_id="user",
            )

    def test_state_and_audit_migrations_are_advisory_locked_and_append_only(self) -> None:
        state_pool = _Pool()
        state = PostgresStateStore(
            "postgresql://state/db",
            apply_migrations=True,
            pool_factory=lambda: state_pool,
        )
        try:
            self.assertTrue(state.quick_check())
            state_sql = "\n".join(statement for statement, _ in state_pool.connection_value.statements)
            self.assertIn("pg_advisory_xact_lock", state_sql)
            self.assertIn("CREATE TABLE IF NOT EXISTS cios_idempotency", state_sql)
            self.assertIn("JSONB", state_sql)
        finally:
            state.close()
        self.assertTrue(state_pool.closed)

        audit_pool = _Pool()
        audit = PostgresAuditLedger(
            "postgresql://audit/db",
            apply_migrations=True,
            pool_factory=lambda: audit_pool,
        )
        try:
            audit_sql = "\n".join(statement for statement, _ in audit_pool.connection_value.statements)
            self.assertIn("pg_advisory_xact_lock", audit_sql)
            self.assertIn("CIOS_AUDIT_APPEND_ONLY", audit_sql)
            self.assertIn("BEFORE UPDATE", audit_sql)
            self.assertIn("BEFORE DELETE", audit_sql)
        finally:
            audit.close()
        self.assertTrue(audit_pool.closed)

    def test_cloud_run_identity_token_can_coexist_with_application_secret_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = ProviderRuntimeConfig(
                bearer_token=TOKEN,
                db_path=str(root / "state.sqlite"),
                audit_path=str(root / "audit.sqlite"),
                expected_source_sha=SHA,
                runtime_source_sha=SHA,
                runtime_identity="runtime",
                tenant_id="tenant",
                runtime_user_id="user",
                host="127.0.0.1",
            )
            app = ProviderRuntimeApplication(config)
            try:
                status, payload = app.handle(
                    "GET",
                    "/health",
                    {
                        "Authorization": "Bearer provider-identity-token",
                        "X-CIOS-Token": TOKEN,
                    },
                )
                self.assertEqual(200, status)
                self.assertEqual("ok", payload["status"])
                self.assertEqual("sqlite", payload["storage_backend"])
            finally:
                app.close()

    def test_runtime_container_installs_bounded_postgres_driver_and_uses_tcp_probes(self) -> None:
        dockerfile = self.source_file(
            "evidenceops/capital_intelligence_os/Dockerfile.runtime"
        ).read_text(encoding="utf-8")
        requirements = self.source_file(
            "evidenceops/capital_intelligence_os/requirements-runtime.txt"
        ).read_text(encoding="utf-8")
        operator_source = self.source_file(
            "ops/federation_omega_operator/lib/google_cloud.mjs"
        ).read_text(encoding="utf-8")
        self.assertIn("requirements-runtime.txt", dockerfile)
        self.assertIn("psycopg[binary]>=3.2,<4", requirements)
        self.assertIn("psycopg_pool>=3.2,<4", requirements)
        self.assertIn('startupProbe: { tcpSocket: { port: 8080 }', operator_source)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", operator_source)

    def test_operator_contract_carries_no_secret_values_or_mutable_image_tags(self) -> None:
        contracts = self.source_file(
            "ops/federation_omega_operator/lib/contracts.mjs"
        ).read_text(encoding="utf-8")
        adapter = self.source_file(
            "ops/federation_omega_operator/lib/google_cloud.mjs"
        ).read_text(encoding="utf-8")
        self.assertIn("@sha256:", contracts)
        self.assertIn("CIOS_MANAGED_POSTGRES_RECOVERY_READY", adapter)
        self.assertIn("applicationSecretValueReturned: false", adapter)
        self.assertIn("ifGenerationMatch=0", adapter)

    def test_runtime_and_provider_contracts_remain_json_parseable(self) -> None:
        for name in ["BUILD_CONTRACT.json", "PROVIDER_RUNTIME_CONTRACT.json"]:
            path = self.source_file(f"evidenceops/capital_intelligence_os/{name}")
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_main_push_discovery_is_provider_native_and_zero_mutation(self) -> None:
        workflow = self.source_file(
            ".github/workflows/cios-production-lane.yml"
        ).read_text(encoding="utf-8")
        discovery = workflow.split("\n  provider-discovery:\n", 1)[1].split(
            "\n  provider:\n", 1
        )[0]
        self.assertIn("github.event_name == 'push'", discovery)
        self.assertIn('"gcloud", "secrets", "describe"', discovery)
        self.assertIn('"gcloud", "billing", "projects", "describe"', discovery)
        self.assertIn('"provider_mutation_attempted": False', discovery)
        self.assertIn('"secret_version_access_attempted": False', discovery)
        for forbidden in (
            "gcloud builds",
            "gcloud run deploy",
            "update-traffic",
            "secrets versions access",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, discovery)


if __name__ == "__main__":
    unittest.main()
