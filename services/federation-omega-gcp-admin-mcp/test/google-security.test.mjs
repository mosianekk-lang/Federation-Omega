import assert from "node:assert/strict";
import test from "node:test";
import {safeGoogleApiError} from "../dist/googleError.js";

test("provider failures expose bounded status and digest, never raw bodies", () => {
  const secret = "super-secret-provider-body";
  const body = JSON.stringify({error: {status: "PERMISSION_DENIED", message: secret}});
  const error = safeGoogleApiError(403, body);
  assert.match(error.message, /^GOOGLE_API_403:PERMISSION_DENIED:response_sha256=[0-9a-f]{64}$/);
  assert.equal(error.message.includes(secret), false);
});

test("non-JSON provider failures are digest-only", () => {
  const secret = "token=do-not-leak";
  const error = safeGoogleApiError(500, secret);
  assert.match(error.message, /^GOOGLE_API_500:REQUEST_FAILED:response_sha256=[0-9a-f]{64}$/);
  assert.equal(error.message.includes(secret), false);
});
