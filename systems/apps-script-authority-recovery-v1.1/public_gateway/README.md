# Minimum-Scope Signed Gateway v1.1

This is a separate Apps Script project from the privileged administration plane.

## Contract

- exactly one global `doGet` and one global `doPost`;
- deployer execution is retained only for this minimum-scope gateway;
- OAuth scope is limited to `script.external_request`; no Cloud Platform, Apps Script project/deployment, Drive or Sheets scope is present;
- POST accepts only a complete HMAC-SHA256 envelope bound to timestamp, nonce, action, canonical target and payload;
- allowed actions are `STATUS` and `CHALLENGE` only;
- unknown fields, malformed payloads and credential-like challenge values fail closed;
- replay state stores nonce hashes only in 16 bounded Script-Property shards; corrupt state fails closed;
- no IAM, API enablement, source/deployment mutation or privileged provider call is implemented;
- public status exposes no internal spreadsheet, runtime, principal, service-account or capability inventory.

## Required property

Set a random 32+ character `SOVARA_GATEWAY_HMAC_SECRET` Script Property through a trusted owner-controlled administration route. Never put it in source, a Sheet, a URL, a log or a request body.

## Truth boundary

Source and hostile-test readiness only. This project is not live-deployed by this package and does not prove Google provider authority.
