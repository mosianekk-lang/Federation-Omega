# Minimum-Scope Signed Gateway

This is a separate Apps Script project from the privileged admin plane.

- deployer execution is retained only for the minimum-scope gateway;
- OAuth scope is `script.external_request` only;
- one `doGet` and one `doPost` exist;
- POST requires HMAC-SHA256, timestamp, canonical target and durable nonce claim;
- allowed actions are `STATUS` and `CHALLENGE` only;
- no API enablement, IAM, Apps Script source/deployment, Drive, Sheets or Cloud Run mutation is implemented;
- public status returns no internal spreadsheet, runtime, service-account or capability inventory.

Set a random 32+ character `SOVARA_GATEWAY_HMAC_SECRET` Script Property through the trusted owner-controlled administration surface. Do not put it in source, a Sheet, a URL or a request body.
