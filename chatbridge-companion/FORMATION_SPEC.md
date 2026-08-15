# Formation specification

Mission: reduce the user burden of compliant conversation-limit handoff without expanding platform authority.

- Owner: Kim Kagiso Mosiane.
- Authority: A1 local reversible build; browser installation/deployment is a separate external trust boundary.
- Cost: zero new recurring cost.
- Effectful path: one user-initiated ChatBridge click → one tab-bound transfer → one successor prompt → one consume receipt.
- Prohibited claims: native ChatGPT modification, unlimited context transfer, hidden-chat access, deployment without browser readback.
- Managed-device rule: inspect policy read-only; never elevate, change policy or route around an organisational extension block. Use the enterprise handoff when an administrator-controlled route is required.
- Stop switch: disable/remove the extension.
- Rollback: remove the extension; no provider-side data has been mutated by the extension itself.
- Proof states: DESIGNED → IMPLEMENTED → TESTED → REGISTERED. DEPLOYED and PROVEN require a live browser canary.
