import os, sys, unittest, urllib.parse, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fuse_x_oauth_v4.contract import *
from fuse_x_oauth_v4.pkce import *
from fuse_x_oauth_v4.authority import *
from fuse_x_oauth_v4.client import *
from fuse_x_oauth_v4.token_store import *

class ContractTests(unittest.TestCase):
    def test_01_callback_exact_loopback(self): self.assertEqual(CALLBACK_URI, "http://127.0.0.1:8080/callback")
    def test_02_no_localhost(self): self.assertNotIn("localhost", CALLBACK_URI)
    def test_03_users_email_omitted_ro(self): self.assertNotIn("users.email", READ_ONLY.scopes)
    def test_04_users_email_omitted_full(self): self.assertNotIn("users.email", FULL_SURFACE.scopes)
    def test_05_offline_access_present(self): self.assertIn("offline.access", READ_ONLY.scopes)
    def test_06_docs_head_bound(self): self.assertEqual(len(DOCS_HEAD), 40)
    def test_07_predecessor_sha_bound(self): self.assertEqual(len(PREDECESSOR_V3_SHA256), 64)
    def test_08_profile_api_not_claimed(self): self.assertFalse(PROFILE_MUTATION_API_VERIFIED)
    def test_09_enterprise_like(self): self.assertIn("X_LIKE", ENTERPRISE_ONLY_ACTIONS)
    def test_10_enterprise_follow(self): self.assertIn("X_FOLLOW", ENTERPRISE_ONLY_ACTIONS)
    def test_11_quote_not_selfserve(self): self.assertIn("X_QUOTE_POST", NOT_SELF_SERVE_ACTIONS)

class PKCETests(unittest.TestCase):
    def test_12_pkce_method(self):
        p=generate_pkce(); self.assertGreaterEqual(len(p.verifier), 43); self.assertGreaterEqual(len(p.challenge), 43)
    def test_13_state_entropy(self): self.assertGreaterEqual(len(generate_state()), 32)
    def test_14_auth_url_client(self):
        p=generate_pkce(); u=build_authorization_url("cid", READ_ONLY, "st", p); q=urllib.parse.parse_qs(urllib.parse.urlparse(u).query); self.assertEqual(q["client_id"][0],"cid")
    def test_15_auth_url_s256(self):
        p=generate_pkce(); u=build_authorization_url("cid", READ_ONLY, "st", p); q=urllib.parse.parse_qs(urllib.parse.urlparse(u).query); self.assertEqual(q["code_challenge_method"][0],"S256")
    def test_16_auth_url_callback(self):
        p=generate_pkce(); u=build_authorization_url("cid", READ_ONLY, "st", p); q=urllib.parse.parse_qs(urllib.parse.urlparse(u).query); self.assertEqual(q["redirect_uri"][0],CALLBACK_URI)
    def test_17_auth_url_empty_client_fails(self):
        with self.assertRaises(ValueError): build_authorization_url("", READ_ONLY, "s", generate_pkce())
    def test_18_scope_sorted(self):
        p=generate_pkce(); u=build_authorization_url("cid", READ_ONLY, "st", p); q=urllib.parse.parse_qs(urllib.parse.urlparse(u).query); self.assertEqual(q["scope"][0]," ".join(sorted(READ_ONLY.scopes)))

class CallbackTests(unittest.TestCase):
    def test_19_callback_ok(self): self.assertEqual(parse_callback_url(CALLBACK_URI+"?code=abc&state=s","s"),"abc")
    def test_20_state_mismatch(self):
        with self.assertRaises(OAuthProtocolError): parse_callback_url(CALLBACK_URI+"?code=abc&state=x","s")
    def test_21_callback_host_mismatch(self):
        with self.assertRaises(OAuthProtocolError): parse_callback_url("http://localhost:8080/callback?code=a&state=s","s")
    def test_22_callback_error(self):
        with self.assertRaises(OAuthProtocolError): parse_callback_url(CALLBACK_URI+"?error=denied&state=s","s")
    def test_23_callback_missing_code(self):
        with self.assertRaises(OAuthProtocolError): parse_callback_url(CALLBACK_URI+"?state=s","s")

class TokenTests(unittest.TestCase):
    def test_24_token_body_no_secret(self):
        body=token_request_body("cid","code","ver").decode(); self.assertNotIn("client_secret",body)
    def test_25_token_body_callback(self):
        q=urllib.parse.parse_qs(token_request_body("cid","code","ver").decode()); self.assertEqual(q["redirect_uri"][0], CALLBACK_URI)
    def test_26_refresh_no_secret(self):
        body=refresh_request_body("cid","r").decode(); self.assertNotIn("client_secret",body)
    def test_27_me_endpoint(self): self.assertEqual(endpoint("me"), API_BASE+"/users/me")
    def test_28_timeline_needs_id(self):
        with self.assertRaises(ValueError): endpoint("home_timeline")
    def test_29_timeline_encodes_id(self): self.assertIn("/users/a%2Fb/", endpoint("home_timeline",user_id="a/b"))
    def test_30_recent_search(self): self.assertEqual(endpoint("recent_search"), API_BASE+"/tweets/search/recent")

class AuthorityTests(unittest.TestCase):
    def good(self, action, scopes, ent=frozenset()):
        return ActionAuthority(action=action,target="123",owner_authorized=True,policy_authorized=True,plan_entitlements=ent,granted_scopes=frozenset(scopes))
    def test_31_post_scope(self): validate_action(self.good("X_POST",{"tweet.write"}))
    def test_32_post_missing_scope(self):
        with self.assertRaises(PermissionError): validate_action(self.good("X_POST",set()))
    def test_33_like_needs_enterprise(self):
        with self.assertRaises(PermissionError): validate_action(self.good("X_LIKE",{"like.write"}))
    def test_34_like_enterprise_ok(self): validate_action(self.good("X_LIKE",{"like.write"},{"ENTERPRISE"}))
    def test_35_follow_enterprise_ok(self): validate_action(self.good("X_FOLLOW",{"follows.write"},{"ENTERPRISE"}))
    def test_36_target_required(self):
        a=ActionAuthority("X_POST","",True,True,frozenset(),frozenset({"tweet.write"}))
        with self.assertRaises(PermissionError): validate_action(a)
    def test_37_owner_authority_required(self):
        a=ActionAuthority("X_POST","1",False,True,frozenset(),frozenset({"tweet.write"}))
        with self.assertRaises(PermissionError): validate_action(a)
    def test_38_policy_authority_required(self):
        a=ActionAuthority("X_POST","1",True,False,frozenset(),frozenset({"tweet.write"}))
        with self.assertRaises(PermissionError): validate_action(a)

class CustodyTests(unittest.TestCase):
    def test_39_non_windows_dpapi_fails_closed(self):
        if os.name == "nt": self.skipTest("Linux-only negative court")
        with self.assertRaises(TokenStoreError): protect_current_user(b"x")
    def test_40_source_scope_subset(self):
        self.assertTrue(READ_ONLY.scopes.issubset(FULL_SURFACE.scopes))

if __name__=="__main__":
    unittest.main()
