from __future__ import annotations
import json, unittest
from federation.fuse_x_xurl_adapter_v1 import XurlReadOnlyAdapter,XurlAdapterError,PolicyError,validate_args,fingerprint_probe
class XurlAdapterV1Tests(unittest.TestCase):
    def test_timeline_allowed(self): validate_args(["timeline","-n","20"])
    def test_search_allowed(self): validate_args(["search","AI","-n","10"])
    def test_raw_v2_allowed(self): validate_args(["/2/users/me"])
    def test_raw_non_v2_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["/1.1/account/settings.json"])
    def test_post_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["post","hello"])
    def test_reply_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["reply","1","x"])
    def test_like_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["like","1"])
    def test_dm_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["dm","@u","x"])
    def test_token_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["token"])
    def test_verbose_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["--verbose","whoami"])
    def test_secret_flag_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["auth","apps","add","x","--client-secret","secret"])
    def test_auth_login_blocked(self):
        with self.assertRaises(PolicyError): validate_args(["auth","oauth2"])
    def test_auth_status_allowed(self): validate_args(["auth","status"])
    def test_auth_apps_list_allowed(self): validate_args(["auth","apps","list"])
    def test_auth_redirect_get_allowed(self): validate_args(["auth","apps","redirect-uri","get","prod"])
    def test_timeline_clamped_json(self):
        seen=[]
        def run(argv,env): seen.append(argv); return 0,json.dumps({"data":[{"id":"1"}]}),""
        out=XurlReadOnlyAdapter(runner=run).timeline(999)
        self.assertEqual(seen[0],["xurl","timeline","-n","100"]); self.assertEqual(out["data"][0]["id"],"1")
    def test_nonjson_fails_closed(self):
        with self.assertRaisesRegex(XurlAdapterError,"XURL_NON_JSON"): XurlReadOnlyAdapter(runner=lambda a,e:(0,"not-json","")).whoami()
    def test_error_sanitized(self):
        a=XurlReadOnlyAdapter(runner=lambda a,e:(1,"","401 unauthorized token=SHOULD_NOT_ECHO"))
        with self.assertRaises(XurlAdapterError) as cm: a.whoami()
        self.assertEqual(cm.exception.category,"XURL_UNAUTHORIZED"); self.assertNotIn("SHOULD_NOT_ECHO",str(cm.exception))
    def test_status_identity_minimized(self):
        sample="▸ prod [client_id: ABCDEF…]\n redirect_uri: http://localhost:8080/callback [app config]\n ▸ oauth2: alice\n oauth1: –\n bearer: –\n"
        st=XurlReadOnlyAdapter(runner=lambda a,e:(0,sample,"")).auth_status()
        self.assertEqual(st.app_count,1); self.assertEqual(st.oauth2_user_count,1); self.assertTrue(st.redirect_uri_configured); self.assertNotIn("alice",json.dumps(st.to_dict()))
    def test_probe_authorized_identity_minimized(self):
        status="▸ prod [client_id: ABCDEF…]\n redirect_uri: http://localhost:8080/callback [app config]\n ▸ oauth2: alice\n"
        def run(argv,env):
            if argv[1:]==["auth","status"]: return 0,status,""
            return 0,json.dumps({"data":{"id":"u1","username":"alice"}}),""
        p=XurlReadOnlyAdapter(runner=run).probe(); self.assertTrue(p["authorized"]); self.assertNotIn("username",json.dumps(p))
    def test_fingerprint_stable(self):
        p={"authorized":False}; self.assertEqual(fingerprint_probe(p),fingerprint_probe(p))
if __name__=="__main__": unittest.main()
