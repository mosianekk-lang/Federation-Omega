from __future__ import annotations

import json
from pathlib import Path
import time
import unittest

from respawn.work_plane_gcs_runtime import CasConflict, DurableBundleRuntime, GoogleStorageGenerationClient, InMemoryGenerationClient


class WorkPlaneGcsBundleTests(unittest.TestCase):
    def setUp(self):
        self.client = InMemoryGenerationClient()
        self.rt = DurableBundleRuntime(bucket="b", object_name="work-plane/state.json", client=self.client)

    def test_publish_claim_checkpoint_survive_new_runtime_instance(self):
        p = self.rt.execute(operation="PUBLISH", mission_id="M1")
        self.assertEqual(1, p.committed_generation)
        c = self.rt.execute(operation="CLAIM", mission_id="M1", actor="A", ttl_seconds=60)
        fence = c.result["fence"]
        self.rt.execute(operation="RUNNING", mission_id="M1", actor="A", fence=fence)
        self.rt.execute(operation="CHECKPOINT", mission_id="M1", actor="A", fence=fence, payload={"step": 4})

        recreated = DurableBundleRuntime(bucket="b", object_name="work-plane/state.json", client=self.client)
        projection = recreated.execute(operation="PROJECTION", mission_id="M1")
        self.assertEqual("CHECKPOINTED", projection.result["state"])
        self.assertEqual(fence, projection.result["fence"])
        self.assertIsNotNone(projection.result["checkpoint_hash"])

    def test_generation_conflict_rejects_lost_update(self):
        self.rt.execute(operation="PUBLISH", mission_id="M2")
        gen, raw = self.client.read("b", "work-plane/state.json")
        self.assertEqual(1, gen)
        self.client.put("b", "work-plane/state.json", raw, if_generation_match=gen)
        with self.assertRaises(CasConflict):
            self.client.put("b", "work-plane/state.json", raw, if_generation_match=gen)

    def test_stale_actor_takeover_uses_newer_fence(self):
        self.rt.execute(operation="PUBLISH", mission_id="M3")
        c1=self.rt.execute(operation="CLAIM", mission_id="M3", actor="A", ttl_seconds=0)
        f1=c1.result["fence"]
        c2=self.rt.execute(operation="RECOVER_ORPHAN", mission_id="M3", actor="B", ttl_seconds=60)
        f2=c2.result["fence"]
        self.assertGreater(f2,f1)
        with self.assertRaises(RuntimeError):
            self.rt.execute(operation="CHECKPOINT", mission_id="M3", actor="A", fence=f1, payload={"late":True})

    def test_unknown_effect_requires_readback_and_exact_id(self):
        self.rt.execute(operation="PUBLISH", mission_id="M4")
        c=self.rt.execute(operation="CLAIM", mission_id="M4", actor="A", ttl_seconds=60)
        f=c.result["fence"]
        self.rt.execute(operation="EFFECT_UNKNOWN", mission_id="M4", actor="A", fence=f, effect_id="E4")
        with self.assertRaises(RuntimeError):
            self.rt.execute(operation="RECOVER_ORPHAN", mission_id="M4", actor="B", ttl_seconds=60)

        # Simulate executor disappearance by expiring the lease in the durable bundle
        # without changing the UNKNOWN effect identity.
        gen, raw = self.client.read("b", "work-plane/state.json")
        bundle=json.loads(raw)
        state=json.loads(bundle["state_json"])
        state["missions"]["M4"]["lease_until_ns"]=0
        bundle["state_json"]=json.dumps(state,sort_keys=True,separators=(",",":"))
        self.client.put("b","work-plane/state.json",json.dumps(bundle,sort_keys=True,separators=(",",":")).encode(),if_generation_match=gen)

        with self.assertRaises(RuntimeError):
            self.rt.execute(operation="IMPORT_EXTERNAL_RESULT", mission_id="M4", verifier="JUDGE",
                            effect_id="WRONG", proof_ref="proof:x", payload={"ok":True})
        r=self.rt.execute(operation="IMPORT_EXTERNAL_RESULT", mission_id="M4", verifier="JUDGE",
                          effect_id="E4", proof_ref="proof:match", payload={"ok":True})
        self.assertEqual("RESULT_READY", r.result["event"]["target_state"])
        self.assertEqual("MATCH", r.result["event"]["effect_state"])

    def test_bundle_commit_is_atomic_single_object(self):
        self.rt.execute(operation="PUBLISH", mission_id="M5")
        gen, raw = self.client.read("b", "work-plane/state.json")
        bundle=json.loads(raw)
        self.assertEqual(1, gen)
        self.assertIn('"M5"', bundle["state_json"])
        self.assertIn('"event_type":"PUBLISH"', bundle["events_jsonl"])
        self.assertEqual(1, bundle["commit_count"])

    def test_projection_does_not_advance_generation(self):
        self.rt.execute(operation="PUBLISH", mission_id="M6")
        before,_=self.client.read("b","work-plane/state.json")
        r=self.rt.execute(operation="PROJECTION", mission_id="M6")
        after,_=self.client.read("b","work-plane/state.json")
        self.assertEqual(before, after)
        self.assertEqual(before, r.committed_generation)

    def test_unknown_operation_fails_closed(self):
        with self.assertRaises(ValueError):
            self.rt.execute(operation="SHELL", mission_id="M7")


