from __future__ import annotations
import argparse,json
from federation.fuse_x_public_oauth_v1 import PublicClientOAuth,WindowsDPAPIVault,local_browser_authorize
def main():
    p=argparse.ArgumentParser(); p.add_argument("--client-id",required=True); p.add_argument("--name",default="owner"); args=p.parse_args(); oauth=PublicClientOAuth(args.client_id,WindowsDPAPIVault(),name=args.name); result=local_browser_authorize(oauth); print(json.dumps({"authorized":bool(result.get("has_access_token")),"refreshable":bool(result.get("has_refresh_token")),"scope":result.get("scope","")},sort_keys=True))
if __name__=="__main__": main()
