from __future__ import annotations
import json,os,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

VERSION="0.1.1"
HOST="0.0.0.0"
PORT=int(os.environ.get("PORT","8080"))
UPDATE_VERSION=os.environ.get("FUSE_TOKA_LATEST_VERSION",VERSION)
UPDATE_URL=os.environ.get("FUSE_TOKA_UPDATE_URL","")
UPDATE_SHA256=os.environ.get("FUSE_TOKA_UPDATE_SHA256","")
UPDATE_SIGNATURE=os.environ.get("FUSE_TOKA_UPDATE_SIGNATURE","")
UPDATE_ROOT_ID=os.environ.get("FUSE_TOKA_UPDATE_ROOT_ID","")
UPDATE_CHANNEL=os.environ.get("FUSE_TOKA_UPDATE_CHANNEL","stable")
UPDATE_ISSUED_AT=os.environ.get("FUSE_TOKA_UPDATE_ISSUED_AT_EPOCH","")
UPDATE_EXPIRES_AT=os.environ.get("FUSE_TOKA_UPDATE_EXPIRES_AT_EPOCH","")
MAX_BODY_BYTES=65536

class Handler(BaseHTTPRequestHandler):
    server_version="FuseTokaControl/0.1.1"

    def _send(self,code,obj):
        b=json.dumps(obj,sort_keys=True,separators=(",",":")).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send(200,{"ok":True,"service":"fuse-toka-control-plane","version":VERSION}) if self.path=="/healthz" else self._send(404,{"error":"not_found"})

    def do_POST(self):
        if self.path!="/v1/heartbeat":
            self._send(404,{"error":"not_found"}); return
        try:
            length=int(self.headers.get("Content-Length","0"))
        except ValueError:
            self._send(400,{"error":"invalid_content_length"}); return
        if length<0 or length>MAX_BODY_BYTES:
            self._send(413,{"error":"request_too_large"}); return
        try:
            payload=json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError,UnicodeDecodeError):
            self._send(400,{"error":"invalid_json"}); return
        client_channel=str(payload.get("channel",""))[:32]
        response={"server_version":VERSION,"server_time":int(time.time()),"client_version_seen":str(payload.get("client_version",""))[:64],"commands":[]}
        manifest_values=(UPDATE_URL,UPDATE_SHA256,UPDATE_SIGNATURE,UPDATE_ROOT_ID,UPDATE_CHANNEL,UPDATE_ISSUED_AT,UPDATE_EXPIRES_AT)
        if UPDATE_VERSION and UPDATE_VERSION!=payload.get("client_version") and client_channel==UPDATE_CHANNEL and all(manifest_values):
            try:
                issued=int(UPDATE_ISSUED_AT); expires=int(UPDATE_EXPIRES_AT)
            except ValueError:
                issued=expires=0
            if issued>0 and expires>issued:
                response["update"]={"version":UPDATE_VERSION,"url":UPDATE_URL,"sha256":UPDATE_SHA256,"signature":UPDATE_SIGNATURE,"root_id":UPDATE_ROOT_ID,"channel":UPDATE_CHANNEL,"issued_at_epoch":issued,"expires_at_epoch":expires}
        self._send(200,response)

    def log_message(self,fmt,*args):
        return

def main():
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()

if __name__=="__main__":
    main()
