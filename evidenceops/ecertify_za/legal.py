from __future__ import annotations
from .models import AssuranceLane, CertificationRoute

class CertificationRouteEngine:
    """Separates technical identity/document assurance from legal certification labels."""
    def route(self, requested_status:str, recipient_accepts_digital_assurance:bool=False)->CertificationRoute:
        req=requested_status.strip().lower().replace("-","_").replace(" ","_")
        if recipient_accepts_digital_assurance and req not in {"affidavit","sworn_statement"}:
            return CertificationRoute(AssuranceLane.INSTITUTION_ACCEPTED,"INSTITUTION_ACCEPTED_DIGITAL_ASSURANCE",False,False,"VERIFIED_IDENTITY_OR_TRUSTED_ISSUER",("RECIPIENT_ACCEPTANCE_RULE_VERIFIED","NO_CERTIFICATION_LABEL_CREATED"))
        if req in {"digital_original","electronic_original","original"}:
            return CertificationRoute(AssuranceLane.DIGITAL_ORIGINAL,"VERIFIED_DIGITAL_ORIGINAL",False,False,"RISK_BASED",("SOURCE_OR_ISSUER_VERIFICATION_REQUIRED_WHERE_AVAILABLE",))
        if req in {"copy","document_copy","scan"}:
            return CertificationRoute(AssuranceLane.SOURCE_MATCHED_COPY,"SOURCE_MATCHED_COPY",False,False,"RISK_BASED",("TECHNICAL_ASSURANCE_IS_NOT_STATUTORY_CERTIFICATION",))
        if req in {"certified","certified_copy"}:
            return CertificationRoute(AssuranceLane.CERTIFIED_COPY,"CERTIFICATION_REQUIRED",True,False,"VERIFIED_IDENTITY",("AUTHORIZED_CERTIFIER_EVENT_REQUIRED_BEFORE_CERTIFIED_LABEL",))
        if req in {"affidavit","sworn_statement","declaration"}:
            return CertificationRoute(AssuranceLane.AFFIDAVIT,"COMMISSIONING_REQUIRED",True,True,"VERIFIED_IDENTITY",("PHYSICAL_PRESENCE_DEFAULT","REMOTE_EXCEPTION_MUST_BE_LEGALLY_JUSTIFIED"))
        return CertificationRoute(AssuranceLane.REQUIREMENT_VERIFICATION,"REQUIREMENT_UNVERIFIED",False,False,"NOT_DETERMINED",("RECIPIENT_REQUIREMENT_MUST_BE_VERIFIED_BEFORE_FINAL_LABEL",))
