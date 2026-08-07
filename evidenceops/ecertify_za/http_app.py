from __future__ import annotations
import json,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .identity_receipt import IdentityReceiptGate
from .legal import CertificationRouteEngine
from .receipt_auth import HMACReceiptAuthenticator,ReceiptEnvelope,ReplayStore

def _build_authenticator():
    provider=os.environ.get("ECERTIFY_IDP_PROVIDER","").strip(); secret=os.environ.get("ECERTIFY_IDP_HMAC_SECRET","").encode(); key_id=os.environ.get("ECERTIFY_IDP_KEY_ID","").strip()
    if not provider or not secret or not key_id:return None
    replay=ReplayStore(os.environ.get("ECERTIFY_REPLAY_DB","/tmp/ecertify-replay.sqlite"))
    return HMACReceiptAuthenticator({provider:secret},{provider:{key_id}},int(os.environ.get("ECERTIFY_RECEIPT_MAX_AGE","300")),replay)

class Handler(BaseHTTPRequestHandler):
    identity=IdentityReceiptGate(); routes=CertificationRouteEngine(); authenticator=_build_authenticator()
    def _json(self,status:int,payload:dict):
        data=json.dumps(payload,default=lambda x:getattr(x,"value",str(x))).encode(); self.send_response(status); self.send_header("content-type","application/json"); self.send_header("content-length",str(len(data))); self.send_header("cache-control","no-store"); self.send_header("x-content-type-options","nosniff"); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path=="/health":return self._json(200,{"ok":True,"service":"evidenceops-ecertify-za","version":"0.3.0","identity_processing":"signed-provider-receipt-bound","provider_auth_configured":self.authenticator is not None})
        return self._json(404,{"error":"not_found"})
    def do_POST(self):
        try:
            length=int(self.headers.get("content-length","0"));
            if length>256000:return self._json(413,{"error":"request_too_large"})
            body=json.loads(self.rfile.read(length) or b"{}")
        except Exception:return self._json(400,{"error":"invalid_json"})
        if self.path=="/v1/route":
            r=self.routes.route(str(body.get("requested_status","")),bool(body.get("recipient_accepts_digital_assurance",False)))
            return self._json(200,{"lane":r.lane.value,"final_label":r.final_label,"commissioner_required":r.commissioner_required,"physical_presence_default":r.physical_presence_default,"identity_requirement":r.identity_requirement,"rationale":r.rationale})
        if self.path=="/v1/identity/receipt/assess":
            if self.authenticator is None:return self._json(503,{"error":"identity_provider_auth_not_configured"})
            try:
                env=ReceiptEnvelope(provider=str(body["provider"]),payload=dict(body["payload"]),signature_hex=str(body["signature_hex"]),key_id=str(body["key_id"]))
                authenticated=self.authenticator.verify(env)
                a=self.identity.assess(authenticated,bool(body.get("consent_granted",False)))
            except (KeyError,ValueError,TypeError) as exc:return self._json(400,{"error":"identity_receipt_rejected","detail":str(exc)[:120]})
            return self._json(200,{"decision":a.decision.value,"reasons":a.reasons,"evidence_digest":a.evidence_digest,"provider_transaction_id":a.provider_transaction_id})
        return self._json(404,{"error":"not_found"})
    def log_message(self,fmt,*args):print("ecertify_http",self.command,self.path)

def main():ThreadingHTTPServer(("0.0.0.0",int(os.environ.get("PORT","8080"))),Handler).serve_forever()
if __name__=="__main__":main()
