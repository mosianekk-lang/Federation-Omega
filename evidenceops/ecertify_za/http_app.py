from __future__ import annotations
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .identity_receipt import IdentityReceiptGate, ProviderVerificationReceipt
from .legal import CertificationRouteEngine

class Handler(BaseHTTPRequestHandler):
    identity=IdentityReceiptGate(); routes=CertificationRouteEngine()
    def _json(self,status:int,payload:dict):
        data=json.dumps(payload,default=lambda x:getattr(x,"value",str(x))).encode(); self.send_response(status); self.send_header("content-type","application/json"); self.send_header("content-length",str(len(data))); self.send_header("cache-control","no-store"); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path=="/health": return self._json(200,{"ok":True,"service":"evidenceops-ecertify-za","version":"0.2.0","identity_processing":"provider-receipt-bound"})
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
            try:
                rec=ProviderVerificationReceipt(provider=str(body["provider"]),transaction_id=str(body["transaction_id"]),verification_passed=bool(body["verification_passed"]),live_presence_check_passed=bool(body["live_presence_check_passed"]),trusted_reference_match_passed=bool(body["trusted_reference_match_passed"]),document_check_passed=bool(body["document_check_passed"]),device_attestation_passed=bool(body["device_attestation_passed"]),provider_risk_level=str(body["provider_risk_level"]),policy_version=str(body["policy_version"]),issued_at=str(body["issued_at"]),signature_verified=bool(body["signature_verified"]),raw_sensitive_media_received_by_evidenceops=bool(body.get("raw_sensitive_media_received_by_evidenceops",False)))
                a=self.identity.assess(rec,bool(body.get("consent_granted",False)))
            except (KeyError,ValueError,TypeError) as exc:return self._json(400,{"error":"invalid_receipt_payload","detail":str(exc)[:120]})
            return self._json(200,{"decision":a.decision.value,"reasons":a.reasons,"evidence_digest":a.evidence_digest,"provider_transaction_id":a.provider_transaction_id})
        return self._json(404,{"error":"not_found"})
    def log_message(self,fmt,*args): print("ecertify_http",self.command,self.path)

def main(): ThreadingHTTPServer(("0.0.0.0",int(os.environ.get("PORT","8080"))),Handler).serve_forever()
if __name__=="__main__":main()
