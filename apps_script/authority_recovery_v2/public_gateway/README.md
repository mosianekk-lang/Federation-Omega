# Public Gateway

One public `doGet` and one signed `doPost`; no explicit OAuth scopes and no provider mutation surface. Configure only `SOVARA_GATEWAY_HMAC_SECRET` as rotatable key material. Allowed actions are `STATUS` and `CHALLENGE`. The key itself is never accepted as an approval value or persisted in output.
