from __future__ import annotations

import tempfile
from unittest import TestCase
from unittest.mock import patch

from fuse_sovereign import (
    AuthorityEnvelope,
    CapabilityAdvertisement,
    EffectClass,
    FCOABridge,
    FCOABridgeError,
    FCOA_AGENT_ID,
    InProcessLLMProvider,
    LLMGateway,
    LLMGatewayError,
    LLMUpdateBridge,
    SovereignEngine,
    TaskEnvelope,
)
from fuse_sovereign.update import FuseUpdateClient


class FCOABridgeTests(TestCase):
    def make(self):
        engine = SovereignEngine([
            CapabilityAdvertisement("local-image", ("image.generate", "image.edit"), local=True, private=True),
            CapabilityAdvertisement("api-docs", ("docs.read",), local=False, private=True),
        ])
        engine.bind_handler("local-image", lambda task: {"ok": True, "capability": task.capability})
        engine.bind_handler("api-docs", lambda task: {"ok": True, "capability": task.capability})
        llm = LLMGateway([InProcessLLMProvider("reference-llm", lambda req: "plan:" + req.messages[-1]["content"])])
        td = tempfile.TemporaryDirectory()
        update = LLMUpdateBridge(FuseUpdateClient(cache_dir=td.name, require_verified_commit=False))
        bridge = FCOABridge(engine=engine, llm_gateway=llm, update_bridge=update)
        return bridge, td

    def test_existing_fcoa_identity_preserved(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        self.assertEqual(bridge.profile.agent_id, "FCOA-OMEGA")
        self.assertEqual(bridge.profile.work_plane_id, "WP-FCOA-BOOTSTRAP-001")
        self.assertFalse(bridge.profile.authority_inheritance)

    def test_capability_discovery(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        caps, ex = bridge.capability_snapshot()
        self.assertIn("image.generate", caps)
        self.assertIn("docs.read", caps)
        self.assertIn("local-image", ex)

    def test_bootstrap_includes_update_and_llm(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        fake = {"schema":"FUSE_LLM_UPDATE_SNAPSHOT_V1","sequence":7,"freshness":"CURRENT","authority_boundary":"DATA_ONLY_NO_EFFECT_AUTHORITY"}
        with patch.object(bridge.update_bridge, "fetch_context", return_value=fake):
            snap = bridge.bootstrap()
        self.assertEqual(snap.fuse_update["sequence"], 7)
        self.assertEqual(snap.llm_providers, ("reference-llm",))
        self.assertEqual(snap.authority_boundary, "MISSION_SCOPED_NO_INHERITANCE")

    def test_llm_cognition_receives_fuse_context(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        fake = {"schema":"FUSE_LLM_UPDATE_SNAPSHOT_V1","sequence":1,"freshness":"CURRENT","authority_boundary":"DATA_ONLY_NO_EFFECT_AUTHORITY"}
        with patch.object(bridge.update_bridge, "fetch_context", return_value=fake):
            r = bridge.think(request_id="r1", mission_id="m1", prompt="design a poster")
        self.assertEqual(r.provider_id, "reference-llm")
        self.assertIn("design a poster", r.text)

    def test_llm_output_does_not_execute(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        with patch.object(bridge.update_bridge, "fetch_context", return_value={"schema":"FUSE_LLM_UPDATE_SNAPSHOT_V1","sequence":1,"freshness":"CURRENT"}):
            _ = bridge.think(request_id="r2", mission_id="m2", prompt="publish externally")
        self.assertEqual(len(bridge.engine.audit.events), 0)

    def test_read_only_task_executes_with_agent_authority(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        task = TaskEnvelope("t1", "docs.read", effect=EffectClass.READ_ONLY, payload={})
        auth = AuthorityEnvelope(principal=FCOA_AGENT_ID, allowed_effects=(EffectClass.READ_ONLY,))
        r = bridge.execute_task(task=task, authority=auth)
        self.assertEqual(r["executor"], "api-docs")

    def test_effect_outside_authority_rejected(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        task = TaskEnvelope("t2", "image.generate", effect=EffectClass.LOCAL_WRITE, payload={})
        auth = AuthorityEnvelope(principal=FCOA_AGENT_ID, allowed_effects=(EffectClass.READ_ONLY,))
        with self.assertRaisesRegex(FCOABridgeError, "EFFECT_NOT_AUTHORIZED"):
            bridge.execute_task(task=task, authority=auth)

    def test_bad_principal_rejected(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        task = TaskEnvelope("t3", "docs.read")
        auth = AuthorityEnvelope(principal="RANDOM-AGENT", allowed_effects=(EffectClass.READ_ONLY,))
        with self.assertRaisesRegex(FCOABridgeError, "PRINCIPAL_INVALID"):
            bridge.execute_task(task=task, authority=auth)

    def test_no_provider_is_fail_closed(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        bridge.llm_gateway = LLMGateway([])
        with patch.object(bridge.update_bridge, "fetch_context", return_value={"schema":"FUSE_LLM_UPDATE_SNAPSHOT_V1","sequence":1,"freshness":"CURRENT"}):
            with self.assertRaisesRegex(LLMGatewayError, "NO_QUALIFIED"):
                bridge.think(request_id="r3", mission_id="m3", prompt="x")

    def test_model_context_is_allowlisted(self):
        bridge, td = self.make(); self.addCleanup(td.cleanup)
        fake = {"schema":"FUSE_LLM_UPDATE_SNAPSHOT_V1","sequence":2,"freshness":"CURRENT","secret":"must-not-be-special"}
        with patch.object(bridge.update_bridge, "fetch_context", return_value=fake):
            ctx = bridge.context_for_model()
        self.assertEqual(ctx["schema"], "FCOA_FUSE_CONTEXT_V1")
        self.assertEqual(ctx["fuse_update"]["sequence"], 2)
        self.assertEqual(ctx["authority_boundary"], "MISSION_SCOPED_NO_INHERITANCE")
