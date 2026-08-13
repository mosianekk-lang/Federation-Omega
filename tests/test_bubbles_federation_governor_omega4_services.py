from __future__ import annotations
import os, tempfile, unittest
from bubbles.federation_governor_omega4 import FederationGovernor, FederationTelemetry, Omega3ProjectAdapter


class Omega4ServiceTests(unittest.TestCase):
    def test_omega3_adapter_and_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            gov = FederationGovernor(os.path.join(tmp, "omega4.sqlite3"))
            gov.register_project("LEGAL", "Legal", "MATTER:LEGAL")
            gov.register_mission(project_id="LEGAL", mission_id="M1",
                                 objective="Review disciplinary email")
            adapter = Omega3ProjectAdapter(os.path.join(tmp, "omega3.sqlite3"))
            plan = adapter.compile(gov.registry.mission("M1"),
                                   specialists=["Lex", "Ledger"],
                                   connectors=["Gmail", "Google Drive"])
            self.assertEqual("M1", plan.mission_id)
            self.assertEqual(["Lex", "Ledger"], plan.active_specialists)
            telemetry = FederationTelemetry(gov.registry)
            telemetry.record(cache_hit=True, prevented_call=True, shim_bytes=900)
            snap = telemetry.snapshot()
            self.assertEqual(1.0, snap["federation.cache_hit_rate"])
            self.assertEqual(1.0, snap["federation.prevented_call_rate"])
            self.assertEqual(900.0, snap["federation.shim_bytes"])
            gov.registry.close()
            adapter.state._conn().close()


if __name__ == "__main__":
    unittest.main()
