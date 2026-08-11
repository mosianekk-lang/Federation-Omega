from __future__ import annotations
import json,os,re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
from .verification_registry import SQLiteVerificationRegistry

CODE_RE=re.compile(r"^[A-Z0-9-]{8,64}$")
REGISTRY=SQLiteVerificationRegistry(os.environ.get("ECERTIFY_PUBLIC_REGISTRY_DB","/tmp/ecertify-public.sqlite"))

class Handler(BaseHTTPRequestHandler):
    def _json(self,status:int,payload:dict):
        data=json.dumps(payload).encode();self.send_response(status);self.send_header("content-type","application/json");self.send_header("content-length",str(len(data)));self.send_header("cache-control","no-store");self.send_header("x-content-type-options","nosniff");self.send_header("referrer-policy","no-referrer");self.end_headers();self.wfile.write(data)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/health":return self._json(200,{"ok":True,"service":"evidenceops-ecertify-za-public","version":"0.4.0","registry":"reference"})
        if path.startswith("/v1/verify/"):
            code=path.rsplit("/",1)[-1].upper()
            if not CODE_RE.fullmatch(code):return self._json(400,{"error":"invalid_verification_code"})
            result=REGISTRY.get(code)
            if result is None:return self._json(404,{"status":"NOT_FOUND"})
            return self._json(200,{"verification_code":result.verification_code,"status":result.status,"legal_label":result.legal_label,"document_sha256":result.document_sha256,"issued_at":result.issued_at,"expires_at":result.expires_at})
        return self._json(404,{"error":"not_found"})
    def log_message(self,fmt,*args):print("ecertify_public",self.command,self.path)

def main():ThreadingHTTPServer(("0.0.0.0",int(os.environ.get("PORT","8080"))),Handler).serve_forever()
if __name__=="__main__":main()
