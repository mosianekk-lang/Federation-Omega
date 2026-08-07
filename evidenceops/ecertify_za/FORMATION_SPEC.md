# Formation Specification — eCertify ZA v0.2

Objective: remove unnecessary physical trips for South African document assurance while preserving the legal distinction between technical verification, certified copies and commissioned affidavits.

Selected solution: citizen self-service + approved remote identity provider + signed verification receipt + automatic legal-lane selection + authorised human certifier only when legally or recipient-required + recipient verification API.

Federation reuse: proof-before-claim, cloud-capability contracts, public/private boundary, hash-linked evidence/learning patterns, AO-CRA boundary handling and production-readiness gates.

Rejected route: EvidenceOps implementing or storing raw facial-recognition models/templates itself. The stronger architecture keeps sensitive matching inside a separately governed identity-provider boundary and consumes only signed proof receipts.
