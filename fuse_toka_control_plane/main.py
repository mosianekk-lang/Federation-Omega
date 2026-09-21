from __future__ import annotations
import json,os,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
VERSION="0.1.0"; HOST="0.0.0.0"; PORT=int(os.environ.get("PORT","8080")); UPDATE_VERSION=os.environ.get("FUSE_TOKA_LATEST_VERSION",VERSION); UPDATE_URL=os.environ.get("FUSE_TOKA_UPDATE_URL",""); UPDATE_SHA256=os.environ.get("FUSE_TOKA_UPDATE_SHA256",""); UPDATE_SIGNATURE=os.environ.get("FUSE_TOKA_UPDATE_SIGNATURE",""); UPDATE_ROOT_ID=os.environ.get("FUSE_TOKA_UPDATE_ROOT_ID","")
class Handler(BaseHTTPRequestHandler):
    server_version="FuseTokaControl/0.1"
    def _send(self,code,obj):
        b=json.dumps(obj,sort_keys=True).encode(); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._send(200,{"ok":True,"service":"fuse-toka-control-plane","version":VERSION}) if self.path=="/healthz" else self._send(404,{"error":"not_found"})
    def do_POST(self):
        if self.path!="/v1/heartbeat": self._send(404,{"error":"not_found"}); return
        try: l=min(int(self.headers.get("Content-Length","0")),65536); p=json.loads(self.rfile.read(l) or b"{}")
        except Exception: self._send(400,{"error":"invalid_json"}); return
        r={"server_version":VERSION,"server_time":int(time.time()),"client_version_seen":str(p.get("client_version",""))[:64],"commands":[]}
        if UPDATE_VERSION and UPDATE_VERSION!=p.get("client_version") and all((UPDATE_URL,UPDATE_SHA256,UPDATE_SIGNATURE,UPDATE_ROOT_ID)): r["update"]={"version":UPDATE_VERSION,"url":UPDATE_URL,"sha256":UPDATE_SHA256,"signature":UPDATE_SIGNATURE,"root_id":UPDATE_ROOT_ID}
        self._send(200,r)
    def log_message(self,fmt,*args): return
def main(): ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
if __name__=="__main__": main()
