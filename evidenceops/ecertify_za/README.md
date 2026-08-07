# EvidenceOps eCertify ZA

Production architecture for South African self-service document assurance.

The platform separates four concerns: citizen identity proofing, document integrity/source assurance, recipient acceptance rules, and legal certification/commissioning events.

Identity proofing is provider-bound. EvidenceOps consumes signed verification receipts from an approved identity provider and does not implement or store raw biometric matching models, face images or reusable biometric templates in this repository.

No identity result can by itself create a CERTIFIED COPY or COMMISSIONED AFFIDAVIT label. Those statuses require their separate legal event and evidence gate.