class _FakeResponse:
    def __init__(self, status_code=200, *, json_body=None, content=b""):
        self.status_code=status_code
        self._json=json_body or {}
        self.content=content
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP_{self.status_code}")


class _FakeSession:
    def __init__(self, responses):
        self.responses=list(responses)
        self.calls=[]
    def _next(self, method, url, **kwargs):
        self.calls.append((method,url,kwargs))
        if not self.responses:
            raise AssertionError("UNEXPECTED_HTTP_CALL")
        return self.responses.pop(0)
    def get(self,url,**kwargs):
        return self._next("GET",url,**kwargs)
    def post(self,url,**kwargs):
        return self._next("POST",url,**kwargs)


class GoogleStorageJsonTransportTests(unittest.TestCase):
    def test_read_missing_object_is_generation_zero_without_media_call(self):
        s=_FakeSession([_FakeResponse(404)])
        c=GoogleStorageGenerationClient(session=s)
        gen,raw=c.read("bucket","dir/state.json")
        self.assertEqual((0,None),(gen,raw))
        self.assertEqual(1,len(s.calls))
        self.assertIn("dir%2Fstate.json",s.calls[0][1])

    def test_read_existing_pins_media_to_observed_generation(self):
        s=_FakeSession([
            _FakeResponse(200,json_body={"generation":"41"}),
            _FakeResponse(200,content=b'{"ok":true}'),
        ])
        c=GoogleStorageGenerationClient(session=s)
        gen,raw=c.read("bucket","dir/state.json")
        self.assertEqual(41,gen)
        self.assertEqual(b'{"ok":true}',raw)
        self.assertEqual({"alt":"media","generation":"41"},s.calls[1][2]["params"])

    def test_read_provider_failure_is_phase_status_only(self):
        s=_FakeSession([_FakeResponse(403,json_body={"error":{"message":"sensitive-provider-detail"}})])
        c=GoogleStorageGenerationClient(session=s)
        with self.assertRaisesRegex(RuntimeError,r"^GCS_METADATA_GET_HTTP_403$"):
            c.read("bucket","dir/state.json")

    def test_read_media_provider_failure_is_phase_status_only(self):
        s=_FakeSession([
            _FakeResponse(200,json_body={"generation":"41"}),
            _FakeResponse(403,json_body={"error":{"message":"sensitive-provider-detail"}}),
        ])
        c=GoogleStorageGenerationClient(session=s)
        with self.assertRaisesRegex(RuntimeError,r"^GCS_MEDIA_GET_HTTP_403$"):
            c.read("bucket","dir/state.json")

    def test_put_carries_exact_generation_precondition_and_object_name(self):
        s=_FakeSession([_FakeResponse(200,json_body={"generation":"42"})])
        c=GoogleStorageGenerationClient(session=s)
        gen=c.put("bucket","dir/state.json",b"{}",if_generation_match=41)
        self.assertEqual(42,gen)
        call=s.calls[0]
        self.assertEqual("POST",call[0])
        self.assertEqual("41",call[2]["params"]["ifGenerationMatch"])
        self.assertEqual("dir/state.json",call[2]["params"]["name"])
        self.assertEqual(b"{}",call[2]["data"])

    def test_put_maps_provider_precondition_failure_to_cas_conflict(self):
        s=_FakeSession([_FakeResponse(412)])
        c=GoogleStorageGenerationClient(session=s)
        with self.assertRaisesRegex(CasConflict,"GENERATION_CONFLICT"):
            c.put("bucket","dir/state.json",b"{}",if_generation_match=7)

    def test_put_provider_failure_is_phase_status_only(self):
        s=_FakeSession([_FakeResponse(403,json_body={"error":{"message":"sensitive-provider-detail"}})])
        c=GoogleStorageGenerationClient(session=s)
        with self.assertRaisesRegex(RuntimeError,r"^GCS_MEDIA_PUT_HTTP_403$"):
            c.put("bucket","dir/state.json",b"{}",if_generation_match=0)

    def test_transport_source_has_no_google_api_python_client_dependency(self):
        source=(Path(__file__).resolve().parents[1]/"respawn"/"work_plane_gcs_runtime.py").read_text()
        self.assertNotIn("googleapiclient",source)
        self.assertIn("AuthorizedSession",source)


if __name__ == "__main__":
    unittest.main()
