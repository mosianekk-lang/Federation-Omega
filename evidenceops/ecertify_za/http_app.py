from __future__ import annotations
import json,os
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .identity_receipt import IdentityReceiptGate
from .launch_now import LaunchNowEngine
from .legal import CertificationRouteEngine
from .receipt_auth import HMACReceiptAuthenticator,ReceiptEnvelope
from .replay import load_replay_guard
from .zero_possession import IntegrityReceipt,ZeroPossessionReceiptService

def _production()->bool:
    return os.environ.get("ECERTIFY_ENV","development").strip().lower()=="production"

def _mode()->str:
    value=os.environ.get("ECERTIFY_MODE","launch_now").strip().lower()
    if value not in {"launch_now","full_assurance"}:raise RuntimeError("ECERTIFY_MODE_INVALID")
    return value

def _build_authenticator():
    production=_production();mode=_mode()
    provider=os.environ.get("ECERTIFY_IDP_PROVIDER","").strip();secret=os.environ.get("ECERTIFY_IDP_HMAC_SECRET","").encode();key_id=os.environ.get("ECERTIFY_IDP_KEY_ID","").strip()
    if not provider or not secret or not key_id:
        if production and mode=="full_assurance":raise RuntimeError("PRODUCTION_IDENTITY_PROVIDER_AUTH_NOT_CONFIGURED")
        return None
    replay=load_replay_guard(production=production)
    return HMACReceiptAuthenticator({provider:secret},{provider:{key_id}},int(os.environ.get("ECERTIFY_RECEIPT_MAX_AGE","300")),replay)

def _build_integrity_service():
    key=os.environ.get("ECERTIFY_INTEGRITY_SIGNING_KEY","").encode()
    if not key:
        if _production():raise RuntimeError("PRODUCTION_INTEGRITY_SIGNING_KEY_NOT_CONFIGURED")
        key=b"development-only-integrity-signing-key-0001"
    return ZeroPossessionReceiptService(key,key_id=os.environ.get("ECERTIFY_INTEGRITY_KEY_ID","ecertify-integrity-v1"))

class Handler(BaseHTTPRequestHandler):
    identity=IdentityReceiptGate();routes=CertificationRouteEngine();launch=LaunchNowEngine();authenticator=_build_authenticator();integrity=_build_integrity_service()
    def _json(self,status:int,payload:dict):
        data=json.dumps(payload,default=lambda x:getattr(x,"value",str(x))).encode();self.send_response(status);self.send_header("content-type","application/json");self.send_header("content-length",str(len(data)));self.send_header("cache-control","no-store");self.send_header("x-content-type-options","nosniff");self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=="/health":return self._json(200,{"ok":True,"service":"evidenceops-ecertify-za-private","version":"0.9.0","mode":_mode(),"zero_possession_integrity_receipts":True,"identity_provider_required_for_launch":False,"identity_provider_configured":self.authenticator is not None,"formal_certification":"commissioner-event-gated","environment":os.environ.get("ECERTIFY_ENV","development")})
        return self._json(404,{"error":"not_found"})
    def do_POST(self):
        try:
            length=int(self.headers.get("content-length","0"));
            if length>256000:return self._json(413,{"error":"request_too_large"})
            body=json.loads(self.rfile.read(length) or b"{}")
        except Exception:return self._json(400,{"error":"invalid_json"})
        if self.path=="/v1/launch/route":
            decision=self.launch.route(str(body.get("requested_status","")),issuer_or_source_verified=bool(body.get("issuer_or_source_verified",False)))
            return self._json(200,{"route":decision.route.value,"public_label":decision.public_label,"launchable_without_idv_contract":decision.launchable_without_idv_contract,"commissioner_required":decision.commissioner_required,"physical_presence_default":decision.physical_presence_default,"citizen_experience":decision.citizen_experience,"platform_action":decision.platform_action,"truth_boundary":decision.hard_truth_boundary})
        if self.path=="/v1/integrity/receipt/issue":
            forbidden={"document","document_bytes","document_base64","file","content","raw_document"}
            if any(k in body for k in forbidden):return self._json(400,{"error":"zero_possession_endpoint_rejects_document_bytes"})
            try:r=self.integrity.issue(document_sha256=str(body["document_sha256"]),client_nonce=str(body["client_nonce"]))
            except (KeyError,ValueError,TypeError) as exc:return self._json(400,{"error":"integrity_receipt_rejected","detail":str(exc)[:120]})
            return self._json(200,asdict(r))
        if self.path=="/v1/integrity/receipt/verify":
            try:
                r=IntegrityReceipt(verification_code=str(body["verification_code"]),document_sha256=str(body["document_sha256"]),issued_at=int(body["issued_at"]),key_id=str(body["key_id"]),public_label=str(body["public_label"]),client_nonce_sha256=str(body["client_nonce_sha256"]),signature_hex=str(body["signature_hex"]),truth_boundary=tuple(body["truth_boundary"]))
                ok=self.integrity.verify(r)
            except (KeyError,ValueError,TypeError):ok=False
            return self._json(200,{"valid":bool(ok)})
        if self.path=="/v1/route":
            if "recipient_accepts_digital_assurance" in body or "recipient_acceptance" in body:return self._json(400,{"error":"client_controlled_recipient_acceptance_not_allowed"})
            r=self.routes.route(str(body.get("requested_status","")))
            return self._json(200,{"lane":r.lane.value,"final_label":r.final_label,"commissioner_required":r.commissioner_required,"physical_presence_default":r.physical_presence_default,"identity_requirement":r.identity_requirement,"rationale":r.rationale})
        if self.path=="/v1/identity/receipt/assess":
            if self.authenticator is None:return self._json(503,{"error":"identity_provider_module_not_activated","launch_now_mode_available":True})
            try:
                env=ReceiptEnvelope(provider=str(body["provider"]),payload=dict(body["payload"]),signature_hex=str(body["signature_hex"]),key_id=str(body["key_id"]))
                authenticated=self.authenticator.verify(env);a=self.identity.assess(authenticated,bool(body.get("consent_granted",False)))
            except (KeyError,ValueError,TypeError) as exc:return self._json(400,{"error":"identity_receipt_rejected","detail":str(exc)[:120]})
            return self._json(200,{"decision":a.decision.value,"reasons":a.reasons,"evidence_digest":a.evidence_digest,"provider_transaction_id":a.provider_transaction_id})
        return self._json(404,{"error":"not_found"})
    def log_message(self,fmt,*args):print("ecertify_private",self.command,self.path)

def main():ThreadingHTTPServer(("0.0.0.0",int(os.environ.get("PORT","8080"))),Handler).serve_forever()
if __name__=="__main__":main()
