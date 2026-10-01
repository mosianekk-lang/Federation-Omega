from __future__ import annotations
import os,time,urllib.parse,unittest
from unittest.mock import patch
from federation.fuse_x_public_oauth_v1 import *
class OAuthV1Tests(unittest.TestCase):
    def test_verifier(self): v=generate_verifier(); self.assertGreaterEqual(len(v),43); self.assertLessEqual(len(v),128)
    def test_challenge(self): self.assertEqual(challenge_for("abc"),challenge_for("abc"))
    def test_attempt_pkce_read_scopes(self):
        a=build_attempt("cid"); q=urllib.parse.parse_qs(urllib.parse.urlsplit(a.authorization_url).query); self.assertEqual(q["client_id"],["cid"]); self.assertEqual(q["code_challenge_method"],["S256"]); self.assertIn("offline.access",q["scope"][0]); self.assertNotIn("client_secret",q)
    def test_nonloopback_rejected(self):
        with self.assertRaisesRegex(OAuthError,"LOOPBACK"): build_attempt("cid","https://example.com/cb")
    def test_client_id_required(self):
        with self.assertRaisesRegex(OAuthError,"CLIENT_ID_REQUIRED"): build_attempt("")
    def test_state_mismatch(self):
        o=PublicClientOAuth("cid",MemoryVault(),exchange=lambda u,f:{"access_token":"a"}); a=o.start()
        with self.assertRaisesRegex(OAuthError,"STATE_MISMATCH"): o.complete(a,"?code=x&state=wrong")
    def test_code_required(self):
        o=PublicClientOAuth("cid",MemoryVault(),exchange=lambda u,f:{"access_token":"a"}); a=o.start()
        with self.assertRaisesRegex(OAuthError,"AUTHORIZATION_CODE_MISSING"): o.complete(a,"?state="+urllib.parse.quote(a.state))
    def test_complete_no_secret(self):
        seen=[]
        def ex(url,form): seen.append(form.copy()); return {"access_token":"ACCESS","refresh_token":"REFRESH","expires_in":3600,"token_type":"bearer","scope":"tweet.read users.read offline.access"}
        v=MemoryVault(); o=PublicClientOAuth("cid",v,exchange=ex); a=o.start(); st=o.complete(a,"?code=abc&state="+urllib.parse.quote(a.state)); self.assertTrue(st["has_refresh_token"]); self.assertNotIn("client_secret",seen[0])
    def test_status_hides_tokens(self):
        v=MemoryVault(); v.save("owner",{"access_token":"SECRET","refresh_token":"REF","token_type":"bearer","expires_at":9999999999,"scope":"tweet.read"}); st=PublicClientOAuth("cid",v).status(); self.assertNotIn("access_token",st); self.assertNotIn("refresh_token",st)
    def test_current_access(self):
        v=MemoryVault(); v.save("owner",{"access_token":"ACCESS","refresh_token":"REF","token_type":"bearer","expires_at":9999999999,"scope":"tweet.read"}); self.assertEqual(PublicClientOAuth("cid",v).access_token(),"ACCESS")
    def test_refresh_no_secret(self):
        v=MemoryVault(); v.save("owner",{"access_token":"OLD","refresh_token":"REF","token_type":"bearer","expires_at":int(time.time())-1,"scope":"tweet.read"}); seen=[]
        def ex(url,form): seen.append(form.copy()); return {"access_token":"NEW","expires_in":3600,"token_type":"bearer","scope":"tweet.read"}
        o=PublicClientOAuth("cid",v,exchange=ex); self.assertEqual(o.access_token(),"NEW"); self.assertEqual(v.load("owner")["refresh_token"],"REF"); self.assertNotIn("client_secret",seen[0])
    def test_missing_refresh_fails(self):
        v=MemoryVault(); v.save("owner",{"access_token":"OLD","refresh_token":None,"token_type":"bearer","expires_at":int(time.time())-1,"scope":"tweet.read"})
        with self.assertRaisesRegex(OAuthError,"REFRESH_TOKEN_MISSING"): PublicClientOAuth("cid",v).access_token()
    def test_token_state_expiry(self): self.assertGreater(token_state({"access_token":"a"},100).expires_at,100)
    def test_exchange_invalid(self):
        class R:
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def read(self): return b"{}"
        with patch("urllib.request.urlopen",return_value=R()):
            with self.assertRaisesRegex(OAuthError,"TOKEN_RESPONSE_INVALID"): default_exchange(TOKEN_URL,{})
    def test_windows_vault_nonwindows(self):
        if os.name!="nt":
            with self.assertRaisesRegex(VaultError,"WINDOWS_ONLY"): WindowsDPAPIVault()
    def test_memory_vault_copy(self):
        v=MemoryVault(); x={"a":1}; v.save("x",x); x["a"]=2; self.assertEqual(v.load("x")["a"],1)
    def test_auth_url(self): self.assertTrue(build_attempt("cid").authorization_url.startswith("https://x.com/i/oauth2/authorize?"))
    def test_token_url(self): self.assertEqual(TOKEN_URL,"https://api.x.com/2/oauth2/token")
    def test_scopes(self): self.assertEqual(set(DEFAULT_SCOPES),{"tweet.read","users.read","offline.access"})
    def test_no_write_scope(self): self.assertNotIn("tweet.write",DEFAULT_SCOPES)
    def test_schema(self): self.assertEqual(SCHEMA,"FUSE-X-PUBLIC-OAUTH-V1")
    def test_public_status_flags_only(self):
        st=TokenState("A","R","bearer",100,"tweet.read").public_status(); self.assertEqual(set(st),{"has_access_token","has_refresh_token","token_type","expires_at","scope"})
if __name__=="__main__": unittest.main()
